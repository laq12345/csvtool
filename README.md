# dv — terminal data file toolkit

Quick preview, explore, and convert tabular data files from the terminal. Powered by DuckDB.

## Install

```bash
pip install -e .
```

Or with pixi:

```bash
pixi install
```

## Quick start

```bash
# Peek at a file
dv data.csv

# First 20 rows
dv data.csv -p 20

# Column statistics
dv data.csv -s

# Pipe data
cat data.csv | dv -p 10
```

## Commands

### `peek` — preview and explore

```bash
dv data.csv              # Structure: columns, types, row count
dv data.csv -p 10        # First 10 rows
dv data.csv -s           # Column statistics (min/max/mean/unique/null)
dv -v data.csv           # Debug logging
```

### `convert` — format conversion

```bash
dv convert a.csv b.parquet
dv convert a.csv b.json
dv convert a.parquet b.csv --where "score > 90"
```

Output format is determined by file extension.

### `cat` — concatenate files by row

```bash
dv cat a.csv b.csv c.csv
dv cat part*.csv -o merged.parquet
dv cat a.csv b.csv -p 20
```

Uses `UNION ALL BY NAME` — columns are aligned by name, missing columns filled with NULL.

### `join` — merge two files by column

```bash
dv join a.csv b.csv                        # Auto-detect common column
dv join a.csv b.csv --on gene              # Same-named column
dv join a.csv b.csv --on probe=gene        # Different column names
dv join a.csv b.csv --on id --how left -o joined.parquet
```

Supports `inner` (default), `left`, `right`, `outer`.

### `sql` — raw SQL queries

```bash
dv sql "FROM 'data.csv' SELECT * WHERE score > 90"
dv sql "SELECT gene, AVG(expr) FROM 'data.csv' GROUP BY gene" -o result.parquet
```

## Supported formats

| Format | Extensions |
|--------|-----------|
| CSV / TSV | `.csv` `.tsv` `.txt` `.tab` |
| Parquet | `.parquet` |
| JSON / JSONL | `.json` `.jsonl` |
| Excel | `.xlsx` `.xls` |

## Tech stack

- [DuckDB](https://duckdb.org/) — data engine
- [Typer](https://typer.tiangolo.com/) — CLI framework
- [Rich](https://rich.readthedocs.io/) — terminal output
- [Loguru](https://github.com/Delgan/loguru) — logging
