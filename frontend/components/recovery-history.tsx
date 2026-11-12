"use client";

import { useState } from "react";
import { api, money, label } from "../lib/api";
import type { AuditEvent, Checkout } from "../lib/contracts";

type Entry = {
  proposal_id: string;
  created_at: string;
  amount_minor: number;
  currency: string;
  approval_status: string | null;
  checkout: Checkout | null;
};
type History = { items: Entry[]; next_before: number | null };

export default function RecoveryHistory({ disabled, onError }: {
  disabled: boolean;
  onError: (error: unknown) => void;
}) {
  const [history, setHistory] = useState<History>();
  const [events, setEvents] = useState<AuditEvent[]>([]);
  const [busy, setBusy] = useState(false);
  async function load(before?: number) {
    setBusy(true);
    try {
      setHistory(await api<History>(`history${before ? `?before=${before}` : ""}`));
      setEvents([]);
    } catch (error) { onError(error); }
    finally { setBusy(false); }
  }
  async function inspect(entry: Entry, reconcile = false) {
    setBusy(true);
    try {
      if (reconcile && entry.checkout) {
        const checkout = await api<Checkout>(`checkouts/${entry.checkout.checkout_id}/reconcile`, "POST", {});
        setHistory((previous) => previous ? {
          ...previous, items: previous.items.map((item) => item.proposal_id === entry.proposal_id ? { ...item, checkout } : item),
        } : previous);
      }
      setEvents((await api<{ events: AuditEvent[] }>(`proposals/${entry.proposal_id}/audit`)).events);
    } catch (error) { onError(error); }
    finally { setBusy(false); }
  }
  return (
    <section className="recovery-history" aria-label="Saved purchase history">
      <p className="eyebrow">SAVED ACTIVITY</p>
      <p>Inspect prior purchases after signing in again. Checking an existing payment never starts a new capture.</p>
      <button disabled={disabled || busy} onClick={() => void load()}>Load saved activity</button>
      {history && <>
        {!history.items.length && <p>No saved proposals found.</p>}
        <ul>{history.items.map((entry) => <li key={entry.proposal_id}>
          <p>{money(entry.amount_minor, entry.currency)} · {label(entry.checkout?.state || entry.approval_status || "NOT_CHECKED_OUT")}</p>
          <code>{entry.proposal_id}</code>
          {entry.checkout?.capture_id && <p>Capture reference: {entry.checkout.capture_id}</p>}
          <button disabled={disabled || busy} onClick={() => void inspect(entry)}>Inspect saved record</button>
          {entry.checkout && !["SUCCEEDED", "FAILED"].includes(entry.checkout.state) &&
            <button disabled={disabled || busy} onClick={() => void inspect(entry, true)}>Check existing payment</button>}
        </li>)}</ul>
        {history.next_before && <button disabled={disabled || busy} onClick={() => void load(history.next_before!)}>Older activity</button>}
      </>}
      {!!events.length && <ol aria-label="Saved audit events">{events.map((event, index) =>
        <li key={index}><time>{event.at}</time> · {label(event.event)}</li>)}</ol>}
    </section>
  );
}
