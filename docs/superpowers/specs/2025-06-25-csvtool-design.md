# csvtool: 终端表格文件处理工具 — 设计文档

## 1. 概述

`csvtool` 是一个终端命令行工具，用于快速预览、探查和转换表格数据文件。目标用户是 Python/R 数据分析师，他们在终端做轻量数据查看和格式转换，重分析留在 Notebook 或脚本里完成。

**核心能力**：数据预览/探查（最高优先级）、格式转换、简单 SQL 查询。

## 2. 架构

```
┌─────────────────────────────────────────┐
│              typer CLI (main.py)         │
│  解析参数、调度子命令、全局 --verbose    │
├──────┬──────────────┬───────────┬────────┤
│ peek │   convert    │    sql    │ utils  │
│ 命令  │    命令      │   命令    │ loguru │
├──────┴──────────────┴───────────┴────────┤
│              reader.py                   │
│  格式推断 → DuckDB 读取函数映射          │
├──────────────────────────────────────────┤
│              display.py                  │
│  rich Table / Panel / 统计渲染           │
├──────────────────────────────────────────┤
│           DuckDB (数据引擎)              │
│  read_csv_auto / read_parquet / excel    │
└──────────────────────────────────────────┘
```

**设计原则**：
- 每个模块单一职责，通过函数接口组合
- DuckDB 是唯一数据引擎，不引入 pandas/polars 等重型依赖
- 所有终端输出由 rich 统一渲染

## 3. 命令结构

```
csvtool                              # 主入口 (typer)
├── csvtool <file>                   # 默认 = peek（结构概览）
├── peek <file>                      # 数据预览/探查
│   ├── (no flags)                   # 结构概览：文件名、行列数、列名+类型、文件大小
│   ├── --preview / -p [N]           # 显示前 N 行（默认 10），rich Table 渲染
│   └── --stats / -s                 # 每列统计：count, null, min, max, mean, unique
├── convert <src> <dst>              # 格式转换，根据目标扩展名推断输出格式
│   └── --where "..."                # 可选：转换时先过滤
├── sql <query>                      # 原始 SQL 查询
└── --verbose / -v                   # 全局 flag，开启 loguru DEBUG 日志
```

## 4. 格式支持

| 格式 | 扩展名 | DuckDB 读取方式 | 备注 |
|------|--------|----------------|------|
| CSV | `.csv` | `read_csv_auto` | 自动推断分隔符、表头、类型 |
| TSV / TXT | `.tsv` `.txt` `.tab` | `read_csv_auto` | 自动识别 `\t` 分隔 |
| Parquet | `.parquet` | `read_parquet` | 列式存储，高性能 |
| JSON / JSONL | `.json` `.jsonl` | `read_json_auto` | NDJSON / JSON 数组 |
| Excel | `.xlsx` `.xls` | `excel` extension → `st_read` | 首次使用时自动 INSTALL + LOAD |

**智能推断流程**（`reader.py`）：
1. 取文件扩展名 → 查映射表 → 确定读取函数
2. 未知扩展名 → 输出明确错误提示，列出支持的格式
3. 文件不存在 / 无权限 → loguru error + 退出码 1

## 5. 数据流

```
输入文件 → reader.py (格式推断)
          → DuckDB 注册为临时表
          → 子命令执行查询
          → display.py (rich 渲染)
          → 终端输出
```

- `peek`：执行 `DESCRIBE` + `SELECT COUNT(*)` 获取结构信息；`--preview` 时执行 `SELECT * LIMIT N`；`--stats` 时执行 `SUMMARIZE`
- `convert`：`SELECT * FROM read_*` → `COPY TO dst (FORMAT ...)`
- `sql`：用户 SQL 直接转发 DuckDB 执行

## 6. 输出与显示

使用 **rich** 库渲染：

| 内容 | rich 组件 | 说明 |
|------|----------|------|
| 结构概览 | `Panel` + `Table` | 元数据面板 + 列信息表格 |
| 行数据 | `Table` | 自动列宽对齐、表头高亮 |
| 统计摘要 | `Table` | 每列 stats 表格展示 |
| 错误/警告 | `Console().print` (styled) | 红色错误、黄色警告 |
| SQL 查询结果 | `Table` | 同行数据渲染 |

超过终端高度的长表格自动 pipe 到 `less -S`。

## 7. 错误处理

| 场景 | 行为 |
|------|------|
| 文件不存在 / 无权限 | loguru error + 退出码 1 |
| 格式解析失败 | loguru error + DuckDB 原始报错 + 退出码 1 |
| SQL 语法错误 | DuckDB 错误原样透传 + 退出码 1 |
| 不支持的格式 | 明确提示 + 列出支持格式 + 退出码 1 |
| 非致命（列名不存在等） | loguru warning + 尝试继续 |

## 8. 项目结构

```
~/Developer/Python/csvtool/
├── pyproject.toml             # pixi init --format pyproject 生成
├── src/
│   └── csvtool/
│       ├── __init__.py
│       ├── main.py            # typer app 入口
│       ├── reader.py          # 格式推断 + DuckDB 读取注册
│       ├── commands/
│       │   ├── __init__.py
│       │   ├── peek.py        # 预览/探查子命令
│       │   ├── convert.py     # 格式转换子命令
│       │   └── sql.py         # SQL 查询子命令
│       ├── display.py         # rich 渲染封装
│       └── utils.py           # loguru 配置、通用工具
└── tests/
    ├── __init__.py
    ├── test_peek.py
    ├── test_convert.py
    ├── test_sql.py
    ├── test_reader.py
    └── fixtures/              # 测试用小样本数据
        ├── sample.csv
        ├── sample.tsv
        ├── sample.parquet
        └── sample.json
```

## 9. 依赖

| 依赖 | 版本 | 用途 |
|------|------|------|
| typer | ≥0.15 | CLI 框架 |
| rich | ≥13 | 终端美化输出 |
| duckdb | ≥1.0 | 数据引擎 |
| loguru | ≥0.7 | 结构化日志 |

所有依赖通过 pixi（conda-forge 通道）管理，写入 `pyproject.toml` 的 `[project] dependencies` 和 `[tool.pixi.pypi-dependencies]`。

## 10. 测试策略

- **reader.py** — 单元测试：格式推断映射、未知格式报错、文件不存在报错
- **display.py** — 单元测试：rich 对象结构验证（无需实际渲染）
- **CLI 端到端** — `typer.testing.CliRunner` + 临时 DuckDB 内存数据库 + fixtures 文件
- **fixtures** — 各格式最小样本文件（5-10 行），覆盖 CSV/TSV/Parquet/JSON
- 测试运行：`pixi run pytest`

## 11. 不纳入本阶段的特性

以下明确延后到未来迭代：
- 聚合统计专用命令（当前 `sql` 子命令可覆盖简单聚合）
- 多文件 JOIN / 拼接
- 交互式 REPL 模式
- 配置文件支持
- 插件系统
