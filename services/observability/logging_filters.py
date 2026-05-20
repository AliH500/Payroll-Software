"""Logging filters that mask sensitive fields before records are emitted.

The brief makes this a V1 hard requirement: salary figures, salary-derived
figures, and PII identifiers must never appear in logs, error messages, traces,
or any output channel. This is layer 1 of the defense; `domain.Money.__repr__`
is layer 2 (positional values), and the CI guard scanning logger calls is layer 3.
"""

from __future__ import annotations

import logging
from typing import Any, Final

SENSITIVE_KEYS: Final[frozenset[str]] = frozenset(
    {
        # salary and salary-derived figures
        "salary",
        "base_salary",
        "hourly_rate",
        "unit_rate",
        "deduction",
        "deduction_amount",
        "bonus",
        "bonus_amount",
        "reimbursement",
        "reimbursement_amount",
        "expense",
        "expense_amount",
        "net_pay",
        "gross_pay",
        "amount",
        "payslip_line",
        "payment_instruction",
        # PII identifiers
        "national_id",
        "passport_number",
        "visa_number",
        "bank_account",
        "bank_account_number",
        # secrets
        "password",
        "token",
        "secret",
    }
)

REDACTED: Final[str] = "[REDACTED]"

# Standard fields on every LogRecord that must be left alone even if a name happens to
# collide with a sensitive key. Keeps the filter targeted at user-supplied `extra=` kwargs.
_LOGRECORD_STANDARD_FIELDS: Final[frozenset[str]] = frozenset(
    {
        "name",
        "msg",
        "args",
        "levelname",
        "levelno",
        "pathname",
        "filename",
        "module",
        "exc_info",
        "exc_text",
        "stack_info",
        "lineno",
        "funcName",
        "created",
        "msecs",
        "relativeCreated",
        "thread",
        "threadName",
        "processName",
        "process",
        "message",
        "asctime",
        "taskName",
    }
)


class SensitiveDataFilter(logging.Filter):
    """Drops or masks sensitive fields from log records before emission."""

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.args, dict):
            record.args = self._mask_dict(record.args)

        for key in list(record.__dict__.keys()):
            if key in _LOGRECORD_STANDARD_FIELDS:
                continue
            if key.lower() in SENSITIVE_KEYS:
                record.__dict__[key] = REDACTED

        return True

    @staticmethod
    def _mask_dict(d: dict[str, Any]) -> dict[str, Any]:
        return {
            key: (REDACTED if key.lower() in SENSITIVE_KEYS else value)
            for key, value in d.items()
        }
