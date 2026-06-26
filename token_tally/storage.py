# Token Tally - AI Token Usage Tracker & Cost Analyzer
# SPDX-License-Identifier: MIT

"""Storage engine for token usage entries."""

from __future__ import annotations

import json
import sqlite3
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from .models import CostSummary, Provider, UsageEntry


class StorageError(Exception):
    """Base exception for storage operations."""


class DatabaseError(StorageError):
    """Raised on database operation failures."""


class TokenStorage:
    """SQLite-backed storage for token usage entries."""

    def __init__(self, db_path: Optional[str] = None):
        if db_path is None:
            db_path = str(Path.home() / ".token_tally" / "tally.db")
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._conn: Optional[sqlite3.Connection] = None
        self._initialize()

    def _get_conn(self) -> sqlite3.Connection:
        """Get or create database connection."""
        if self._conn is None:
            self._conn = sqlite3.connect(str(self.db_path))
            self._conn.row_factory = sqlite3.Row
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA foreign_keys=ON")
        return self._conn

    def _initialize(self) -> None:
        """Create tables if they don't exist."""
        conn = self._get_conn()
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS usage_entries (
                id TEXT PRIMARY KEY,
                timestamp TEXT NOT NULL,
                project TEXT NOT NULL DEFAULT 'default',
                session TEXT NOT NULL DEFAULT 'default',
                model TEXT NOT NULL,
                provider TEXT NOT NULL DEFAULT 'openai',
                input_tokens INTEGER NOT NULL CHECK (input_tokens >= 0),
                output_tokens INTEGER NOT NULL CHECK (output_tokens >= 0),
                total_tokens INTEGER NOT NULL CHECK (total_tokens >= 0),
                estimated_cost_usd REAL NOT NULL DEFAULT 0.0 CHECK (estimated_cost_usd >= 0.0),
                prompt_template TEXT NOT NULL DEFAULT '',
                task_type TEXT NOT NULL DEFAULT 'general',
                duration_seconds REAL NOT NULL DEFAULT 0.0 CHECK (duration_seconds >= 0.0),
                metadata TEXT NOT NULL DEFAULT '{}'
            );
            CREATE INDEX IF NOT EXISTS idx_usage_project ON usage_entries(project);
            CREATE INDEX IF NOT EXISTS idx_usage_timestamp ON usage_entries(timestamp);
            CREATE INDEX IF NOT EXISTS idx_usage_model ON usage_entries(model);
            CREATE INDEX IF NOT EXISTS idx_usage_session ON usage_entries(session);
            CREATE TABLE IF NOT EXISTS models (
                name TEXT PRIMARY KEY,
                provider TEXT NOT NULL,
                input_price_per_million REAL NOT NULL,
                output_price_per_million REAL NOT NULL,
                max_context INTEGER NOT NULL,
                supports_images INTEGER NOT NULL DEFAULT 0,
                supports_tools INTEGER NOT NULL DEFAULT 0
            );
        """)
        conn.commit()

    def add_entry(self, entry: UsageEntry) -> str:
        """Add a usage entry to the database."""
        with self._lock:
            conn = self._get_conn()
            try:
                conn.execute(
                    """INSERT OR REPLACE INTO usage_entries
                       (id, timestamp, project, session, model, provider,
                        input_tokens, output_tokens, total_tokens,
                        estimated_cost_usd, prompt_template, task_type,
                        duration_seconds, metadata)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        entry.id, entry.timestamp.isoformat(), entry.project,
                        entry.session, entry.model, entry.provider.value,
                        entry.input_tokens, entry.output_tokens, entry.total_tokens,
                        entry.estimated_cost_usd, entry.prompt_template,
                        entry.task_type, entry.duration_seconds,
                        json.dumps(entry.metadata),
                    ),
                )
                conn.commit()
                return entry.id
            except sqlite3.Error as e:
                raise DatabaseError(f"Failed to add entry: {e}") from e

    def get_entries(
        self,
        project: Optional[str] = None,
        session: Optional[str] = None,
        provider: Optional[Provider] = None,
        model: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 1000,
        offset: int = 0,
        sort_order: str = "desc",
    ) -> list[UsageEntry]:
        """Query usage entries with optional filters."""
        conditions: list[str] = []
        params: list = []

        if project:
            conditions.append("project = ?")
            params.append(project)
        if session:
            conditions.append("session = ?")
            params.append(session)
        if provider:
            conditions.append("provider = ?")
            params.append(provider.value)
        if model:
            conditions.append("model = ?")
            params.append(model)
        if start_date:
            conditions.append("timestamp >= ?")
            params.append(start_date.isoformat())
        if end_date:
            conditions.append("timestamp <= ?")
            params.append(end_date.isoformat())

        where_clause = "WHERE " + " AND ".join(conditions) if conditions else ""
        order = "ASC" if sort_order == "asc" else "DESC"

        with self._lock:
            conn = self._get_conn()
            try:
                cursor = conn.execute(
                    f"""SELECT * FROM usage_entries {where_clause}
                        ORDER BY timestamp {order} LIMIT ? OFFSET ?""",
                    params + [limit, offset],
                )
                return [self._row_to_entry(dict(row)) for row in cursor.fetchall()]
            except sqlite3.Error as e:
                raise DatabaseError(f"Failed to query entries: {e}") from e

    def get_all_projects(self) -> list[str]:
        """Get list of all projects."""
        with self._lock:
            conn = self._get_conn()
            try:
                return [row["project"] for row in conn.execute(
                    "SELECT DISTINCT project FROM usage_entries ORDER BY project"
                ).fetchall()]
            except sqlite3.Error as e:
                raise DatabaseError(f"Failed to get projects: {e}") from e

    def get_all_models(self) -> list[str]:
        """Get list of all models."""
        with self._lock:
            conn = self._get_conn()
            try:
                return [row["model"] for row in conn.execute(
                    "SELECT DISTINCT model FROM usage_entries ORDER BY model"
                ).fetchall()]
            except sqlite3.Error as e:
                raise DatabaseError(f"Failed to get models: {e}") from e

    def get_all_sessions(self, project: str = "default") -> list[str]:
        """Get list of sessions for a project."""
        with self._lock:
            conn = self._get_conn()
            try:
                return [row["session"] for row in conn.execute(
                    "SELECT DISTINCT session FROM usage_entries WHERE project = ? ORDER BY session",
                    (project,),
                ).fetchall()]
            except sqlite3.Error as e:
                raise DatabaseError(f"Failed to get sessions: {e}") from e

    def get_cost_summary(
        self,
        project: Optional[str] = None,
        provider: Optional[Provider] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> CostSummary:
        """Get aggregated cost summary with optional filters."""
        conditions: list[str] = []
        params: list = []

        if project:
            conditions.append("project = ?")
            params.append(project)
        if provider:
            conditions.append("provider = ?")
            params.append(provider.value)
        if start_date:
            conditions.append("timestamp >= ?")
            params.append(start_date.isoformat())
        if end_date:
            conditions.append("timestamp <= ?")
            params.append(end_date.isoformat())

        where_clause = "WHERE " + " AND ".join(conditions) if conditions else ""
        summary_target = project if project else "all"

        with self._lock:
            conn = self._get_conn()
            try:
                cursor = conn.execute(
                    f"""SELECT
                            COALESCE(SUM(input_tokens), 0) as total_input,
                            COALESCE(SUM(output_tokens), 0) as total_output,
                            COALESCE(SUM(total_tokens), 0) as total,
                            COALESCE(SUM(estimated_cost_usd), 0.0) as total_cost,
                            COUNT(*) as entry_count
                         FROM usage_entries {where_clause}""",
                    params,
                )
                row = dict(cursor.fetchone())

                model_breakdown = {}
                for mrow in conn.execute(
                    f"""SELECT model, SUM(total_tokens) as tokens,
                            SUM(estimated_cost_usd) as cost
                         FROM usage_entries {where_clause}
                         GROUP BY model ORDER BY cost DESC""",
                    params,
                ).fetchall():
                    model_breakdown[mrow["model"]] = {"tokens": mrow["tokens"], "cost": round(mrow["cost"], 8)}

                provider_breakdown = {}
                for prow in conn.execute(
                    f"""SELECT provider, SUM(total_tokens) as tokens,
                            SUM(estimated_cost_usd) as cost
                         FROM usage_entries {where_clause}
                         GROUP BY provider ORDER BY cost DESC""",
                    params,
                ).fetchall():
                    provider_breakdown[prow["provider"]] = {"tokens": prow["tokens"], "cost": round(prow["cost"], 8)}

                entry_count = row["entry_count"]
                return CostSummary(
                    project=summary_target,
                    total_input_tokens=row["total_input"],
                    total_output_tokens=row["total_output"],
                    total_tokens=row["total"],
                    total_cost_usd=row["total_cost"],
                    entry_count=entry_count,
                    average_cost_per_request=round(row["total_cost"] / entry_count, 8) if entry_count > 0 else 0.0,
                    average_tokens_per_request=row["total"] / entry_count if entry_count > 0 else 0.0,
                    model_breakdown=model_breakdown,
                    provider_breakdown=provider_breakdown,
                )
            except sqlite3.Error as e:
                raise DatabaseError(f"Failed to compute summary: {e}") from e

    def clear_entries(self, project: Optional[str] = None) -> int:
        """Remove entries, optionally filtered by project."""
        with self._lock:
            conn = self._get_conn()
            try:
                if project:
                    cursor = conn.execute("DELETE FROM usage_entries WHERE project = ?", (project,))
                else:
                    cursor = conn.execute("DELETE FROM usage_entries")
                conn.commit()
                return cursor.rowcount
            except sqlite3.Error as e:
                raise DatabaseError(f"Failed to clear entries: {e}") from e

    def get_daily_stats(self, days: int = 30) -> list[dict]:
        """Get daily token usage and cost stats for the last N days."""
        with self._lock:
            conn = self._get_conn()
            try:
                cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
                cursor = conn.execute(
                    """SELECT DATE(timestamp) as day,
                            SUM(total_tokens) as tokens,
                            SUM(input_tokens) as input_tokens,
                            SUM(output_tokens) as output_tokens,
                            SUM(estimated_cost_usd) as cost,
                            COUNT(*) as requests
                         FROM usage_entries WHERE timestamp >= ?
                         GROUP BY DATE(timestamp) ORDER BY day DESC LIMIT ?""",
                    (cutoff, days),
                )
                return [{
                    "day": r["day"], "tokens": r["tokens"],
                    "input_tokens": r["input_tokens"],
                    "output_tokens": r["output_tokens"],
                    "cost": round(r["cost"], 8),
                    "requests": r["requests"],
                } for r in cursor.fetchall()]
            except sqlite3.Error as e:
                raise DatabaseError(f"Failed to get daily stats: {e}") from e

    @staticmethod
    def _row_to_entry(row: dict) -> UsageEntry:
        """Convert a database row to a UsageEntry."""
        row["provider"] = Provider(row["provider"])
        row["timestamp"] = datetime.fromisoformat(row["timestamp"])
        if isinstance(row.get("metadata"), str):
            row["metadata"] = json.loads(row["metadata"])
        return UsageEntry(**row)

    def close(self) -> None:
        """Close the database connection."""
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
