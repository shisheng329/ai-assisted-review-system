# AI 驱动文献筛选与分析系统

一个基于 `Streamlit + SQLite` 的文献筛选与分析 SaaS Demo。系统支持多用户、多项目、题录数据导入、AI 辅助筛选、BERTopic 聚类分析、PDF 结构化提取和结果导出，适合范围综述、系统综述、证据图谱和课题组内部测试使用。

## 项目功能

- 用户注册、登录和个人 API 配置。
- 多项目管理。
- CSV/XLSX/XLS 题录数据导入。
- 多数据文件管理和当前数据源切换。
- AI 辅助文献筛选。
- Prompt 草稿、AI 扩写、双语审阅和版本历史。
- BERTopic 聚类分析。
- 主题命名、主题解释和图表解读。
- 基于模板的 PDF 信息提取。
- 筛选、聚类和 PDF 提取结果导出。
- 本地、Docker、云服务器和 Streamlit Community Cloud 测试部署支持。

## 技术栈

- 应用框架：Streamlit。
- 数据库：SQLite。
- 数据处理：Pandas、openpyxl、xlrd。
- 大模型调用：httpx。
- 可视化：Plotly。
- 聚类分析：BERTopic、UMAP、SentenceTransformers、scikit-learn。
- PDF 解析：pypdf。
- 部署：Python venv、Docker Compose、Nginx、systemd、Streamlit Community Cloud。

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

这些目录已被 `.gitignore` 排除，不应提交到 GitHub。

## Docker 运行（可选）

Docker 方式保留为本地或兼容环境测试方案。

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

## 在线部署

### 云服务器非 Docker 部署

推荐的正式测试架构：

```text
GitHub 仓库 -> 云服务器 git pull -> Python venv -> systemd -> Nginx -> HTTP/HTTPS
```

部署文档：

- `deploy/README.md`
- `deploy/ALIYUN_39.105.174.183.md`

推荐服务器数据目录：

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

### Streamlit Community Cloud 测试部署

Streamlit Community Cloud 适合快速测试和演示，不适合作为正式长期数据平台。详细说明见：

```text
deploy/STREAMLIT_CLOUD.md
```

部署参数：

```text
Branch: main
Main file path: app/main.py
Python version: 3.11
```

## 项目目录结构

```text
app/
  main.py                 # Streamlit 入口、登录态、导航和页面 shell
  ui.py                   # UI 辅助函数和全局样式
  i18n/messages.py        # 中英文界面文案
  modules/                # 项目、资料、仪表盘、数据接入、筛选、聚类、PDF 页面
  services/               # 数据库、认证、存储、LLM、筛选、BERTopic、PDF 服务
deploy/                   # 部署文档、systemd、Nginx、脚本
plans/                    # 目标系统手册和历史修复计划
data/                     # 本地数据库，忽略提交
uploads/                  # 本地上传文件，忽略提交
exports/                  # 本地导出文件，忽略提交
```

## 核心功能说明

### 数据接入

项目内可上传多个题录数据文件，并指定当前数据源。题录文件至少需要包含 `Record-id`、`Title`、`Abstract`。

### 文献筛选

用户填写综述主题、研究关键点、纳入标准、排除标准和筛选维度。系统支持 AI 扩写、跳过 AI 扩写、最终 Prompt 组装、双语审阅、Prompt 版本保存和筛选结果导出。

### BERTopic 聚类

聚类分析可继承已完成筛选结果，也可上传新的聚类数据集。BERTopic 主流程不依赖 LLM；LLM 仅用于主题命名、主题解释和图表解读。

### PDF 提取

用户上传 PDF 和模板文件，模板列名决定需要提取的字段。系统按模板输出结构化 CSV，并保留每个 PDF 的错误信息。

## 当前开发状态

当前系统核心流程已经具备用户和项目基础能力、数据接入和多文件管理、AI 文献筛选、BERTopic 聚类分析、PDF 模板提取、本地和在线部署文档。

最近一次代码清理已完成 session 过期校验、API 配置事务化、PDF 全失败状态、删除数据文件清理派生结果、BERTopic 来源稳定 key 和样式整理。

## 后续计划

- 用真实样例数据做完整端到端验收。
- 补充自动化测试。
- 评估 API Key 加密或外部密钥管理。
- 长期多人使用前评估 PostgreSQL 和对象存储。
- 评估后台任务队列，用于长时间筛选、聚类和 PDF 提取。
- 统一应用主题与 `.streamlit/config.toml` 的主题设置。

## 注意事项

- 不要提交 `.env`、API Key、数据库、上传文件、导出文件或日志。
- `data/`、`uploads/`、`exports/` 是运行数据目录，不属于代码仓库内容。
- SQLite 适合早期小规模测试；长期多人在线使用建议升级到 PostgreSQL。
- Streamlit Community Cloud 的本地文件不保证长期持久化，只适合测试部署。
- 后续开发前建议先阅读 `PROJECT_CONTEXT.md`、`TODO.md`、`开发记录.md` 和 `plans/test list.md`。
