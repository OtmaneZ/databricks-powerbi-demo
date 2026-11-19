"""Run the versioned Unity Catalog governance scripts (sql/governance/*.sql).

Each file is rendered (``${catalog}`` placeholder), split into statements and executed
with Spark SQL, locally through Databricks Connect or inside a Lakeflow Job task.

Usage (local):
    DATABRICKS_CONFIG_PROFILE=dec-demo uv run python -m dec_demo.governance --catalog dec_dev \
        --files 00_setup.sql 10_security.sql --ensure-groups
"""

from __future__ import annotations

import argparse
import re
from collections.abc import Sequence
from pathlib import Path

DEMO_GROUPS = [
    "dec_platform_admins",
    "dec_analysts_national",
    "dec_pii_readers",
    "dec_region_idf",
    "dec_region_nord",
    "dec_region_est",
    "dec_region_ouest",
    "dec_region_sud_est",
    "dec_region_sud_ouest",
]
# Groups the user running the setup joins, so that the pipeline owner and the
# Power BI connection see every region and unmasked data.
DEFAULT_MEMBERSHIPS = ["dec_platform_admins", "dec_pii_readers"]

_PLACEHOLDER = re.compile(r"\$\{(\w+)\}")
_STATEMENT_END = re.compile(r";[ \t]*(?:--[^\n]*)?(?:\n|$)")


def render(sql: str, params: dict[str, str]) -> str:
    """Substitute ${key} placeholders; fail loudly on unknown keys."""

    def _sub(match: re.Match[str]) -> str:
        key = match.group(1)
        if key not in params:
            raise KeyError(f"Missing SQL parameter: {key}")
        return params[key]

    return _PLACEHOLDER.sub(_sub, sql)


def split_statements(sql: str) -> list[str]:
    """Split a script on statement-ending semicolons, ignoring full-line comments."""
    lines = [line for line in sql.splitlines() if not line.lstrip().startswith("--")]
    body = "\n".join(lines)
    return [stmt.strip() for stmt in _STATEMENT_END.split(body) if stmt.strip()]


def run_files(spark, sql_dir: Path, files: Sequence[str], params: dict[str, str]) -> int:
    count = 0
    for name in files:
        for statement in split_statements(render((sql_dir / name).read_text(encoding="utf-8"), params)):
            first_line = statement.splitlines()[0][:100]
            print(f"[{name}] {first_line}")
            spark.sql(statement)
            count += 1
    return count


def ensure_groups(groups: Sequence[str], memberships: Sequence[str]) -> None:
    """Create workspace-local demo groups and add the current user (Free Edition only).

    On the target platform these groups are account groups provisioned by SCIM from the
    identity provider; this function is then not used.
    """
    from databricks.sdk import WorkspaceClient
    from databricks.sdk.service import iam

    w = WorkspaceClient()
    me = w.current_user.me()
    existing = {g.display_name: g for g in w.groups.list(attributes="id,displayName")}
    for name in groups:
        group = existing.get(name) or w.groups.create(display_name=name)
        print(f"[groups] {name}: {'exists' if name in existing else 'created'}")
        if name in memberships:
            w.groups.patch(
                id=group.id,
                operations=[iam.Patch(op=iam.PatchOp.ADD, path="members", value=[{"value": me.id}])],
                schemas=[iam.PatchSchema.URN_IETF_PARAMS_SCIM_API_MESSAGES_2_0_PATCH_OP],
            )
            print(f"[groups] {me.user_name} added to {name}")


def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Apply Unity Catalog governance SQL scripts.")
    parser.add_argument("--catalog", required=True)
    parser.add_argument("--sql-dir", default="sql/governance")
    parser.add_argument("--files", nargs="+", default=["00_setup.sql", "10_security.sql"])
    parser.add_argument("--ensure-groups", action="store_true", help="Free Edition: create workspace-local groups")
    args = parser.parse_args(argv)

    if args.ensure_groups:
        ensure_groups(DEMO_GROUPS, DEFAULT_MEMBERSHIPS)

    from dec_demo.generate import get_spark

    n = run_files(get_spark(), Path(args.sql_dir), args.files, {"catalog": args.catalog})
    print(f"Applied {n} statements on catalog {args.catalog}")


if __name__ == "__main__":
    main()
