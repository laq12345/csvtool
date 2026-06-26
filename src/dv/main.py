"""dv - Terminal data file preview, exploration, and conversion tool."""

import re
import sys
from pathlib import Path
import duckdb
import typer
from loguru import logger

from dv.utils import setup_logging
from dv.reader import register_file, init_excel_support
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
    ".xls": "FORMAT xlsx, HEADER true",
    ".xlsx": "FORMAT xlsx, HEADER true",
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


def _resolve_output(path: str, con: duckdb.DuckDBPyConnection | None = None) -> tuple[Path, str]:
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
    if con and dst_ext in (".xls", ".xlsx"):
        init_excel_support(con)
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
    preview: int = typer.Option(10, "-p", "--preview", help="Show first N rows"),
    stats: bool = typer.Option(False, "-s", "--stats", help="Show column statistics"),
    columns: str = typer.Option(None, "-c", "--columns", help="Comma-separated columns to show"),
    sort: str = typer.Option(None, "--sort", help="Sort by column (ASC/DESC)"),
    info: bool = typer.Option(False, "-I", "--info", help="Show structure overview instead of preview"),
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
        ctx.invoke(peek, file=None, preview=preview, stats=stats, columns=columns, sort=sort, info=info)


@app.command()
def peek(
    file: str = typer.Argument(None, help="Path to the data file (or stdin if omitted)"),
    preview: int = typer.Option(10, "-p", "--preview", help="Show first N rows"),
    stats: bool = typer.Option(False, "-s", "--stats", help="Show column statistics"),
    columns: str = typer.Option(None, "-c", "--columns", help="Comma-separated columns to show"),
    sort: str = typer.Option(None, "--sort", help="Sort by column (optionally add ASC/DESC)"),
    info: bool = typer.Option(False, "-I", "--info", help="Show structure overview (columns, types, NULLs)"),
):
    """Preview and explore a data file.

    Default shows first 10 rows. Use -I/--info for structure overview.
    Use -p/--preview to change row count (0 = show structure).
    Use -s/--stats to see column statistics.
    Use -c/--columns to select specific columns.
    Use --sort to order by a column.

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
        if preview < 0:
            logger.error("Preview count must be >= 0, got {}", preview)
            raise typer.Exit(code=1)
        fmt = register_file(con, file_path, "_src")
        if sort or columns:
            select = "SELECT *" if not columns else f"SELECT {', '.join(c.strip() for c in columns.split(','))}"
            order = f" ORDER BY {sort}" if sort else ""
            con.sql(f"CREATE OR REPLACE VIEW data AS {select} FROM _src{order}")
        else:
            con.sql("CREATE OR REPLACE VIEW data AS SELECT * FROM _src")
        if info or preview == 0:
            display_structure(con, display_name, fmt, file_size)
        elif stats:
            display_stats(con)
        else:
            display_preview(con, n_rows=preview)
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

    con = duckdb.connect()
    try:
        dst_path, copy_opts = _resolve_output(dst, con)
        if dst_path.exists():
            logger.warning("Overwriting existing file: {}", dst_path)
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
            dst_path, copy_opts = _resolve_output(output, con)
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
    preview: int = typer.Option(10, "-p", "--preview", help="Show first N rows"),
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
        if preview < 0:
            logger.error("Preview count must be >= 0, got {}", preview)
            raise typer.Exit(code=1)
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
            dst_path, copy_opts = _resolve_output(output, con)
            dst_abs = str(dst_path.resolve())
            con.sql(f"COPY (SELECT * FROM data) TO '{dst_abs}' ({copy_opts})")
            logger.info("Saved to {}", dst_path.name)
        elif preview == 0:
            count = con.sql("SELECT COUNT(*) FROM data").fetchone()[0]
            display_structure(
                con, f"{first_name} + {len(files) - 1} more", "CONCAT", total_size
            )
            logger.debug("Concatenated {} files: {} rows", len(files), count)
        elif stats:
            display_stats(con)
        else:
            display_preview(con, n_rows=preview)
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
    preview: int = typer.Option(10, "-p", "--preview", help="Show first N rows"),
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
        if preview < 0:
            logger.error("Preview count must be >= 0, got {}", preview)
            raise typer.Exit(code=1)
        register_file(con, a_path, "a")
        register_file(con, b_path, "b")

        on_clause = _resolve_join_on(con, on)
        a_cols = _get_column_names(con, "a")
        b_cols = _get_column_names(con, "b")
        join_col_raw = _get_join_column(on, a_cols, b_cols)

        # Build explicit column list to avoid duplicate column errors
        select_cols = [f"a.{c}" for c in a_cols]
        for c in b_cols:
            if c != join_col_raw:
                select_cols.append(f"b.{c} AS {c}_2" if c in a_cols else f"b.{c}")

        col_list = ", ".join(select_cols)
        con.sql(
            f"CREATE OR REPLACE VIEW data AS "
            f"SELECT {col_list} FROM a {how_sql} JOIN b {on_clause}"
        )

        total_size = _format_size(a_path.stat().st_size + b_path.stat().st_size)
        count = con.sql("SELECT COUNT(*) FROM data").fetchone()[0]

        if output:
            dst_path, copy_opts = _resolve_output(output, con)
            dst_abs = str(dst_path.resolve())
            con.sql(f"COPY (SELECT * FROM data) TO '{dst_abs}' ({copy_opts})")
            logger.info("Saved to {}", dst_path.name)
        elif preview == 0:
            display_structure(
                con,
                f"{a_path.name} ⋈ {b_path.name}",
                f"JOIN ({how_lower})",
                total_size,
            )
            logger.debug("Joined: {} rows ({} JOIN)", count, how_lower)
        elif stats:
            display_stats(con)
        else:
            display_preview(con, n_rows=preview)
    except typer.Exit:
        raise
    except Exception as e:
        logger.error("Join failed: {}", e)
        raise typer.Exit(code=1)
    finally:
        con.close()


@app.command()
def search(
    pattern: str = typer.Argument(..., help="Regex pattern to search for"),
    file: str = typer.Argument(..., help="Path to the data file"),
    column: str = typer.Option(None, "--in", help="Limit search to one column"),
    ignore_case: bool = typer.Option(False, "-i", "--ignore-case", help="Case-insensitive search"),
    literal: bool = typer.Option(False, "-l", "--literal", help="Treat pattern as literal text, not regex"),
    preview: int = typer.Option(10, "-p", "--preview", help="Show first N matching rows"),
    output: str = typer.Option(None, "-o", "--output", help="Save results to file"),
):
    """Search for rows matching a regex pattern.

    Searches all text columns unless --in is specified.
    Use -i for case-insensitive matching.

    Examples:
        dv search "TP53" data.csv
        dv search "TP53|BRCA1" data.csv --in gene -i
    """
    file_path = Path(file)
    if not file_path.exists():
        logger.error("File not found: {}", file_path)
        raise typer.Exit(code=1)

    con = duckdb.connect()
    try:
        if preview < 0:
            logger.error("Preview count must be >= 0, got {}", preview)
            raise typer.Exit(code=1)
        register_file(con, file_path, "_src")
        flags = "'i'" if ignore_case else ""
        safe_pattern = pattern.replace("'", "''")
        if literal:
            safe_pattern = re.escape(safe_pattern)
        col_info = con.sql("DESCRIBE SELECT * FROM _src").fetchall()
        col_names = [r[0] for r in col_info]
        col_types = [r[1] for r in col_info]

        if column:
            if column not in col_names:
                logger.error("Column '{}' not found. Available: {}", column, ", ".join(col_names))
                raise typer.Exit(code=1)
            col_type = col_types[col_names.index(column)]
            if "VARCHAR" not in str(col_type).upper():
                logger.error(
                    "Column '{}' is type {}, not text — cannot regex search.",
                    column, col_type
                )
                raise typer.Exit(code=1)
            where = f"WHERE regexp_matches(\"{column}\", '{safe_pattern}'{',' + flags if flags else ''})"
        else:
            str_cols = [c for c, t in zip(col_names, col_types) if "VARCHAR" in str(t).upper()]
            if not str_cols:
                logger.error("No text columns found to search in.")
                raise typer.Exit(code=1)
            conditions = " OR ".join(
                f"regexp_matches(\"{c}\", '{safe_pattern}'{',' + flags if flags else ''})"
                for c in str_cols
            )
            where = f"WHERE {conditions}"

        con.sql(f"CREATE OR REPLACE VIEW data AS SELECT * FROM _src {where}")

        if output:
            dst_path, copy_opts = _resolve_output(output, con)
            dst_abs = str(dst_path.resolve())
            con.sql(f"COPY (SELECT * FROM data) TO '{dst_abs}' ({copy_opts})")
            logger.info("Saved to {}", dst_path.name)
        elif preview > 0:
            display_preview(con, n_rows=preview)
        else:
            display_structure(con, file_path.name, "FILTERED", _format_size(file_path.stat().st_size))
    except typer.Exit:
        raise
    except Exception as e:
        logger.error("Search failed: {}", e)
        raise typer.Exit(code=1)
    finally:
        con.close()


@app.command()
def rename(
    file: str = typer.Argument(..., help="Path to the data file"),
    mapping: str = typer.Argument(..., help="Rename mapping: old=new or old1=new1,old2=new2"),
    output: str = typer.Option(None, "-o", "--output", help="Save to file"),
    info: bool = typer.Option(False, "-I", "--info", help="Show structure overview instead of preview"),
):
    """Rename columns in a data file.

    Examples:
        dv rename data.csv column0=gene
        dv rename data.csv "id=gene_id,name=symbol"
        dv rename data.csv p_val_adj=padj -o cleaned.csv
    """
    file_path = Path(file)
    if not file_path.exists():
        logger.error("File not found: {}", file_path)
        raise typer.Exit(code=1)

    pairs = []
    for part in mapping.split(","):
        if "=" not in part:
            logger.error("Invalid mapping '{}'. Use old=new format.", part.strip())
            raise typer.Exit(code=1)
        old, new = part.split("=", 1)
        pairs.append((old.strip(), new.strip()))

    con = duckdb.connect()
    try:
        fmt = register_file(con, file_path, "_src")
        col_names = [r[0] for r in con.sql("DESCRIBE SELECT * FROM _src").fetchall()]

        select_parts = []
        for old, new in pairs:
            if old not in col_names:
                logger.error("Column '{}' not found. Available: {}", old, ", ".join(col_names))
                raise typer.Exit(code=1)
            select_parts.append(f'"{old}" AS "{new}"')

        renamed = set(old for old, _ in pairs)
        for c in col_names:
            if c not in renamed:
                select_parts.append(f'"{c}"')

        select_str = ", ".join(select_parts)
        con.sql(f"CREATE OR REPLACE VIEW data AS SELECT {select_str} FROM _src")

        if output:
            dst_path, copy_opts = _resolve_output(output, con)
            dst_abs = str(dst_path.resolve())
            con.sql(f"COPY (SELECT * FROM data) TO '{dst_abs}' ({copy_opts})")
            logger.info("Saved to {}", dst_path.name)
        else:
            display_structure(con, file_path.name, fmt.upper(), _format_size(file_path.stat().st_size))
    except typer.Exit:
        raise
    except Exception as e:
        logger.error("Rename failed: {}", e)
        raise typer.Exit(code=1)
    finally:
        con.close()


def _get_column_names(con: duckdb.DuckDBPyConnection, table: str) -> list[str]:
    return [
        r[0]
        for r in con.sql(
            f"SELECT column_name FROM information_schema.columns WHERE table_name='{table}'"
        ).fetchall()
    ]


def _get_join_column(on: str | None, a_cols: list[str], b_cols: list[str]) -> str | None:
    if on is None:
        common = sorted(set(a_cols) & set(b_cols))
        return common[0] if len(common) == 1 else None
    if "=" in on:
        return on.split("=", 1)[0].strip()
    return on


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
    """If the first non-flag argument looks like a file path, insert 'peek' at position 1."""
    known = {
        "peek", "convert", "sql", "cat", "join", "search", "rename",
        "--help", "-h", "--show-completion", "--install-completion",
    }
    if any(a in known for a in sys.argv[1:]):
        return
    for i, arg in enumerate(sys.argv[1:], start=1):
        if arg.startswith("-") or "=" in arg:
            continue
        if "/" in arg or "\\" in arg or "." in arg:
            sys.argv.insert(1, "peek")
            return


def main_cli():
    """Entry point for console_scripts and __main__."""
    _patch_default_peek()
    app()


if __name__ == "__main__":
    main_cli()
