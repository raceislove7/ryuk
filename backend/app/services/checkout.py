"""Trusted backend checkout coordination; no browser/model-authored financial terms.

Authority remains in the existing approval service. Execution, budget holds and
provider observations are durable. Public authentication/UI are separate adapters.
"""

import asyncio
import sqlite3
from collections.abc import Callable, Iterator
from contextlib import ExitStack, contextmanager
from dataclasses import replace
from datetime import datetime, timezone
from uuid import uuid4

from pydantic import AwareDatetime, TypeAdapter

from app.schemas import ApprovalState, ApprovalStatus, PaymentIntent, PaymentState
from app.schemas.checkout import CheckoutRecord, OrderCreationState
from app.schemas.policy import AttemptSnapshot, AttemptState
from app.services.approvals import InMemoryApprovalService
from app.services.checkout_store import CheckoutStore
from app.services.durable_approvals import DurableApprovalService, authority_transaction
from app.services.payment_state_machine import PaymentEvent, transition_payment_intent
from app.services.paypal import (
    PayPalCaptureDeclined,
    PayPalError,
    PayPalOrderResult,
    PayPalOrderTerms,
    PayPalSandboxAdapter,
    PayPalUncertain,
    request_id,
)
from app.services.proposal_binding import require_proposal_binding

TERMINAL = frozenset({PaymentState.SUCCEEDED, PaymentState.FAILED})


class CheckoutBlocked(RuntimeError):
    """Current canonical records do not authorize dispatch; no capture was sent."""


class CheckoutUnavailable(RuntimeError):
    """Provider outcome unavailable; consult persisted checkout and audit state."""


class CheckoutService:
    def __init__(
        self,
        store: CheckoutStore,
        approvals: InMemoryApprovalService,
        paypal: PayPalSandboxAdapter,
        *,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.store = store
        self.approvals = approvals
        if isinstance(approvals, DurableApprovalService) and approvals.store is not store:
            raise ValueError("Durable authority and checkout must share one store instance")
        self.paypal = paypal
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def _now(self) -> datetime:
        return TypeAdapter(AwareDatetime).validate_python(self._clock(), strict=True)

    def _move(
        self, connection: sqlite3.Connection, record: CheckoutRecord, event: PaymentEvent
    ) -> None:
        record.payment = transition_payment_intent(record.payment, event)
        self.store.save(connection, record)
        self.store.audit(connection, record.payment.payment_intent_id, event.value, self._now())

    def _note(self, payment_id: str, actor: str, event: str) -> None:
        with self.store.transaction() as connection:
            self.store.load(connection, payment_id, actor)
            self.store.audit(connection, payment_id, event, self._now())

    @contextmanager
    def _authority_transaction(self) -> Iterator[tuple[sqlite3.Connection, ExitStack]]:
        # Release canonical authority locks only after the durable claim commits.
        with ExitStack() as guards:
            with authority_transaction(self.store) as connection:
                yield connection, guards

    async def create_checkout(self, proposal_id: str, *, actor_user_id: str) -> CheckoutRecord:
        """Unique checkout per canonical proposal; retries return the existing record.

        actor_user_id must originate from trusted authentication, not a JSON user ID.
        Application approval must already exist when current policy requires it.
        """
        with self._authority_transaction() as (connection, guards):
            # Check canonical ownership even when returning an existing checkout.
            self.approvals.get_proposal(proposal_id, actor_user_id=actor_user_id)
            existing = connection.execute(
                "SELECT payment_id FROM checkouts WHERE proposal_id=?", (proposal_id,)
            ).fetchone()
            if existing is not None:
                return self.store.load(connection, existing["payment_id"], actor_user_id)
            policy = self.store.policy(connection, actor_user_id)
            budget = self.store.budget(connection, actor_user_id)
            attempts = AttemptSnapshot(
                user_id=actor_user_id, proposal_id=proposal_id, state=AttemptState.CLEAR
            )
            proposal, approval = guards.enter_context(
                self.approvals.checkout_guard(
                    proposal_id,
                    actor_user_id=actor_user_id,
                    at=self._now(),
                    policy=policy,
                    budget=budget,
                    attempts=attempts,
                )
            )
            require_proposal_binding(proposal)
            payment_id, key = str(uuid4()), str(uuid4())
            terms = PayPalOrderTerms(
                reference_id=payment_id,
                merchant_id=self.store.merchant(connection, proposal.offer.merchant_id),
                amount_minor=proposal.offer.amount_minor,
                currency=proposal.offer.currency,
            )
            payment = PaymentIntent(
                payment_intent_id=payment_id,
                idempotency_key=key,
                created_at=self._now(),
                proposal_id=proposal_id,
                user_id=actor_user_id,
                offer_id=proposal.offer.offer_id,
                merchant_id=proposal.offer.merchant_id,
                amount_minor=proposal.offer.amount_minor,
                currency=proposal.offer.currency,
                policy_version=proposal.policy_version,
                verification_snapshot_id=proposal.verification.verification_snapshot_id,
                proposal_digest=proposal.proposal_digest,
                approval_state=(ApprovalState.APPROVED if approval else ApprovalState.NOT_REQUIRED),
                approval_request_id=approval.approval_request_id if approval else None,
            )
            record = CheckoutRecord(payment=payment, terms=terms)
            connection.execute(
                "INSERT INTO checkouts VALUES (?, ?, ?, ?)",
                (
                    payment_id,
                    proposal_id,
                    actor_user_id,
                    record.model_dump_json(),
                ),
            )
            self._move(connection, record, PaymentEvent.START_POLICY_CHECK)
            self._move(connection, record, PaymentEvent.POLICY_ALLOWED)
            self.store.audit(
                connection,
                payment_id,
                "ORDER_CREATE_DISPATCH",
                self._now(),
                {
                    "provider_request_id": request_id("create", key),
                },
            )
        # Claim and stable key are committed before provider I/O. No DB lock spans await.
        try:
            result = await self.paypal.create_order(record.terms, idempotency_key=key)
        except PayPalUncertain:
            return self._creation_failed(payment_id, actor_user_id, uncertain=True)
        except PayPalError:
            return self._creation_failed(payment_id, actor_user_id, uncertain=False)
        except asyncio.CancelledError:
            self._creation_failed(payment_id, actor_user_id, uncertain=True)
            raise
        except Exception:
            self._creation_failed(payment_id, actor_user_id, uncertain=True)
            raise CheckoutUnavailable(
                "Order creation interrupted; inspect checkout state"
            ) from None
        with self.store.transaction() as connection:
            record = self.store.load(connection, payment_id, actor_user_id)
            record.order_id = result.order_id
            # Creation never authorizes one-step capture or trusts a surprise paid result.
            if result.state != PaymentState.AWAITING_PAYPAL_BUYER:
                record.order_creation = OrderCreationState.UNKNOWN
                self.store.save(connection, record)
                self.store.audit(
                    connection, payment_id, "ORDER_CREATE_REVIEW_REQUIRED", self._now()
                )
            else:
                record.order_creation = OrderCreationState.READY
                self._move(connection, record, PaymentEvent.START_BUYER_APPROVAL)
                self.store.audit(connection, payment_id, "PAYPAL_ORDER_CREATED", self._now())
            return record

    def _creation_failed(self, payment_id: str, actor: str, *, uncertain: bool) -> CheckoutRecord:
        with self.store.transaction() as connection:
            record = self.store.load(connection, payment_id, actor)
            record.order_creation = (
                OrderCreationState.UNKNOWN if uncertain else OrderCreationState.FAILED
            )
            if not uncertain:
                self._move(connection, record, PaymentEvent.CANCEL)
            self.store.save(connection, record)
            self.store.audit(
                connection,
                payment_id,
                "ORDER_CREATE_UNKNOWN" if uncertain else "ORDER_CREATE_FAILED_BEFORE_DISPATCH",
                self._now(),
            )
            return record

    def _claim_capture(self, payment_id: str, actor: str) -> None:
        """After provider GET/OAuth, atomically reload authority, reserve and claim POST."""
        with self._authority_transaction() as (connection, guards):
            record = self.store.load(connection, payment_id, actor)
            payment = record.payment
            if payment.state != PaymentState.AWAITING_PAYPAL_BUYER:
                raise CheckoutBlocked("Capture already claimed or checkout no longer ready")
            policy = self.store.policy(connection, actor)
            budget = self.store.budget(connection, actor)
            attempts = AttemptSnapshot(
                user_id=actor, proposal_id=payment.proposal_id, state=AttemptState.CLEAR
            )
            proposal, approval = guards.enter_context(
                self.approvals.checkout_guard(
                    payment.proposal_id,
                    actor_user_id=actor,
                    at=self._now(),
                    policy=policy,
                    budget=budget,
                    attempts=attempts,
                    approval_request_id=payment.approval_request_id,
                )
            )
            require_proposal_binding(proposal)
            if proposal.proposal_digest != payment.proposal_digest:
                raise CheckoutBlocked("Canonical proposal changed; new checkout required")
            current_id = approval.approval_request_id if approval else None
            if current_id != payment.approval_request_id or (
                approval is not None and approval.status != ApprovalStatus.APPROVED
            ):
                raise CheckoutBlocked("Checkout approval changed; new checkout required")
            expected = PayPalOrderTerms(
                reference_id=payment_id,
                merchant_id=self.store.merchant(connection, proposal.offer.merchant_id),
                amount_minor=proposal.offer.amount_minor,
                currency=proposal.offer.currency,
            )
            if expected != record.terms:
                raise CheckoutBlocked("Sandbox merchant mapping or payment terms changed")
            self.store.audit(
                connection,
                payment_id,
                "CAPTURE_REVALIDATED",
                self._now(),
                {
                    "proposal_digest": proposal.proposal_digest,
                    "verification_snapshot_id": proposal.verification.verification_snapshot_id,
                    "policy_version": policy.version,
                    "approval_request_id": current_id,
                },
            )
            connection.execute(
                "INSERT INTO reservations VALUES (?, ?, ?, ?, 'HELD')",
                (
                    payment_id,
                    actor,
                    payment.currency,
                    payment.amount_minor,
                ),
            )
            # Policy approval and reservation form one durable linearization point.
            self._move(connection, record, PaymentEvent.RECHECK_POLICY)
            self._move(connection, record, PaymentEvent.POLICY_ALLOWED)
            self._move(connection, record, PaymentEvent.START_BUYER_APPROVAL)
            self.store.audit(
                connection,
                payment_id,
                "BUDGET_RESERVED",
                self._now(),
                {
                    "amount_minor": payment.amount_minor,
                    "currency": payment.currency,
                },
            )
            self.store.audit(connection, payment_id, "PAYPAL_BUYER_APPROVED", self._now())
            self._move(connection, record, PaymentEvent.REQUEST_CAPTURE)
            self.store.audit(
                connection,
                payment_id,
                "CAPTURE_DISPATCH",
                self._now(),
                {
                    "provider_request_id": request_id("capture", payment.idempotency_key),
                },
            )

    async def capture(self, payment_id: str, *, actor_user_id: str) -> CheckoutRecord:
        """A buyer callback only asks for processing; provider GET establishes approval."""
        record = self.store.get_checkout(payment_id, actor_user_id=actor_user_id)
        if record.payment.state in TERMINAL:
            return record
        if record.payment.state in {PaymentState.CAPTURE_PENDING, PaymentState.PENDING_PROVIDER}:
            return await self.reconcile(payment_id, actor_user_id=actor_user_id)
        if (
            record.order_creation != OrderCreationState.READY
            or record.order_id is None
            or record.payment.state != PaymentState.AWAITING_PAYPAL_BUYER
        ):
            raise CheckoutBlocked("Order creation is incomplete or uncertain")
        claimed = False

        def before_capture() -> None:
            nonlocal claimed
            self._claim_capture(payment_id, actor_user_id)
            claimed = True

        try:
            result = await self.paypal.capture(
                record.order_id,
                record.terms,
                idempotency_key=record.payment.idempotency_key,
                before_capture=before_capture,
            )
        except PayPalCaptureDeclined as error:
            with self.store.transaction() as connection:
                persisted = self.store.load(connection, payment_id, actor_user_id)
                if (
                    not claimed
                    or error.order_id != persisted.order_id
                    or error.request_id != request_id("capture", persisted.payment.idempotency_key)
                ):
                    raise CheckoutBlocked("Decline evidence does not match dispatched capture")
                persisted.capture_decline_code = error.code
                persisted.decline_request_id = error.request_id
                self.store.save(connection, persisted)
                self.store.audit(
                    connection,
                    payment_id,
                    "CAPTURE_DECLINE_RECORDED",
                    self._now(),
                    {"code": error.code},
                )
            self._mark_pending(payment_id, actor_user_id)
            return await self.reconcile(payment_id, actor_user_id=actor_user_id)
        except PayPalUncertain:
            self._mark_pending(payment_id, actor_user_id)
            return self.store.get_checkout(payment_id, actor_user_id=actor_user_id)
        except asyncio.CancelledError:
            if claimed:
                self._mark_pending(payment_id, actor_user_id)
            raise
        except Exception:
            if claimed:
                self._mark_pending(payment_id, actor_user_id)
                raise CheckoutUnavailable(
                    "Capture outcome unavailable; reconciliation required"
                ) from None
            self._note(payment_id, actor_user_id, "CAPTURE_BLOCKED_BEFORE_DISPATCH")
            raise CheckoutBlocked(
                "Current canonical authority or provider preflight blocks capture"
            ) from None
        return self._finish(payment_id, actor_user_id, result)

    def _mark_pending(self, payment_id: str, actor: str) -> None:
        with self.store.transaction() as connection:
            record = self.store.load(connection, payment_id, actor)
            if record.payment.state == PaymentState.CAPTURE_PENDING:
                self._move(connection, record, PaymentEvent.CAPTURE_UNCERTAIN)

    async def reconcile(self, payment_id: str, *, actor_user_id: str) -> CheckoutRecord:
        """Only query the provider; never capture again or release an inconclusive hold."""
        record = self.store.get_checkout(payment_id, actor_user_id=actor_user_id)
        if record.payment.state in TERMINAL:
            return record
        if record.payment.state not in {
            PaymentState.CAPTURE_PENDING,
            PaymentState.PENDING_PROVIDER,
        }:
            raise CheckoutBlocked("No attempted capture to reconcile")
        self._mark_pending(payment_id, actor_user_id)
        try:
            result = await self.paypal.get_status(
                record.order_id, record.terms, capture_attempted=True
            )
        except PayPalError:
            self._note(payment_id, actor_user_id, "PROVIDER_STATUS_UNAVAILABLE")
            return self.store.get_checkout(payment_id, actor_user_id=actor_user_id)
        if (
            record.capture_decline_code == "INSTRUMENT_DECLINED"
            and record.decline_request_id == request_id("capture", record.payment.idempotency_key)
            and result.order_id == record.order_id
            and result.capture_absent
            and result.capture_id is None
            and result.provider_status in {"CREATED", "SAVED", "APPROVED", "PAYER_ACTION_REQUIRED"}
            and result.state == PaymentState.PENDING_PROVIDER
        ):
            result = replace(result, state=PaymentState.FAILED)
        return self._finish(payment_id, actor_user_id, result)

    def _finish(self, payment_id: str, actor: str, result: PayPalOrderResult) -> CheckoutRecord:
        with self.store.transaction() as connection:
            record = self.store.load(connection, payment_id, actor)
            if record.payment.state in TERMINAL:
                return record  # Concurrent/repeated status observations cannot double settle.
            if result.order_id != record.order_id:
                raise CheckoutBlocked("Provider result refers to a different order")
            if record.payment.state == PaymentState.AWAITING_PAYPAL_BUYER:
                # A provider terminal preflight sends no POST. Record financial truth even
                # if an external actor captured it; never silently omit a confirmed debit.
                if result.state == PaymentState.FAILED:
                    self._move(connection, record, PaymentEvent.BUYER_DECLINED)
                    return record
                if result.state != PaymentState.SUCCEEDED:
                    raise CheckoutBlocked("No conclusive capture observation")
                self.store.audit(connection, payment_id, "EXTERNAL_CAPTURE_DISCOVERED", self._now())
                connection.execute(
                    "INSERT INTO reservations VALUES (?, ?, ?, ?, 'HELD')",
                    (
                        payment_id,
                        actor,
                        record.payment.currency,
                        record.payment.amount_minor,
                    ),
                )
                self._move(connection, record, PaymentEvent.REQUEST_CAPTURE)
            if result.state not in TERMINAL:
                if record.payment.state == PaymentState.CAPTURE_PENDING:
                    self._move(connection, record, PaymentEvent.CAPTURE_UNCERTAIN)
                self.store.audit(
                    connection, payment_id, "PROVIDER_RECONCILIATION_INCONCLUSIVE", self._now()
                )
                return record
            pending = record.payment.state == PaymentState.PENDING_PROVIDER
            succeeded = result.state == PaymentState.SUCCEEDED
            event = (
                (PaymentEvent.RECONCILED_SUCCESS if succeeded else PaymentEvent.RECONCILED_FAILURE)
                if pending
                else (PaymentEvent.CAPTURE_CONFIRMED if succeeded else PaymentEvent.CAPTURE_FAILED)
            )
            row = connection.execute(
                "SELECT status FROM reservations WHERE payment_id=?", (payment_id,)
            ).fetchone()
            if row is None or row["status"] != "HELD":
                raise CheckoutBlocked("Missing durable reservation; manual recovery required")
            if succeeded:
                connection.execute(
                    "UPDATE accounts SET settled_minor=settled_minor+? WHERE user_id=?",
                    (record.payment.amount_minor, actor),
                )
                record.capture_id = result.capture_id
            connection.execute(
                "UPDATE reservations SET status=? WHERE payment_id=?",
                ("SETTLED" if succeeded else "RELEASED", payment_id),
            )
            self._move(connection, record, event)
            self.store.audit(
                connection,
                payment_id,
                "BUDGET_SETTLED" if succeeded else "BUDGET_RELEASED",
                self._now(),
            )
            return record

    def cancel(self, payment_id: str, *, actor_user_id: str) -> CheckoutRecord:
        """Local buyer cancellation; cannot cancel a dispatched or uncertain capture."""
        with self.store.transaction() as connection:
            record = self.store.load(connection, payment_id, actor_user_id)
            if record.payment.state in TERMINAL:
                return record
            if record.payment.state != PaymentState.AWAITING_PAYPAL_BUYER:
                raise CheckoutBlocked("Only an order awaiting its buyer can be canceled")
            self._move(connection, record, PaymentEvent.BUYER_DECLINED)
            return record
