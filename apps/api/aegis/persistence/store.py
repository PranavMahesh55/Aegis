import json
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from aegis.domain.enums import IncidentState, SourceSystem
from aegis.domain.models import AgentRun, AuditEvent, RunStep


def utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


class AegisStore:
    def __init__(self, path: Path, *, prime_blocked: bool = True) -> None:
        self.path = path
        self.prime_blocked = prime_blocked
        path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    @contextmanager
    def connection(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.path, timeout=10)
        connection.row_factory = sqlite3.Row
        try:
            yield connection
            connection.commit()
        finally:
            connection.close()

    def _initialize(self) -> None:
        with self.connection() as connection:
            connection.executescript(
                """
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS demo_state (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    incident_state TEXT NOT NULL,
                    version INTEGER NOT NULL,
                    active_source TEXT NOT NULL,
                    source_approved INTEGER NOT NULL,
                    remediation_applied INTEGER NOT NULL,
                    datahub_incident_urn TEXT,
                    writeback_state TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS audit_events (
                    id TEXT PRIMARY KEY,
                    event_type TEXT NOT NULL,
                    actor TEXT NOT NULL,
                    occurred_at TEXT NOT NULL,
                    detail TEXT NOT NULL,
                    source_system TEXT NOT NULL,
                    payload TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS evaluations (
                    id TEXT PRIMARY KEY,
                    evaluated_at TEXT NOT NULL,
                    payload TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS attestations (
                    id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    payload TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS regression_runs (
                    id TEXT PRIMARY KEY,
                    completed_at TEXT NOT NULL,
                    payload TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS tool_receipts (
                    id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    payload TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS graph_snapshots (
                    id TEXT PRIMARY KEY,
                    captured_at TEXT NOT NULL,
                    content_hash TEXT NOT NULL,
                    payload TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS agent_runs (
                    id TEXT PRIMARY KEY,
                    pipeline_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    payload TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_agent_runs_pipeline_updated
                    ON agent_runs (pipeline_id, updated_at DESC);
                CREATE TABLE IF NOT EXISTS run_steps (
                    id TEXT PRIMARY KEY,
                    run_id TEXT NOT NULL,
                    sequence INTEGER NOT NULL,
                    occurred_at TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    UNIQUE (run_id, sequence),
                    FOREIGN KEY (run_id) REFERENCES agent_runs(id) ON DELETE CASCADE
                );
                CREATE TABLE IF NOT EXISTS datahub_event_inbox (
                    event_id TEXT PRIMARY KEY,
                    received_at TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    entity_urn TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    processed_at TEXT
                );
                """
            )
            row = connection.execute("SELECT id FROM demo_state WHERE id = 1").fetchone()
            if row is None:
                self._seed_state(connection, blocked=self.prime_blocked)

    def _seed_state(self, connection: sqlite3.Connection, *, blocked: bool) -> None:
        state = IncidentState.BLOCKED if blocked else IncidentState.HEALTHY
        connection.execute(
            """
            INSERT OR REPLACE INTO demo_state
            (id, incident_state, version, active_source, source_approved,
             remediation_applied, datahub_incident_urn, writeback_state, updated_at)
            VALUES (1, ?, ?, ?, ?, 0, ?, ?, ?)
            """,
            (
                state.value,
                2 if blocked else 0,
                "refund-policy-q4-draft.md" if blocked else "refund-policy-v12.md",
                0 if blocked else 1,
                "urn:li:incident:aegis-4821" if blocked else None,
                "ACTIVE" if blocked else "NOT_CREATED",
                utc_now(),
            ),
        )

    def get_state(self) -> dict[str, Any]:
        with self.connection() as connection:
            row = connection.execute("SELECT * FROM demo_state WHERE id = 1").fetchone()
        if row is None:
            raise RuntimeError("Aegis state has not been initialized")
        return dict(row)

    def update_state(self, **updates: Any) -> dict[str, Any]:
        allowed = {
            "incident_state",
            "version",
            "active_source",
            "source_approved",
            "remediation_applied",
            "datahub_incident_urn",
            "writeback_state",
        }
        unknown = set(updates) - allowed
        if unknown:
            raise ValueError(f"Unknown state fields: {sorted(unknown)}")
        updates["updated_at"] = utc_now()
        assignments = ", ".join(f"{key} = ?" for key in updates)
        values = list(updates.values())
        with self.connection() as connection:
            connection.execute(
                f"UPDATE demo_state SET {assignments} WHERE id = 1",  # noqa: S608
                values,
            )
        return self.get_state()

    def reset(self, *, blocked: bool = False) -> dict[str, Any]:
        with self.connection() as connection:
            for table in (
                "audit_events",
                "evaluations",
                "attestations",
                "regression_runs",
                "tool_receipts",
                "graph_snapshots",
                "run_steps",
                "agent_runs",
                "datahub_event_inbox",
            ):
                connection.execute(f"DELETE FROM {table}")  # noqa: S608
            self._seed_state(connection, blocked=blocked)
        self.append_audit(
            "DEMO_PRIMED" if blocked else "DEMO_RESET",
            "Blocked demonstration state restored" if blocked else "Healthy baseline restored",
        )
        return self.get_state()

    def append_audit(
        self,
        event_type: str,
        detail: str,
        *,
        actor: str = "aegis-demo-operator",
        source_system: SourceSystem = SourceSystem.AEGIS,
        payload: dict[str, Any] | None = None,
    ) -> AuditEvent:
        event = AuditEvent(
            id=f"evt-{uuid4().hex[:12]}",
            type=event_type,
            actor=actor,
            occurredAt=utc_now(),
            detail=detail,
            sourceSystem=source_system,
        )
        with self.connection() as connection:
            connection.execute(
                "INSERT INTO audit_events VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    event.id,
                    event.type,
                    event.actor,
                    event.occurredAt,
                    event.detail,
                    event.sourceSystem.value,
                    json.dumps(payload or {}, sort_keys=True),
                ),
            )
        return event

    def list_audit(self) -> list[AuditEvent]:
        with self.connection() as connection:
            rows = connection.execute(
                "SELECT * FROM audit_events ORDER BY occurred_at DESC"
            ).fetchall()
        return [
            AuditEvent(
                id=row["id"],
                type=row["event_type"],
                actor=row["actor"],
                occurredAt=row["occurred_at"],
                detail=row["detail"],
                sourceSystem=SourceSystem(row["source_system"]),
            )
            for row in rows
        ]

    def save_json(self, table: str, record_id: str, timestamp_field: str, payload: Any) -> None:
        allowed = {
            "evaluations": "evaluated_at",
            "attestations": "created_at",
            "regression_runs": "completed_at",
            "tool_receipts": "created_at",
        }
        if allowed.get(table) != timestamp_field:
            raise ValueError("Unsupported JSON table")
        timestamp = utc_now()
        serialized = (
            payload.model_dump_json()
            if hasattr(payload, "model_dump_json")
            else json.dumps(payload)
        )
        with self.connection() as connection:
            connection.execute(
                f"INSERT OR REPLACE INTO {table} (id, {timestamp_field}, payload) VALUES (?, ?, ?)",  # noqa: S608
                (record_id, timestamp, serialized),
            )

    def latest_json(self, table: str) -> dict[str, Any] | None:
        order_fields = {
            "evaluations": "evaluated_at",
            "attestations": "created_at",
            "regression_runs": "completed_at",
            "tool_receipts": "created_at",
        }
        order = order_fields.get(table)
        if order is None:
            raise ValueError("Unsupported JSON table")
        with self.connection() as connection:
            row = connection.execute(
                f"SELECT payload FROM {table} ORDER BY {order} DESC LIMIT 1"  # noqa: S608
            ).fetchone()
        return json.loads(row["payload"]) if row else None

    def save_run(self, run: AgentRun) -> AgentRun:
        serialized = run.model_dump_json()
        with self.connection() as connection:
            connection.execute(
                """
                INSERT INTO agent_runs (id, pipeline_id, status, created_at, updated_at, payload)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                  status=excluded.status, updated_at=excluded.updated_at, payload=excluded.payload
                """,
                (
                    run.id,
                    run.pipelineId,
                    run.status.value,
                    run.startedAt,
                    run.updatedAt,
                    serialized,
                ),
            )
        return run

    def get_run(self, run_id: str, *, include_steps: bool = True) -> AgentRun | None:
        with self.connection() as connection:
            row = connection.execute(
                "SELECT payload FROM agent_runs WHERE id = ?", (run_id,)
            ).fetchone()
        if row is None:
            return None
        run = AgentRun.model_validate_json(row["payload"])
        if include_steps:
            run.steps = self.list_run_steps(run_id)
        return run

    def latest_run(self, pipeline_id: str) -> AgentRun | None:
        with self.connection() as connection:
            row = connection.execute(
                "SELECT id FROM agent_runs WHERE pipeline_id = ? ORDER BY updated_at DESC LIMIT 1",
                (pipeline_id,),
            ).fetchone()
        return self.get_run(row["id"]) if row else None

    def append_run_step(self, step: RunStep) -> RunStep:
        with self.connection() as connection:
            connection.execute(
                """INSERT INTO run_steps
                   (id, run_id, sequence, occurred_at, payload) VALUES (?, ?, ?, ?, ?)""",
                (step.id, step.runId, step.sequence, step.occurredAt, step.model_dump_json()),
            )
        return step

    def list_run_steps(self, run_id: str, *, after_sequence: int = 0) -> list[RunStep]:
        with self.connection() as connection:
            rows = connection.execute(
                "SELECT payload FROM run_steps WHERE run_id = ? AND sequence > ? ORDER BY sequence",
                (run_id, after_sequence),
            ).fetchall()
        return [RunStep.model_validate_json(row["payload"]) for row in rows]

    def receive_datahub_event(
        self, event_id: str, event_type: str, entity_urn: str, payload: dict[str, Any]
    ) -> bool:
        with self.connection() as connection:
            cursor = connection.execute(
                """
                INSERT OR IGNORE INTO datahub_event_inbox
                (event_id, received_at, event_type, entity_urn, payload)
                VALUES (?, ?, ?, ?, ?)
                """,
                (event_id, utc_now(), event_type, entity_urn, json.dumps(payload, sort_keys=True)),
            )
        return cursor.rowcount == 1
