"""Admin import, inventory, and export helpers."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

from src.storage import CodeInviterStorage


@dataclass(slots=True)
class ImportSummary:
    success: int = 0
    duplicate: int = 0
    failed: int = 0


class AdminService:
    """Core admin operations independent from AstrBot command wiring."""

    def __init__(self, storage: CodeInviterStorage, export_dir: Path, csv_encoding: str = "utf-8-sig") -> None:
        self.storage = storage
        self.export_dir = export_dir
        self.csv_encoding = csv_encoding

    def import_text_codes(self, *, pool_id: str, lines: list[str], batch: str = "") -> ImportSummary:
        summary = ImportSummary()
        for raw_line in lines:
            code = raw_line.strip()
            if not code:
                continue
            try:
                created = self.storage.add_code(pool_id=pool_id, code=code, batch=batch)
            except Exception:
                summary.failed += 1
                continue
            if created:
                summary.success += 1
            else:
                summary.duplicate += 1
        return summary

    def inventory(self, *, pool_id: str) -> dict[str, int]:
        counts = self.storage.count_codes_by_status(pool_id=pool_id)
        return {
            "unused": counts.get("unused", 0),
            "claimed": counts.get("claimed", 0),
            "disabled": counts.get("disabled", 0),
        }

    def export_claim_records(self, *, pool_id: str) -> tuple[Path, int]:
        self.export_dir.mkdir(parents=True, exist_ok=True)
        output_path = self.export_dir / f"{pool_id}-claim-records.csv"
        rows = self.storage.list_claim_records(pool_id=pool_id)
        with output_path.open("w", encoding=self.csv_encoding, newline="") as file:
            writer = csv.DictWriter(
                file,
                fieldnames=[
                    "record_id",
                    "pool_id",
                    "user_id",
                    "user_nickname",
                    "source_group_id",
                    "source_group_name",
                    "code",
                    "claimed_at",
                    "claim_index",
                    "status",
                ],
            )
            writer.writeheader()
            for row in rows:
                writer.writerow(
                    {
                        "record_id": row["id"],
                        "pool_id": row["pool_id"],
                        "user_id": row["user_id"],
                        "user_nickname": row["user_nickname"],
                        "source_group_id": row["source_group_id"],
                        "source_group_name": row["source_group_name"],
                        "code": row["code"],
                        "claimed_at": row["claimed_at"],
                        "claim_index": row["claim_index_for_user"],
                        "status": row["status"],
                    }
                )
        return output_path, len(rows)

