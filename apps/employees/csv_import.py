"""CSV bulk-import of Employee rows."""

from __future__ import annotations

import csv
import io
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation

from apps.employees.models import Employee
from apps.tenants.models import Company

REQUIRED_COLUMNS = (
    "employee_code",
    "first_name",
    "last_name",
    "salary",
    "hire_date",
)
OPTIONAL_COLUMNS = (
    "work_email",
    "phone",
    "national_id",
    "passport_number",
    "passport_expiry",
    "visa_number",
    "visa_expiry",
    "bank_account_number",
    "conveyance_allowance",
    "attendance_allowance",
    "performance_bonus",
    "is_active",
)
ALL_COLUMNS = REQUIRED_COLUMNS + OPTIONAL_COLUMNS


@dataclass(frozen=True)
class RowOutcome:
    line_number: int
    ok: bool
    message: str
    employee_id: int | None = None


def _parse_date(s: str) -> date | None:
    s = s.strip()
    if not s:
        return None
    try:
        return date.fromisoformat(s)
    except ValueError as e:
        raise ValueError(f"invalid date {s!r} (use YYYY-MM-DD)") from e


def _parse_decimal(s: str) -> Decimal | None:
    s = s.strip()
    if not s:
        return None
    try:
        return Decimal(s)
    except InvalidOperation as e:
        raise ValueError(f"invalid number {s!r}") from e


def _parse_bool(s: str) -> bool:
    return s.strip().lower() in {"1", "true", "yes", "y", "t"}


def import_employees(company: Company, csv_data: bytes | str) -> list[RowOutcome]:
    """Parse and ingest CSV.

    Required headers: employee_code, first_name, last_name, salary, hire_date.
    Conveyance allowance, attendance allowance, and performance bonus are optional
    and default to zero when absent or blank.
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
        try:
            employee = _row_to_employee(company, row, seen_codes)
            outcomes.append(RowOutcome(
                line_number=line_number, ok=True,
                message=f"Imported {employee.full_name} ({employee.employee_code})",
                employee_id=employee.pk,
            ))
        except ValueError as exc:
            outcomes.append(RowOutcome(line_number=line_number, ok=False, message=str(exc)))
    return outcomes


def _resolve_employee_code(company: Company, row: dict[str, str], seen_codes: set[str]) -> str:
    code = (row.get("employee_code") or "").strip()
    if not code:
        raise ValueError("employee_code is required")
    if code in seen_codes:
        raise ValueError(f"duplicate employee_code {code!r} in this file")
    # tenant-bypass-allowed: uniqueness check is scoped to the passed company
    if Employee.all_tenants.filter(company=company, employee_code=code).exists():
        raise ValueError(f"employee_code {code!r} already exists for this company")
    seen_codes.add(code)
    return code


def _allowance(row: dict[str, str], column: str) -> Decimal:
    """Optional allowance/bonus column; absent or blank means zero."""
    return _parse_decimal(row.get(column, "")) or Decimal("0")


def _row_to_employee(company: Company, row: dict[str, str], seen_codes: set[str]) -> Employee:
    code = _resolve_employee_code(company, row, seen_codes)
    salary = _parse_decimal(row.get("salary", ""))
    if salary is None:
        raise ValueError("salary is required")
    payload = dict(
        company=company,
        employee_code=code,
        first_name=row.get("first_name", "").strip(),
        last_name=row.get("last_name", "").strip(),
        work_email=row.get("work_email", "").strip(),
        phone=row.get("phone", "").strip(),
        national_id=(row.get("national_id") or "").strip() or None,
        passport_number=(row.get("passport_number") or "").strip() or None,
        passport_expiry=_parse_date(row.get("passport_expiry", "")),
        visa_number=(row.get("visa_number") or "").strip() or None,
        visa_expiry=_parse_date(row.get("visa_expiry", "")),
        bank_account_number=(row.get("bank_account_number") or "").strip() or None,
        salary=salary,
        conveyance_allowance=_allowance(row, "conveyance_allowance"),
        attendance_allowance=_allowance(row, "attendance_allowance"),
        performance_bonus=_allowance(row, "performance_bonus"),
        hire_date=_parse_date(row.get("hire_date", "")),
        is_active=_parse_bool(row.get("is_active", "true")),
    )
    if payload["hire_date"] is None:
        raise ValueError("hire_date is required")
    if not payload["first_name"] or not payload["last_name"]:
        raise ValueError("first_name and last_name are required")

    return Employee.objects.create(**payload)


def csv_template_headers() -> Iterable[str]:
    return ALL_COLUMNS
