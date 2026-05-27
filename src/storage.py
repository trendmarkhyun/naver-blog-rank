"""SQLite 저장소."""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterator
from zoneinfo import ZoneInfo

KST = ZoneInfo("Asia/Seoul")


@dataclass
class RankingRecord:
    collected_at: str
    business_id: str
    business_name: str
    keyword: str
    rank: int | None
    found: bool
    result_count: int
    error: str | None


class Storage:
    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS businesses (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    place_id TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS keywords (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    text TEXT NOT NULL UNIQUE
                );

                CREATE TABLE IF NOT EXISTS rankings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    collected_at TEXT NOT NULL,
                    business_id TEXT NOT NULL,
                    keyword_id INTEGER NOT NULL,
                    rank INTEGER,
                    found INTEGER NOT NULL,
                    result_count INTEGER NOT NULL DEFAULT 0,
                    error TEXT,
                    FOREIGN KEY (business_id) REFERENCES businesses(id),
                    FOREIGN KEY (keyword_id) REFERENCES keywords(id)
                );

                CREATE INDEX IF NOT EXISTS idx_rankings_collected_at
                    ON rankings(collected_at);
                CREATE INDEX IF NOT EXISTS idx_rankings_business_keyword
                    ON rankings(business_id, keyword_id, collected_at);
                """
            )

    def sync_businesses(self, businesses: list) -> None:
        with self._connect() as conn:
            for biz in businesses:
                conn.execute(
                    """
                    INSERT INTO businesses (id, name, place_id)
                    VALUES (?, ?, ?)
                    ON CONFLICT(id) DO UPDATE SET
                        name = excluded.name,
                        place_id = excluded.place_id
                    """,
                    (biz.id, biz.name, biz.place_id),
                )

    def get_or_create_keyword_id(self, keyword: str) -> int:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT id FROM keywords WHERE text = ?", (keyword,)
            ).fetchone()
            if row:
                return int(row["id"])

            cursor = conn.execute(
                "INSERT INTO keywords (text) VALUES (?)", (keyword,)
            )
            return int(cursor.lastrowid)

    @staticmethod
    def now_kst_iso() -> str:
        return datetime.now(KST).replace(microsecond=0).isoformat()

    def save_ranking(
        self,
        *,
        collected_at: str,
        business_id: str,
        keyword: str,
        rank: int | None,
        found: bool,
        result_count: int,
        error: str | None = None,
    ) -> None:
        keyword_id = self.get_or_create_keyword_id(keyword)
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO rankings (
                    collected_at, business_id, keyword_id,
                    rank, found, result_count, error
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    collected_at,
                    business_id,
                    keyword_id,
                    rank,
                    1 if found else 0,
                    result_count,
                    error,
                ),
            )

    def export_rankings(
        self,
        date_from: str | None = None,
        date_to: str | None = None,
    ) -> list[RankingRecord]:
        query = """
            SELECT
                r.collected_at,
                b.id AS business_id,
                b.name AS business_name,
                k.text AS keyword,
                r.rank,
                r.found,
                r.result_count,
                r.error
            FROM rankings r
            JOIN businesses b ON b.id = r.business_id
            JOIN keywords k ON k.id = r.keyword_id
            WHERE 1=1
        """
        params: list[str] = []

        if date_from:
            query += " AND r.collected_at >= ?"
            params.append(f"{date_from}T00:00:00+09:00")
        if date_to:
            query += " AND r.collected_at <= ?"
            params.append(f"{date_to}T23:59:59+09:00")

        query += " ORDER BY r.collected_at DESC, b.id, k.text"

        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()

        return [
            RankingRecord(
                collected_at=row["collected_at"],
                business_id=row["business_id"],
                business_name=row["business_name"],
                keyword=row["keyword"],
                rank=row["rank"],
                found=bool(row["found"]),
                result_count=row["result_count"],
                error=row["error"],
            )
            for row in rows
        ]
