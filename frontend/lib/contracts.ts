export type Verdict =
  | "ALLOW_ELIGIBLE_FOR_CHECKOUT"
  | "REQUIRE_APPROVAL"
  | "DENY";
export type CheckStatus = "PASS" | "FAIL" | "UNKNOWN";
export type PaymentState =
  | "CREATED"
  | "POLICY_CHECK"
  | "AWAITING_APPROVAL"
  | "CHECKOUT_READY"
  | "AWAITING_PAYPAL_BUYER"
  | "CAPTURE_PENDING"
  | "SUCCEEDED"
  | "FAILED"
  | "PENDING_PROVIDER";
export interface Intent {
  category: string;
  query: string;
  currency: string;
  budget_max_minor: number;
  approval_threshold_minor: number;
  required_attributes: Record<string, unknown>;
  preferred_attributes: Record<string, unknown>;
  quantity: number;
  requirement_sources?: {
    role: "required" | "preferred";
    name: string;
    quote: string;
    start: number;
    end: number;
  }[];
}
export interface Check {
  requirement: string;
  status: CheckStatus;
  evidence: string[];
  explanation: string;
}
export interface Verification {
  status: CheckStatus;
  verification_snapshot_id: string;
  required_checks: Check[];
  preferred_checks: Check[];
  preference_score: number;
  explanation: string;
}
export interface Offer {
  offer_id: string;
  merchant_id: string;
  title: string;
  amount_minor: number;
  currency: string;
  attributes: Record<string, unknown>;
}
export interface Policy {
  decision: Verdict;
  reason_codes: string[];
  budget_remaining_minor: number;
  policy_version: string;
}
export interface Candidate {
  proposal: {
    proposal_id: string;
    offer: Offer;
    intent: Intent;
    verification: Verification;
    proposal_digest: string;
  };
  policy: Policy;
  required_verified: number;
  required_total: number;
}
export interface Investigation {
  request_id: string;
  intent: Intent;
  candidates: Candidate[];
  synthetic: boolean;
  notice: string;
}
export interface Workspace {
  budget: {
    currency: string;
    limit_minor: number;
    settled_minor: number;
    reserved_minor: number;
    available_minor: number;
  };
  policy: {
    max_amount_minor: number;
    approval_threshold_minor: number;
    version: string;
  };
  paypal: { configured: boolean; client_id: string; environment: string };
}
export interface Approval {
  approval_request_id: string;
  merchant_id: string;
  amount_minor: number;
  currency: string;
  expires_at: string;
  status: string;
}
export interface Checkout {
  checkout_id: string;
  state: PaymentState;
  order_creation: string;
  paypal_order_id: string | null;
  amount_minor: number;
  currency: string;
  merchant_id: string;
  verification_snapshot_id: string;
  capture_id: string | null;
  provider_status: string | null;
  proposal_id: string;
}
export interface AuditEvent {
  event: string;
  at: string;
  details: Record<string, unknown>;
}
