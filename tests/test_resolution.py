from pathlib import Path

from clangd_probe.resolve import resolve_target


def test_location_form_parses_file_line_and_column(tmp_path):
    source = tmp_path / "demo.cpp"
    source.write_text("int main() { return 0; }\n", encoding="utf-8")

    result = resolve_target(f"{source}:12:7")

    assert result.status == "ok"
    assert result.results == [
        {
            "kind": "location",
            "path": str(source.resolve()),
            "line": 12,
            "column": 7,
        }
    ]


def test_scope_qualified_symbol_ranks_exact_match_first():
    matches = [
        {"name": "solve", "qualified_name": "Other::solve", "path": "other.cpp", "line": 9, "column": 1},
        {"name": "solve", "qualified_name": "CollideBGK::solve", "path": "bgk.cpp", "line": 5, "column": 3},
    ]

    result = resolve_target("CollideBGK::solve", symbol_lookup=lambda _query: matches)

    assert result.status == "ok"
    assert result.results[0]["qualified_name"] == "CollideBGK::solve"


def test_ambiguous_symbol_name_is_reported():
    matches = [
        {"name": "solve", "qualified_name": "A::solve", "path": "a.cpp", "line": 1, "column": 1},
        {"name": "solve", "qualified_name": "B::solve", "path": "b.cpp", "line": 1, "column": 1},
    ]

    result = resolve_target("solve", symbol_lookup=lambda _query: matches)

    assert result.status == "ambiguous"
    assert len(result.results) == 2


def test_symbol_form_without_lookup_is_unsupported():
    result = resolve_target("CollideBGK::solve")

    assert result.status == "unsupported"
    assert result.diagnostics[0]["error_kind"] == "setup_failure"


def test_symbol_form_with_no_results_stays_distinct():
    result = resolve_target("Missing::symbol", symbol_lookup=lambda _query: [])

    assert result.status == "no_results"
    assert result.results == []


def test_ranking_is_stable_for_exact_name_before_prefix():
    matches = [
        {"name": "solve_extra", "qualified_name": "CollideBGK::solve_extra", "path": "x.cpp", "line": 3, "column": 1},
        {"name": "solve", "qualified_name": "CollideBGK::solve", "path": "y.cpp", "line": 4, "column": 2},
    ]

    result = resolve_target("solve", symbol_lookup=lambda _query: matches)

    assert result.status == "ok"
    assert result.results[0]["qualified_name"] == "CollideBGK::solve"

