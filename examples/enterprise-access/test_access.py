from access_world import Fault, demo_idp


def test_provision_adds_role() -> None:
    idp = demo_idp()
    assert idp.permissions("USER-ada")["allowed"] is True
    result = idp.provision("USER-ada", "payments.admin")
    assert result["applied"] is True
    assert "payments.admin" in idp.users["USER-ada"].roles


def test_idp_reject_does_not_grant_role() -> None:
    idp = demo_idp(Fault.IDP_REJECT)
    result = idp.provision("USER-ada", "payments.admin")
    assert result["applied"] is False
    assert "payments.admin" not in idp.users["USER-ada"].roles


def test_revoke_eligibility() -> None:
    idp = demo_idp()
    idp.revoke_eligibility("USER-ada")
    assert idp.permissions("USER-ada")["allowed"] is False
    assert idp.users["USER-ada"].eligible is False
