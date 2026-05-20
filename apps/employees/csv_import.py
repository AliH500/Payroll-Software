"""CSV bulk-import of Employee rows."""

from __future__ import annotations

import csv
import io
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation

from apps.employees.models import Employee, PayBasis
from apps.tenants.models import Company

REQUIRED_COLUMNS = (
    "first_name",
    "last_name",
    "pay_basis",
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
    "base_salary",
    "hourly_rate",
    "unit_rate",
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

    Required headers: first_name, last_name, pay_basis, hire_date.
    pay_basis must be one of: fixed | hourly | unit. The matching rate column
    (base_salary / hourly_rate / unit_rate) must be present for that row.
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

    outcomes: list[RowOutcome] = []
    for line_number, row in enumerate(reader, start=2):
        try:
            employee = _row_to_employee(company, row)
            outcomes.append(RowOutcome(
                line_number=line_number, ok=True,
                message=f"Imported {employee.full_name}",
                employee_id=employee.pk,
            ))
        except ValueError as exc:
            outcomes.append(RowOutcome(line_number=line_number, ok=False, message=str(exc)))
    return outcomes


def _row_to_employee(company: Company, row: dict[str, str]) -> Employee:
    basis = (row.get("pay_basis") or "").strip().lower()
    if basis not in PayBasis.values:
        raise ValueError(
            f"pay_basis must be one of {sorted(PayBasis.values)}; got {basis!r}"
        )
    payload = dict(
        company=company,
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
        pay_basis=basis,
        hire_date=_parse_date(row.get("hire_date", "")),
        is_active=_parse_bool(row.get("is_active", "true")),
    )
    if payload["hire_date"] is None:
        raise ValueError("hire_date is required")
    if not payload["first_name"] or not payload["last_name"]:
        raise ValueError("first_name and last_name are required")

    if basis == PayBasis.FIXED:
        payload["base_salary"] = _parse_decimal(row.get("base_salary", ""))
        if payload["base_salary"] is None:
            raise ValueError("base_salary required for pay_basis=fixed")
    elif basis == PayBasis.HOURLY:
        payload["hourly_rate"] = _parse_decimal(row.get("hourly_rate", ""))
        if payload["hourly_rate"] is None:
            raise ValueError("hourly_rate required for pay_basis=hourly")
    elif basis == PayBasis.UNIT:
        payload["unit_rate"] = _parse_decimal(row.get("unit_rate", ""))
        if payload["unit_rate"] is None:
            raise ValueError("unit_rate required for pay_basis=unit")

    return Employee.objects.create(**payload)


def csv_template_headers() -> Iterable[str]:
    return ALL_COLUMNS
