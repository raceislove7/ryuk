"use client";
import { FormEvent, useEffect, useRef, useState } from "react";
import PayPalCheckout from "../components/paypal";
import IntentSources from "../components/intent-sources";
import RecoveryHistory from "../components/recovery-history";
import { ActivityNotice, BudgetBar, PolicyReasons, SandboxNotice } from "../components/presentation";
import { api, ApiError, label, money } from "../lib/api";
import type {
  Approval,
  AuditEvent,
  Candidate,
  Check,
  Checkout,
  Investigation,
  Workspace,
} from "../lib/contracts";

const EXAMPLE =
  "Find a hotel in Switzerland for 5 nights under USD 1,500.\nGym, mountain view and free cancellation are required.\nPrivate pool preferred. Ask me above USD 1,300.";
const terminal = (record: Checkout) =>
  ["SUCCEEDED", "FAILED"].includes(record.state);
const verdictText = {
  ALLOW_ELIGIBLE_FOR_CHECKOUT: "Eligible for checkout",
  REQUIRE_APPROVAL: "Your approval is required",
  DENY: "Purchase blocked",
};
const verdictClass = {
  ALLOW_ELIGIBLE_FOR_CHECKOUT: "pass",
  REQUIRE_APPROVAL: "review",
  DENY: "fail",
};
function Status({ value }: { value: string }) {
  return (
    <span
      className={`status ${value === "PASS" ? "pass" : value === "FAIL" ? "fail" : "review"}`}
    >
      <i />
      {value}
    </span>
  );
}
function CheckRow({ check, preferred }: { check: Check; preferred?: boolean }) {
  return (
    <tr>
      <td>
        <strong>{label(check.requirement)}</strong>
        <span className="micro">{preferred ? "PREFERRED" : "REQUIRED"}</span>
      </td>
      <td>
        <Status
          value={
            check.status === "PASS" && !check.evidence.length
              ? "UNKNOWN"
              : check.status
          }
        />
      </td>
      <td>
        {check.evidence.length ? (
          check.evidence.map((source, i) => <p key={i}>{source}</p>)
        ) : (
          <span className="subtle">No supporting evidence supplied.</span>
        )}
        <span className="check-explanation">{check.explanation}</span>
      </td>
    </tr>
  );
}
export default function Home() {
  const [session, setSession] = useState({
    configured: false,
    authenticated: false,
  });
  const [workspace, setWorkspace] = useState<Workspace>();
  const [query, setQuery] = useState(EXAMPLE);
  const [investigation, setInvestigation] = useState<Investigation>();
  const [selected, setSelected] = useState<Candidate>();
  const [showAll, setShowAll] = useState(false);
  const [approval, setApproval] = useState<Approval>();
  const [checkout, setCheckout] = useState<Checkout>();
  const checkoutRef = useRef<Checkout | undefined>(undefined);
  const [events, setEvents] = useState<AuditEvent[]>([]);
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [password, setPassword] = useState("");
  const authDialog = useRef<HTMLDialogElement>(null);
  const approvalDialog = useRef<HTMLDialogElement>(null);
  const active = !!checkout && !terminal(checkout);
  const available = workspace?.budget.available_minor;
  function fail(e: unknown) {
    setError(e instanceof Error ? e.message : "This action is unavailable.");
    if (e instanceof ApiError && e.status === 401)
      setSession((s) => ({ ...s, authenticated: false }));
  }
  async function refreshWorkspace() {
    setWorkspace(await api<Workspace>("workspace"));
  }
  async function refreshAudit(id: string) {
    setEvents(
      (await api<{ events: AuditEvent[] }>(`proposals/${id}/audit`)).events,
    );
  }
  useEffect(() => {
    let mounted = true;
    api<{ configured: boolean; authenticated: boolean }>("session")
      .then(async (state) => {
        if (!mounted) return;
        setSession(state);
        if (state.authenticated) {
          const ws = await api<Workspace>("workspace");
          if (mounted) setWorkspace(ws);
        }
      })
      .catch((e) => {
        if (mounted)
          setError(e instanceof Error ? e.message : "Workspace unavailable");
      });
    return () => {
      mounted = false;
    };
  }, []);
  async function signIn(event: FormEvent) {
    event.preventDefault();
    setBusy("Unlocking your workspace");
    setError("");
    try {
      await api("session", "POST", { password });
      setPassword("");
      setSession({ configured: true, authenticated: true });
      await refreshWorkspace();
      authDialog.current?.close();
    } catch (e) {
      fail(e);
    } finally {
      setBusy("");
    }
  }
  async function signOut() {
    try {
      await api("session", "DELETE");
      setSession((s) => ({ ...s, authenticated: false }));
      setWorkspace(undefined);
      setInvestigation(undefined);
      setSelected(undefined);
      setEvents([]);
      setCheckout(undefined);
      checkoutRef.current = undefined;
    } catch (e) {
      fail(e);
    }
  }
  async function investigate(event: FormEvent) {
    event.preventDefault();
    if (!session.authenticated) {
      authDialog.current?.showModal();
      return;
    }
    setBusy("Parsing your instruction and examining the evidence");
    setError("");
    setNotice("");
    try {
      const result = await api<Investigation>("requests", "POST", { query });
      setInvestigation(result);
      setShowAll(false);
      setSelected(undefined);
      setApproval(undefined);
      setCheckout(undefined);
      checkoutRef.current = undefined;
      setEvents([]);
      document
        .getElementById("candidates")
        ?.scrollIntoView({ behavior: "smooth", block: "start" });
    } catch (e) {
      fail(e);
    } finally {
      setBusy("");
    }
  }
  async function select(candidate: Candidate) {
    setBusy("Loading the case file");
    setError("");
    setApproval(undefined);
    setCheckout(undefined);
    checkoutRef.current = undefined;
    try {
      const fresh = await api<Candidate>(
        `proposals/${candidate.proposal.proposal_id}/select`,
        "POST",
        {},
      );
      setSelected(fresh);
      await refreshAudit(fresh.proposal.proposal_id);
      document
        .getElementById("verification")
        ?.scrollIntoView({ behavior: "smooth", block: "start" });
    } catch (e) {
      fail(e);
    } finally {
      setBusy("");
    }
  }
  async function requestApproval() {
    if (!selected) return;
    setBusy("Loading exact approval terms");
    setError("");
    try {
      setApproval(
        await api<Approval>(
          `proposals/${selected.proposal.proposal_id}/approval`,
          "POST",
          {},
        ),
      );
      await refreshAudit(selected.proposal.proposal_id);
      approvalDialog.current?.showModal();
    } catch (e) {
      fail(e);
    } finally {
      setBusy("");
    }
  }
  async function decide(decision: "APPROVE" | "REJECT") {
    if (!approval || !selected) return;
    setBusy("Recording your decision");
    setError("");
    try {
      setApproval(
        await api<Approval>(
          `approvals/${approval.approval_request_id}/decision`,
          "POST",
          { decision },
        ),
      );
      setSelected(
        await api<Candidate>(`proposals/${selected.proposal.proposal_id}`),
      );
      await refreshAudit(selected.proposal.proposal_id);
      approvalDialog.current?.close();
      setNotice(
        decision === "APPROVE"
          ? "Application approval recorded. PayPal buyer approval is still required."
          : "Approval rejected. Checkout is blocked.",
      );
    } catch (e) {
      fail(e);
    } finally {
      setBusy("");
    }
  }
  async function recordCheckout(record: Checkout) {
    checkoutRef.current = record;
    setCheckout(record);
    await Promise.allSettled([
      refreshWorkspace(),
      refreshAudit(record.proposal_id),
    ]);
  }
  async function checkPayment() {
    const record = checkoutRef.current;
    if (!record) return;
    setBusy("Checking the backend payment record");
    setError("");
    try {
      let fresh = await api<Checkout>(`checkouts/${record.checkout_id}`);
      if (["PENDING_PROVIDER", "CAPTURE_PENDING"].includes(fresh.state))
        fresh = await api<Checkout>(
          `checkouts/${record.checkout_id}/reconcile`,
          "POST",
          {},
        );
      await recordCheckout(fresh);
    } catch (e) {
      fail(e);
    } finally {
      setBusy("");
    }
  }
  async function paypalError(message: string) {
    await checkPayment();
    setError(message);
  }
  const offer = selected?.proposal.offer;
  return (
    <div className="casebook">
      <header className="masthead">
        <a href="#command" className="brand" aria-label="Ryuk home">
          <span className="brand-seal" aria-hidden="true">
            R<span />
          </span>
          <span>
            RYUK<small>INTENT BEFORE PAYMENT</small>
          </span>
        </a>
        <nav aria-label="Workspace navigation">
          <a className="current" href="#command">
            The casebook
          </a>
          <a href="#audit">Execution log</a>
          <a href="#protocol">Protocol ↗</a>
        </nav>
        <button
          className="session-button"
          onClick={() =>
            session.authenticated
              ? void signOut()
              : authDialog.current?.showModal()
          }
        >
          {session.authenticated
            ? "● PRIVATE SESSION / SIGN OUT"
            : "○ UNLOCK WORKSPACE"}
        </button>
      </header>
      <div className="workspace-shell">
        <aside className="margin-notes">
          <p className="eyebrow">A FINANCIAL NOTEBOOK</p>
          <div className="margin-rule" />
          <p className="vertical-title">
            Deliberate
            <br />
            by design.
          </p>
          <p className="margin-copy">
            An instruction becomes a proposal.
            <br />
            Evidence becomes a decision.
            <br />
            You remain in control.
          </p>
          <div className="case-index">
            <span className="micro">THIS ENTRY</span>
            {[
              ["command", "The instruction"],
              ["candidates", "Candidate records"],
              ["verification", "The evidence"],
              ["verdict", "Financial authority"],
              ["audit", "Execution log"],
            ].map(([id, title], i) => (
              <a key={id} href={`#${id}`}>
                <b>0{i + 1}</b>
                {title}
              </a>
            ))}
          </div>
          <div className="rail-note">
            <span className="red-line" />
            <p>
              AI can choose.
              <br />
              <em>You stay in control.</em>
            </p>
          </div>
        </aside>
        <main>
          {session.authenticated && <RecoveryHistory disabled={!!busy || active} onError={fail} />}
          <section className="opening" id="command">
            <div>
              <p className="eyebrow">
                <span className="red-square" /> BUYER-SIDE COMMERCE / SANDBOX
              </p>
              <h1>
                Every detail.
                <br />
                <em>Before a dollar.</em>
              </h1>
              <p className="intro">
                Give the instruction. Examine the evidence.
                <br />
                Nothing moves without the right authority.
              </p>
            </div>
            <div className="entry-mark">
              <span>FIELD NOTES</span>
              <b>№ 001</b>
              <span>INTENT → EVIDENCE → CONSENT</span>
            </div>
          </section>
          <div className="command-layout">
            <form className="command-panel" onSubmit={investigate}>
              <div className="panel-label">
                <span>01 / THE INSTRUCTION</span>
                <span>PLAIN LANGUAGE. PRECISE LIMITS.</span>
              </div>
              <label htmlFor="instruction" className="sr-only">
                Your purchase instruction
              </label>
              <textarea
                id="instruction"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                maxLength={4000}
                disabled={!!busy || active}
                spellCheck={false}
              />
              <div className="command-bottom">
                <button
                  type="button"
                  className="text-button"
                  onClick={() => setQuery(EXAMPLE)}
                  disabled={!!busy || active}
                >
                  ↳ Use hotel example
                </button>
                <button
                  className="primary"
                  type="submit"
                  disabled={!!busy || active || !query.trim()}
                >
                  {busy
                    ? "EXAMINING…"
                    : session.authenticated
                      ? "OPEN INVESTIGATION"
                      : "UNLOCK TO BEGIN"}
                  <span>↗</span>
                </button>
              </div>
            </form>
            <aside className="budget-panel">
              <div className="panel-label">
                <span>AVAILABLE BUDGET</span>
                <span className="small-dot" />
              </div>
              <strong className="budget-value">
                {available === undefined
                  ? "—"
                  : money(available, workspace?.budget.currency)}
                <small>
                  {workspace?.budget.currency || "AWAITING SESSION"}
                </small>
              </strong>
              <dl>
                <div>
                  <dt>Purchase ceiling</dt>
                  <dd>
                    {workspace
                      ? money(
                          workspace.policy.max_amount_minor,
                          workspace.budget.currency,
                        )
                      : "—"}
                  </dd>
                </div>
                <div>
                  <dt>Ask me above</dt>
                  <dd>
                    {workspace
                      ? money(
                          workspace.policy.approval_threshold_minor,
                          workspace.budget.currency,
                        )
                      : "—"}
                  </dd>
                </div>
                <div>
                  <dt>Reserved</dt>
                  <dd>
                    {workspace
                      ? money(
                          workspace.budget.reserved_minor,
                          workspace.budget.currency,
                        )
                      : "—"}
                  </dd>
                </div>
              </dl>
              {workspace && <BudgetBar budget={workspace.budget} />}
              <p className="micro">
                {workspace
                  ? `POLICY / ${workspace.policy.version}`
                  : "PRIVATE · SERVER-ENFORCED RULES"}
              </p>
            </aside>
          </div>
          <div className="flow-caption">
            <span>01 / DESCRIBE</span>
            <i>→</i>
            <span>02 / VERIFY</span>
            <i>→</i>
            <span>03 / AUTHORIZE</span>
            <i>→</i>
            <span>04 / PAY</span>
            <p>The model proposes. The backend decides.</p>
          </div>
          {busy && (
            <ActivityNotice message={busy} />
          )}
          {error && (
            <div className="message error" role="alert">
              <strong>ACTION NEEDS ATTENTION</strong>
              <p>{error}</p>
              {/^[A-Z_]+(?: · [A-Z_]+)*$/.test(error) && <PolicyReasons codes={error.split(" · ")} />}
              <p className="subtle">The action is not confirmed. For a checkout timeout, do not press Pay again; use Saved activity or the existing backend status control.</p>
              <button className="text-button" onClick={() => setError("")}>
                Dismiss ×
              </button>
            </div>
          )}
          {notice && (
            <div className="message notice" role="status">
              {notice}
            </div>
          )}
          {investigation && (
            <section className="parsed-intent">
              <p className="eyebrow">
                BACKEND INTENT / {investigation.intent.category.toUpperCase()}
              </p>
              <div>
                <span>
                  Budget{" "}
                  <b>
                    {money(
                      investigation.intent.budget_max_minor,
                      investigation.intent.currency,
                    )}
                  </b>
                </span>
                <span>
                  Review above{" "}
                  <b>
                    {money(
                      investigation.intent.approval_threshold_minor,
                      investigation.intent.currency,
                    )}
                  </b>
                </span>
              </div>
              <IntentSources intent={investigation.intent} />
            </section>
          )}
          <section id="candidates" className="section-block" aria-busy={!!busy}>
            <div className="section-heading">
              <div>
                <p className="eyebrow">02 / CANDIDATE RECORDS</p>
                <h2>The shortlist.</h2>
              </div>
              <span className="micro">
                {investigation
                  ? `${investigation.candidates.length} RECORDS / SYNTHETIC HOTEL DATA`
                  : "AWAITING YOUR INSTRUCTION"}
              </span>
            </div>
            {investigation && investigation.candidates.length > 0 ? (
              <>
                <div className="candidates">
                  {investigation.candidates
                    .slice(0, showAll ? undefined : 3)
                    .map((c, i) => (
                      <article
                        key={c.proposal.proposal_id}
                        className={`candidate ${selected?.proposal.proposal_id === c.proposal.proposal_id ? "selected" : ""}`}
                      >
                        <div className="candidate-top">
                          <span>CASE / {String(i + 1).padStart(2, "0")}</span>
                          <span className={verdictClass[c.policy.decision]}>
                            {c.policy.decision === "DENY"
                              ? "BLOCKED"
                              : c.policy.decision === "REQUIRE_APPROVAL"
                                ? "REVIEW"
                                : "ELIGIBLE"}
                          </span>
                        </div>
                        <div className="candidate-landscape" aria-hidden="true">
                          <svg viewBox="0 0 280 90">
                            <path d="M0 89 63 32 91 59 140 6 209 72 235 41 280 89M31 89 92 59M111 37 140 6 169 35 155 31 144 38 133 27Z" />
                          </svg>
                          <span>
                            {String(
                              c.proposal.offer.attributes.country ||
                                "HOTEL RECORD",
                            ).toUpperCase()}
                          </span>
                        </div>
                        <p className="micro merchant">
                          {c.proposal.offer.merchant_id}
                        </p>
                        <h3>
                          {c.proposal.offer.title.replace("[Synthetic] ", "")}
                        </h3>
                        <p className="offer-subtitle">
                          {String(c.proposal.offer.attributes.nights ?? "—")}{" "}
                          nights ·{" "}
                          {String(c.proposal.offer.attributes.rooms ?? "—")}{" "}
                          room · Fictional stay
                        </p>
                        <p className="offer-price">
                          {money(
                            c.proposal.offer.amount_minor,
                            c.proposal.offer.currency,
                          )}
                          <small>TOTAL / {c.proposal.offer.currency}</small>
                        </p>
                        <div className="match-detail">
                          <span>Required verified</span>
                          <b>
                            {c.required_verified}/{c.required_total}
                          </b>
                          <span>Preference match</span>
                          <b>{c.proposal.verification.preference_score}%</b>
                        </div>
                        <div className="requirement-summary">
                          {c.proposal.verification.required_checks.map(
                            (check) => (
                              <span
                                key={check.requirement}
                                className={
                                  check.status === "PASS" &&
                                  check.evidence.length
                                    ? "pass"
                                    : check.status === "FAIL"
                                      ? "fail"
                                      : "review"
                                }
                              >
                                {check.status === "PASS" &&
                                check.evidence.length
                                  ? "✓"
                                  : check.status === "FAIL"
                                    ? "×"
                                    : "?"}{" "}
                                {label(check.requirement)}
                              </span>
                            ),
                          )}
                        </div>
                        <button
                          className="record-button"
                          disabled={!!busy || active}
                          onClick={() => void select(c)}
                        >
                          {selected?.proposal.proposal_id ===
                          c.proposal.proposal_id
                            ? "CASE FILE OPEN"
                            : "EXAMINE RECORD"}
                          <span>↗</span>
                        </button>
                      </article>
                    ))}
                </div>
                {investigation.candidates.length > 3 && (
                  <button
                    className="secondary more-records"
                    onClick={() => setShowAll((value) => !value)}
                    disabled={!!busy || active}
                  >
                    {showAll
                      ? "SHOW TOP 3 RECORDS ↑"
                      : `SHOW ALL ${investigation.candidates.length} RECORDS ↓`}
                  </button>
                )}
                <p className="fixture-note">
                  {investigation.notice} Sandbox checkout pays the configured
                  Ryuk demo merchant; it does not book a hotel.
                </p>
              </>
            ) : (
              <div className="empty-record">
                <span className="crosshair" aria-hidden="true">
                  ⌖
                </span>
                <div>
                  <h3>{investigation ? "No candidate records returned." : "No conclusions without evidence."}</h3>
                  <p>
                    {investigation ? "The backend returned no offers for this request. Review your instruction before starting a different search." : "Your instruction will open a shortlist of candidate records."}
                    <br />
                    Every requirement is checked before checkout.
                  </p>
                </div>
                <span className="micro">NO CASE OPEN</span>
              </div>
            )}
          </section>
          {selected && offer && (
            <>
              <section
                id="verification"
                className="section-block evidence-section"
              >
                <div className="section-heading">
                  <div>
                    <p className="eyebrow">03 / THE EVIDENCE</p>
                    <h2>Trust the trace.</h2>
                  </div>
                  <Status value={selected.proposal.verification.status} />
                </div>
                <div className="evidence-title">
                  <span>{offer.title.replace("[Synthetic] ", "")}</span>
                  <span className="micro">
                    FIXTURE EVIDENCE / NO LIVE AVAILABILITY
                  </span>
                </div>
                <div className="table-wrap">
                  <table>
                    <thead>
                      <tr>
                        <th>REQUIREMENT</th>
                        <th>VERDICT</th>
                        <th>SUPPORTING EVIDENCE</th>
                      </tr>
                    </thead>
                    <tbody>
                      {selected.proposal.verification.required_checks.map(
                        (c) => (
                          <CheckRow key={c.requirement} check={c} />
                        ),
                      )}
                      {selected.proposal.verification.preferred_checks.map(
                        (c) => (
                          <CheckRow key={c.requirement} check={c} preferred />
                        ),
                      )}
                    </tbody>
                  </table>
                </div>
                <div className="snapshot">
                  <span>VERIFICATION SNAPSHOT</span>
                  <code>
                    {selected.proposal.verification.verification_snapshot_id}
                  </code>
                </div>
              </section>
              <section
                id="verdict"
                className={`verdict-panel ${verdictClass[selected.policy.decision]}`}
              >
                <div>
                  <p className="eyebrow">04 / RYUK POLICY VERDICT</p>
                  <h2>{verdictText[selected.policy.decision]}</h2>
                  <code>{selected.policy.decision}</code>
                  <p className="subtle">{selected.policy.decision === "REQUIRE_APPROVAL" ? "Review the exact request and offer before recording your decision. Nothing is approved automatically." : selected.policy.decision === "DENY" ? "This offer cannot proceed under the current backend rules." : "Eligible under current backend rules. This is not a capture confirmation."}</p>
                  <PolicyReasons codes={selected.policy.reason_codes} />
                  <p className="subtle">
                    Deterministic rules. Evaluated by the backend.
                  </p>
                </div>
                <div className="verdict-terms">
                  <div>
                    <span>EXACT AMOUNT</span>
                    <strong>{money(offer.amount_minor, offer.currency)}</strong>
                  </div>
                  <div>
                    <span>MERCHANT RECORD</span>
                    <code>{offer.merchant_id}</code>
                  </div>
                  {!checkout &&
                    selected.policy.decision === "REQUIRE_APPROVAL" && (
                      <button
                        className="primary"
                        disabled={!!busy}
                        onClick={() => void requestApproval()}
                      >
                        REVIEW EXACT TERMS ↗
                      </button>
                    )}
                  {selected.policy.decision === "DENY" && (
                    <p className="blocked-stamp">CHECKOUT LOCKED</p>
                  )}
                  {approval?.status === "APPROVED" && (
                    <span className="micro pass">
                      APPLICATION APPROVAL RECORDED
                    </span>
                  )}
                </div>
              </section>
              {selected.policy.decision === "ALLOW_ELIGIBLE_FOR_CHECKOUT" && (
                  <section className="checkout-panel">
                    <div>
                      <p className="eyebrow">BUYER AUTHORIZATION</p>
                      <h3>One final decision. Yours.</h3>
                      <p>
                        This is a PayPal Sandbox transaction to the configured
                        demo merchant. The hotel is synthetic. No real booking
                        or real funds.
                      </p>
                    </div>
                    <div className="checkout-action">
                      {workspace?.paypal.configured ? (
                        <PayPalCheckout
                          proposalId={selected.proposal.proposal_id}
                          clientId={workspace.paypal.client_id}
                          currency={offer.currency}
                          inactive={!!checkout && checkout.state !== "AWAITING_PAYPAL_BUYER"}
                          onRecord={recordCheckout}
                          onActivity={setBusy}
                          onError={(message) => void paypalError(message)}
                        />
                      ) : (
                        <div className="provider-unavailable">
                          <span className="micro review">
                            SANDBOX NOT CONNECTED
                          </span>
                          <p>
                            Checkout is unavailable until the operator connects
                            the Sandbox account.
                          </p>
                        </div>
                      )}
                      <span className="micro">
                        SUCCESS REQUIRES BACKEND CONFIRMATION
                      </span>
                      <p className="subtle">If the PayPal button does not load, no outcome is confirmed. Inspect any error before trying a different action. After pressing Pay, use the status control instead of pressing Pay again.</p>
                    </div>
                  </section>
                )}
              {checkout && (
                <section
                  className={`payment-result ${checkout.state === "SUCCEEDED" ? "confirmed" : ""}`}
                  aria-live="polite"
                  aria-busy={!!busy}
                >
                  <p className="eyebrow">BACKEND PAYMENT RECORD</p>
                  <h2>
                    {checkout.state === "SUCCEEDED"
                      ? "Sandbox payment confirmed."
                      : ["PENDING_PROVIDER", "CAPTURE_PENDING"].includes(
                            checkout.state,
                          )
                        ? "Confirmation pending."
                        : checkout.state === "FAILED"
                          ? "Sandbox payment not completed."
                          : checkout.order_creation !== "READY"
                            ? "Order needs review."
                            : "Awaiting your PayPal approval."}
                  </h2>
                  <p className="result-price">
                    {money(checkout.amount_minor, checkout.currency)}
                  </p>
                  <p>{offer.title.replace("[Synthetic] ", "")}</p>
                  <div className="result-checks">
                    {selected.proposal.verification.required_checks
                      .filter((c) => c.status === "PASS" && c.evidence.length)
                      .map((c) => (
                        <span key={c.requirement}>
                          ✓ {label(c.requirement)}
                        </span>
                      ))}
                  </div>
                  <dl>
                    {[
                      [
                        "PayPal status",
                        checkout.provider_status || "Not confirmed",
                      ],
                      [
                        "Provider capture",
                        checkout.capture_id || "Not confirmed",
                      ],
                      ["Backend state", checkout.state],
                      [
                        "Ryuk budget available",
                        available === undefined
                          ? "—"
                          : money(available, workspace?.budget.currency),
                      ],
                      ["Payment reference", checkout.checkout_id],
                      [
                        "Verification snapshot",
                        checkout.verification_snapshot_id,
                      ],
                    ].map(([key, value]) => (
                      <div key={key}>
                        <dt>{key}</dt>
                        <dd>{value}</dd>
                      </div>
                    ))}
                  </dl>
                  <p className="subtle">Sandbox record only. No real money moved and no hotel was booked.</p>
                  {!terminal(checkout) && (
                    <>
                      <p className="subtle">
                        {["PENDING_PROVIDER", "CAPTURE_PENDING"].includes(
                          checkout.state,
                        )
                          ? "Do not press Pay again; use CHECK BACKEND STATUS. Your sandbox budget remains held. Checking status will not retry capture."
                          : "A PayPal callback alone is not confirmation of payment."}
                      </p>
                      <button
                        className="secondary"
                        disabled={!!busy}
                        onClick={() => void checkPayment()}
                      >
                        CHECK BACKEND STATUS ↗
                      </button>
                    </>
                  )}
                </section>
              )}
            </>
          )}
          <section id="audit" className="section-block audit-section">
            <div className="section-heading">
              <div>
                <p className="eyebrow">05 / THE EXECUTION LOG</p>
                <h2>A record. Not a black box.</h2>
              </div>
              <span className="micro">
                {events.length
                  ? `${events.length} BACKEND EVENTS`
                  : "NO EVENTS YET"}
              </span>
            </div>
            {events.length ? (
              <ol className="audit-log">
                {events.map((event, i) => (
                  <li key={`${event.at}-${i}`}>
                    <time dateTime={event.at}>
                      {new Date(event.at).toLocaleTimeString("en-GB", {
                        hour12: false,
                      })}
                    </time>
                    <span className="audit-dot" />
                    <div>
                      <strong>{event.event}</strong>
                      {Object.keys(event.details).length > 0 && (
                        <p>
                          {Object.entries(event.details)
                            .map(
                              ([k, v]) =>
                                `${label(k)}: ${typeof v === "object" ? JSON.stringify(v) : String(v)}`,
                            )
                            .join(" / ")}
                        </p>
                      )}
                    </div>
                    <span className="micro">
                      {String(i + 1).padStart(2, "0")}
                    </span>
                  </li>
                ))}
              </ol>
            ) : (
              <p className="audit-empty">
                The record begins with your instruction. Backend events appear
                here as the case progresses.
              </p>
            )}
          </section>
          <section id="protocol" className="protocol">
            <span className="brand-word">RYUK</span>
            <div>
              <h3>The line between reasoning and authority.</h3>
              <p>
                AI interprets your request. Evidence checks the offer.
                Deterministic policy controls spending. You authorize the
                purchase. PayPal confirms the payment.
              </p>
            </div>
            <span className="protocol-seal">
              INTENT
              <br />
              BEFORE
              <br />
              PAYMENT
            </span>
          </section>
          <footer>
            <span>RYUK / A CONTROLLED COMMERCE EXPERIMENT</span>
            <span>SYNTHETIC OFFERS · PAYPAL SANDBOX · NO REAL BOOKINGS</span>
          </footer>
        </main>
      </div>
      <dialog ref={authDialog} className="modal">
        <button
          className="modal-close"
          aria-label="Close sign in"
          onClick={() => authDialog.current?.close()}
        >
          ×
        </button>
        <SandboxNotice />
        <p className="eyebrow">PRIVATE CASEBOOK</p>
        <h2>Access is deliberate.</h2>
        {busy && <ActivityNotice message={busy} />}
        <p>
          Sign in to the password-protected demo workspace. Financial rules stay
          on the server.
        </p>
        {!session.configured && (
          <p className="review">
            This workspace has not been configured by its operator yet.
          </p>
        )}
        <form onSubmit={signIn}>
          <label htmlFor="workspace-password">Workspace password</label>
          <input
            id="workspace-password"
            type="password"
            autoComplete="current-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
            maxLength={1024}
          />
          <button className="primary" disabled={!!busy}>
            UNLOCK WORKSPACE ↗
          </button>
        </form>
        {error && (
          <p className="fail" role="alert">
            {error}
          </p>
        )}
      </dialog>
      <dialog
        ref={approvalDialog}
        className="modal approval-modal"
        aria-label="Review exact application terms"
        aria-busy={!!busy}
        onCancel={(event) => {
          if (busy) event.preventDefault();
        }}
      >
        <button
          className="modal-close"
          aria-label="Close approval"
          disabled={!!busy}
          onClick={() => approvalDialog.current?.close()}
        >
          ×
        </button>
        <SandboxNotice />
        <p className="eyebrow">EXPLICIT APPLICATION CONSENT</p>
        <h2>Read before you authorize.</h2>
        {busy && <ActivityNotice message={busy} />}
        {selected && approval && (
          <>
            <p>
              This approval applies only to these exact terms. It does not
              replace PayPal buyer authorization.
            </p>
            <PolicyReasons codes={selected.policy.reason_codes} />
            <div className="intent-review">
              <IntentSources intent={selected.proposal.intent} />
              <p>
                Quantity: {selected.proposal.intent.quantity}. Budget: {money(
                  selected.proposal.intent.budget_max_minor,
                  selected.proposal.intent.currency,
                )}. Requested review threshold: {money(
                  selected.proposal.intent.approval_threshold_minor,
                  selected.proposal.intent.currency,
                )}.
              </p>
              <p>
                Approve only if this interpretation preserves every mandatory requirement
                and preference. Otherwise reject and clarify your instruction.
              </p>
            </div>
            <dl>
              {[
                ["Proposal digest", selected.proposal.proposal_digest],
                ["Merchant", approval.merchant_id],
                [
                  "Amount / currency",
                  `${money(approval.amount_minor, approval.currency)} / ${approval.currency}`,
                ],
                [
                  "Available budget",
                  available === undefined
                    ? "—"
                    : money(available, workspace?.budget.currency),
                ],
                ["Verification", selected.proposal.verification.status],
                [
                  "Reason for escalation",
                  selected.policy.reason_codes.join(" / "),
                ],
                [
                  "Approval expires",
                  new Date(approval.expires_at).toLocaleString(),
                ],
              ].map(([key, value]) => (
                <div key={key}>
                  <dt>{key}</dt>
                  <dd>{value}</dd>
                </div>
              ))}
            </dl>
            <div className="modal-actions">
              <button
                className="secondary"
                disabled={!!busy}
                onClick={() => void decide("REJECT")}
              >
                REJECT
              </button>
              <button
                className="primary"
                disabled={!!busy}
                onClick={() => void decide("APPROVE")}
              >
                APPROVE EXACT TERMS ↗
              </button>
            </div>
          </>
        )}
        {error && (
          <p className="fail" role="alert">
            {error}
          </p>
        )}
      </dialog>
    </div>
  );
}
