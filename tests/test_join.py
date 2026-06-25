"""Tests for csvtool join command."""

from pathlib import Path
import duckdb
from typer.testing import CliRunner
from dv.main import app

runner = CliRunner()
FIXTURES = Path(__file__).parent / "fixtures"


class TestJoin:
    def test_join_with_on(self):
        result = runner.invoke(
            app,
            [
                "join",
                str(FIXTURES / "sample.csv"),
                str(FIXTURES / "sample.csv"),
                "--on",
                "id",
            ],
        )
        assert result.exit_code == 0

    def test_join_preview(self):
        result = runner.invoke(
            app,
            [
                "join",
                str(FIXTURES / "sample.csv"),
                str(FIXTURES / "sample.csv"),
                "--on",
                "id",
                "-p",
                "2",
            ],
        )
        assert result.exit_code == 0

    def test_join_left(self):
        result = runner.invoke(
            app,
            [
                "join",
                str(FIXTURES / "sample.csv"),
                str(FIXTURES / "sample.csv"),
                "--on",
                "id",
                "--how",
                "left",
            ],
        )
        assert result.exit_code == 0

    def test_join_outer(self):
        result = runner.invoke(
            app,
            [
                "join",
                str(FIXTURES / "sample.csv"),
                str(FIXTURES / "sample.csv"),
                "--on",
                "id",
                "--how",
                "outer",
            ],
        )
        assert result.exit_code == 0

    def test_join_save(self, tmp_path):
        output = tmp_path / "joined.parquet"
        result = runner.invoke(
            app,
            [
                "join",
                str(FIXTURES / "sample.csv"),
                str(FIXTURES / "sample.csv"),
                "--on",
                "id",
                "-o",
                str(output),
            ],
        )
        assert result.exit_code == 0
        assert output.exists()
        con = duckdb.connect()
        rows = con.sql(
            f"SELECT COUNT(*) FROM read_parquet('{output}')"
        ).fetchone()
        assert rows[0] == 5
        con.close()

    def test_join_invalid_how(self):
        result = runner.invoke(
            app,
            [
                "join",
                str(FIXTURES / "sample.csv"),
                str(FIXTURES / "sample.csv"),
                "--how",
                "bad",
            ],
        )
        assert result.exit_code == 1

    def test_join_file_not_found(self):
        result = runner.invoke(
            app,
            [
                "join",
                str(FIXTURES / "sample.csv"),
                str(FIXTURES / "nonexistent.csv"),
            ],
        )
        assert result.exit_code == 1

    def test_join_auto_detect_unique(self, tmp_path):
        left = tmp_path / "left.csv"
        right = tmp_path / "right.csv"
        left.write_text("gene,expr\nBRCA1,10\nTP53,20\n")
        right.write_text("gene,pathway\nBRCA1,repair\nTP53,apoptosis\n")
        result = runner.invoke(app, ["join", str(left), str(right)])
        assert result.exit_code == 0

    def test_join_auto_detect_multi_error(self):
        result = runner.invoke(
            app,
            [
                "join",
                str(FIXTURES / "sample.csv"),
                str(FIXTURES / "sample.csv"),
            ],
        )
        assert result.exit_code == 1

    def test_join_different_column_names(self, tmp_path):
        left = tmp_path / "a.csv"
        right = tmp_path / "b.csv"
        left.write_text("probe,expr\np1,10\np2,20\n")
        right.write_text("probeset,pathway\np1,repair\np2,apoptosis\n")
        result = runner.invoke(
            app,
            ["join", str(left), str(right), "--on", "probe=probeset"],
        )
        assert result.exit_code == 0

    def test_join_right_how(self):
        result = runner.invoke(
            app,
            [
                "join",
                str(FIXTURES / "sample.csv"),
                str(FIXTURES / "sample.csv"),
                "--on",
                "id",
                "--how",
                "right",
            ],
        )
        assert result.exit_code == 0

    def test_join_column_not_exist(self):
        result = runner.invoke(
            app,
            [
                "join",
                str(FIXTURES / "sample.csv"),
                str(FIXTURES / "sample.csv"),
                "--on",
                "nonexistent_col",
            ],
        )
        assert result.exit_code == 1

    def test_join_auto_detect_none(self, tmp_path):
        a_file = tmp_path / "a.csv"
        b_file = tmp_path / "b.csv"
        a_file.write_text("col1,x\n1,2\n")
        b_file.write_text("col2,y\n3,4\n")
        result = runner.invoke(app, ["join", str(a_file), str(b_file)])
        assert result.exit_code == 1

    def test_join_stats(self):
        result = runner.invoke(
            app,
            [
                "join",
                str(FIXTURES / "sample.csv"),
                str(FIXTURES / "sample.csv"),
                "--on", "id", "-s",
            ],
        )
        assert result.exit_code == 0
