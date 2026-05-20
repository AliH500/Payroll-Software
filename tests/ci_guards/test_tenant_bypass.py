"""CI guard: flag every `<PIIModel>.all_tenants` access that is not annotated as an
intentional bypass.

The TenantManager is the default queryset on every tenant-aware model; `all_tenants`
is the explicit escape hatch. Legitimate uses (Django admin, payroll services that
must read across encrypted tables) must carry a `# tenant-bypass-allowed: <reason>`
comment either on the same line or on the line immediately above the call, OR live
in a path that is allow-listed below (migrations, tests, the manager definition
itself, management commands).

Any other `all_tenants` access on a PII model is a security defect.
"""

from __future__ import annotations

import ast
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCAN_DIRS = ["apps", "services"]

# Models whose data is sensitive enough to require an explicit bypass marker.
PII_MODELS = {
    "Employee",
    "Payslip",
    "PayslipLine",
    "Bonus",
    "Deduction",
    "ExpenseReimbursement",
    "AuditLogEntry",
}

# Files / directories where bypass is structurally allowed without inline markers.
ALLOWED_PATH_PARTS = (
    "migrations/",
    "/tests/",
    "/test_",
    "apps/tenants/models_base.py",
    "apps/tenants/managers.py",
    "apps/tenants/management/",
    "tests/ci_guards/",
)

ALLOW_MARKER = "tenant-bypass-allowed"


def _is_allowed_path(rel_path: str) -> bool:
    return any(part in rel_path for part in ALLOWED_PATH_PARTS)


def _has_allow_marker(source_lines: list[str], lineno: int) -> bool:
    """A marker on the call's line, the line above, or up to 3 lines above
    (to allow short surrounding `if`/`assignment` context) satisfies the guard.
    """
    upper = lineno
    lower = max(1, lineno - 3)
    for idx in range(lower - 1, upper):
        if 0 <= idx < len(source_lines) and ALLOW_MARKER in source_lines[idx]:
            return True
    return False


def _pii_model_name_from_value(node: ast.AST) -> str | None:
    """Return the model name if `node.all_tenants` refers to a PII model."""
    if isinstance(node, ast.Name) and node.id in PII_MODELS:
        return node.id
    if isinstance(node, ast.Attribute) and node.attr in PII_MODELS:
        return node.attr
    return None


def _collect_violations(py_file: Path) -> list[str]:
    source = py_file.read_text(encoding="utf-8")
    lines = source.splitlines()
    try:
        tree = ast.parse(source, filename=str(py_file))
    except SyntaxError:
        return []

    violations: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Attribute):
            continue
        if node.attr != "all_tenants":
            continue
        model = _pii_model_name_from_value(node.value)
        if model is None:
            continue
        if _has_allow_marker(lines, node.lineno):
            continue
        rel = py_file.relative_to(REPO_ROOT).as_posix()
        violations.append(f"{rel}:{node.lineno}: {model}.all_tenants used without "
                          f"`# {ALLOW_MARKER}: <reason>` marker")
    return violations


def _iter_python_files() -> list[Path]:
    files: list[Path] = []
    for scan_dir in SCAN_DIRS:
        for py_file in (REPO_ROOT / scan_dir).rglob("*.py"):
            rel = py_file.relative_to(REPO_ROOT).as_posix()
            if _is_allowed_path(rel):
                continue
            files.append(py_file)
    return files


def test_no_unannotated_pii_tenant_bypass() -> None:
    all_violations: list[str] = []
    for py_file in _iter_python_files():
        all_violations.extend(_collect_violations(py_file))
    assert not all_violations, (
        "Found tenant-bypass calls on PII models without an inline "
        f"`# {ALLOW_MARKER}: <reason>` marker:\n  - "
        + "\n  - ".join(all_violations)
    )
