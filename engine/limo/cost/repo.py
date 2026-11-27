from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from limo.cost.models import TokenCounts
from limo.cost.pricing import PriceMicros
from limo.llm.ports import LlmUsage
from limo.store.db import connect


class PriceRepo:
    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path

    def get(self, model: str) -> PriceMicros | None:
        conn = connect(self._db_path)
        try:
            row = conn.execute(
                "SELECT input_micros, output_micros, cache_read_micros, cache_write_micros"
                " FROM prices WHERE model = ?",
                (model,),
            ).fetchone()
        finally:
            conn.close()
        if row is None:
            return None
        return PriceMicros(row[0], row[1], row[2], row[3])

    def set(self, model: str, price: PriceMicros) -> None:
        conn = connect(self._db_path)
        try:
            conn.execute(
                "INSERT INTO prices (model, input_micros, output_micros, cache_read_micros,"
                " cache_write_micros, updated_at) VALUES (?, ?, ?, ?, ?, ?)"
                " ON CONFLICT(model) DO UPDATE SET input_micros = excluded.input_micros,"
                " output_micros = excluded.output_micros, cache_read_micros = excluded.cache_read_micros,"
                " cache_write_micros = excluded.cache_write_micros, updated_at = excluded.updated_at",
                (
                    model,
                    price.input,
                    price.output,
                    price.cache_read,
                    price.cache_write,
                    datetime.now(UTC).isoformat(),
                ),
            )
            conn.commit()
        finally:
            conn.close()

    def list(self) -> list[tuple[str, PriceMicros]]:
        conn = connect(self._db_path)
        try:
            rows = conn.execute(
                "SELECT model, input_micros, output_micros, cache_read_micros, cache_write_micros"
                " FROM prices ORDER BY model"
            ).fetchall()
        finally:
            conn.close()
        return [(row[0], PriceMicros(row[1], row[2], row[3], row[4])) for row in rows]


@dataclass(frozen=True)
class UsageRow:
    run_id: str
    project_id: str
    agent: str
    feature: str
    ticket: str | None
    seq: int
    model: str
    usage: LlmUsage
    cost_micros: int
    priced: bool


class UsageRepo:
    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path

    def add(self, row: UsageRow) -> None:
        conn = connect(self._db_path)
        try:
            conn.execute(
                "INSERT INTO usage (run_id, project_id, agent, feature, ticket, seq, model, input_tokens,"
                " output_tokens, cache_read_tokens, cache_write_tokens, cost_micros, priced, created_at)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    row.run_id,
                    row.project_id,
                    row.agent,
                    row.feature,
                    row.ticket,
                    row.seq,
                    row.model,
                    row.usage.input_tokens,
                    row.usage.output_tokens,
                    row.usage.cache_read_tokens,
                    row.usage.cache_write_tokens,
                    row.cost_micros,
                    int(row.priced),
                    datetime.now(UTC).isoformat(),
                ),
            )
            conn.commit()
        finally:
            conn.close()

    def run_sum(self, run_id: str) -> tuple[TokenCounts, int]:
        conn = connect(self._db_path)
        try:
            row = conn.execute(
                "SELECT COALESCE(SUM(input_tokens), 0), COALESCE(SUM(output_tokens), 0),"
                " COALESCE(SUM(cache_read_tokens), 0), COALESCE(SUM(cache_write_tokens), 0),"
                " COALESCE(SUM(cost_micros), 0) FROM usage WHERE run_id = ?",
                (run_id,),
            ).fetchone()
        finally:
            conn.close()
        tokens = TokenCounts(input=row[0], output=row[1], cache_read=row[2], cache_write=row[3])
        return tokens, row[4]

    def project_rows(self, project_id: str) -> list[tuple[str, str | None, int]]:
        conn = connect(self._db_path)
        try:
            rows = conn.execute(
                "SELECT agent, ticket, SUM(cost_micros) FROM usage WHERE project_id = ?"
                " GROUP BY agent, ticket ORDER BY agent, ticket",
                (project_id,),
            ).fetchall()
        finally:
            conn.close()
        return [(row[0], row[1], row[2]) for row in rows]

    def ticket_spent(self, project_id: str, feature: str, ticket: str) -> int:
        conn = connect(self._db_path)
        try:
            row = conn.execute(
                "SELECT COALESCE(SUM(cost_micros), 0) FROM usage"
                " WHERE project_id = ? AND feature = ? AND ticket = ?",
                (project_id, feature, ticket),
            ).fetchone()
        finally:
            conn.close()
        return int(row[0])

    def agent_spent(self, project_id: str, feature: str, ticket: str) -> dict[str, int]:
        conn = connect(self._db_path)
        try:
            rows = conn.execute(
                "SELECT agent, COALESCE(SUM(cost_micros), 0) FROM usage"
                " WHERE project_id = ? AND feature = ? AND ticket = ? GROUP BY agent",
                (project_id, feature, ticket),
            ).fetchall()
        finally:
            conn.close()
        return {str(r[0]): int(r[1]) for r in rows}
