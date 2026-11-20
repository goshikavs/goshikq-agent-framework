"""Travel booking: a hold acknowledgement is not a confirmed PNR.

Usage:
    python main.py
    python main.py --fault never_confirms
    python main.py --fault availability_changed
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys

from goshikq_ai import Agent, DecisionRef, Evidence, Goal, InvariantOutcome, Runtime, StateSnapshot, tool, with_evidence
from goshikq_ai.models import MockModel, ModelTurn, last_tool_result
from goshikq_ai.state import SnapshotContext
from goshikq_ai.tools import VerifierResult

from travel_world import Fault, SimulatedAirline, demo_airline

AIRLINE: SimulatedAirline = demo_airline()


def _verify_reservation(arguments: dict, output, state: StateSnapshot):
    reservations = state.get("reservations") or {}
    res = None
    if output and isinstance(output, dict):
        rid = (output.get("reservation") or {}).get("id")
        res = reservations.get(rid or "")
    if not res and reservations:
        res = next(iter(reservations.values()))
    if not res:
        return VerifierResult.inconclusive("no reservation in snapshot")
    actual = {"status": res.get("status"), "pnr": res.get("pnr")}
    if res.get("status") == "confirmed" and res.get("pnr"):
        return VerifierResult.verified(expected={"status": "confirmed"}, actual=actual, method="reservation.status+pnr")
    if output and isinstance(output, dict) and output.get("accepted") and res.get("status") != "confirmed":
        return VerifierResult.waiting(
            "hold accepted; provider confirmation pending",
            expected={"status": "confirmed"},
            actual=actual,
            method="reservation.status+pnr",
        )
    return VerifierResult.inconclusive(f"status={res.get('status')}", method="reservation.status")


@tool(effect="read_only")
def check_availability(flight_id: str) -> dict:
    raw = AIRLINE.availability(flight_id)
    flight = AIRLINE.flights.get(flight_id)
    return with_evidence(
        raw,
        [
            Evidence(
                source_system="inventory",
                resource_id=f"flight:{flight_id}",
                resource_version=str(flight.version) if flight else None,
                trust="authoritative",
                access_scope="bookings-read",
            )
        ],
        DecisionRef(
            id=f"dec:avail:{flight_id}",
            kind="availability",
            depends_on=[f"flight:{flight_id}"],
            action="act:hold_reservation",
            payload={"resource_id": f"flight:{flight_id}"},
        ),
    )


@tool(effect="idempotent_write", idempotent=True, risk="low", verifier=_verify_reservation)
def hold_reservation(flight_id: str, passenger: str) -> dict:
    return AIRLINE.hold(flight_id, passenger, f"hold:{flight_id}:{passenger}")


@tool(effect="read_only")
def get_reservation(reservation_id: str) -> dict:
    return AIRLINE.confirm_status(reservation_id)


class AirlineProvider:
    def snapshot(self, context: SnapshotContext) -> StateSnapshot:
        snap = AIRLINE.snapshot()
        return StateSnapshot(state=snap, version=str(AIRLINE.flights["FLIGHT-9"].version), source="airline-inventory")

    def version(self, resource_id: str) -> str | None:
        key = resource_id.removeprefix("flight:")
        flight = AIRLINE.flights.get(key)
        return str(flight.version) if flight else None


def reservation_confirmed(state: StateSnapshot) -> InvariantOutcome:
    reservations = state.get("reservations") or {}
    confirmed = [r for r in reservations.values() if r.get("status") == "confirmed" and r.get("pnr")]
    ok = len(confirmed) == 1
    return InvariantOutcome(
        ok,
        expected={"confirmed": 1},
        actual=len(confirmed),
        reason=None if ok else "no confirmed PNR in authoritative inventory",
    )


def no_duplicate_holds(state: StateSnapshot) -> InvariantOutcome:
    ok = AIRLINE.hold_count <= 1
    return InvariantOutcome(ok, expected={"max_holds": 1}, actual=AIRLINE.hold_count)


def policy(messages, tools, idx: int) -> ModelTurn:
    if idx == 0:
        return ModelTurn(tool_calls=[("check_availability", {"flight_id": "FLIGHT-9"})])
    avail = last_tool_result(messages, "check_availability") or {}
    inner = avail.get("result", avail)
    if not inner.get("available"):
        return ModelTurn(content=f"No seats: {inner}")
    if idx == 1:
        return ModelTurn(tool_calls=[("hold_reservation", {"flight_id": "FLIGHT-9", "passenger": "Ada"})])
    held = last_tool_result(messages, "hold_reservation") or {}
    payload = held.get("result", held)
    rid = (payload.get("reservation") or {}).get("id")
    if payload.get("accepted") and not payload.get("confirmed") and rid:
        return ModelTurn(tool_calls=[("get_reservation", {"reservation_id": rid})])
    if payload.get("confirmed"):
        return ModelTurn(content=f"Reservation confirmed {rid}")
    return ModelTurn(content=f"Reservation not confirmed: {payload}")


async def run_once(fault: str) -> int:
    global AIRLINE
    AIRLINE = demo_airline(fault)
    wait = "8" if fault == Fault.NEVER_CONFIRMS else "20"
    os.environ["GOSHIKQ_EXTERNAL_WAIT_SECONDS"] = wait
    agent = Agent(
        name="travel_agent",
        model=MockModel(policy=policy),
        tools=[check_availability, hold_reservation, get_reservation],
    )
    goal = Goal(
        description="Ada has a confirmed PNR on FLIGHT-9",
        success=reservation_confirmed,
        invariants=[no_duplicate_holds],
        max_steps=8,
        external_wait_seconds=int(wait),
    )
    async with Runtime(agent, state_provider=AirlineProvider()) as rt:
        result = await rt.run(goal, input={"flight_id": "FLIGHT-9", "fault": fault})
    print(result.summary())
    print(f"hold_count: {AIRLINE.hold_count}")
    print(f"reservations: {AIRLINE.snapshot()['reservations']}")
    return 0 if result.verified else 1


def main() -> int:
    logging.basicConfig(level=os.environ.get("GOSHIKQ_LOG", "WARNING"))
    p = argparse.ArgumentParser(description="Goshikq travel booking demo")
    p.add_argument("--fault", default=Fault.NONE, choices=[e.value for e in Fault])
    args = p.parse_args()
    return asyncio.run(run_once(args.fault))


if __name__ == "__main__":
    sys.exit(main())
