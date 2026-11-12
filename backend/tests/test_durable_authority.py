"""Restart, revocation and cross-connection tests with isolated SQLite/provider fixtures."""

import json
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta

import pytest
import test_checkout as checkout
from test_workspace import ORIGIN, client, investigate  # noqa: F401

from app.services.approvals import ApprovalAccessError, ApprovalPolicyError, ApprovalStateError
from app.services.checkout import CheckoutBlocked, CheckoutService
from app.services.checkout_store import CheckoutStore
from app.services.durable_approvals import DurableApprovalService
from app.services.verifier import verify_offer
from app.services.workspace import WorkspaceService


@pytest.fixture
def durable(tmp_path):
    generator = checkout.env.__wrapped__(tmp_path)
    env = next(generator)
    env["approvals"] = DurableApprovalService(env["store"])
    env["approvals"].register_proposal(env["proposal"], at=env["now"][0])
    env["service"] = CheckoutService(
        env["store"], env["approvals"], env["paypal"], clock=lambda: env["now"][0]
    )
    yield env
    with pytest.raises(StopIteration):
        next(generator)


def restart(env):
    env["store"] = CheckoutStore(env["store"].path)
    env["approvals"] = DurableApprovalService(env["store"])
    env["service"] = CheckoutService(
        env["store"], env["approvals"], env["paypal"], clock=lambda: env["now"][0]
    )


def inputs(env, proposal):
    from app.schemas.policy import AttemptSnapshot

    return {
        **checkout.ACTOR,
        "at": env["now"][0],
        "policy": env["policy"],
        "budget": env["store"].get_budget("user-1"),
        "attempts": AttemptSnapshot(
            user_id="user-1", proposal_id=proposal.proposal_id, state="CLEAR"
        ),
    }


def test_restart_keeps_pending_review_and_ttl(durable):
    env = durable
    p = checkout.register(env, number="002")
    request = env["approvals"].create_request(p.proposal_id, **inputs(env, p))
    restart(env)
    assert env["approvals"].get_proposal(p.proposal_id, **checkout.ACTOR) == p
    assert env["approvals"].create_request(p.proposal_id, **inputs(env, p)) == request
    approved = env["approvals"].approve_request(request.approval_request_id, **inputs(env, p))
    restart(env)
    assert (
        env["approvals"].get_request(
            request.approval_request_id, **checkout.ACTOR, at=env["now"][0]
        )
        == approved
    )
    with pytest.raises(ApprovalStateError):
        env["approvals"].approve_request(request.approval_request_id, **inputs(env, p))


def test_valid_persisted_consent_can_capture_once_after_restart(durable):
    env = durable
    p = checkout.register(env, number="002")
    checkout.grant(env, p)
    record = checkout.run(checkout.ready(env, p))
    restart(env)
    result = checkout.run(
        env["service"].capture(record.payment.payment_intent_id, **checkout.ACTOR)
    )
    assert result.payment.state == "SUCCEEDED"
    restart(env)
    checkout.run(env["service"].capture(record.payment.payment_intent_id, **checkout.ACTOR))
    assert len(env["sandbox"].capture_posts()) == 1
    assert env["store"].get_budget("user-1").settled_minor == 139000


def test_expired_consent_does_not_revive_after_restart(durable):
    env = durable
    p = checkout.register(env, number="002")
    request = checkout.grant(env, p)
    env["now"][0] = request.expires_at
    restart(env)
    with pytest.raises(ApprovalPolicyError):
        checkout.run(env["service"].create_checkout(p.proposal_id, **checkout.ACTOR))
    restart(env)
    assert (
        env["approvals"]
        .get_request(request.approval_request_id, **checkout.ACTOR, at=env["now"][0])
        .status
        == "EXPIRED"
    )
    assert not env["sandbox"].orders


def test_observed_policy_revocation_persists_even_when_checkout_denied(durable):
    env = durable
    p = checkout.register(env, number="002")
    grant = checkout.grant(env, p)
    original = env["policy"]
    env["store"].put_policy(original.model_copy(update={"version": "v2"}))
    with pytest.raises(ApprovalPolicyError):
        checkout.run(env["service"].create_checkout(p.proposal_id, **checkout.ACTOR))
    env["store"].put_policy(original)
    restart(env)
    assert (
        env["approvals"]
        .get_request(grant.approval_request_id, **checkout.ACTOR, at=env["now"][0])
        .status
        == "INVALIDATED"
    )
    with pytest.raises(ApprovalPolicyError):
        checkout.run(env["service"].create_checkout(p.proposal_id, **checkout.ACTOR))


def test_amount_change_during_preflight_revokes_persisted_grant(durable):
    env = durable
    p = checkout.register(env, number="002")
    request = checkout.grant(env, p)
    record = checkout.run(checkout.ready(env, p))
    changed = p.model_copy(deep=True)
    changed.offer.amount_minor += 1
    changed.verification = verify_offer(changed.intent, changed.offer)
    env["sandbox"].on_get = lambda: DurableApprovalService(
        CheckoutStore(env["store"].path)
    ).register_proposal(changed, at=env["now"][0], expected_digest=p.proposal_digest)
    with pytest.raises((ApprovalPolicyError, CheckoutBlocked)):
        checkout.run(env["service"].capture(record.payment.payment_intent_id, **checkout.ACTOR))
    restart(env)
    assert (
        env["approvals"]
        .get_request(request.approval_request_id, **checkout.ACTOR, at=env["now"][0])
        .status
        == "INVALIDATED"
    )
    assert not env["sandbox"].capture_posts()
    assert env["store"].get_budget("user-1").reserved_minor == 0


def test_concurrent_services_share_one_pending_request_and_one_decision(durable):
    env = durable
    p = checkout.register(env, number="002")
    args = inputs(env, p)

    def service():
        return DurableApprovalService(CheckoutStore(env["store"].path))

    with ThreadPoolExecutor(max_workers=2) as pool:
        requests = list(
            pool.map(lambda _: service().create_request(p.proposal_id, **args), range(2))
        )
    assert requests[0] == requests[1]

    def approve(_):
        try:
            service().approve_request(requests[0].approval_request_id, **args)
            return "APPROVED"
        except ApprovalStateError:
            return "BLOCKED"

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(approve, range(2))) == ["APPROVED", "BLOCKED"]


def test_rejection_and_monotonic_time_survive_restart(durable):
    env = durable
    p = checkout.register(env, number="002")
    request = env["approvals"].create_request(p.proposal_id, **inputs(env, p))
    env["approvals"].reject_request(request.approval_request_id, **checkout.ACTOR, at=env["now"][0])
    restart(env)
    assert (
        env["approvals"]
        .get_request(request.approval_request_id, **checkout.ACTOR, at=env["now"][0])
        .status
        == "REJECTED"
    )
    with pytest.raises(ValueError):
        env["approvals"].get_request(
            request.approval_request_id, **checkout.ACTOR, at=env["now"][0] - timedelta(seconds=1)
        )
    with pytest.raises(ApprovalAccessError):
        env["approvals"].get_proposal(p.proposal_id, actor_user_id="someone-else")


def test_authority_and_audit_rollback_together(durable):
    env = durable
    p = env["proposal"]
    with pytest.raises(RuntimeError):
        with env["store"].transaction():
            env["approvals"].create_request(p.proposal_id, **inputs(env, p))
            raise RuntimeError("simulate failed outer transaction")
    with env["store"].transaction() as connection:
        data = json.loads(connection.execute("SELECT body FROM proposal_authority").fetchone()[0])
        assert data["requests"] == []
        assert connection.execute("SELECT COUNT(*) FROM approval_lookup").fetchone()[0] == 0
        assert (
            connection.execute(
                "SELECT COUNT(*) FROM proposal_audit WHERE event='APPROVAL_STATE_CHANGED'"
            ).fetchone()[0]
            == 0
        )


def test_history_and_full_timeline_recover_without_provider_calls(client):  # noqa: F811
    candidates = investigate(client)
    pid = candidates[0]["proposal"]["proposal_id"]
    app = client.app
    previous = app.state.workspace
    store = CheckoutStore(previous.store.path)
    approvals = DurableApprovalService(store)
    app.state.workspace = WorkspaceService(previous.catalog, store, approvals)
    response = client.get("/v1/history")
    assert response.status_code == 200
    assert len(response.json()["items"]) == len(candidates)
    assert not client.sandbox.calls
    assert "USER_INTENT_CREATED" in {
        e["event"] for e in client.get(f"/v1/proposals/{pid}/audit").json()["events"]
    }
    with store.transaction() as connection:
        connection.execute("UPDATE recovery_index SET user_id='different-owner'")
    assert client.get("/v1/history").json()["items"] == []
    client.delete("/v1/session", headers=ORIGIN)
    assert client.get("/v1/history").status_code == 401


def test_legacy_checkout_backfill_preserves_money_and_never_recreates_consent(tmp_path):
    generator = checkout.env.__wrapped__(tmp_path)
    env = next(generator)
    try:
        record = checkout.run(checkout.ready(env))
        before = env["store"].get_budget("user-1")
        restart(env)
        with env["store"].transaction() as connection:
            assert connection.execute("SELECT COUNT(*) FROM recovery_index").fetchone()[0] == 1
            assert connection.execute("SELECT COUNT(*) FROM proposal_authority").fetchone()[0] == 0
        with pytest.raises(CheckoutBlocked):
            checkout.run(env["service"].capture(record.payment.payment_intent_id, **checkout.ACTOR))
        assert env["store"].get_budget("user-1") == before
        assert not env["sandbox"].capture_posts()
        workspace = WorkspaceService(checkout.CatalogService(), env["store"], env["approvals"])
        assert workspace.timeline(record.payment.proposal_id, "user-1")
        with pytest.raises(ApprovalAccessError):
            workspace.timeline(record.payment.proposal_id, "other-user")
    finally:
        with pytest.raises(StopIteration):
            next(generator)


def test_pending_reconciliation_after_restart_never_recaptures(durable):
    env = durable
    record = checkout.run(checkout.ready(env))
    env["sandbox"].capture_mode = "timeout_after_capture"
    result = checkout.run(
        env["service"].capture(record.payment.payment_intent_id, **checkout.ACTOR)
    )
    assert result.payment.state == "PENDING_PROVIDER"
    restart(env)
    result = checkout.run(
        env["service"].reconcile(record.payment.payment_intent_id, **checkout.ACTOR)
    )
    assert result.payment.state == "SUCCEEDED"
    assert len(env["sandbox"].capture_posts()) == 1


def test_history_pagination_and_legacy_views(client):  # noqa: F811
    app = client.app
    store = app.state.workspace.store
    actor = app.state.demo_sessions.actor
    candidates = investigate(client)
    pid = candidates[0]["proposal"]["proposal_id"]
    # Simulate multiple historical rows without touching any payment or invoking providers.
    with store.transaction() as connection:
        for i in range(55):
            connection.execute(
                "INSERT INTO recovery_index(proposal_id,user_id) VALUES (?,?)",
                ("orphan-" + str(i), actor),
            )
    page = client.get("/v1/history").json()
    assert page["next_before"] is not None
    next_page = client.get("/v1/history", params={"before": page["next_before"]}).json()
    assert pid in {r["proposal_id"] for r in next_page["items"]}
    assert client.get("/v1/history?before=0").status_code == 422
    assert not client.sandbox.calls
