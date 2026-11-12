"""Only isolated financial fixtures are used; export never writes or contacts a provider."""

from test_checkout import ACTOR, env, ready, run  # noqa: F401

from app.export_acceptance import EvidenceUnavailable, export_acceptance


def test_success_export_has_one_settlement_and_no_credentials(env):  # noqa: F811
    async def scenario():
        record = await ready(env)
        return await env["service"].capture(record.payment.payment_intent_id, **ACTOR)

    record = run(scenario())
    before = env["store"].get_budget("user-1")
    receipt = export_acceptance(env["store"].path)
    assert receipt["checks_passed"]
    assert receipt["capture_id"] == record.capture_id
    assert receipt["amount_minor"] == 118000
    assert receipt["audit"] and all(
        set(row) == {"sequence", "event", "at"} for row in receipt["audit"]
    )
    assert env["store"].get_budget("user-1") == before


def test_pending_export_never_claims_payment_or_releases_hold(env):  # noqa: F811
    async def scenario():
        record = await ready(env)
        env["sandbox"].capture_mode = "timeout"
        return await env["service"].capture(record.payment.payment_intent_id, **ACTOR)

    record = run(scenario())
    receipt = export_acceptance(env["store"].path, record.payment.payment_intent_id)
    assert not receipt["checks_passed"]
    assert not receipt["checks"]["backend_succeeded"]
    assert env["store"].get_budget("user-1").reserved_minor == 118000


def test_missing_database_not_created(tmp_path):
    import pytest

    path = tmp_path / "missing.sqlite3"
    with pytest.raises(EvidenceUnavailable):
        export_acceptance(path)
    assert not path.exists()
