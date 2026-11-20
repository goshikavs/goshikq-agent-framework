from bank_world import Fault, demo_bank


def test_happy_path_applies_new_routing() -> None:
    bank = demo_bank()
    assert bank.lookup("ACCT-1")["routing"] == "021000021"
    auth = bank.authorize("ACCT-1", "Ada")
    assert auth["authorized"] is True
    result = bank.apply_update("ACCT-1", "026009593", auth["version"])
    assert result["applied"] is True
    assert bank.accounts["ACCT-1"].routing == "026009593"
    assert bank.accounts["ACCT-1"].core_status == "applied"
    assert bank.apply_count == 1


def test_version_conflict_does_not_apply() -> None:
    bank = demo_bank()
    bank.bump_version("ACCT-1")
    result = bank.apply_update("ACCT-1", "026009593", 3)
    assert result["applied"] is False
    assert result["reason"] == "version_conflict"
    assert bank.accounts["ACCT-1"].routing == "021000021"


def test_ack_is_not_applied_on_readback_mismatch() -> None:
    bank = demo_bank(Fault.READBACK_MISMATCH)
    result = bank.apply_update("ACCT-1", "026009593", 3)
    assert result["accepted"] is True
    assert result["applied"] is False
    assert bank.accounts["ACCT-1"].routing == "021000021"
    assert bank.accounts["ACCT-1"].core_status == "update_pending"


def test_rejected_auth() -> None:
    bank = demo_bank(Fault.REJECTED_AUTH)
    assert bank.authorize("ACCT-1", "Ada")["authorized"] is False
