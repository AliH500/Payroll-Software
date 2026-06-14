"""CSV bulk-import of attendance, keyed by employee_code."""

from __future__ import annotations

import csv
import io
from collections.abc import Iterable
from dataclasses import dataclass

from apps.attendance.models import AttendanceRecord, AttendanceSheet
from apps.employees.models import Employee
from apps.tenants.models import Company

COUNT_COLUMNS = (
    "days_present",
    "days_late",
    "days_total_absent",
    "days_absent",
    "days_leave",
)
REQUIRED_COLUMNS = ("employee_code", *COUNT_COLUMNS)
ALL_COLUMNS = REQUIRED_COLUMNS


@dataclass(frozen=True)
class RowOutcome:
    line_number: int
    ok: bool
    message: str
    employee_code: str | None = None


def _parse_count(row: dict[str, str], column: str) -> int:
    raw = (row.get(column) or "").strip()
    if not raw:
        return 0
    try:
        value = int(raw)
    except ValueError as exc:
        raise ValueError(f"invalid number {raw!r} in {column}") from exc
    if value < 0:
        raise ValueError(f"{column} cannot be negative")
    return value


def import_attendance(sheet: AttendanceSheet, csv_data: bytes | str) -> list[RowOutcome]:
    """Parse and ingest an attendance CSV into the given sheet.

    Required headers: employee_code plus the five day-count columns. Each row is
    matched to an employee by employee_code within the sheet's company; an
    existing record for that employee is updated, otherwise one is created.
    """
    if isinstance(csv_data, bytes):
        text = csv_data.decode("utf-8-sig")
    else:
        text = csv_data

    reader = csv.DictReader(io.StringIO(text))
    headers = reader.fieldnames or []
    missing = [c for c in REQUIRED_COLUMNS if c not in headers]
    if missing:
        return [RowOutcome(
            line_number=1, ok=False,
            message=f"Missing required column(s): {', '.join(missing)}",
        )]

    seen_codes: set[str] = set()
    outcomes: list[RowOutcome] = []
    for line_number, row in enumerate(reader, start=2):
        code = (row.get("employee_code") or "").strip()
        try:
            _ingest_row(sheet, sheet.company, code, row, seen_codes)
        except ValueError as exc:
            outcomes.append(RowOutcome(
                line_number=line_number, ok=False, message=str(exc), employee_code=code or None,
            ))
            continue
        outcomes.append(RowOutcome(
            line_number=line_number, ok=True,
            message=f"Recorded attendance for {code}", employee_code=code,
        ))
    return outcomes


def _ingest_row(
    sheet: AttendanceSheet, company: Company, code: str,
    row: dict[str, str], seen_codes: set[str],
) -> None:
    if not code:
        raise ValueError("employee_code is required")
    if code in seen_codes:
        raise ValueError(f"duplicate employee_code {code!r} in this file")
    try:
        # tenant-bypass-allowed: lookup is explicitly scoped to the sheet's company
        employee = Employee.all_tenants.get(company=company, employee_code=code)
    except Employee.DoesNotExist as exc:
        raise ValueError(f"no employee with code {code!r} in this company") from exc

    counts = {column: _parse_count(row, column) for column in COUNT_COLUMNS}
    if counts["days_total_absent"] != counts["days_absent"] + counts["days_leave"]:
        raise ValueError(
            "days_total_absent must equal days_absent + days_leave "
            f"({counts['days_absent']} + {counts['days_leave']})"
        )
    seen_codes.add(code)
    AttendanceRecord.all_tenants.update_or_create(
        sheet=sheet, employee=employee,
        defaults={"company": company, **counts},
    )


def csv_template_headers() -> Iterable[str]:
    return ALL_COLUMNS
