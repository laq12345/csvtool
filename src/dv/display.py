"""Rich-based display functions for dv output."""

from typing import Any
import duckdb
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from loguru import logger


def _create_console() -> Console:
    """Create a Rich Console instance."""
    return Console()


def _results_to_table(
    columns: list[str],
    rows: list[tuple[Any, ...]],
    title: str = "",
    column_types: list[str] | None = None,
) -> Table:
    """Convert query results to a Rich Table.

    Args:
        columns: Column names.
        rows: Row data as tuples.
        title: Optional table title.
        column_types: Optional column type strings, shown below column names.
    """
    table = Table(title=title, expand=False)

    if column_types and len(column_types) == len(columns):
        for name, dtype in zip(columns, column_types):
            header = f"{name}\n[dim italic]{dtype}[/dim italic]"
            table.add_column(header, overflow="ellipsis", no_wrap=False)
    else:
        for col_name in columns:
            table.add_column(str(col_name), overflow="ellipsis", no_wrap=False)

    for row in rows:
        table.add_row(*[str(v) if v is not None else "" for v in row])

    return table


def display_structure(
    con: duckdb.DuckDBPyConnection,
    file_name: str,
    format_name: str,
    file_size: str,
) -> None:
    """Display file structure overview: columns, types, row count.

    Args:
        con: Active DuckDB connection with 'data' table registered.
        file_name: Name of the source file.
        format_name: Detected format (csv, parquet, etc.).
        file_size: Human-readable file size string.
    """
    console = _create_console()

    # Get column info via DESCRIBE
    desc_result = con.sql("DESCRIBE SELECT * FROM data").fetchall()
    # Get row count
    count_result = con.sql("SELECT COUNT(*) AS cnt FROM data").fetchone()
    row_count = count_result[0] if count_result else 0

    # Build column info table
    col_table = Table(expand=False, show_header=True, header_style="bold cyan")
    col_table.add_column("Column", style="cyan")
    col_table.add_column("Type")
    col_table.add_column("Nullable")

    for row in desc_result:
        col_name, col_type, nullable = row[0], row[1], row[2]
        col_table.add_row(str(col_name), str(col_type), str(nullable))

    # Summary stats in subtitle
    col_count = len(desc_result)

    # Build panel
    panel = Panel(
        col_table,
        title=f"[bold]{file_name}[/bold]",
        subtitle=(
            f"{format_name.upper()} | {file_size} | "
            f"{row_count} rows × {col_count} columns"
        ),
        border_style="green",
        expand=False,
    )

    console.print(panel)
    logger.debug("Displayed structure: {} cols, {} rows", col_count, row_count)


def display_preview(
    con: duckdb.DuckDBPyConnection,
    n_rows: int = 10,
) -> None:
    """Display first N rows of the registered table.

    Args:
        con: Active DuckDB connection with 'data' table registered.
        n_rows: Number of rows to display.
    """
    console = _create_console()

    result = con.sql(f"SELECT * FROM data LIMIT {n_rows}")
    columns = [desc[0] for desc in result.description]
    types = [desc[1] for desc in result.description]
    rows = result.fetchall()

    table = _results_to_table(
        columns, rows,
        title=f"Preview (first {len(rows)} rows)",
        column_types=types,
    )
    console.print(table)
    logger.debug("Displayed preview: {} rows", len(rows))


def display_stats(con: duckdb.DuckDBPyConnection) -> None:
    """Display column statistics using DuckDB SUMMARIZE.

    Args:
        con: Active DuckDB connection with 'data' table registered.
    """
    console = _create_console()

    try:
        result = con.sql("SUMMARIZE SELECT * FROM data")
    except Exception:
        # SUMMARIZE may fail for some formats; fall back to DESCRIBE
        logger.warning("SUMMARIZE not supported; falling back to DESCRIBE")
        result = con.sql("DESCRIBE SELECT * FROM data")

    columns = [desc[0] for desc in result.description]
    rows = result.fetchall()

    table = _results_to_table(columns, rows, title="Column Statistics")
    console.print(table)
    logger.debug("Displayed stats: {} columns", len(columns))


def display_query_result(
    con: duckdb.DuckDBPyConnection,
    query: str,
) -> None:
    """Execute a SQL query and display results.

    Args:
        con: Active DuckDB connection.
        query: SQL query string.
    """
    console = _create_console()

    result = con.sql(query)
    columns = [desc[0] for desc in result.description]
    types = [desc[1] for desc in result.description]
    rows = result.fetchall()

    table = _results_to_table(
        columns, rows,
        title="Query Result",
        column_types=types,
    )
    console.print(table)
    logger.debug("Displayed query result: {} rows", len(rows))
