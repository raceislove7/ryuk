/** Display-only explanations. Backend decisions and reason codes remain authoritative. */
export const reasonSentences: Record<string, string> = {
  BUDGET_EXCEEDED: "Blocked: this offer exceeds a budget limit or the available balance.",
  CURRENCY_MISMATCH: "Blocked: the offer and budget currencies do not match.",
  REQUIRED_ATTRIBUTE_FAILED: "Blocked: this offer lacks a requirement you marked mandatory.",
  MISSING_EVIDENCE: "Review needed: evidence for a mandatory requirement is missing or uncertain.",
  APPROVAL_THRESHOLD_EXCEEDED: "Review needed: this amount exceeds your approval threshold.",
  INTENT_REVIEW_REQUIRED: "Review needed: compare your original request with the parsed requirements.",
  MERCHANT_REVIEW_REQUIRED: "Review needed: this merchant is not on the current allowed list.",
  DUPLICATE_ATTEMPT: "Blocked: this proposal already has a checkout attempt. Inspect its saved status.",
  APPROVAL_EXPIRED: "Review needed: the earlier application approval has expired.",
  PROPOSAL_CHANGED: "Blocked: the proposal or its approval terms have changed. Reload the record.",
  VERIFICATION_INVALID: "Blocked: the verification no longer matches the current offer.",
  PAYMENT_STATE_UNKNOWN: "Blocked: a prior payment outcome is uncertain. Check status; do not pay again.",
  APPROVAL_PENDING: "Review needed: your application decision has not been recorded yet.",
  APPROVAL_REJECTED: "Blocked: the application approval was rejected.",
  APPROVAL_INVALID: "Blocked: the application approval is not valid for this request.",
  APPROVAL_GRANTED: "Application approval is recorded for these terms; PayPal buyer approval is separate.",
};
export function reasonSentence(code: string): string {
  return Object.hasOwn(reasonSentences, code)
    ? reasonSentences[code]
    : "The backend supplied an additional condition. Keep the decision unchanged and inspect this code.";
}
export interface BudgetDisplay {
  limit_minor: number;
  settled_minor: number;
  reserved_minor: number;
  available_minor: number;
  currency: string;
}
export function budgetRows(budget: BudgetDisplay) {
  // Scale only the illustration. Labels always show the unchanged backend values.
  const maximum = Math.max(1, budget.limit_minor);
  return [
    { label: "Settled", value: budget.settled_minor },
    { label: "Held", value: budget.reserved_minor },
    { label: "Available", value: budget.available_minor },
  ].map((row) => ({ ...row, maximum, progress: Math.min(maximum, Math.max(0, row.value)) }));
}
