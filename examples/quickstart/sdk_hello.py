"""Standalone Python SDK example. Run it from any directory after the package is installed.

The package is not on PyPI yet. Install a built wheel, then run this file.
The runtime must already be healthy at GOSHIKQ_RUNTIME_URL (default http://127.0.0.1:7400).
No paid model key is required.
"""

from goshikq_ai import Agent, Goal, Runtime, StateSnapshot, tool
from goshikq_ai.models import MockModel, ModelTurn
from goshikq_ai.state import SnapshotContext

GREETINGS: dict[str, str] = {}


@tool(effect="idempotent_write", idempotent=True, risk="low")
def record_greeting(name: str, message: str) -> dict:
    """Store a greeting for name. Writing the same greeting twice is a no-op."""
    GREETINGS[name] = message
    return {"stored": True, "name": name}


class GreetingState:
    def snapshot(self, context: SnapshotContext) -> StateSnapshot:
        return StateSnapshot(state={"greetings": dict(GREETINGS)}, version=str(len(GREETINGS)), source="greetings-memory")

    def version(self, resource_id: str) -> str:
        return str(len(GREETINGS))


def ada_was_greeted(state: StateSnapshot) -> bool:
    greeting = state.get("greetings.Ada")
    return isinstance(greeting, str) and "Ada" in greeting


def no_more_than_one_greeting(state: StateSnapshot) -> bool:
    greetings = state.get("greetings") or {}
    return len(greetings) <= 1


def main() -> None:
    agent = Agent(
        name="hello-agent",
        model=MockModel(
            script=[
                ModelTurn(tool_calls=[("record_greeting", {"name": "Ada", "message": "Hello, Ada!"})]),
                ModelTurn(content="Greeted Ada."),
            ]
        ),
        instructions="Greet the person named in the input.",
        tools=[record_greeting],
    )
    goal = Goal(
        description="Ada has been greeted exactly once",
        success=ada_was_greeted,
        invariants=[no_more_than_one_greeting],
        max_steps=4,
    )
    result = Runtime(agent, state_provider=GreetingState()).run_sync(goal, input={"name": "Ada"})
    print(result.summary())
    if not result.verified:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
