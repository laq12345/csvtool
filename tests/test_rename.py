"""Tests for dv rename command."""

from pathlib import Path
from typer.testing import CliRunner
from dv.main import app

runner = CliRunner()
FIXTURES = Path(__file__).parent / "fixtures"


class TestRename:
    def test_rename_single_column(self):
        result = runner.invoke(
            app,
            ["rename", str(FIXTURES / "sample.csv"), "id=gene_id"],
        )
        assert result.exit_code == 0
        assert "gene_id" in result.stdout

    def test_rename_multiple_columns(self):
        result = runner.invoke(
            app,
            ["rename", str(FIXTURES / "sample.csv"), "id=gene_id,name=symbol"],
        )
        assert result.exit_code == 0
        assert "gene_id" in result.stdout
        assert "symbol" in result.stdout

    def test_rename_not_found(self):
        result = runner.invoke(
            app,
            ["rename", str(FIXTURES / "sample.csv"), "nonexistent=foo"],
        )
        assert result.exit_code == 1

    def test_rename_save(self, tmp_path):
        output = tmp_path / "renamed.csv"
        result = runner.invoke(
            app,
            [
                "rename",
                str(FIXTURES / "sample.csv"),
                "id=gene_id",
                "-o",
                str(output),
            ],
        )
        assert result.exit_code == 0
        assert output.exists()

    def test_rename_file_not_found(self):
        result = runner.invoke(
            app,
            ["rename", str(FIXTURES / "nonexistent.csv"), "id=x"],
        )
        assert result.exit_code == 1
