"""SQLite ledger for external execution identity.

This is the SDK-side journal used by the orchestrator and by process-restart tests.
The runtime table `external_executions` (migration 0010) is the server record.
Both are project-scoped. A lookup with the wrong project id returns nothing.
"""

from __future__ import annotations

import json
import sqlite3
import uuid
from dataclasses import dataclass
from typing import Any

from .lifecycle import ExternalLifecycle


@dataclass
class ExecutionRecord:
    id: str
    project_id: str
    run_id: str
    framework: str
    adapter_version: str
    framework_version: str
    idempotency_key: str
    correlation_id: str
    dispatch_id: str
    lifecycle: ExternalLifecycle
    tenant_id: str | None = None
    parent_run_id: str | None = None
    task_id: str | None = None
    trace_id: str | None = None
    external_run_id: str | None = None
    external_thread_id: str | None = None
    capabilities: dict[str, Any] | None = None
    evidence: dict[str, Any] | None = None
    result: dict[str, Any] | None = None
    error: str | None = None
    reused: bool = False


class SqliteLedger:
    def __init__(self, path: str) -> None:
        self._conn = sqlite3.connect(path)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS external_executions (
                id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL,
                run_id TEXT NOT NULL,
                parent_run_id TEXT,
                task_id TEXT,
                tenant_id TEXT,
                framework TEXT NOT NULL,
                adapter_version TEXT NOT NULL,
                framework_version TEXT NOT NULL,
                external_run_id TEXT,
                external_thread_id TEXT,
                correlation_id TEXT NOT NULL,
                trace_id TEXT,
                idempotency_key TEXT NOT NULL,
                dispatch_id TEXT NOT NULL,
                lifecycle TEXT NOT NULL,
                capabilities TEXT NOT NULL,
                evidence TEXT NOT NULL,
                result TEXT,
                error TEXT,
                UNIQUE (project_id, idempotency_key)
            )
            """
        )
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()

    def get_by_idempotency(self, project_id: str, idempotency_key: str) -> ExecutionRecord | None:
        row = self._conn.execute(
            "SELECT * FROM external_executions WHERE project_id = ? AND idempotency_key = ?",
            (project_id, idempotency_key),
        ).fetchone()
        return _record(row) if row else None

    def get(self, project_id: str, execution_id: str) -> ExecutionRecord | None:
        row = self._conn.execute(
            "SELECT * FROM external_executions WHERE project_id = ? AND id = ?",
            (project_id, execution_id),
        ).fetchone()
        return _record(row) if row else None

    def insert(self, record: ExecutionRecord) -> ExecutionRecord:
        self._conn.execute(
            """
            INSERT INTO external_executions (
                id, project_id, run_id, parent_run_id, task_id, tenant_id, framework,
                adapter_version, framework_version, external_run_id, external_thread_id,
                correlation_id, trace_id, idempotency_key, dispatch_id, lifecycle,
                capabilities, evidence, result, error
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            _params(record),
        )
        self._conn.commit()
        stored = self.get(record.project_id, record.id)
        if stored is None:
            raise RuntimeError("insert did not persist")
        return stored

    def save(self, record: ExecutionRecord) -> ExecutionRecord:
        cursor = self._conn.execute(
            """
            UPDATE external_executions SET
                lifecycle = ?, external_run_id = ?, external_thread_id = ?,
                evidence = ?, result = ?, error = ?
            WHERE project_id = ? AND id = ?
            """,
            (
                record.lifecycle.value,
                record.external_run_id,
                record.external_thread_id,
                json.dumps(record.evidence or {}),
                json.dumps(record.result) if record.result is not None else None,
                record.error,
                record.project_id,
                record.id,
            ),
        )
        if cursor.rowcount == 0:
            raise KeyError(record.id)
        self._conn.commit()
        stored = self.get(record.project_id, record.id)
        if stored is None:
            raise KeyError(record.id)
        return stored


def new_id() -> str:
    return str(uuid.uuid4())


def _record(row: sqlite3.Row) -> ExecutionRecord:
    return ExecutionRecord(
        id=row["id"],
        project_id=row["project_id"],
        run_id=row["run_id"],
        parent_run_id=row["parent_run_id"],
        task_id=row["task_id"],
        tenant_id=row["tenant_id"],
        framework=row["framework"],
        adapter_version=row["adapter_version"],
        framework_version=row["framework_version"],
        external_run_id=row["external_run_id"],
        external_thread_id=row["external_thread_id"],
        correlation_id=row["correlation_id"],
        trace_id=row["trace_id"],
        idempotency_key=row["idempotency_key"],
        dispatch_id=row["dispatch_id"],
        lifecycle=ExternalLifecycle(row["lifecycle"]),
        capabilities=json.loads(row["capabilities"]),
        evidence=json.loads(row["evidence"]),
        result=json.loads(row["result"]) if row["result"] else None,
        error=row["error"],
    )


def _params(record: ExecutionRecord) -> tuple[Any, ...]:
    return (
        record.id,
        record.project_id,
        record.run_id,
        record.parent_run_id,
        record.task_id,
        record.tenant_id,
        record.framework,
        record.adapter_version,
        record.framework_version,
        record.external_run_id,
        record.external_thread_id,
        record.correlation_id,
        record.trace_id,
        record.idempotency_key,
        record.dispatch_id,
        record.lifecycle.value,
        json.dumps(record.capabilities or {}),
        json.dumps(record.evidence or {}),
        json.dumps(record.result) if record.result is not None else None,
        record.error,
    )
