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


@dataclass(slots=True)
class ClaimRecordSummary:
    record_id: int
    pool_id: str
    user_id: str
    user_nickname: str
    source_group_id: str
    source_group_name: str
    code: str
    batch: str
    claimed_at: str
    claim_index: int
    status: str


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

    def import_csv_codes(self, *, pool_id: str, csv_path: Path, batch: str = "") -> ImportSummary:
        summary = ImportSummary()
        with csv_path.open("r", encoding=self.csv_encoding, newline="") as file:
            reader = csv.DictReader(file)
            for row in reader:
                code = str(row.get("code", "")).strip()
                if not code:
                    summary.failed += 1
                    continue
                code_batch = str(row.get("batch", "")).strip() or batch
                remark = str(row.get("remark", "")).strip()
                try:
                    created = self.storage.add_code(
                        pool_id=pool_id,
                        code=code,
                        batch=code_batch,
                        remark=remark,
                    )
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

    def query_user_claims(self, *, user_id: str, pool_id: str = "") -> list[ClaimRecordSummary]:
        rows = self.storage.list_claim_records_by_user(user_id=user_id, pool_id=pool_id)
        return [self._claim_record_summary(row) for row in rows]

    def block_user(self, *, user_id: str, reason: str = "", created_by: str = "") -> None:
        self.storage.upsert_blocked_user(user_id=user_id, reason=reason, created_by=created_by)

    def unblock_user(self, *, user_id: str) -> None:
        self.storage.remove_blocked_user(user_id=user_id)

    def export_claim_records(
        self,
        *,
        pool_id: str,
        pool_name: str = "",
        claimed_after: str = "",
        claimed_before: str = "",
    ) -> tuple[Path, int]:
        self.export_dir.mkdir(parents=True, exist_ok=True)
        output_path = self.export_dir / f"{pool_id}-claim-records.csv"
        rows = self.storage.list_claim_records(
            pool_id=pool_id,
            claimed_after=claimed_after,
            claimed_before=claimed_before,
        )
        with output_path.open("w", encoding=self.csv_encoding, newline="") as file:
            writer = csv.DictWriter(
                file,
                fieldnames=[
                    "record_id",
                    "pool_id",
                    "pool_name",
                    "user_id",
                    "user_nickname",
                    "source_group_id",
                    "source_group_name",
                    "code",
                    "batch",
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
                        "pool_name": pool_name,
                        "user_id": row["user_id"],
                        "user_nickname": row["user_nickname"],
                        "source_group_id": row["source_group_id"],
                        "source_group_name": row["source_group_name"],
                        "code": row["code"],
                        "batch": row["batch"],
                        "claimed_at": row["claimed_at"],
                        "claim_index": row["claim_index_for_user"],
                        "status": row["status"],
                    }
                )
        return output_path, len(rows)

    def _claim_record_summary(self, row) -> ClaimRecordSummary:
        return ClaimRecordSummary(
            record_id=int(row["id"]),
            pool_id=str(row["pool_id"]),
            user_id=str(row["user_id"]),
            user_nickname=str(row["user_nickname"]),
            source_group_id=str(row["source_group_id"]),
            source_group_name=str(row["source_group_name"]),
            code=str(row["code"]),
            batch=str(row["batch"] or ""),
            claimed_at=str(row["claimed_at"]),
            claim_index=int(row["claim_index_for_user"]),
            status=str(row["status"]),
        )
