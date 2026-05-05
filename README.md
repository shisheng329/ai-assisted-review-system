# 20260423 Streamlit Literature Screening SaaS Demo

这是一个基于 `Streamlit + SQLite` 的文献筛选与分析系统，支持多用户、多项目、题录数据导入、AI 辅助筛选、BERTopic 聚类分析和 PDF 结构化提取。

系统可以用三种方式运行：

1. 本地 Python 虚拟环境运行。
2. 云服务器非 Docker 部署，适合做成在线访问网页。
3. Docker Compose 运行，作为可选兼容方式保留。

## 主要能力

- 用户注册、登录和个人 API 配置。
- 多项目管理。
- CSV/XLSX/XLS 题录数据导入。
- 多数据文件管理和当前数据源切换。
- AI 辅助文献筛选、Prompt 版本和双语审阅。
- BERTopic 聚类分析。
- 基于模板的 PDF 信息提取。
- 结果导出。

## 本地运行

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
streamlit run app/main.py --server.port 8502
```

访问：

```text
http://localhost:8502
```

本地默认运行数据目录：

```text
data/
uploads/
exports/
```

这些目录已被 `.gitignore` 排除，不会上传到 GitHub。

## 在线部署

如果要做成“点击链接即可访问”的网页，推荐第一阶段使用云服务器直接运行 Python，不依赖 Docker。

推荐架构：

```text
GitHub 私有仓库 -> 云服务器 git pull -> Python venv -> systemd -> Nginx -> HTTPS 域名
```

推荐服务器：

- 测试最低配置：2 核 4G
- 小范围课题组推荐：4 核 8G
- BERTopic 数据量较大：4 核 16G 或更高
- 系统：Ubuntu 22.04 LTS 或 24.04 LTS
- 硬盘：至少 80GB，建议 100GB 以上

部署模板见：

```text
deploy/
```

快速部署说明见：

```text
deploy/README.md
```

服务器推荐运行数据目录：

```text
/opt/literature-screening-data/app.db
/opt/literature-screening-data/uploads
/opt/literature-screening-data/exports
```

对应环境变量：

```env
DATABASE_PATH=/opt/literature-screening-data/app.db
UPLOADS_PATH=/opt/literature-screening-data/uploads
EXPORTS_PATH=/opt/literature-screening-data/exports
```

## GitHub 上传原则

GitHub 仓库只保存代码、配置模板和部署文档。

不要提交：

- `.env`
- API Key
- 数据库文件
- `data/`
- `uploads/`
- `exports/`
- `.venv/`

当前 `.gitignore` 已排除这些运行数据。正式推送前仍建议执行：

```powershell
git status --short
```

确认没有敏感文件被加入暂存区。

## Docker 运行（可选）

Docker 方式仍然保留，但不是在线部署的必需方式。

```powershell
docker compose build --no-cache
docker compose up -d
```

访问：

```text
http://localhost:8503
```

健康检查：

```text
http://localhost:8503/health
```

## 关键模块

- `app/main.py`：系统入口和应用壳层。
- `app/modules/`：页面模块。
- `app/services/`：数据库、认证、项目、存储、LLM、BERTopic、PDF 和导出逻辑。
- `app/i18n/`：中英文界面文案。
- `deploy/`：非 Docker 在线部署模板。

## 长期多人使用建议

当前 SQLite 方案适合自己或小范围课题组使用。若要长期多人在线使用，建议后续升级：

- SQLite 迁移到 PostgreSQL。
- 上传文件迁移到对象存储，例如阿里云 OSS、腾讯云 COS 或 S3。
- API Key 加密存储。
- 增加管理员后台、用户配额、日志监控和后台任务队列。
