"""Format detection and DuckDB file registration for dv."""

from pathlib import Path
import duckdb
from loguru import logger


# Extension -> format name mapping for DuckDB read functions
FORMAT_MAP: dict[str, str] = {
    ".csv": "csv",
    ".tsv": "tsv",
    ".txt": "tsv",
    ".tab": "tsv",
    ".parquet": "parquet",
    ".json": "json",
    ".jsonl": "json",
    ".xlsx": "excel",
    ".xls": "excel",
}

# Extension -> SQL read function template
READ_SQL_TEMPLATES: dict[str, str] = {
    "csv": "read_csv_auto('{path}')",
    "tsv": "read_csv_auto('{path}')",
    "parquet": "read_parquet('{path}')",
    "json": "read_json_auto('{path}')",
}


def detect_format(file_path: Path) -> str:
    """Detect data format from file extension.

    Args:
        file_path: Path to the data file.

    Returns:
        Format name string (e.g. 'csv', 'parquet', 'excel').

    Raises:
        ValueError: If the file extension is not supported.
    """
    ext = file_path.suffix.lower()
    if not ext:
        raise ValueError(
            f"Cannot detect format: '{file_path}' has no file extension. "
            f"Supported extensions: {', '.join(sorted(set(FORMAT_MAP.values())))}\n"
            f"Supported file types: {', '.join(sorted(FORMAT_MAP.keys()))}"
        )

    fmt = FORMAT_MAP.get(ext)
    if fmt is None:
        raise ValueError(
            f"Unsupported file format: '{ext}'. "
            f"Supported extensions: {', '.join(sorted(FORMAT_MAP.keys()))}"
        )
    return fmt


def init_excel_support(con: duckdb.DuckDBPyConnection) -> None:
    """Install and load DuckDB excel extension if not already available.

    Args:
        con: Active DuckDB connection.
    """
    try:
        con.sql("LOAD excel")
        logger.debug("excel extension loaded")
    except Exception:
        logger.debug("Installing excel extension...")
        con.sql("INSTALL excel")
        con.sql("LOAD excel")
        logger.debug("excel extension installed and loaded")


def register_file(
    con: duckdb.DuckDBPyConnection,
    file_path: Path,
    table_name: str = "data",
) -> str:
    """Register a data file as a DuckDB view.

    Args:
        con: Active DuckDB connection.
        file_path: Path to the data file.
        table_name: Name for the registered view (default: 'data').

    Returns:
        The format name used to read the file.

    Raises:
        FileNotFoundError: If the file does not exist.
        ValueError: If the format is not supported.
    """
    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    fmt = detect_format(file_path)
    path_str = str(file_path.resolve())
    logger.debug("Registering {} as format={} table={}", path_str, fmt, table_name)

    if fmt == "excel":
        init_excel_support(con)
        con.sql(
            f"CREATE OR REPLACE VIEW {table_name} AS "
            f"SELECT * FROM st_read('{path_str}')"
        )
    else:
        read_fn = READ_SQL_TEMPLATES[fmt].format(path=path_str)
        con.sql(f"CREATE OR REPLACE VIEW {table_name} AS SELECT * FROM {read_fn}")

    logger.info(
        "Registered '{}' as table '{}' (format: {})", file_path.name, table_name, fmt
    )
    return fmt
