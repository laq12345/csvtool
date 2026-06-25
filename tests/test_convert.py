"""Tests for csvtool convert command via CliRunner."""

from pathlib import Path
import duckdb
from typer.testing import CliRunner
from dv.main import app

runner = CliRunner()
FIXTURES = Path(__file__).parent / "fixtures"


class TestConvert:
    def test_csv_to_parquet(self, tmp_path):
        output = tmp_path / "out.parquet"
        result = runner.invoke(
            app,
            ["convert", str(FIXTURES / "sample.csv"), str(output)],
        )
        assert result.exit_code == 0
        assert output.exists()

        # Verify output is valid parquet with correct row count
        con = duckdb.connect()
        rows = con.sql(f"SELECT COUNT(*) FROM read_parquet('{output}')").fetchone()
        assert rows[0] == 5
        con.close()

    def test_csv_to_csv(self, tmp_path):
        output = tmp_path / "out.csv"
        result = runner.invoke(
            app,
            ["convert", str(FIXTURES / "sample.csv"), str(output)],
        )
        assert result.exit_code == 0
        assert output.exists()

        con = duckdb.connect()
        rows = con.sql(f"SELECT COUNT(*) FROM read_csv_auto('{output}')").fetchone()
        assert rows[0] == 5
        con.close()

    def test_with_where(self, tmp_path):
        output = tmp_path / "filtered.parquet"
        result = runner.invoke(
            app,
            [
                "convert",
                str(FIXTURES / "sample.csv"),
                str(output),
                "--where",
                "age > 30",
            ],
        )
        assert result.exit_code == 0
        assert output.exists()

        con = duckdb.connect()
        rows = con.sql(f"SELECT COUNT(*) FROM read_parquet('{output}')").fetchone()
        assert rows[0] == 1
        con.close()

    def test_source_not_found(self, tmp_path):
        result = runner.invoke(
            app,
            ["convert", str(tmp_path / "nope.csv"), str(tmp_path / "out.parquet")],
        )
        assert result.exit_code == 1
        assert "not found" in (result.stdout + result.stderr).lower()

    def test_unsupported_output_format(self, tmp_path):
        result = runner.invoke(
            app,
            [
                "convert",
                str(FIXTURES / "sample.csv"),
                str(tmp_path / "out.xyz"),
            ],
        )
        assert result.exit_code == 1
        assert "unsupported" in (result.stdout + result.stderr).lower()
