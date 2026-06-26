"""Tests for dv search command."""

from pathlib import Path
from typer.testing import CliRunner
from dv.main import app

runner = CliRunner()
FIXTURES = Path(__file__).parent / "fixtures"


class TestSearch:
    def test_search_all_columns(self):
        result = runner.invoke(
            app,
            ["search", "Alice", str(FIXTURES / "sample.csv"), "-p", "2"],
        )
        assert result.exit_code == 0
        assert "Alice" in result.stdout

    def test_search_specific_column(self):
        result = runner.invoke(
            app,
            ["search", "Eve", str(FIXTURES / "sample.csv"), "--in", "name", "-p", "2"],
        )
        assert result.exit_code == 0
        assert "Eve" in result.stdout

    def test_search_ignore_case(self):
        result = runner.invoke(
            app,
            ["search", "alice", str(FIXTURES / "sample.csv"), "-i", "-p", "2"],
        )
        assert result.exit_code == 0
        assert "Alice" in result.stdout

    def test_search_no_match(self):
        result = runner.invoke(
            app,
            ["search", "ZZZNOTFOUND", str(FIXTURES / "sample.csv")],
        )
        assert result.exit_code == 0

    def test_search_save(self, tmp_path):
        output = tmp_path / "found.csv"
        result = runner.invoke(
            app,
            [
                "search",
                "Alice",
                str(FIXTURES / "sample.csv"),
                "-o",
                str(output),
            ],
        )
        assert result.exit_code == 0
        assert output.exists()

    def test_search_file_not_found(self):
        result = runner.invoke(
            app,
            ["search", "x", str(FIXTURES / "nonexistent.csv")],
        )
        assert result.exit_code == 1
