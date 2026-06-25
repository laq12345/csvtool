# csvtool Phase 2 实现计划

> 基于设计文档 `docs/superpowers/specs/2025-06-26-csvtool-phase2-design.md`

---

## Phase 1: `sql -o` 保存功能（最小改动）

**文件**: `src/csvtool/main.py`

在 `sql()` 函数中新增 `-o` 参数：

```python
@app.command()
def sql(
    query: str = typer.Argument(...),
    output: str = typer.Option(None, "-o", "--output", help="Save results to file"),
):
    con = duckdb.connect()
    try:
        _find_and_register_files(con, query)
        if output:
            dst_path = Path(output)
            dst_ext = dst_path.suffix.lower()
            copy_opts = COPY_FORMATS.get(dst_ext)
            if copy_opts is None:
                logger.error("Unsupported output format: '{}'", dst_ext)
                raise typer.Exit(code=1)
            dst_path.parent.mkdir(parents=True, exist_ok=True)
            dst_abs = str(dst_path.resolve())
            con.sql(f"COPY ({query}) TO '{dst_abs}' ({copy_opts})")
            logger.info("Saved to {}", dst_path.name)
        else:
            display_query_result(con, query)
    except Exception as e:
        logger.error("SQL execution failed: {}", e)
        raise typer.Exit(code=1)
    finally:
        con.close()
```

**改动量**：约 15 行（在现有 `sql` 函数中加 if/else）

**验证**：
- `csvtool sql "SELECT * FROM 'data.csv'" -o out.parquet` → 文件生成且可读
- `csvtool sql "..." -o out.xyz` → 报错 exit 1

---

## Phase 2: `cat` 命令（多文件拼接）

**文件**: `src/csvtool/main.py`

```python
@app.command()
def cat(
    files: list[str] = typer.Argument(..., help="Files to concatenate (2+)"),
    preview: int = typer.Option(0, "-p", "--preview"),
    stats: bool = typer.Option(False, "-s", "--stats"),
    output: str = typer.Option(None, "-o", "--output"),
):
```

**核心逻辑**：
1. 检查 `len(files) >= 2`
2. 依次注册每个文件为 `src_i`
3. 构造 `CREATE OR REPLACE VIEW data AS SELECT * FROM src_0 UNION ALL BY NAME SELECT * FROM src_1 UNION ALL BY NAME ...`
4. 有 `-o` 则 COPY 导出，否则走 `-p`/`-s`/默认显示

**改动量**：约 45 行

**验证**：
- 2 文件拼接 → 行数正确
- 3 文件拼接 → 行数正确
- 列顺序不一致 → `UNION ALL BY NAME` 自动对齐
- 文件不存在 → exit 1

---

## Phase 3: `join` 命令（两表合并）

**文件**: `src/csvtool/main.py`

```python
@app.command()
def join(
    a: str = typer.Argument(...),
    b: str = typer.Argument(...),
    on: str = typer.Option(None, "--on"),
    how: str = typer.Option("inner", "--how"),
    preview: int = typer.Option(0, "-p", "--preview"),
    stats: bool = typer.Option(False, "-s", "--stats"),
    output: str = typer.Option(None, "-o", "--output"),
):
```

**`--on` 解析逻辑**：
| 输入 | SQL |
|------|-----|
| 不传 | 自动检测唯一共有列 → `USING (col)` |
| `col`（无 `=`） | `USING (col)` |
| `a_col=b_col`（有 `=`） | `ON a.a_col = b.b_col` |

**自动检测**：注册两表后，查询 `INFORMATION_SCHEMA.COLUMNS` 找交集列名。

**`--how` 校验**：必须是 inner / left / right / outer 之一。

**SQL 构造**：
```sql
CREATE OR REPLACE VIEW a AS SELECT * FROM read_*(...);
CREATE OR REPLACE VIEW b AS SELECT * FROM read_*(...);
CREATE OR REPLACE VIEW data AS SELECT * FROM a {how} JOIN b {on_clause};
```

**改动量**：约 60 行

**验证**：
- 同名列 JOIN → 结果正确
- 不同名列 JOIN → 结果正确
- 自动检测 → 唯一共有列生效
- 自动检测 → 多列重名时报错
- 无效 `--how` → 报错

---

## Phase 4: stdin 管道支持

**改动**: `peek` 的 `FILE` 参数改为可选，`sql` 支持 stdin

```python
@app.command()
def peek(
    file: str = typer.Argument(None),
    ...
):
    if file is None:
        # 从 stdin 读取
        ...
```

**实现**：DuckDB 支持 `read_csv_auto('/dev/stdin')`，直接注册即可。需 flush stdin 到 `/dev/stdin` 或者用临时文件。

**最简单方案**：`sys.stdin.buffer` 写入临时文件 → 注册 → 用完删除。

**改动量**：约 25 行

---

## Phase 5: 测试

| 文件 | 场景数 | 覆盖 |
|------|--------|------|
| `tests/test_sql_output.py` | 4 | `-o` csv/parquet/json + 错误格式 |
| `tests/test_cat.py` | 5 | 2 文件、3 文件、列顺序不一致、文件不存在、`-o` |
| `tests/test_join.py` | 7 | 同名列、不同名、自动检测、自动检测多列报错、left/right/outer、列不存在、`-o` |

---

## Phase 6: 最终验证

```bash
# sql -o
csvtool sql "FROM 'sample.csv' SELECT * LIMIT 2" -o /tmp/out.parquet
csvtool peek /tmp/out.parquet          # 验证 2 行

# cat
csvtool cat a.csv b.csv -p 10           # 拼接预览
csvtool cat a.csv b.csv -o merged.parquet

# join
csvtool join deg.csv meta.csv           # 自动检测
csvtool join a.csv b.csv --on id=gene   # 不同名列
csvtool join a.csv b.csv --on id --how left -o joined.csv
```

---

## 实现顺序与并行策略

```
Phase 1 (sql -o): 串行 ← 最小改动，先验证思路
    ↓
Phase 2+3+4 (cat / join / stdin): 串行 ← 都在 main.py 同一文件
    ↓
Phase 5 (测试): 并行 ← 各测试文件独立
    ↓
Phase 6 (验证): 串行
```

**预估总改动量**：~150 行新增代码，全部集中于 `main.py` + 测试文件。不新增依赖，不修改 `reader.py`/`display.py`/`utils.py`。
