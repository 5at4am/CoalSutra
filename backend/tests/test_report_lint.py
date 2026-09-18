"""Facts-check lint: every figure in a drafted report must be fact-backed + cited."""

from app.services.reporting.lint import lint_sections

FACTS = [
    {"fact_id": 1, "entity": "coal_production", "value": "38.5", "unit": "MT"},
    {"fact_id": 2, "entity": "coal_production", "value": "40.2", "unit": "MT"},
    {"fact_id": 3, "entity": "overburden_removal", "value": "9480", "unit": "BCM"},
]


def _section(body, citations=None, automatic=False):
    draft = {"body": body, "citations": citations or []}
    if automatic:
        draft["automatic"] = True
    return draft


def test_all_figures_backed_and_cited_ok():
    sections = {
        "trends": _section(
            "Production moved from 38.5 MT to 40.2 MT. Overburden was 9480 BCM.",
            [{"fact_id": 1}, {"fact_id": 2}, {"fact_id": 3}],
        )
    }
    result = lint_sections(sections, FACTS)
    assert result["ok"] is True
    assert result["summary"]["figures_checked"] == 3
    assert result["summary"]["figures_matched_to_facts"] == 3
    assert result["issues"] == []


def test_uncited_figure_is_error():
    sections = {
        "trends": _section(
            "Production moved from 38.5 MT to 40.2 MT.",
            [{"fact_id": 1}],
        )
    }
    result = lint_sections(sections, FACTS)
    assert result["ok"] is False
    assert result["summary"]["errors"] == 1
    assert result["issues"][0]["number"] == "40.2"
    assert "does not cite" in result["issues"][0]["reason"]


def test_derived_delta_is_not_a_false_error():
    sections = {
        "trends": _section(
            "Production rose 1.7 from 38.5 MT to 40.2 MT.",
            [{"fact_id": 1}, {"fact_id": 2}],
        )
    }
    result = lint_sections(sections, FACTS)
    assert result["ok"] is True
    assert result["summary"]["errors"] == 0


def test_unverifiable_figure_added_to_ok_scope():
    sections = {
        "key_figures": _section(
            "Production was 38.5 MT, and output peaked at 99.0 MT.",
            [{"fact_id": 1}],
        )
    }
    result = lint_sections(sections, FACTS)
    assert result["ok"] is False
    assert any(issue["number"] == "99.0" for issue in result["issues"])


def test_percentage_and_year_references_are_not_flagged_as_errors():
    sections = {
        "trends": _section(
            "Output rose 6.8% between Jan and Mar 2026.",
            [{"fact_id": 1}, {"fact_id": 2}],
        )
    }
    result = lint_sections(sections, FACTS)
    assert result["ok"] is True
    numbers = {issue["number"] for issue in result["issues"]}
    assert "2026" not in numbers
    assert "6.8%" not in numbers or (
        all(issue["severity"] == "info" for issue in result["issues"])
    )


def test_automatic_sections_are_skipped():
    sections = {"sources": _section("arbitrary 42.0 text", [{"fact_id": 1}], automatic=True)}
    result = lint_sections(sections, FACTS)
    assert result["summary"]["figures_checked"] == 0
    assert result["ok"] is True