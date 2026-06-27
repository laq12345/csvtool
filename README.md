# dv — 终端表格数据工具

在终端快速预览、探查、转换各种表格数据文件。基于 DuckDB 引擎。

## 安装

**从 GitHub Release 安装**（推荐）：

```bash
pip install https://github.com/laq12345/csvtool/releases/latest/download/dv-0.3.0-py3-none-any.whl
```

**从源码安装**：

```bash
git clone https://github.com/laq12345/csvtool.git
cd csvtool
pip install .
```

**用 pixi**：

```bash
pixi install
```

## 快速开始

```bash
# 默认：显示前 10 行
dv data.csv

# 结构概览（列名、类型、NULL 数）
dv data.csv -I

# 选列、排序、限制行数
dv data.csv -c gene,avg_log2FC --sort "avg_log2FC DESC" -p 20

# 列统计
dv data.csv -s

# 管道输入
cat data.csv | dv -p 10
```

## 命令

### `peek` — 数据预览

```bash
dv data.csv                    # 前 10 行（默认）
dv data.csv -I                 # 结构面板：列名、类型、NULL 数
dv data.csv -p 50              # 前 50 行
dv data.csv -c id,name -p 10   # 选列查看
dv data.csv --sort "score DESC" # 排序预览
dv data.csv -s                 # 列统计
dv -v data.csv                 # 调试日志
```

### `search` — 正则搜索

```bash
dv search "TP53" data.csv                    # 搜索所有文本列
dv search "TP53|BRCA1" data.csv --in gene    # 搜索指定列
dv search "TP53" data.csv -i                 # 忽略大小写
dv search "p_value" data.csv -l              # 字面量搜索（非正则）
```

### `rename` — 列重命名

```bash
dv rename data.csv column0=gene                # 重命名一列
dv rename data.csv "id=gene_id,name=symbol"    # 重命名多列
dv rename data.csv p_val_adj=padj -o cleaned.csv
```

### `convert` — 格式转换

```bash
dv convert a.csv b.parquet
dv convert a.csv b.xlsx
dv convert a.parquet b.csv --where "score > 90"
```

输出格式由文件扩展名自动推断。

### `cat` — 多文件拼接

```bash
dv cat a.csv b.csv c.csv
dv cat part*.csv -o merged.parquet
dv cat a.csv b.csv -p 20
```

按列名对齐（`UNION ALL BY NAME`），列数不同的文件缺失列自动填 NULL。

### `join` — 两表合并

```bash
dv join a.csv b.csv                        # 自动检测共有列
dv join a.csv b.csv --on gene              # 同名列合并
dv join a.csv b.csv --on probe=gene        # 不同名列合并
dv join a.csv b.csv --on id --how left -o joined.parquet
```

支持 `inner`（默认）、`left`、`right`、`outer`。

### `sql` — 原始 SQL 查询

```bash
dv sql "FROM 'data.csv' SELECT * WHERE score > 90"
dv sql "SELECT gene, AVG(expr) FROM 'data.csv' GROUP BY gene" -o result.parquet
```

## 支持格式

| 格式 | 扩展名 |
|------|--------|
| CSV / TSV | `.csv` `.tsv` `.txt` `.tab` |
| Parquet | `.parquet` |
| JSON / JSONL | `.json` `.jsonl` |
| Excel | `.xlsx` `.xls` |

## 技术栈

- [DuckDB](https://duckdb.org/) — 数据引擎
- [Typer](https://typer.tiangolo.com/) — CLI 框架
- [Rich](https://rich.readthedocs.io/) — 终端输出
- [Loguru](https://github.com/Delgan/loguru) — 日志
