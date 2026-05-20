"""CI guard: flag logger / print calls that reference forbidden field names.

Backs up the runtime `SensitiveDataFilter` with a static check so a stray
`logger.info(f"net pay {payslip.net_pay}")` cannot land in the codebase.

Detection rules:
- For every `logger.<level>(...)` or bare `print(...)` call, walk each argument:
  * `ast.Constant` (str) arguments — flag if a forbidden field name appears as
    a standalone word (word-boundary match) in the string.
  * `ast.JoinedStr` (f-string) arguments — flag if any `FormattedValue.value`
    references attribute access whose `attr` is a forbidden field name
    (e.g. `f"{employee.base_salary}"`).
- Logger names: any local name that matches `logger`, `log`, `logging`, or
  anything ending in `_logger`. Plus the builtin `print`.

Allow-marker: `# log-key-allowed: <reason>` on the same line or up to 3 lines
above suppresses the violation, mirroring the tenant-bypass guard.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

from services.observability.logging_filters import SENSITIVE_KEYS

REPO_ROOT = Path(__file__).resolve().parents[2]
SCAN_DIRS = ["apps", "services"]

ALLOWED_PATH_PARTS = (
    "migrations/",
    "/tests/",
    "/test_",
    "tests/ci_guards/",
    # The filter itself defines SENSITIVE_KEYS as string literals.
    "services/observability/logging_filters.py",
)

LOGGER_NAME_RE = re.compile(r"^(logger|log|logging|.+_logger)$")
LOGGER_LEVELS = {"debug", "info", "warning", "warn", "error", "critical", "exception", "log"}
ALLOW_MARKER = "log-key-allowed"

# Build word-boundary regexes once. lowercase comparison.
_WORD_BOUNDARIES = {
    key: re.compile(rf"\b{re.escape(key)}\b", re.IGNORECASE) for key in SENSITIVE_KEYS
}


def _is_allowed_path(rel_path: str) -> bool:
    return any(part in rel_path for part in ALLOWED_PATH_PARTS)


def _has_allow_marker(source_lines: list[str], lineno: int) -> bool:
    upper = lineno
    lower = max(1, lineno - 3)
    for idx in range(lower - 1, upper):
        if 0 <= idx < len(source_lines) and ALLOW_MARKER in source_lines[idx]:
            return True
    return False


def _is_logger_or_print_call(call: ast.Call) -> bool:
    """Return True for `logger.<level>(...)`, `<x>_logger.<level>(...)`, or `print(...)`."""
    func = call.func
    if isinstance(func, ast.Name) and func.id == "print":
        return True
    if isinstance(func, ast.Attribute) and func.attr.lower() in LOGGER_LEVELS:
        value = func.value
        if isinstance(value, ast.Name) and LOGGER_NAME_RE.match(value.id):
            return True
        if isinstance(value, ast.Attribute) and LOGGER_NAME_RE.match(value.attr):
            return True
    return False


def _matches_for_string(text: str) -> list[str]:
    return [key for key, regex in _WORD_BOUNDARIES.items() if regex.search(text)]


def _scan_arg(arg: ast.AST) -> list[str]:
    matches: list[str] = []
    if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
        matches.extend(_matches_for_string(arg.value))
    elif isinstance(arg, ast.JoinedStr):
        for part in arg.values:
            if isinstance(part, ast.Constant) and isinstance(part.value, str):
                matches.extend(_matches_for_string(part.value))
            elif isinstance(part, ast.FormattedValue):
                attr = part.value
                if isinstance(attr, ast.Attribute) and attr.attr.lower() in SENSITIVE_KEYS:
                    matches.append(attr.attr)
                elif isinstance(attr, ast.Name) and attr.id.lower() in SENSITIVE_KEYS:
                    matches.append(attr.id)
    return matches


def _collect_violations(py_file: Path) -> list[str]:
    source = py_file.read_text(encoding="utf-8")
    lines = source.splitlines()
    try:
        tree = ast.parse(source, filename=str(py_file))
    except SyntaxError:
        return []

    violations: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if not _is_logger_or_print_call(node):
            continue
        if _has_allow_marker(lines, node.lineno):
            continue
        hits: list[str] = []
        for arg in node.args:
            hits.extend(_scan_arg(arg))
        for kw in node.keywords:
            if kw.value is not None:
                hits.extend(_scan_arg(kw.value))
        if hits:
            rel = py_file.relative_to(REPO_ROOT).as_posix()
            uniq = ", ".join(sorted(set(hits)))
            violations.append(
                f"{rel}:{node.lineno}: logger/print references forbidden key(s): {uniq}"
            )
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


def test_no_sensitive_keys_in_logger_calls() -> None:
    all_violations: list[str] = []
    for py_file in _iter_python_files():
        all_violations.extend(_collect_violations(py_file))
    assert not all_violations, (
        "Found logger/print calls referencing forbidden field names:\n  - "
        + "\n  - ".join(all_violations)
    )
