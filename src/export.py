"""CSV 내보내기."""

from __future__ import annotations

import csv
from pathlib import Path

from src.storage import RankingRecord, Storage


def export_rankings_to_csv(
    storage: Storage,
    output_path: str | Path,
    date_from: str | None = None,
    date_to: str | None = None,
) -> int:
    records = storage.export_rankings(date_from=date_from, date_to=date_to)
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "collected_at",
                "business_id",
                "business_name",
                "keyword",
                "rank",
                "found",
                "result_count",
                "error",
            ]
        )
        for record in records:
            writer.writerow(
                [
                    record.collected_at,
                    record.business_id,
                    record.business_name,
                    record.keyword,
                    record.rank if record.rank is not None else "",
                    "Y" if record.found else "N",
                    record.result_count,
                    record.error or "",
                ]
            )

    return len(records)
