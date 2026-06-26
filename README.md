# dv — terminal data file toolkit

Quick preview, explore, and convert tabular data files from the terminal. Powered by DuckDB.

## Install

**From GitHub Release** (recommended):

```bash
pip install https://github.com/laq12345/dv/releases/latest/download/dv-0.2.0-py3-none-any.whl
```

**From source**:

```bash
git clone https://github.com/laq12345/dv.git
cd dv
pip install .
```

**With pixi**:

```bash
pixi install
```

## Quick start

```bash
# Default: first 10 rows
dv data.csv

# Structure overview (columns, types, NULLs)
dv data.csv -I

# Select columns, sort, limit
dv data.csv -c gene,avg_log2FC --sort "avg_log2FC DESC" -p 20

# Column statistics
dv data.csv -s

# Pipe data
cat data.csv | dv -p 10
```

## Commands

### `peek` — preview and explore

```bash
dv data.csv                    # First 10 rows (default)
dv data.csv -I                 # Structure: columns, types, NULL count
dv data.csv -p 50              # First 50 rows
dv data.csv -c id,name -p 10   # Select columns
dv data.csv --sort "score DESC" # Sort by column
dv data.csv -s                 # Column statistics
dv -v data.csv                 # Debug logging
```

### `search` — regex search

```bash
dv search "TP53" data.csv                    # Search all text columns
dv search "TP53|BRCA1" data.csv --in gene    # Search specific column
dv search "TP53" data.csv -i                 # Case-insensitive
dv search "p_value" data.csv -l              # Literal text (not regex)
```

### `rename` — rename columns

```bash
dv rename data.csv column0=gene                # Rename one column
dv rename data.csv "id=gene_id,name=symbol"    # Rename multiple
dv rename data.csv p_val_adj=padj -o cleaned.csv
```

### `convert` — format conversion

```bash
dv convert a.csv b.parquet
dv convert a.csv b.xlsx
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
