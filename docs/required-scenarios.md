# Required acceptance scenarios — 2026-11-12

Verified against repository baseline c8c88eb plus the mandatory-requirement API regression in this change. This is automated backend/service/API acceptance using fresh SQLite fixtures and mocked model/PayPal transports. No new live payment, existing ledger reset or private credential is used. It does not certify another live UI transaction, timing, or production readiness.

## Results: six requested scenarios

| Scenario | Trigger and required outcome | Verified evidence |
| --- | --- | --- |
| Eligible | Complete-evidence trusted internal USD1,180 proposal within limits. Model-derived proposals still need review. | ALLOW_ELIGIBLE_FOR_CHECKOUT at policy layer; valid trusted checkout reaches SUCCEEDED after buyer approval, with a prior atomic reservation and one settlement. |
| Approval required | Model-derived proposals, including below-threshold offers, require explicit original/parsed intent review. A USD1,390 offer also exceeds the USD1,300 review threshold. | Checkout returns 409 before application approval; exact approval permits order creation; capture is blocked until separate provider buyer approval. |
| Budget denied | USD1,620 offer against USD1,500 ceiling; lower requested, policy and remaining-balance ceilings checked independently. | DENY/BUDGET_EXCEEDED; review cannot authorize the denied checkout; no provider order. |
| Mandatory requirement denied | USD980 offer explicitly lacks mandatory gym; price is within budget. | DENY/REQUIRED_ATTRIBUTE_FAILED without BUDGET_EXCEEDED; both approval and checkout return 409; zero provider calls and zero settled/reserved money. |
| Tampering blocked | Browser supplies amount/merchant/user/status/order/approval fields, or canonical terms/evidence/policy change during provider preflight. | Unexpected HTTP authority fields return 422 before provider calls. Changed canonical/provider bindings block capture with no capture POST or reservation. |
| Duplicate payment prevented | Repeat create/capture/reconcile or race simultaneous create/capture handlers. | One order/claim, one capture POST and one settlement. Concurrent requests cannot spend funds already reserved for another purchase. |

**Earlier five-scenario focused verification: 32 tests passed.** Existing tests were rerun; a new mandatory-failure HTTP regression closes the gap between a policy label and proving execution is blocked. No financial implementation was changed to obtain these results.

## Specific regression evidence

- Eligible: test_policy.py::test_planned_fixture_decisions (001); test_checkout.py::test_checkout_success_exact_terms_durable_audit_and_reservation_before_post. This internal trusted-proposal path does not exempt model-derived requests from review.
- Approval: test_workspace.py::test_approval_ui_backend_to_order_capture_and_audit; test_checkout.py::test_application_approval_and_paypal_buyer_approval_are_separate; test_security_boundaries.py::test_every_model_candidate_requires_explicit_review.
- Budget: test_policy.py::test_each_independent_budget_ceiling_is_enforced and ::test_planned_fixture_decisions; test_workspace.py::test_blocked_offer_and_rejected_approval_never_reach_checkout.
- Mandatory failure: test_required_scenarios.py::test_mandatory_requirement_denial_never_dispatches_provider; fixture decision for synthetic-hotel-004.
- Tampering: test_checkout.py::test_http_rejects_browser_authority_fields, ::test_canonical_changes_during_provider_preflight_block_capture and ::test_provider_binding_mismatch_during_preflight_blocks_capture.
- Duplicates/concurrency: test_checkout.py::test_checkout_and_capture_retries_do_not_create_orders_or_double_settle, ::test_simultaneous_capture_handlers_dispatch_once_while_hold_is_in_flight, ::test_simultaneous_create_returns_claim_without_duplicate_provider_order and ::test_concurrent_different_proposals_cannot_spend_reserved_funds.

From backend/ with development dependencies installed, this broader command reruns all relevant scenario modules (not just the focused 32):

```sh
.venv/bin/pytest -q tests/test_policy.py tests/test_workspace.py tests/test_checkout.py tests/test_security_boundaries.py tests/test_required_scenarios.py
```

For full regression, run `.venv/bin/pytest -q`. Financial fixtures are newly created by pytest; provider/model requests are mocked. Do not prove duplicate prevention by manually submitting another live capture, and never reset a real ledger for a demonstration. Keep real successful-payment receipts private, as described in operations.md.

The later six-scenario rerun uses the full backend suite, including the eligible-policy/checkout cases and explicit amount mutation/browser amount-field cases. Its results are recorded in STATUS.md. No runtime features were added.

## Step 13 final rerun

The full 1,082-test suite at runtime source 8497325 covers all six scenarios, including trusted eligible execution, model-intent review, budget and mandatory denial, duplicate prevention and amount tampering. The browser suite includes saved-history recovery after reload. This documentation-only freeze does not grant any new financial authority. See STATUS.md for final packaging/rehearsal results.
