"""Tests for csvtool peek command via CliRunner."""

from pathlib import Path
from typer.testing import CliRunner
from dv.main import app

runner = CliRunner()
FIXTURES = Path(__file__).parent / "fixtures"


class TestPeekStructure:
    def test_shows_columns(self):
        result = runner.invoke(app, ["peek", str(FIXTURES / "sample.csv")])
        assert result.exit_code == 0
        assert "id" in result.stdout
        assert "name" in result.stdout
        assert "age" in result.stdout
        assert "score" in result.stdout

    def test_shows_row_count(self):
        result = runner.invoke(app, ["peek", str(FIXTURES / "sample.csv")])
        assert "5 rows" in result.stdout

    def test_shows_format(self):
        result = runner.invoke(app, ["peek", str(FIXTURES / "sample.csv"), "-I"])
        assert "CSV" in result.stdout.upper()


class TestPeekPreview:
    def test_preview_default(self):
        result = runner.invoke(app, ["peek", str(FIXTURES / "sample.csv"), "-p", "3"])
        assert result.exit_code == 0
        assert "Alice" in result.stdout
        assert "Bob" in result.stdout

    def test_preview_long_flag(self):
        result = runner.invoke(
            app, ["peek", str(FIXTURES / "sample.csv"), "--preview", "2"]
        )
        assert result.exit_code == 0


class TestPeekStats:
    def test_stats(self):
        result = runner.invoke(app, ["peek", str(FIXTURES / "sample.csv"), "-s"])
        assert result.exit_code == 0
        output = result.stdout.lower()
        assert "count" in output or "column" in output or "approx" in output

    def test_stats_long_flag(self):
        result = runner.invoke(app, ["peek", str(FIXTURES / "sample.csv"), "--stats"])
        assert result.exit_code == 0


class TestPeekErrors:
    def test_file_not_found(self):
        result = runner.invoke(app, ["peek", "/tmp/nonexistent_file_xyz.csv"])
        assert result.exit_code == 1
        assert "not found" in (result.stdout + result.stderr).lower()

    def test_unsupported_format(self, tmp_path):
        bad_file = tmp_path / "test.xyz"
        bad_file.write_text("hello")
        result = runner.invoke(app, ["peek", str(bad_file)])
        assert result.exit_code == 1
        assert "unsupported" in (result.stdout + result.stderr).lower()


class TestPeekVerbose:
    def test_verbose_enables_debug(self):
        result = runner.invoke(
            app, ["-v", "peek", str(FIXTURES / "sample.csv"), "-p", "1"]
        )
        assert result.exit_code == 0
        output = result.stdout + result.stderr
        assert "DEBUG" in output


class TestPeekStdin:
    def test_stdin_pipe(self):
        result = runner.invoke(
            app,
            ["peek"],
            input="a,b\n1,2\n3,4\n",
        )
        assert result.exit_code == 0
        assert "2 rows" in result.stdout or "a" in result.stdout


class TestPeekColumns:
    def test_columns_selection(self):
        result = runner.invoke(
            app,
            ["peek", str(FIXTURES / "sample.csv"), "-c", "id,name", "-p", "2"],
        )
        assert result.exit_code == 0
        assert "name" in result.stdout
        assert "score" not in result.stdout

    def test_sort_ascending(self):
        result = runner.invoke(
            app,
            ["peek", str(FIXTURES / "sample.csv"), "--sort", "age", "-p", "3"],
        )
        assert result.exit_code == 0

    def test_sort_descending(self):
        result = runner.invoke(
            app,
            ["peek", str(FIXTURES / "sample.csv"), "--sort", "age DESC", "-p", "3"],
        )
        assert result.exit_code == 0
