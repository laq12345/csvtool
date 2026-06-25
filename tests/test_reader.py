"""Tests for csvtool.reader module."""

from pathlib import Path
import duckdb
import pytest
from dv.reader import detect_format, FORMAT_MAP, register_file


class TestDetectFormat:
    def test_csv(self):
        assert detect_format(Path("data.csv")) == "csv"

    def test_tsv(self):
        assert detect_format(Path("data.tsv")) == "tsv"

    def test_txt(self):
        assert detect_format(Path("data.txt")) == "tsv"

    def test_parquet(self):
        assert detect_format(Path("data.parquet")) == "parquet"

    def test_json(self):
        assert detect_format(Path("data.json")) == "json"

    def test_jsonl(self):
        assert detect_format(Path("data.jsonl")) == "json"

    def test_xlsx(self):
        assert detect_format(Path("data.xlsx")) == "excel"

    def test_no_extension(self):
        with pytest.raises(ValueError, match="no file extension"):
            detect_format(Path("noext"))

    def test_unknown_extension(self):
        with pytest.raises(ValueError, match="Unsupported file format"):
            detect_format(Path("data.xyz"))

    def test_case_insensitive(self):
        assert detect_format(Path("DATA.CSV")) == "csv"
        assert detect_format(Path("Data.Parquet")) == "parquet"


class TestRegisterFile:
    def test_register_csv(self, tmp_path):
        csv_file = tmp_path / "test.csv"
        csv_file.write_text("a,b\n1,2\n3,4")

        con = duckdb.connect()
        fmt = register_file(con, csv_file)
        assert fmt == "csv"
        result = con.sql("SELECT COUNT(*) FROM data").fetchone()
        assert result[0] == 2
        con.close()

    def test_register_parquet(self, tmp_path):
        csv_file = tmp_path / "test.csv"
        csv_file.write_text("x,y\n10,20\n30,40")

        con = duckdb.connect()
        pq_file = tmp_path / "test.parquet"
        con.sql(
            f"COPY (SELECT * FROM read_csv_auto('{csv_file}')) "
            f"TO '{pq_file}' (FORMAT parquet)"
        )
        con.close()

        con2 = duckdb.connect()
        fmt = register_file(con2, pq_file)
        assert fmt == "parquet"
        result = con2.sql("SELECT COUNT(*) FROM data").fetchone()
        assert result[0] == 2
        con2.close()

    def test_file_not_found(self, tmp_path):
        con = duckdb.connect()
        with pytest.raises(FileNotFoundError, match="File not found"):
            register_file(con, tmp_path / "nonexistent.csv")
        con.close()


class TestFormatMap:
    def test_all_keys_have_values(self):
        for ext, fmt in FORMAT_MAP.items():
            assert ext.startswith(".")
            assert isinstance(fmt, str)
            assert len(fmt) > 0
