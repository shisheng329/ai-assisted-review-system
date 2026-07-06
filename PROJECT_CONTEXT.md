# 项目上下文：AI 驱动文献筛选与分析系统

## 1. 项目基本信息

- 项目名称：AI 驱动文献筛选与分析系统。
- 代码项目名：`20260423-system-demo`。
- 当前定位：基于 `Streamlit + SQLite` 的多用户、多项目文献筛选与分析 SaaS Demo。
- 当前阶段：核心流程已可运行，正在补齐部署、文档、稳定性和长期使用能力。

## 2. 项目目标

项目目标是把文献研究中分散在 Excel、脚本、聊天工具和文献管理软件中的步骤集中到一个项目空间内：

1. 导入题录数据。
2. 配置筛选标准和 Prompt。
3. 执行 AI 辅助标题/摘要筛选。
4. 对筛选结果或新数据集做 BERTopic 聚类分析。
5. 按模板从 PDF 全文中抽取结构化信息。
6. 保存中间过程、版本历史和导出结果。

## 3. 使用场景与核心用户

适用场景包括范围综述、系统综述、证据图谱、文献计量辅助分析、课题组内部文献初筛和主题分析。核心用户是研究生、科研人员、小型课题组，以及希望用较低代码门槛完成文献筛选与分析的用户。

## 4. 当前主要功能逻辑

### 账户、项目和 API

- 用户可以注册、登录、退出。
- 登录状态通过 cookie/session 保持，session 已加入过期校验。
- 每个用户拥有自己的项目列表。
- 个人资料页维护 API 配置库，active 配置被 AI 扩写、双语审阅、文献筛选、PDF 提取和 LLM 后处理复用。
- 当前供应商目录包括 OpenAI、Anthropic、DeepSeek、通义千问、智谱、Kimi、豆包、Gemini、Groq、SiliconFlow 等。

### 数据接入

- 支持上传 CSV、XLSX、XLS 题录文件。
- 必填列：`Record-id`、`Title`、`Abstract`。
- 项目可以保存多个数据文件，并切换当前数据源。
- 删除数据文件时，会删除该数据文件关联的筛选运行、聚类运行及受管导出文件。

### 文献筛选

- 用户填写综述主题、研究关键点、纳入标准、排除标准和筛选维度。
- 筛选维度采用 `D1..Dn + 维度名称 + 维度说明` 的结构。
- AI 扩写是可选流程，不应成为强制前置条件。
- 系统可组装最终英文 Prompt，支持双语审阅、Prompt 版本保存和历史恢复。
- 筛选结果持久化保存，并支持导出。

### BERTopic 聚类分析

- 支持继承已完成的筛选结果，或上传新的聚类数据集。
- BERTopic 主流程不依赖 LLM。
- LLM 只作为后处理能力，用于主题命名、主题解释和图表解读。
- 图表解读按 `topic_run_id + chart_key` 保存，避免不同图表互相覆盖。

### PDF 提取

- 用户先上传 PDF 文件，再上传模板文件。
- 模板列名决定要提取的字段。
- 只有点击开始提取后才执行提取。
- 结果表包含文件名、模板字段和 `error_message`。
- 如果一批 PDF 全部失败，运行状态会标记为 `failed`。

## 5. 页面结构

未进入项目时包括登录/注册页、项目列表页、个人资料/API 配置页。进入项目后包括项目仪表盘、数据接入、文献筛选、聚类分析、PDF 提取和个人资料/API 配置。当前代码主要使用左侧 sidebar 导航；历史目标文档曾提到固定顶部导航，这一点属于待确认。

## 6. 数据结构和关键概念

SQLite schema 位于 `app/services/db.py`。

| 概念 | 表 | 说明 |
| --- | --- | --- |
| 用户 | `users` | 注册用户、邮箱、显示名、语言偏好 |
| 登录会话 | `sessions` | cookie token 与过期时间 |
| API 配置 | `api_configs` | 供应商、Base URL、模型、API Key、active 状态 |
| 项目 | `projects` | 研究项目，保存当前数据文件和当前 PDF 模板 |
| 题录文件 | `data_files` | 上传的 CSV/XLSX/XLS 数据文件 |
| 标准快照 | `criteria_snapshots` | 筛选草稿、维度、AI 扩写结果 |
| Prompt 版本 | `prompt_versions` | 完整 Prompt 与双语审阅结果 |
| 筛选运行/结果 | `screening_runs` / `screening_results` | 筛选任务和逐条结果 |
| 聚类运行/解读 | `topic_runs` / `topic_interpretations` | BERTopic 结果、图表和 LLM 解读 |
| PDF 模板/文件/运行/结果 | `pdf_templates` / `pdf_files` / `pdf_runs` / `pdf_results` | PDF 提取流程 |

## 7. 已确定的设计规则

- 不随意改变现有功能入口、页面流程和用户操作路径。
- 修改应克制、准确，只解决明确问题。
- 多文件项目必须明确当前数据源。
- AI 扩写是可选项。
- 文献筛选结果中的维度应优先使用 `D1..Dn`。
- BERTopic 聚类主流程不依赖 LLM。
- PDF 提取必须先模板、后执行。
- GitHub 仓库只保存代码、配置模板和文档，不保存运行数据。
- API Key、`.env`、数据库、上传文件、导出文件不得提交。
- 目标设计、当前实现、待确认内容必须分开记录。

## 8. 当前技术栈

- 前端/应用框架：Streamlit。
- 数据库：SQLite。
- 数据处理：Pandas、openpyxl、xlrd。
- 大模型调用：httpx，自定义 OpenAI-compatible 和 Anthropic-compatible transport。
- 可视化：Plotly。
- 聚类分析：BERTopic、UMAP、SentenceTransformers、scikit-learn。
- PDF 解析：pypdf。
- 部署：Python venv、Docker Compose、Nginx、systemd、Streamlit Community Cloud。

## 9. 重要文件和目录

| 路径 | 作用 |
| --- | --- |
| `app/main.py` | Streamlit 入口、登录态、页面导航、项目级 shell |
| `app/ui.py` | 页面标题、统计卡片、状态标签、全局 CSS |
| `app/modules/` | 各页面模块 |
| `app/services/` | 数据库、认证、存储、项目、LLM、筛选、BERTopic、PDF 等服务逻辑 |
| `app/i18n/messages.py` | 中文/英文界面文案 |
| `plans/test list.md` | 目标系统手册和交互规范基准 |
| `plans/*.md` | 历史修复计划和阶段计划 |
| `deploy/` | 非 Docker 部署、阿里云部署、Streamlit Cloud 测试部署说明 |
| `.streamlit/config.toml` | Streamlit Cloud/运行配置 |
| `requirements.txt` | Python 依赖 |
| `data/`、`uploads/`、`exports/` | 本地运行数据目录，已被 `.gitignore` 排除 |

## 10. 已明确提出过的关键需求

- 文档化项目上下文，方便新 Codex 聊天接续。
- 代码要干净、逻辑紧密，不希望为了实现某功能而把其他功能写得奇怪。
- 修改应克制、准确，不随意修改未提到的部分。
- 不改变系统现有功能的前提下修复已发现问题。
- 部署文档和代码提交要分清楚。
- 文档语言使用中文，技术名词可保留英文。
- 不确定内容必须标注“待确认”。

## 11. 不希望被随意改动的设定

- 不随意改页面结构、导航入口和已有工作流。
- 不随意改数据库 schema。
- 不随意改变筛选、聚类、PDF 提取的核心业务逻辑。
- 不把 Streamlit Community Cloud 描述成正式长期生产环境。
- 不提交本地运行数据、测试数据库、日志、API Key 或 `.env`。
- 不把历史目标文档中的理想状态误写成当前代码已经实现。

## 12. 需求与代码不一致之处

- 历史目标文档提到固定顶部导航；当前代码主要是左侧 sidebar 导航。是否要改为顶部固定导航待确认。
- 长期多人在线使用建议 PostgreSQL + 对象存储；当前代码仍使用 SQLite + 本地文件目录。
- `.streamlit/config.toml` 当前主题色偏蓝，而应用全局 CSS 已调整为绿色主题。是否统一待确认。
- `plans/test list.md` 是目标系统手册，其中部分交互可能是目标状态，不一定完全等同于当前代码。

## 13. 后续开发原则

1. 先读 `PROJECT_CONTEXT.md`、`TODO.md`、`README.md`、`开发记录.md` 和 `plans/test list.md`。
2. 再读相关代码模块，不要直接猜实现。
3. 小范围修改，小范围验证。
4. 优先保持现有功能稳定。
5. 修改前确认当前工作树，避免覆盖用户未提交改动。
6. 对不确定需求标注待确认，不擅自实现。
7. 涉及部署、数据持久化、安全、API Key 的改动要单独评估风险。
