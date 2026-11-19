import re
from pathlib import Path

import pytest

from dec_demo.governance import render, split_statements

SQL_DIR = Path(__file__).parent.parent / "sql" / "governance"


def test_render_substitutes_catalog():
    assert render("SELECT * FROM ${catalog}.gold.t", {"catalog": "dec_dev"}) == "SELECT * FROM dec_dev.gold.t"


def test_render_fails_on_unknown_placeholder():
    with pytest.raises(KeyError):
        render("SELECT ${unknown}", {"catalog": "dec_dev"})


def test_split_ignores_comments_and_keeps_inner_semicolon_free_bodies():
    sql = "-- header; not a statement\nCREATE TABLE a (x INT);\n\nSELECT 'a;b' AS v\n;\n"
    assert split_statements(sql) == ["CREATE TABLE a (x INT)", "SELECT 'a;b' AS v"]


def test_split_accepts_trailing_comment_after_semicolon():
    sql = "GRANT SELECT ON t TO `account users`;  -- noqa: RF05\nSELECT 1;\n"
    assert split_statements(sql) == ["GRANT SELECT ON t TO `account users`", "SELECT 1"]


@pytest.mark.parametrize("name", sorted(p.name for p in SQL_DIR.glob("*.sql")))
def test_governance_scripts_render_and_split(name):
    statements = split_statements(render((SQL_DIR / name).read_text(encoding="utf-8"), {"catalog": "dec_dev"}))
    assert statements, f"{name} produced no statement"
    assert all("${" not in s for s in statements)
    assert all("dec_dev" in s for s in statements), "every statement must target the rendered catalog"


def test_row_filter_parameter_is_not_shadowed():
    """A parameter named like a column of the entitlement table would leak every row."""
    sql = (SQL_DIR / "10_security.sql").read_text(encoding="utf-8")
    assert re.search(r"rf_region\s*\(row_region STRING\)", sql)
    assert "a.region IN (row_region, '*')" in sql
