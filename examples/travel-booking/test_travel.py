from travel_world import Fault, demo_airline


def test_hold_confirms_and_is_idempotent() -> None:
    air = demo_airline()
    first = air.hold("FLIGHT-9", "Ada", "k1")
    assert first["confirmed"] is True
    assert first["reservation"]["pnr"]
    second = air.hold("FLIGHT-9", "Ada", "k1")
    assert second["duplicate"] is True
    assert air.hold_count == 1
    assert len(air.reservations) == 1


def test_never_confirms_is_pending_not_pnr() -> None:
    air = demo_airline(Fault.NEVER_CONFIRMS)
    held = air.hold("FLIGHT-9", "Ada", "k2")
    assert held["accepted"] is True
    assert held["confirmed"] is False
    assert held["reservation"]["status"] == "pending_confirmation"
    assert held["reservation"]["pnr"] is None


def test_availability_changed_blocks_hold() -> None:
    air = demo_airline(Fault.AVAILABILITY_CHANGED)
    assert air.availability("FLIGHT-9")["available"] is False
    assert air.hold("FLIGHT-9", "Ada", "k3")["accepted"] is False
