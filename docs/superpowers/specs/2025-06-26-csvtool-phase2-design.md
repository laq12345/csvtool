# csvtool Phase 2 — 查询保存与多文件操作 — 设计文档

## 1. 概述

Phase 1 实现了数据预览（peek）、格式转换（convert）、SQL 查询（sql）。Phase 2 新增三个子命令：`cat`（按行拼接）、`join`（按列合并），并为 `sql` 命令新增 `-o` 保存功能。同时加入 stdin 管道支持作为基础设施。

## 2. 新增命令结构

```
csvtool
├── peek <file> [-p N] [-s]              # 现有
├── convert <src> <dst> [--where]        # 现有
├── sql <query>                           # 扩展
│   └── -o / --output <path>             # 新增
├── cat <files...>                        # 新增
│   ├── [-p N | -s]                       # 同 peek 的预览/统计
│   └── -o / --output <path>             # 保存
└── join <a> <b>                          # 新增
    ├── --on <col>                        # JOIN 列
    ├── --how <inner|left|right|outer>    # JOIN 方式
    ├── [-p N | -s]                       # 预览/统计
    └── -o / --output <path>             # 保存
```

## 3. `sql -o` 设计

**用法**：
```bash
csvtool sql "FROM 'data.csv' SELECT * WHERE score > 90" -o filtered.parquet
csvtool sql "SELECT gene, avg_log2FC FROM 'deg.csv'" -o top.csv
csvtool sql "SELECT * FROM 'a.json'" -o out.jsonl
```

**行为**：
- 不加 `-o`：现有预览行为不变
- 加 `-o`：复用 `COPY_FORMATS` 映射，根据目标扩展名推断输出格式
- 输出格式由目标扩展名决定（`.csv/.tsv/.parquet/.json/.jsonl`）

**实现要点**：
- `sql` 函数新增 `-o` 可选参数
- 有 `-o` 时，查询结果用 `COPY (query) TO 'path' (FORMAT ...)` 导出
- 无 `-o` 时，走现有 `display_query_result` 路径
- 自动创建目标目录（已有逻辑）

## 4. `cat` 设计 — 多文件按行拼接

**用法**：
```bash
cat part_*.csv | sort → csvtool cat part_*.csv    # 拼接多文件
csvtool cat a.csv b.csv c.csv -p 10               # 拼接后预览
csvtool cat a.csv b.csv -o merged.parquet          # 拼接后保存
```

**语义**：
- 接受 2+ 个文件路径作为位置参数
- 按列名对齐（`UNION ALL BY NAME`），自动处理列顺序不一致
- 各文件列数可以不同，缺失列填 NULL
- 列名大小写敏感（DuckDB 默认行为）

**SQL 实现**：
```sql
CREATE OR REPLACE VIEW data_1 AS SELECT * FROM read_csv_auto('a.csv');
CREATE OR REPLACE VIEW data_2 AS SELECT * FROM read_csv_auto('b.csv');
CREATE OR REPLACE VIEW data AS SELECT * FROM data_1 UNION ALL BY NAME SELECT * FROM data_2;
```

**参数**：
| 参数 | 说明 |
|------|------|
| `FILES...` | 位置参数，2+ 个文件路径 |
| `-p / --preview N` | 拼接后预览前 N 行 |
| `-s / --stats` | 拼接后显示统计 |
| `-o / --output` | 保存到文件 |

默认行为：显示拼接后的结构概览（同 peek）

## 5. `join` 设计 — 两表按列合并

**用法**：
```bash
csvtool join deg.csv meta.csv                     # 自动检测共有列
csvtool join deg.csv meta.csv --on gene           # 同名列
csvtool join expr.csv meta.csv --on probe=gene    # 不同名列
csvtool join a.parquet b.csv --on id --how left -o joined.csv
```

**`--on` 语义**：

| 形式 | 示例 | SQL |
|------|------|-----|
| `col`（同名列） | `--on gene` | `USING (gene)` |
| `a_col=b_col`（不同名） | `--on probe=gene` | `ON a.probe = b.gene` |
| 省略（自动检测） | 不传 `--on` | 自动找唯一共有列 → `USING (col)`；多列重名时报错并列出候选 |

**`--how` 可选值**：inner / left / right / outer（默认 inner）

**SQL 实现**：
```sql
-- 同名列
CREATE OR REPLACE VIEW a AS SELECT * FROM read_csv_auto('a.csv');
CREATE OR REPLACE VIEW b AS SELECT * FROM read_csv_auto('b.csv');
CREATE OR REPLACE VIEW data AS SELECT * FROM a INNER JOIN b USING (gene);

-- 不同名列
CREATE OR REPLACE VIEW data AS SELECT * FROM a LEFT JOIN b ON a.probe = b.gene;
```

**参数**：
| 参数 | 说明 |
|------|------|
| `A` | 位置参数，左表路径 |
| `B` | 位置参数，右表路径 |
| `--on` | 可选。`col`（同名列）或 `a_col=b_col`（不同名）。省略时自动检测唯一共有列 |
| `--how` | 可选，JOIN 方式：inner/left/right/outer（默认 inner） |
| `-p / --preview N` | 预览前 N 行 |
| `-s / --stats` | 统计摘要 |
| `-o / --output` | 保存到文件 |

默认行为：显示 JOIN 结果的结构概览

## 6. stdin 管道支持（基础设施）

为 `peek`、`sql` 新增 stdin 输入支持：

```bash
cat data.csv | csvtool peek       # stdin 输入
curl URL | csvtool sql "SELECT * FROM stdin"   # SQL 查询管道数据
csvtool sql "SELECT * FROM 'a.csv'" | csvtool peek  # 命令串联
```

**实现**：
- `peek` 的 `FILE` 参数改为可选，为空时从 `sys.stdin` 读取，写入临时文件后注册
- DuckDB 支持 `read_csv_auto('/dev/stdin')`（Linux），可作为更高效路径

## 7. 项目结构更新

```
src/csvtool/
├── main.py                    # 新增 cat、join 命令 + -o 参数
├── reader.py                  # 现有
├── display.py                 # 现有
└── utils.py                   # 现有
```

`main.py` 行数预计从 200 行增加到约 350 行。如果后续继续膨胀，可拆分 `cat`/`join` 到独立模块。

## 8. 测试计划

| 测试 | 场景 |
|------|------|
| `sql -o test.csv` | SELECT 结果保存为 CSV，验证文件存在且内容正确 |
| `sql -o test.parquet --where` | 带 WHERE 的保存 |
| `sql -o` 不支持的格式 | `.xyz` → 报错退出 |
| `cat a.csv b.csv` | 2 文件拼接，验证行数 = sum |
| `cat` 3+ 文件 | 多文件拼接 |
| `cat` 列顺序不一致 | `UNION ALL BY NAME` 自动对齐 |
| `cat` 文件不存在 | 报错 exit 1 |
| `join` inner | 默认 INNER JOIN 验证 |
| `join --how left` | LEFT JOIN 保留左表所有行 |
| `join` 列不存在 | 报错 exit 1 |
| `join` 文件不存在 | 报错 exit 1 |
| stdin pipe | `echo "a,b" \| csvtool peek` |

## 9. 依赖

无新增依赖。所有功能复用现有 DuckDB + Typer + Rich + Loguru。

## 10. 不纳入本阶段的特性

- REPL 模式 → `duckdb` CLI 替代
- `convert` 批量通配符 → shell `for` 循环替代，YAGNI
- 三表及以上 JOIN → 用 `sql` 命令写 SQL 替代
- 聚合统计专用命令 → `sql` 命令可覆盖
- 配置文件支持
- 插件系统
