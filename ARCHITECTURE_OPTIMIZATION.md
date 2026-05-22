# GitHub Trending Scraper - 项目结构文档

## 项目概览

**项目名称**: github-trending-scraper v2.0.0  
**项目描述**: 多源趋势项目发现与分析平台  
**Python 版本**: >=3.9  
**技术栈**: Python, Flask, SQLite, HTML/CSS/JS  

---

## 完整目录结构

```
githubPH/
├── .gitignore                     # Git 忽略规则
├── Dockerfile                     # Docker 构建文件
├── Makefile                       # 便捷命令集合
├── docker-compose.yml             # Docker Compose 编排
├── main.py                        # CLI 主入口（命令调度）
├── admin_server.py                # Flask 管理服务入口
├── pyproject.toml                 # Python 项目元数据和依赖
├── requirements.txt               # 依赖清单
├── pytest.ini                     # pytest 配置
│
├── admin/                         # Web 管理后台模块
│   ├── __init__.py                # Flask Blueprint 注册
│   ├── auth.py                    # 用户认证（登录/密码哈希/会话）
│   ├── export.py                  # 数据导出（JSON/CSV/Markdown/TXT）
│   ├── llm.py                     # LLM 代码生成器（AI 辅助创建爬虫）
│   ├── llm_api.py                 # LLM API 调用封装
│   ├── routes.py                  # 管理后台路由（所有 /admin/* 接口）
│   ├── security.py                # 自定义数据源安全加载
│   ├── utils.py                   # 工具函数（配置读写、前端重生成）
│   └── templates/                 # Jinja2 管理后台模板
│       ├── base.html              # 基础布局模板
│       ├── login.html             # 登录页
│       ├── dashboard.html         # 仪表盘（统计概览）
│       ├── projects.html          # 项目管理页
│       ├── edit_project.html      # 编辑项目
│       ├── delete_project.html    # 删除项目确认
│       ├── new_project.html       # 新建项目
│       ├── sources.html           # 数据源管理页
│       ├── custom_source_form.html# 自定义数据源表单（AI 生成）
│       ├── custom_sources.html    # 自定义数据源列表
│       ├── exports.html           # 数据导出页
│       ├── audit_log.html         # 审计日志
│       ├── source_logs.html       # 数据源采集日志
│       ├── settings.html          # 系统设置（LLM 配置）
│       ├── user_form.html         # 用户表单
│       └── users.html             # 用户管理页
│
├── analyzer/                      # 数据分析模块
│   ├── __init__.py
│   ├── dark_horse.py              # 黑马项目检测算法
│   ├── readme_scorer.py           # README 质量评分
│   ├── report_generator.py        # Markdown 分析报告生成器
│   └── trend_analyzer.py          # 语言热度趋势分析
│
├── config/                        # 配置模块
│   ├── __init__.py
│   ├── config.py                  # 统一配置管理器（环境变量 > YAML > 默认值）
│   └── sources.yaml               # 数据源配置文件
│
├── generator/                     # HTML 页面生成模块
│   ├── __init__.py
│   ├── html_generator.py          # 静态 HTML 生成器（嵌入数据 + JS 渲染）
│   └── templates/
│       └── index.html             # HTML 模板（支持服务端变量替换）
│
├── scraper/                       # 数据采集模块
│   ├── __init__.py
│   └── sources/                   # 数据源实现
│       ├── __init__.py            # 数据源注册表 + 装饰器注册机制
│       ├── base.py                # 数据源抽象基类
│       ├── models.py              # 统一数据模型 (UnifiedProject)
│       ├── framework.py           # 多源采集编排器（优先级、重试、翻译）
│       ├── github_html.py         # GitHub Trending HTML 爬虫
│       ├── github_trending_api.py # GitHub Trending GraphQL API 爬虫
│       ├── hackernews.py          # HackerNews Firebase API 爬虫
│       ├── reddit.py              # Reddit 编程社区爬虫
│       ├── gitee.py               # Gitee（码云）Trending 爬虫
│       ├── juejin.py              # 掘金热文爬虫
│       └── translator.py          # 英->中翻译服务（Google/MyMemory）
│
├── storage/                       # 数据持久层
│   ├── __init__.py
│   └── sqlite_store.py            # SQLite 数据仓库（完整的 CRUD + 管理表）
│
├── tests/                         # 测试套件
│   ├── __init__.py
│   ├── test_auth.py               # 认证测试
│   ├── test_config.py             # 配置管理测试
│   ├── test_framework.py          # 抓取框架测试
│   ├── test_html_generator.py     # HTML 生成器测试
│   ├── test_models.py             # 数据模型测试
│   └── test_sqlite_store.py       # 数据库存储测试
│
├── docs/                          # 项目文档
│   └── ARCHITECTURE_OPTIMIZATION.md  # 架构优化文档
│
└── logs/                          # 运行时日志目录（.gitignore）
```

---

## 核心模块详解

### 1. CLI 入口 (`main.py`)

`main.py:296` - 命令行参数调度器，支持以下命令：

| 命令 | 说明 |
|------|------|
| `--scrape` | 采集所有数据源 |
| `--generate` | 生成 HTML 展示页 |
| `--analyze` | 趋势分析 + 报告生成 |
| `--report` | 仅生成报告 |
| `--stats` | 数据库统计信息 |
| `--init-db` | 初始化数据库 |
| `--daemon` | 守护进程模式（定时采集） |
| `--admin` | 启动 Web 管理后台 |
| `--language` | 按语言过滤 |
| `--config` | 指定配置文件路径 |
| `--db` | 指定数据库路径 |

### 2. 数据采集层 (`scraper/`)

#### 数据模型 (`scraper/sources/models.py`)
统一的 `UnifiedProject` 数据类，包含字段：
- `source` - 数据来源
- `project_name` - 项目名称
- `project_url` - 项目链接
- `description` - 项目描述
- `author` - 作者
- `stars` / `forks` - 互动数据
- `language` - 编程语言
- `category` - 分类
- `scraped_at` - 采集时间

#### 数据源注册机制 (`scraper/sources/__init__.py`)
使用装饰器模式的全局注册表 `SOURCE_REGISTRY`：
- 每个数据源通过 `@register_source("name")` 装饰器自动注册
- 支持动态加载自定义数据源代码

#### 数据源基类 (`scraper/sources/base.py`)
`BaseSource` 抽象基类，定义了 `scrape()` 和 `normalize()` 接口。

#### 内置数据源（7 个）

| 数据源 | 文件 | 优先级 | 采集方式 | 说明 |
|--------|------|--------|----------|------|
| GitHub Trending | `github_html.py` | 1 | HTML 解析 | GitHub Trending 页面 |
| GitHub API | `github_trending_api.py` | 2 | GraphQL API | GitHub 趋势 API |
| HackerNews | `hackernews.py` | 3 | Firebase API | HN 热门帖子 |
| Reddit | `reddit.py` | 4 | JSON API | /r/programming 等 |
| 掘金 | `juejin.py` | 5 | REST API | 掘金热文排行 |
| V2EX | `v2ex.py` | 6 | HTML 解析 | 中文开发者社区 |
| Gitee | `gitee.py` | 7 | REST API | 码云 Trending |

#### 采集框架 (`scraper/sources/framework.py`)
`ScraperFramework` 编排器职责：
- 按优先级排序后依次采集所有数据源
- 内置重试机制（连接错误不重试，超时/服务端错误重试）
- 支持中英文翻译（Google Translate / MyMemory API）
- 支持自定义数据源（从数据库动态加载并安全执行）

### 3. 数据存储层 (`storage/`)

`storage/sqlite_store.py` - 基于 SQLite 的完整数据仓库，包含表：

| 表名 | 说明 |
|------|------|
| `projects` | 项目数据（唯一约束：source + project_name） |
| `custom_sources` | 自定义数据源代码 |
| `settings` | KV 键值对配置存储 |
| `audit_log` | 审计日志 |
| `source_health` | 数据源健康状态 |
| `scrape_logs` | 采集执行日志 |
| `users` | 管理后台用户表 |

支持功能：CRUD、分页查询、搜索、排序、统计、设置管理。

### 4. HTML 页面生成 (`generator/`)

`generator/html_generator.py` - 将项目数据嵌入 HTML 模板，生成包含：
- 左侧数据源导航
- 分类标签过滤
- 搜索功能
- 热门项目排行
- 分页（每页 50 条）
- 响应式布局
- 移动端适配
- 键盘快捷键

### 5. 数据分析 (`analyzer/`)

| 模块 | 功能 |
|------|------|
| `trend_analyzer.py` | 语言热度分析，使用复合热度公式 |
| `dark_horse.py` | 黑马项目检测（标准差/排名/多重平均值三种方法） |
| `readme_scorer.py` | README 文档质量评分 |
| `report_generator.py` | 生成 Markdown 格式分析报告 |

### 6. Web 管理后台 (`admin/`)

基于 Flask Blueprint 的完整管理系统：

**功能模块**:
- 用户认证（登录/登出/角色管理）
- 仪表盘（统计概览）
- 项目管理（增删改查/批量操作）
- 数据源管理（启停/定时/测试/LLM 代码生成）
- 数据导出（JSON/CSV/Markdown/TXT）
- 审计日志
- 数据源健康监控
- LLM API 配置（OpenAI/Anthropic）

**路由前缀**: `/admin/`  
**默认端口**: 5001

### 7. 配置系统 (`config/`)

`config/config.py` - 统一配置管理器，优先级：
1. 环境变量
2. YAML 配置文件
3. 程序默认值

配置文件 `sources.yaml` 控制数据源的启用/禁用、优先级、定时任务间隔等。

---

## 数据库 Schema

### projects 表
```
id              INTEGER PRIMARY KEY AUTOINCREMENT
source          TEXT NOT NULL
project_name    TEXT NOT NULL
project_url     TEXT NOT NULL
description     TEXT
author          TEXT
stars           INTEGER DEFAULT 0
forks           INTEGER DEFAULT 0
language        TEXT
category        TEXT
scraped_at      TEXT NOT NULL
created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
UNIQUE(source, project_name)
```

### custom_sources 表
```
id                INTEGER PRIMARY KEY AUTOINCREMENT
name              TEXT UNIQUE NOT NULL
description       TEXT
source_code       TEXT NOT NULL
config_schema     TEXT
enabled           INTEGER DEFAULT 1
created_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP
updated_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP
schedule_interval INTEGER DEFAULT 0
```

### users 表
```
id              INTEGER PRIMARY KEY AUTOINCREMENT
username        TEXT UNIQUE NOT NULL
password_hash   TEXT NOT NULL
role            TEXT DEFAULT 'user'
created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
```

---

## 部署方式

### Docker 部署
```bash
docker-compose up -d
```
- 管理后台：`http://localhost:5001/admin/`
- 前端页面：`http://localhost:8080/`

### 直接运行
```bash
pip install -r requirements.txt
python main.py --init-db
python main.py --admin
```

---

## 数据流转

```
数据源 (GitHub/HN/Reddit/掘金/V2EX/Gitee)
    │
    ▼
ScraperFramework (采集编排 + 重试 + 翻译)
    │
    ▼
SQLite 数据库 (projects 表)
    │
    ├──► HTMLGenerator → 静态前端页面
    ├──► ReportGenerator → Markdown 分析报告
    └──► Admin API (Flask) → Web 管理后台
```

---

## 开发

### 运行测试
```bash
pytest tests/ -v
```

### 代码检查
```bash
ruff check .
ruff format .
```

### 覆盖率
```bash
pytest --cov=. --cov-report=html
```
