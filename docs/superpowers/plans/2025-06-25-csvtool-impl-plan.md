# csvtool 实现计划

> 基于设计文档 `docs/superpowers/specs/2025-06-25-csvtool-design.md`

---

## Phase 0: 文档发现 —— 已验证 API 清单

以下 API 均来自官方文档验证，禁止使用清单外的虚构 API。

### DuckDB (`duckdb`)

| 用途 | API | 来源 |
|------|-----|------|
| 创建连接 | `duckdb.connect()` 返回连接对象 | duckdb-python 官方 |
| SQL 查询 | `con.sql("SELECT ...")` 或 `duckdb.sql("SELECT ...")` | duckdb-python 官方 |
| 读 CSV | `read_csv_auto('file.csv', all_varchar=False, sample_size=50000)` | duckdb-python tests |
| 读 Parquet | `read_parquet('file.parquet')` | 标准 DuckDB SQL |
| 读 JSON | `read_json_auto('file.json')` | 标准 DuckDB SQL |
| Excel 支持 | `con.sql("INSTALL excel; LOAD excel;")` 后用 `st_read()` | DuckDB 文档 |
| 统计摘要 | `SUMMARIZE SELECT * FROM ...` (DuckDB 内置表函数) | DuckDB SQL 文档 |
| 结构描述 | `DESCRIBE SELECT * FROM ...` | DuckDB SQL 文档 |
| 导出数据 | `COPY (SELECT ...) TO 'path' (FORMAT csv, HEADER true)` | duckdb-python tests |
| 文件直接引用 | `SELECT * FROM 'file.csv'` (SQL 内直接路径) | DuckDB SQL |
| 结果转字典 | `.fetchall()` 或 `.df().to_dict()` (Pandas 可选) | duckdb-python |

### Typer (`typer`)

| 用途 | API | 来源 |
|------|-----|------|
| 创建 app | `app = typer.Typer()` | typer.tiangolo.com |
| 全局回调 | `@app.callback()` → 声明 `--verbose` + 修改 state | typer.tiangolo.com |
| 无命令时默认行为 | `app = typer.Typer(invoke_without_command=True)` | typer reference |
| 子命令挂载 | `app.add_typer(sub_app, name="peek")` | typer.tiangolo.com |
| 位置参数 | `file: Annotated[str, typer.Argument()]` | typer reference |
| 可选 flag | `preview: Annotated[int, typer.Option("-p", "--preview")] = 0` | typer reference |
| CLI 测试 | `from typer.testing import CliRunner` → `runner.invoke(app, [...])` | typer 文档 |
| 退出码 | `raise typer.Exit(code=1)` | typer 文档 |

### Rich (`rich`)

| 用途 | API | 来源 |
|------|-----|------|
| 创建表格 | `table = Table(title="...", expand=False)` | rich.readthedocs.io |
| 添加列 | `table.add_column("Name", justify="left", style="cyan", overflow="ellipsis")` | rich.readthedocs.io |
| 添加行 | `table.add_row("val1", "val2", ...)` | rich.readthedocs.io |
| 创建面板 | `Panel(renderable, title="...", subtitle="...", border_style="...")` | rich.readthedocs.io |
| 打印到终端 | `console = Console()` → `console.print(obj)` | rich.readthedocs.io |
| 样式文本 | `"[red]error[/red]"`, `"[bold]text[/bold]"` (Rich markup) | rich 文档 |
| 溢出处理 | `overflow="ellipsis"` / `"fold"` / `"crop"` | rich.readthedocs.io |

### Loguru (`loguru`)

| 用途 | API | 来源 |
|------|-----|------|
| 清除默认 handler | `logger.remove()` | loguru 文档 |
| 添加 handler | `logger.add(sys.stderr, level="WARNING", format="...")` | loguru 文档 |
| 动态设级别 | `logger.level("DEBUG")` | loguru 文档 |
| 结构化日志 | `logger.info("Processing {}", file)` | loguru 文档 |

---

## Phase 1: 项目骨架 + 环境配置

### 1.1 配置 pyproject.toml 依赖

当前 `pyproject.toml` 只有空 `dependencies = []`，添加所有依赖。

**文件**: `pyproject.toml`

```toml
dependencies = [
    "typer>=0.15",
    "rich>=13",
    "duckdb>=1.0",
    "loguru>=0.7",
]
```

同时加 `[tool.pixi.pypi-dependencies]`（已有 editable 路径安装）。

### 1.2 创建包目录结构

```bash
mkdir -p src/csvtool/commands
mkdir -p tests/fixtures
```

### 1.3 创建 `__init__.py` 文件

- `src/csvtool/__init__.py` — 空
- `src/csvtool/commands/__init__.py` — 空
- `tests/__init__.py` — 空

### 1.4 安装依赖并验证

```bash
pixi install
pixi run python -c "import typer, rich, duckdb, loguru; print('OK')"
```

### 验证点
- [ ] `pixi install` 成功
- [ ] 四个核心依赖可导入

---

## Phase 2: 核心模块实现（可并行）

### 2.1 `utils.py` — loguru 配置

**文件**: `src/csvtool/utils.py`

```python
import sys
from loguru import logger

def setup_logging(verbose: bool) -> None:
    logger.remove()
    level = "DEBUG" if verbose else "WARNING"
    logger.add(
        sys.stderr,
        level=level,
        format="<level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
        colorize=True,
    )
```

- `setup_logging(verbose: bool)` — 清除默认 handler，根据 verbose 设级别，输出到 stderr

### 2.2 `reader.py` — 格式推断 + DuckDB 读取

**文件**: `src/csvtool/reader.py`

核心逻辑：
1. 定义 `FORMAT_MAP`: `{".csv": "csv", ".tsv": "tsv", ".txt": "tsv", ".tab": "tsv", ".parquet": "parquet", ".json": "json", ".jsonl": "json", ".xlsx": "excel", ".xls": "excel"}`
2. `detect_format(file_path: Path) -> str` — 从扩展名取格式，未知则报错
3. `init_excel_support(con: duckdb.DuckDBPyConnection) -> None` — 安装并加载 excel extension
4. `register_file(con, file_path: Path, table_name: str = "data") -> str` — 根据格式调用对应 read 函数，注册为表

DuckDB SQL 模板：
- CSV/TSV: `CREATE OR REPLACE VIEW {table_name} AS SELECT * FROM read_csv_auto('{path}')`
- Parquet: `CREATE OR REPLACE VIEW {table_name} AS SELECT * FROM read_parquet('{path}')`
- JSON: `CREATE OR REPLACE VIEW {table_name} AS SELECT * FROM read_json_auto('{path}')`
- Excel: 先 `init_excel_support()`，然后 `CREATE OR REPLACE VIEW {table_name} AS SELECT * FROM st_read('{path}')`

### 2.3 `display.py` — rich 渲染

**文件**: `src/csvtool/display.py`

三个渲染函数：

1. **`display_structure(con, file_path, format_name, file_size)`**
   - 执行 `DESCRIBE SELECT * FROM data` + `SELECT COUNT(*) FROM data`
   - 用 `Panel(title=f"[bold]{file_path.name}[/bold]", subtitle=f"{format_name} | {file_size} | {row_count} rows × {col_count} columns")` 包装
   - 内部用 `Table` 显示列名、类型、nullable

2. **`display_preview(con, n_rows: int)`**
   - 执行 `SELECT * FROM data LIMIT {n_rows}`
   - 用 `Table` 渲染，`overflow="ellipsis"`，自动列宽

3. **`display_stats(con)`**
   - 执行 `SUMMARIZE SELECT * FROM data`
   - 用 `Table` 渲染统计结果

4. **`display_query_result(con, query: str)`**
   - 执行用户 SQL
   - 用 `Table` 渲染结果

通用函数：
- `_create_console() -> Console` — 返回 Console 实例
- `_results_to_table(columns, rows) -> Table` — 通用查询结果 → Table 转换

### 验证点
- [ ] `utils.setup_logging(verbose=True)` 输出 DEBUG 日志
- [ ] `reader.detect_format(Path("test.csv"))` → `"csv"`
- [ ] `reader.detect_format(Path("test.xyz"))` → 抛异常
- [ ] `display._results_to_table(...)` 返回 rich Table 对象

---

## Phase 3: 子命令实现（可并行）

### 3.1 `commands/peek.py` — 预览/探查

**文件**: `src/csvtool/commands/peek.py`

```python
import typer
from pathlib import Path

peek_app = typer.Typer()

@peek_app.callback(invoke_without_command=True)
def peek(
    file: str = typer.Argument(..., help="Path to the data file"),
    preview: int = typer.Option(0, "-p", "--preview", help="Show first N rows"),
    stats: bool = typer.Option(False, "-s", "--stats", help="Show column statistics"),
):
    # 1. 创建 DuckDB 连接
    # 2. 注册文件
    # 3. 如果 --preview: 显示前 N 行
    # 4. 否则如果 --stats: 显示统计
    # 5. 否则：显示结构概览
```

行为优先级：`--preview` > `--stats` > 默认结构概览

### 3.2 `commands/convert.py` — 格式转换

**文件**: `src/csvtool/commands/convert.py`

```python
@convert_app.command("convert")
def convert_file(
    src: str = typer.Argument(..., help="Source file path"),
    dst: str = typer.Argument(..., help="Destination file path"),
    where: str = typer.Option(None, "--where", help="SQL WHERE clause to filter rows"),
):
    # 1. 注册源文件
    # 2. 构建 SELECT 查询（可选 WHERE）
    # 3. 用 COPY ... TO 导出到目标格式
    # 4. 根据 dst 扩展名选择 FORMAT
```

格式映射：`.csv` → `FORMAT csv, HEADER true` | `.tsv` → `FORMAT csv, HEADER true, DELIMITER '\t'` | `.parquet` → `FORMAT parquet` | `.json` → `FORMAT json` | `.jsonl` → `FORMAT json, ARRAY false`

### 3.3 `commands/sql.py` — SQL 查询

**文件**: `src/csvtool/commands/sql.py`

```python
@sql_app.command("sql")
def run_sql(
    query: str = typer.Argument(..., help="SQL query to execute"),
):
    # 1. 解析 SQL 中引用的文件路径（如 'file.csv'）
    # 2. 如果 SQL 里没引用文件，报错提示
    # 3. 注册所有引用文件为表
    # 4. 执行查询
    # 5. 显示结果
```

复杂查询可直接在 SQL 里写 `FROM 'data.csv'`，DuckDB 自动处理。

### 验证点
- [ ] `csvtool peek data.csv` → 显示结构概览
- [ ] `csvtool peek data.csv -p 5` → 显示前 5 行
- [ ] `csvtool peek data.csv -s` → 显示统计摘要
- [ ] `csvtool convert a.csv b.parquet` → 生成 parquet 文件
- [ ] `csvtool sql "FROM 'data.csv' SELECT * LIMIT 3"` → 显示前 3 行

---

## Phase 4: `main.py` — 组装 + 全局回调

**文件**: `src/csvtool/main.py`

```python
import typer
from csvtool.commands.peek import peek_app
from csvtool.commands.convert import convert_app
from csvtool.commands.sql import sql_app
from csvtool.utils import setup_logging

app = typer.Typer(
    name="csvtool",
    help="Terminal data file preview, exploration, and conversion tool.",
    invoke_without_command=True,
)

app.add_typer(peek_app, name="peek", help="Preview and explore data files")
app.add_typer(convert_app, name="convert", help="Convert between data formats")
app.add_typer(sql_app, name="sql", help="Run SQL queries on data files")

@app.callback()
def main(
    ctx: typer.Context,
    verbose: bool = typer.Option(False, "-v", "--verbose", help="Enable debug logging"),
):
    setup_logging(verbose)
    # 无子命令: 显示 help
    if ctx.invoked_subcommand is None:
        pass  # Typer shows help automatically
```

### 验证点
- [ ] `csvtool --help` → 显示帮助
- [ ] `csvtool -v peek data.csv` → DEBUG 日志可见
- [ ] `csvtool data.csv` → 等同 `csvtool peek data.csv`（通过 invoke_without_command + 默认帮助）
- 注意：方案 C 说的"不指定子命令时自动 peek"在 Typer 里可以通过 `invoke_without_command=True` + `@app.callback` 里检测 `invoked_subcommand is None` 后手动调用 peek 逻辑实现。或者更简单：在 callback 中调用 `peek` 函数。

---

## Phase 5: 测试

### 5.1 创建 fixtures

**目录**: `tests/fixtures/`

| 文件 | 内容 |
|------|------|
| `sample.csv` | 5 行 4 列：`id,name,age,score` + 5 行数据（含 NULL） |
| `sample.tsv` | 同 CSV 的 tab 分隔版 |
| `sample.parquet` | 用 DuckDB 从 CSV 生成 |
| `sample.json` | JSON 数组，同数据结构 |

### 5.2 测试文件

**`tests/test_reader.py`**:
- `test_detect_format_csv` — `.csv` → `"csv"`
- `test_detect_format_unknown` — `.xyz` → 抛异常
- `test_register_csv` — 注册 CSV 后 `SELECT COUNT(*)` 返回正确行数
- `test_register_parquet` — 同上

**`tests/test_peek.py`** (CliRunner):
- `test_peek_default` — `invoke(app, ["peek", "fixtures/sample.csv"])` → stdout 含列名
- `test_peek_preview` — `["peek", "fixtures/sample.csv", "-p", "3"]` → 3 行数据
- `test_peek_stats` — `["peek", "fixtures/sample.csv", "-s"]` → 含统计信息
- `test_peek_file_not_found` — 不存在的文件 → 退出码 1

**`tests/test_convert.py`** (CliRunner):
- `test_convert_csv_to_parquet` — 生成 `.parquet` 文件，验证可读
- `test_convert_with_where` — 过滤后导出，验证行数

### 验证点
- [ ] `pixi run pytest` 全部通过
- [ ] 无虚构 API 调用

---

## Phase 6: 最终验证

### 6.1 功能验证

```bash
# 结构概览
pixi run csvtool peek tests/fixtures/sample.csv

# 前 3 行
pixi run csvtool peek tests/fixtures/sample.csv -p 3

# 统计
pixi run csvtool peek tests/fixtures/sample.csv -s

# CSV → Parquet
pixi run csvtool convert tests/fixtures/sample.csv /tmp/test_out.parquet

# SQL 查询
pixi run csvtool sql "FROM 'tests/fixtures/sample.csv' SELECT * WHERE age > 30"

# 默认行为
pixi run csvtool tests/fixtures/sample.csv

# verbose 日志
pixi run csvtool -v peek tests/fixtures/sample.csv
```

### 6.2 代码质量
- [ ] 所有文件 `lsp_diagnostics` 无错误
- [ ] `duckdb-connection` 正确关闭（with 或 try-finally）

---

## 实现顺序与并行策略

```
Phase 1 (骨架): 串行，先完成
    ↓
Phase 2 (核心模块): 并行 ← utils.py, reader.py, display.py 互不依赖
    ↓
Phase 3 (子命令): 并行 ← peek.py, convert.py, sql.py 互不依赖
    ↓
Phase 4 (main.py): 串行 ← 依赖 Phase 3
    ↓
Phase 5 (测试): 并行 ← 各测试文件独立
    ↓
Phase 6 (最终验证): 串行
```
