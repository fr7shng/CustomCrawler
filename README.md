# GitHub Trending Scraper

多源趋势项目发现与分析平台 — 从 GitHub、HackerNews、Reddit、掘金、V2EX、Gitee 等平台采集热门项目，自动生成展示页面和分析报告。

## 核心功能

- **多源采集**: 支持 7 个内置数据源，可自定义扩展
- **智能分析**: 黑马项目识别、README 评分、语言热度分析
- **Web 展示**: 客户端筛选/搜索/分页的现代 HTML 界面
- **管理后台**: Flask Web 后台，支持项目管理、数据源配置、用户权限
- **定时任务**: 守护进程模式，按数据源独立配置刷新间隔
- **数据导出**: 支持 JSON / CSV / Markdown / TXT 格式导出
- **AI 辅助**: LLM 驱动的自定义爬虫代码生成
- **英中翻译**: 自动翻译英文项目名和描述为中文

## 快速开始

### 环境要求

- Python >= 3.9
- pip

### 安装

```bash
pip install -r requirements.txt
```

### 基本使用

```bash
# 初始化数据库
python main.py --init-db

# 采集所有数据源
python main.py --scrape

# 采集 + 生成 HTML 页面 + 分析报告
python main.py --scrape --generate --analyze

# 启动 Web 管理后台 (http://localhost:5001/admin/)
python main.py --admin

# 守护进程模式（定时自动采集）
python main.py --daemon
```

### Docker 部署

```bash
docker-compose up -d
```

- 管理后台：`http://localhost:5001/admin/`
- 前端页面：`http://localhost:8080/`

## 命令行参考

| 参数 | 说明 |
|------|------|
| `--init-db` | 初始化数据库 |
| `--scrape` | 采集所有启用的数据源 |
| `--generate` | 生成 HTML 展示页面 |
| `--analyze` | 趋势分析并生成 Markdown 报告 |
| `--report` | 仅生成报告（不重新采集） |
| `--stats` | 显示数据库统计信息 |
| `--daemon` | 守护进程模式 |
| `--admin` | 启动 Web 管理后台 |
| `--admin-port PORT` | 管理后台端口（默认：5001） |
| `--language LANG` | 按编程语言过滤 |
| `--config PATH` | 指定配置文件路径 |
| `--db PATH` | 指定数据库文件路径 |
| `--output DIR` | 指定 HTML 输出目录 |
| `--reports DIR` | 指定报告输出目录 |

## 数据源

内置数据源（需在 `config/sources.yaml` 中手动启用）：

| 数据源 | 说明 | 采集方式 | 状态 |
|--------|------|----------|------|
| GitHub Trending | GitHub 趋势项目 | HTML 解析 | 可用 |
| GitHub API | GitHub 趋势 API | GraphQL | 可用 |
| HackerNews | HN 热门帖子 | Firebase API | 可用 |
| Reddit | /r/programming 等版块 | JSON API | 待实现 |
| 掘金 | 中文技术社区热文 | REST API | 可用 |
| V2EX | 中文开发者论坛 | HTML 解析 | 待实现 |
| Gitee | 码云趋势项目 | REST API | 待实现 |

> **注意**：默认情况下所有内置数据源均为禁用状态。首次使用前，请编辑 `config/sources.yaml` 将需要的数据源 `enabled` 设为 `true`。

### 自定义数据源

通过管理后台的 LLM 代码生成功能，可以用自然语言描述来创建新的爬虫数据源。生成的自定义数据源存储在数据库中，支持动态加载和定时调度。

## 配置

编辑 `config/sources.yaml` 来控制数据源行为:

```yaml
sources:
  github_html:
    enabled: true
    priority: 1
    schedule_interval: 30   # 每 30 分钟刷新
  hackernews:
    enabled: true
    priority: 3
    top_count: 30

translation:
  enabled: true             # 启用英中翻译
  target_lang: zh-CN
```

## 环境变量

| 变量 | 说明 | 必需 |
|------|------|------|
| `GITHUB_TOKEN` | GitHub Personal Access Token | 否 |
| `PH_API_KEY` | Product Hunt API Key | 否 |
| `HTTP_PROXY` | HTTP 代理地址 | 否 |
| `DATABASE_PATH` | 数据库文件路径 | 否 |
| `FLASK_SECRET_KEY` | Flask 密钥（Docker 部署时） | 否 |
| `LOG_LEVEL` | 日志级别 | 否 |

## 项目结构

```
githubPH/
├── main.py                    # CLI 入口
├── admin_server.py            # Flask 管理服务入口
├── scraper/                   # 数据采集层
│   └── sources/               # 7 个内置数据源 + 自定义扩展
├── storage/                   # SQLite 数据持久层
├── generator/                 # HTML 静态页面生成
├── analyzer/                  # 数据分析（黑马/热度/评分）
├── admin/                     # Web 管理后台
│   └── templates/             # 16 个管理页面模板
├── config/                    # 配置管理
└── docs/                      # 项目文档
```

详细结构参见 [ARCHITECTURE_OPTIMIZATION.md](ARCHITECTURE_OPTIMIZATION.md)。

## 开发

```bash
# 安装开发依赖
pip install -r requirements.txt

# 运行测试
make test

# 代码检查
make lint

# 代码格式化
make format
```

## License

MIT
