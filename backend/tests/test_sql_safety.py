"""No SQL is ever assembled from a formatted string.

Atlas builds every query through the ORM, so this should be true by
construction — but "should be" is not a guarantee, and the one place raw SQL is
unavoidable (migrations, which must name tables that no longer have models) is
exactly where a formatted value would be easiest to slip in.

The check is static: any SQL entry point receiving an f-string, a ``%`` format
or ``.format()`` is a failure unless it is on the allowlist below, which exists
only for *identifier* interpolation — table and column names cannot be bound
parameters in SQL, so they have to be spliced. Every allowlisted site must take
its identifiers from module-level literals, never from a request.
"""
from __future__ import annotations

import ast
from pathlib import Path

APP = Path(__file__).resolve().parents[1] / "app"

#: Functions whose first argument is SQL.
SQL_CALLS = {"text", "execute", "exec_driver_sql", "executemany", "executescript"}

#: (relative path, reason) for the sites that splice a *table name* from a
#: hardcoded list. Values in these statements are still bound parameters.
ALLOWED_IDENTIFIER_SPLICING = {
    "migrations/versions/c4a1f9b73e02_multi_user_data_scoping.py",
}


def _sql_arg(node: ast.Call) -> ast.expr | None:
    """The SQL string argument of a call, if this looks like a SQL entry point."""
    name = (
        node.func.attr
        if isinstance(node.func, ast.Attribute)
        else node.func.id
        if isinstance(node.func, ast.Name)
        else None
    )
    if name not in SQL_CALLS or not node.args:
        return None
    return node.args[0]


def _is_formatted(node: ast.expr) -> bool:
    """True for f-strings, %-formatting and .format() — anything interpolated."""
    if isinstance(node, ast.JoinedStr):
        return any(isinstance(v, ast.FormattedValue) for v in node.values)
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Mod):
        return True
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
        return node.func.attr == "format"
    # Implicit concatenation of literals is fine; a runtime `+` is not.
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        return not (
            isinstance(node.left, ast.Constant) and isinstance(node.right, ast.Constant)
        )
    return False


def test_no_sql_is_built_by_string_formatting():
    offenders: list[str] = []

    for path in APP.rglob("*.py"):
        rel = path.relative_to(APP).as_posix()
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            arg = _sql_arg(node)
            if arg is None or not _is_formatted(arg):
                continue
            if rel in ALLOWED_IDENTIFIER_SPLICING:
                continue
            offenders.append(f"{rel}:{node.lineno}")

    assert not offenders, (
        "SQL built by string formatting — use bound parameters instead:\n  "
        + "\n  ".join(offenders)
    )


def test_allowlisted_sites_still_bind_their_values():
    """The migration may splice table names, but never a value."""
    path = APP / "migrations/versions/c4a1f9b73e02_multi_user_data_scoping.py"
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        arg = _sql_arg(node)
        if arg is None or not isinstance(arg, ast.JoinedStr):
            continue
        # Every interpolation must be a bare name (a table from the literal
        # list overhead), and the statement must bind its values with `:name`.
        for value in arg.values:
            if isinstance(value, ast.FormattedValue):
                assert isinstance(value.value, ast.Name), (
                    f"{path.name}:{node.lineno} interpolates an expression, "
                    "which is how a value sneaks into SQL"
                )
        literal = "".join(
            v.value for v in arg.values if isinstance(v, ast.Constant)
        )
        if "WHERE" in literal.upper() or "SET" in literal.upper():
            assert ":" in literal, (
                f"{path.name}:{node.lineno} has no bound parameter — "
                "a value may have been spliced in"
            )
