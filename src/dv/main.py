"""dv - Terminal data file preview, exploration, and conversion tool."""

import re
import sys
from pathlib import Path
import duckdb
import typer
from loguru import logger

from dv.utils import setup_logging
from dv.reader import register_file
from dv.display import (
    display_structure,
    display_preview,
    display_stats,
    display_query_result,
)

app = typer.Typer(
    name="dv",
    help="Preview, explore, and convert tabular data files from the terminal.",
)

COPY_FORMATS: dict[str, str] = {
    ".csv": "FORMAT csv, HEADER true",
    ".tsv": "FORMAT csv, HEADER true, DELIMITER '\\t'",
    ".txt": "FORMAT csv, HEADER true, DELIMITER '\\t'",
    ".tab": "FORMAT csv, HEADER true, DELIMITER '\\t'",
    ".parquet": "FORMAT parquet",
    ".json": "FORMAT json",
    ".jsonl": "FORMAT json, ARRAY false",
}

FILE_PATH_PATTERN = re.compile(
    r"""['"]([^'"]+\.(?:csv|tsv|txt|tab|parquet|jsonl?|xlsx?))['"]""",
    re.IGNORECASE,
)

VALID_JOIN_HOW = {"inner", "left", "right", "outer"}


def _format_size(size_bytes: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} TB"


def _resolve_output(path: str) -> tuple[Path, str]:
    """Validate output path and return (resolved_path, copy_opts_string)."""
    dst_path = Path(path)
    dst_ext = dst_path.suffix.lower()
    copy_opts = COPY_FORMATS.get(dst_ext)
    if copy_opts is None:
        logger.error(
            "Unsupported output format: '{}'. Supported: {}",
            dst_ext,
            ", ".join(sorted(COPY_FORMATS.keys())),
        )
        raise typer.Exit(code=1)
    dst_path.parent.mkdir(parents=True, exist_ok=True)
    return dst_path, copy_opts


def _find_and_register_files(con: duckdb.DuckDBPyConnection, query: str) -> None:
    seen = set()
    for match in FILE_PATH_PATTERN.finditer(query):
        file_str = match.group(1)
        if file_str in seen:
            continue
        seen.add(file_str)
        file_path = Path(file_str)
        if file_path.exists():
            table_name = file_path.stem.replace(".", "_")
            register_file(con, file_path, table_name)


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    verbose: bool = typer.Option(False, "-v", "--verbose", help="Enable debug logging"),
    preview: int = typer.Option(0, "-p", "--preview", help="Show first N rows"),
    stats: bool = typer.Option(False, "-s", "--stats", help="Show column statistics"),
):
    """dv - Terminal data file tool powered by DuckDB.

    Examples:
        dv data.csv                 Show file structure (auto-peek)
        dv peek data.csv -p 10      Show first 10 rows
        dv convert a.csv b.parquet  Convert CSV to Parquet
        dv sql "FROM 'data.csv' SELECT * LIMIT 5"
        cat data.csv | dv           Pipe data to auto-peek
        cat data.csv | dv -p 10     Pipe with preview
    """
    setup_logging(verbose)
    if ctx.invoked_subcommand is None and not sys.stdin.isatty():
        ctx.invoke(peek, file=None, preview=preview, stats=stats)


@app.command()
def peek(
    file: str = typer.Argument(None, help="Path to the data file (or stdin if omitted)"),
    preview: int = typer.Option(0, "-p", "--preview", help="Show first N rows"),
    stats: bool = typer.Option(False, "-s", "--stats", help="Show column statistics"),
):
    """Preview and explore a data file.

    Without flags, shows structure overview (columns, types, row count).
    Use -p/--preview to see the first N rows.
    Use -s/--stats to see column statistics.

    If no file is given, reads from stdin.
    """
    import tempfile

    tmp_file = None
    if file is None:
        if sys.stdin.isatty():
            logger.error("No file specified and stdin is a terminal. Pipe data or provide a file.")
            raise typer.Exit(code=1)
        data = sys.stdin.buffer.read()
        tmp_file = tempfile.NamedTemporaryFile(suffix=".csv", delete=False)
        tmp_file.write(data)
        tmp_file.close()
        file_path = Path(tmp_file.name)
        file_size = _format_size(len(data))
        display_name = "stdin"
    else:
        file_path = Path(file)
        display_name = file_path.name
        try:
            file_size = _format_size(file_path.stat().st_size)
        except FileNotFoundError:
            logger.error("File not found: {}", file_path)
            raise typer.Exit(code=1)

    con = duckdb.connect()
    try:
        fmt = register_file(con, file_path)
        if preview > 0:
            display_preview(con, n_rows=preview)
        elif stats:
            display_stats(con)
        else:
            display_structure(con, display_name, fmt, file_size)
    except ValueError as e:
        logger.error(str(e))
        raise typer.Exit(code=1)
    except Exception as e:
        logger.error("Failed to process file: {}", e)
        raise typer.Exit(code=1)
    finally:
        con.close()
        if tmp_file:
            Path(tmp_file.name).unlink(missing_ok=True)


@app.command()
def convert(
    src: str = typer.Argument(..., help="Source file path"),
    dst: str = typer.Argument(..., help="Destination file path"),
    where: str = typer.Option(None, "--where", help="SQL WHERE clause to filter rows"),
):
    """Convert a data file to another format.

    Output format is determined by the destination file extension.
    Supported: .csv, .tsv, .parquet, .json, .jsonl
    """
    src_path = Path(src)

    if not src_path.exists():
        logger.error("Source file not found: {}", src_path)
        raise typer.Exit(code=1)

    dst_path, copy_opts = _resolve_output(dst)

    con = duckdb.connect()
    try:
        register_file(con, src_path)
        dst_abs = str(dst_path.resolve())
        query = (
            f"COPY (SELECT * FROM data WHERE {where}) TO '{dst_abs}' ({copy_opts})"
            if where
            else f"COPY (SELECT * FROM data) TO '{dst_abs}' ({copy_opts})"
        )
        con.sql(query)
        logger.info("Converted {} -> {}", src_path.name, dst_path.name)
    except Exception as e:
        logger.error("Conversion failed: {}", e)
        raise typer.Exit(code=1)
    finally:
        con.close()


@app.command()
def sql(
    query: str = typer.Argument(
        ..., help="SQL query. Use 'filename' to reference files."
    ),
    output: str = typer.Option(
        None, "-o", "--output", help="Save results to file (format from extension)"
    ),
):
    """Run a SQL query directly on data files.

    Files referenced in the query (e.g., 'data.csv') are automatically registered.

    Without -o, displays results. With -o, saves to file.

    Example:
dv sql "FROM 'data.csv' SELECT * WHERE age > 30"
dv sql "SELECT * FROM 'data.csv'" -o result.parquet
    """
    con = duckdb.connect()
    tmp_path = None
    try:
        if not sys.stdin.isatty():
            data = sys.stdin.buffer.read()
            if data:
                import tempfile
                tmp = tempfile.NamedTemporaryFile(suffix=".csv", delete=False)
                tmp.write(data)
                tmp.close()
                tmp_path = tmp.name
                register_file(con, Path(tmp_path), "stdin")
        _find_and_register_files(con, query)
        if output:
            dst_path, copy_opts = _resolve_output(output)
            dst_abs = str(dst_path.resolve())
            con.sql(f"CREATE OR REPLACE TABLE _copy_tmp AS {query}")
            con.sql(f"COPY (SELECT * FROM _copy_tmp) TO '{dst_abs}' ({copy_opts})")
            con.sql("DROP TABLE IF EXISTS _copy_tmp")
            logger.info("Saved to {}", dst_path.name)
        else:
            display_query_result(con, query)
    except Exception as e:
        logger.error("SQL execution failed: {}", e)
        raise typer.Exit(code=1)
    finally:
        con.close()
        if tmp_path:
            Path(tmp_path).unlink(missing_ok=True)


@app.command()
def cat(
    files: list[str] = typer.Argument(..., help="Files to concatenate (2+)"),
    preview: int = typer.Option(0, "-p", "--preview", help="Show first N rows"),
    stats: bool = typer.Option(False, "-s", "--stats", help="Show column statistics"),
    output: str = typer.Option(
        None, "-o", "--output", help="Save to file (format from extension)"
    ),
):
    """Concatenate multiple data files by row (UNION ALL BY NAME).

    Columns are aligned by name. Missing columns in any file are filled with NULL.

    Examples:
dv cat a.csv b.csv               Concat and preview structure
dv cat a.csv b.csv -p 10         Concat and preview 10 rows
dv cat part*.csv -o merged.parquet
    """
    if len(files) < 2:
        logger.error("Need at least 2 files to concatenate, got {}", len(files))
        raise typer.Exit(code=1)

    con = duckdb.connect()
    try:
        for i, f in enumerate(files):
            fp = Path(f)
            if not fp.exists():
                logger.error("File not found: {}", fp)
                raise typer.Exit(code=1)
            register_file(con, fp, f"src_{i}")

        unions = "\n  UNION ALL BY NAME\n".join(
            f"SELECT * FROM src_{i}" for i in range(len(files))
        )
        con.sql(f"CREATE OR REPLACE VIEW data AS {unions}")

        first_name = Path(files[0]).name
        total_size = _format_size(sum(Path(f).stat().st_size for f in files))

        if output:
            dst_path, copy_opts = _resolve_output(output)
            dst_abs = str(dst_path.resolve())
            con.sql(f"COPY (SELECT * FROM data) TO '{dst_abs}' ({copy_opts})")
            logger.info("Saved to {}", dst_path.name)
        elif preview > 0:
            display_preview(con, n_rows=preview)
        elif stats:
            display_stats(con)
        else:
            count = con.sql("SELECT COUNT(*) FROM data").fetchone()[0]
            display_structure(
                con, f"{first_name} + {len(files) - 1} more", "CONCAT", total_size
            )
            logger.debug("Concatenated {} files: {} rows", len(files), count)
    except typer.Exit:
        raise
    except Exception as e:
        logger.error("Concatenation failed: {}", e)
        raise typer.Exit(code=1)
    finally:
        con.close()


@app.command()
def join(
    a: str = typer.Argument(..., help="Left table file path"),
    b: str = typer.Argument(..., help="Right table file path"),
    on: str = typer.Option(
        None, "--on", help="Join column: 'col' (same name) or 'a_col=b_col' (different names). Auto-detects if omitted."
    ),
    how: str = typer.Option(
        "inner", "--how", help="Join type: inner, left, right, outer"
    ),
    preview: int = typer.Option(0, "-p", "--preview", help="Show first N rows"),
    stats: bool = typer.Option(False, "-s", "--stats", help="Show column statistics"),
    output: str = typer.Option(
        None, "-o", "--output", help="Save to file (format from extension)"
    ),
):
    """Join two data files by a common column.

    Without --on, automatically detects a unique common column.
    Use --how to choose join type (default: inner).

    Examples:
dv join deg.csv meta.csv                    Auto-detect join column
dv join deg.csv meta.csv --on gene          Same-named column
dv join expr.csv meta.csv --on probe=gene   Different column names
dv join a.csv b.csv --on id --how left -o joined.parquet
    """
    a_path, b_path = Path(a), Path(b)

    for p, label in [(a_path, "Left"), (b_path, "Right")]:
        if not p.exists():
            logger.error("{} file not found: {}", label, p)
            raise typer.Exit(code=1)

    how_lower = how.lower()
    if how_lower not in VALID_JOIN_HOW:
        logger.error(
            "Invalid --how '{}'. Must be one of: {}",
            how,
            ", ".join(sorted(VALID_JOIN_HOW)),
        )
        raise typer.Exit(code=1)

    how_sql = {"inner": "INNER", "left": "LEFT", "right": "RIGHT", "outer": "FULL"}[how_lower]

    con = duckdb.connect()
    try:
        register_file(con, a_path, "a")
        register_file(con, b_path, "b")

        on_clause = _resolve_join_on(con, on)
        con.sql(
            f"CREATE OR REPLACE VIEW data AS "
            f"SELECT * FROM a {how_sql} JOIN b {on_clause}"
        )

        total_size = _format_size(a_path.stat().st_size + b_path.stat().st_size)
        count = con.sql("SELECT COUNT(*) FROM data").fetchone()[0]

        if output:
            dst_path, copy_opts = _resolve_output(output)
            dst_abs = str(dst_path.resolve())
            con.sql(f"COPY (SELECT * FROM data) TO '{dst_abs}' ({copy_opts})")
            logger.info("Saved to {}", dst_path.name)
        elif preview > 0:
            display_preview(con, n_rows=preview)
        elif stats:
            display_stats(con)
        else:
            display_structure(
                con,
                f"{a_path.name} ⋈ {b_path.name}",
                f"JOIN ({how_lower})",
                total_size,
            )
            logger.debug("Joined: {} rows ({} JOIN)", count, how_lower)
    except typer.Exit:
        raise
    except Exception as e:
        logger.error("Join failed: {}", e)
        raise typer.Exit(code=1)
    finally:
        con.close()


def _resolve_join_on(con: duckdb.DuckDBPyConnection, on: str | None) -> str:
    """Resolve the ON/USING clause for a JOIN.

    Returns a SQL fragment like "USING (gene)" or "ON a.probe = b.gene".
    """
    if on is not None and "=" in on:
        parts = on.split("=", 1)
        left_col, right_col = parts[0].strip(), parts[1].strip()
        return f"ON a.{left_col} = b.{right_col}"

    if on is not None:
        return f"USING ({on})"

    a_cols = {
        r[0]
        for r in con.sql(
            "SELECT column_name FROM information_schema.columns WHERE table_name='a'"
        ).fetchall()
    }
    b_cols = {
        r[0]
        for r in con.sql(
            "SELECT column_name FROM information_schema.columns WHERE table_name='b'"
        ).fetchall()
    }
    common = sorted(a_cols & b_cols)

    if len(common) == 0:
        logger.error("No common columns found between the two files. Use --on to specify the join columns.")
        raise typer.Exit(code=1)
    if len(common) == 1:
        return f"USING ({common[0]})"

    logger.error(
        "Multiple common columns found: {}. Use --on to specify which one to join on.",
        ", ".join(common),
    )
    raise typer.Exit(code=1)


def _patch_default_peek():
    """If the first non-flag argument is a file path, insert 'peek' before it."""
    known = {
        "peek", "convert", "sql", "cat", "join",
        "--help", "-h", "--show-completion", "--install-completion",
    }
    if any(a in known for a in sys.argv[1:]):
        return
    for i, arg in enumerate(sys.argv[1:], start=1):
        if arg.startswith("-"):
            continue
        path = Path(arg)
        if path.exists() and path.is_file():
            sys.argv.insert(i, "peek")
            return


def main_cli():
    """Entry point for console_scripts and __main__."""
    _patch_default_peek()
    app()


if __name__ == "__main__":
    main_cli()
