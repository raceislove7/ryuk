"use client";

import { useEffect, useState } from "react";
import { money } from "../lib/api";
import { budgetRows, reasonSentence, type BudgetDisplay } from "../lib/presentation";

export function SandboxNotice() {
  return <aside className="sandbox-notice" aria-label="Sandbox scope" role="note">
    PayPal Sandbox - synthetic inventory - no real money
  </aside>;
}
export function PolicyReasons({ codes }: { codes: string[] }) {
  return <ul className="policy-reasons" aria-label="Backend policy conditions">
    {codes.map((code) => <li key={code}><code>{code}</code><p>{reasonSentence(code)}</p></li>)}
  </ul>;
}
export function BudgetBar({ budget }: { budget: BudgetDisplay }) {
  return <section className="budget-bars" aria-label="Sandbox budget breakdown">
    <p className="micro">SANDBOX BUDGET · BACKEND VALUES</p>
    {budgetRows(budget).map((row) => <div key={row.label}>
      <div className="budget-bar-label"><span>{row.label}</span><span>{money(row.value, budget.currency)}</span></div>
      <progress aria-label={`${row.label} sandbox budget`} max={row.maximum} value={row.progress} />
    </div>)}
    {budget.available_minor === 0 && <p>No budget is available. Held funds are not available to spend.</p>}
    {budget.limit_minor === 0 && <p>The backend budget limit is zero.</p>}
  </section>;
}
export function ActivityNotice({ message }: { message: string }) {
  const [slowMessage, setSlowMessage] = useState("");
  useEffect(() => {
    const timer = setTimeout(() => setSlowMessage(message), 15000);
    return () => clearTimeout(timer);
  }, [message]);
  const slow = slowMessage === message;
  return <div className="activity" role="status" aria-live="polite" aria-atomic="true">
    <p>{message}…</p>
    <p>{slow
      ? "This is taking longer than expected. The outcome is not confirmed. Do not resubmit or press Pay again; use the status control when it becomes available."
      : "Waiting for a backend response. This is not a payment confirmation."}</p>
  </div>;
}
