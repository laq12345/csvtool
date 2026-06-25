"""Tests for csvtool sql -o (save results to file)."""

from pathlib import Path
import duckdb
from typer.testing import CliRunner
from dv.main import app

runner = CliRunner()
FIXTURES = Path(__file__).parent / "fixtures"


class TestSqlOutput:
    def test_save_parquet(self, tmp_path):
        output = tmp_path / "out.parquet"
        result = runner.invoke(
            app,
            [
                "sql",
                "SELECT * FROM read_csv_auto('"
                + str(FIXTURES / "sample.csv")
                + "') WHERE age > 30",
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
        assert rows[0] == 1
        con.close()

    def test_save_csv(self, tmp_path):
        output = tmp_path / "out.csv"
        result = runner.invoke(
            app,
            [
                "sql",
                "SELECT name, score FROM read_csv_auto('"
                + str(FIXTURES / "sample.csv")
                + "') LIMIT 2",
                "-o",
                str(output),
            ],
        )
        assert result.exit_code == 0
        assert output.exists()
        con = duckdb.connect()
        rows = con.sql(
            f"SELECT COUNT(*) FROM read_csv_auto('{output}')"
        ).fetchone()
        assert rows[0] == 2
        con.close()

    def test_unsupported_output_format(self, tmp_path):
        output = tmp_path / "out.xyz"
        result = runner.invoke(
            app,
            [
                "sql",
                "SELECT 1",
                "-o",
                str(output),
            ],
        )
        assert result.exit_code == 1
        assert "unsupported" in (result.stdout + result.stderr).lower()

    def test_preview_still_works(self):
        result = runner.invoke(
            app,
            [
                "sql",
                "SELECT * FROM read_csv_auto('"
                + str(FIXTURES / "sample.csv")
                + "') LIMIT 1",
            ],
        )
        assert result.exit_code == 0

    def test_save_json(self, tmp_path):
        output = tmp_path / "out.json"
        result = runner.invoke(
            app,
            [
                "sql",
                "SELECT name, score FROM read_csv_auto('"
                + str(FIXTURES / "sample.csv")
                + "') LIMIT 2",
                "-o",
                str(output),
            ],
        )
        assert result.exit_code == 0
        assert output.exists()
        con = duckdb.connect()
        rows = con.sql(
            f"SELECT COUNT(*) FROM read_json_auto('{output}')"
        ).fetchone()
        assert rows[0] == 2
        con.close()

    def test_save_tsv(self, tmp_path):
        output = tmp_path / "out.tsv"
        result = runner.invoke(
            app,
            [
                "sql",
                "SELECT * FROM read_csv_auto('"
                + str(FIXTURES / "sample.csv")
                + "') LIMIT 2",
                "-o",
                str(output),
            ],
        )
        assert result.exit_code == 0
        assert output.exists()
        con = duckdb.connect()
        rows = con.sql(
            f"SELECT COUNT(*) FROM read_csv_auto('{output}')"
        ).fetchone()
        assert rows[0] == 2
        con.close()
