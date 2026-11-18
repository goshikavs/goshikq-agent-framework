"""Simulated airline inventory. A hold acknowledgement is not a confirmed PNR."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from uuid import uuid4


class Fault(str, Enum):
    NONE = "none"
    NEVER_CONFIRMS = "never_confirms"
    AVAILABILITY_CHANGED = "availability_changed"
    DUPLICATE_HOLD = "duplicate_hold"


@dataclass
class Flight:
    id: str
    seats: int
    version: int = 1


@dataclass
class Reservation:
    id: str
    flight_id: str
    passenger: str
    status: str
    pnr: str | None = None
    idempotency_key: str = ""


@dataclass
class SimulatedAirline:
    fault: str = Fault.NONE
    flights: dict[str, Flight] = field(default_factory=dict)
    reservations: dict[str, Reservation] = field(default_factory=dict)
    keys: dict[str, str] = field(default_factory=dict)
    hold_count: int = 0

    def availability(self, flight_id: str) -> dict:
        f = self.flights.get(flight_id)
        if not f:
            return {"available": False, "reason": "unknown_flight"}
        if self.fault == Fault.AVAILABILITY_CHANGED:
            return {"available": False, "seats": 0, "flight_id": flight_id, "version": f.version}
        return {"available": f.seats > 0, "seats": f.seats, "flight_id": flight_id, "version": f.version}

    def hold(self, flight_id: str, passenger: str, idempotency_key: str) -> dict:
        if idempotency_key in self.keys:
            existing = self.reservations[self.keys[idempotency_key]]
            return {
                "accepted": True,
                "duplicate": True,
                "reservation": {"id": existing.id, "status": existing.status, "pnr": existing.pnr},
            }
        f = self.flights[flight_id]
        if f.seats <= 0 or self.fault == Fault.AVAILABILITY_CHANGED:
            return {"accepted": False, "reason": "sold_out"}
        self.hold_count += 1
        rid = str(uuid4())
        res = Reservation(
            id=rid,
            flight_id=flight_id,
            passenger=passenger,
            status="pending_confirmation",
            idempotency_key=idempotency_key,
        )
        self.reservations[rid] = res
        self.keys[idempotency_key] = rid
        f.seats -= 1
        f.version += 1
        if self.fault != Fault.NEVER_CONFIRMS:
            res.status = "confirmed"
            res.pnr = f"PNR-{rid[:8].upper()}"
        return {
            "accepted": True,
            "duplicate": False,
            "confirmed": res.status == "confirmed",
            "reservation": {"id": res.id, "status": res.status, "pnr": res.pnr},
        }

    def confirm_status(self, reservation_id: str) -> dict:
        r = self.reservations.get(reservation_id)
        if not r:
            return {"found": False}
        return {"found": True, "id": r.id, "status": r.status, "pnr": r.pnr}

    def snapshot(self) -> dict:
        return {
            "flights": {k: {"id": v.id, "seats": v.seats, "version": v.version} for k, v in self.flights.items()},
            "reservations": {
                k: {
                    "id": v.id,
                    "flight_id": v.flight_id,
                    "passenger": v.passenger,
                    "status": v.status,
                    "pnr": v.pnr,
                }
                for k, v in self.reservations.items()
            },
        }


def demo_airline(fault: str = Fault.NONE) -> SimulatedAirline:
    return SimulatedAirline(fault=fault, flights={"FLIGHT-9": Flight(id="FLIGHT-9", seats=2)})
