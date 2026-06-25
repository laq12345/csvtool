"""Tests for csvtool cat command (file concatenation)."""

from pathlib import Path
import duckdb
from typer.testing import CliRunner
from dv.main import app

runner = CliRunner()
FIXTURES = Path(__file__).parent / "fixtures"


class TestCat:
    def test_cat_two_files(self):
        result = runner.invoke(
            app,
            [
                "cat",
                str(FIXTURES / "sample.csv"),
                str(FIXTURES / "sample.csv"),
            ],
        )
        assert result.exit_code == 0

    def test_cat_preview(self):
        result = runner.invoke(
            app,
            [
                "cat",
                str(FIXTURES / "sample.csv"),
                str(FIXTURES / "sample.csv"),
                "-p",
                "2",
            ],
        )
        assert result.exit_code == 0

    def test_cat_save(self, tmp_path):
        output = tmp_path / "merged.parquet"
        result = runner.invoke(
            app,
            [
                "cat",
                str(FIXTURES / "sample.csv"),
                str(FIXTURES / "sample.csv"),
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
        assert rows[0] == 10
        con.close()

    def test_cat_three_files(self):
        result = runner.invoke(
            app,
            [
                "cat",
                str(FIXTURES / "sample.csv"),
                str(FIXTURES / "sample.csv"),
                str(FIXTURES / "sample.csv"),
            ],
        )
        assert result.exit_code == 0

    def test_cat_one_file_error(self):
        result = runner.invoke(
            app,
            ["cat", str(FIXTURES / "sample.csv")],
        )
        assert result.exit_code == 1

    def test_cat_nonexistent(self):
        result = runner.invoke(
            app,
            [
                "cat",
                str(FIXTURES / "sample.csv"),
                str(FIXTURES / "nonexistent.csv"),
            ],
        )
        assert result.exit_code == 1

    def test_cat_column_order_mismatch(self, tmp_path):
        file_a = tmp_path / "a.csv"
        file_b = tmp_path / "b.csv"
        file_a.write_text("col1,col2\n1,2\n3,4\n")
        file_b.write_text("col2,col1\n5,6\n7,8\n")
        result = runner.invoke(
            app, ["cat", str(file_a), str(file_b)]
        )
        assert result.exit_code == 0
        assert "4 rows" in result.stdout

    def test_cat_stats(self):
        result = runner.invoke(
            app,
            ["cat", str(FIXTURES / "sample.csv"), str(FIXTURES / "sample.csv"), "-s"],
        )
        assert result.exit_code == 0
