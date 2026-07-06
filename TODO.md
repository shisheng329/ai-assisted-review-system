# TODO：AI 驱动文献筛选与分析系统

> 本文件用于后续开发接续。任务按状态分类，避免把已完成和未完成内容混在一起。

## 已完成

| 任务内容 | 当前状态 | 涉及文件 | 优先级 | 是否需要确认 |
| --- | --- | --- | --- | --- |
| 多用户注册、登录、退出和 session 机制 | 已完成，session 已增加过期校验 | `app/main.py`、`app/services/auth.py`、`app/services/db.py` | 高 | 否 |
| 多项目管理 | 已完成基础能力 | `app/modules/project_list.py`、`app/services/projects.py` | 高 | 否 |
| 数据文件上传、校验、预览、激活和删除 | 已完成；删除时已清理关联派生结果 | `app/modules/data_input.py`、`app/services/storage.py` | 高 | 否 |
| API 配置库和多供应商支持 | 已完成基础能力；保存 active 配置已事务化 | `app/modules/profile.py`、`app/services/llm.py`、`app/services/provider_catalog.py` | 高 | 否 |
| Prompt 草稿、AI 扩写、双语审阅和 Prompt 版本 | 已完成主要流程 | `app/modules/llm_screening.py`、`app/services/screening.py`、`app/services/prompting.py` | 高 | 否 |
| 文献筛选运行与结果导出 | 已完成主要流程 | `app/services/screening.py`、`app/modules/llm_screening.py` | 高 | 否 |
| BERTopic 聚类、主题命名、主题解释和图表解读 | 已完成主要流程；来源选择已改为稳定 key | `app/modules/bertopic_analysis.py`、`app/services/bertopic_service.py` | 高 | 否 |
| PDF 模板提取 | 已完成主要流程；全失败任务会标记为 `failed` | `app/modules/pdf_extraction.py`、`app/services/pdf_service.py`、`app/services/storage.py` | 高 | 否 |
| 阿里云非 Docker 部署文档 | 已完成 | `deploy/README.md`、`deploy/ALIYUN_39.105.174.183.md`、`deploy/scripts/` | 中 | 否 |
| Streamlit Cloud 测试部署文档和配置 | 已完成 | `deploy/STREAMLIT_CLOUD.md`、`.streamlit/config.toml` | 中 | 否 |
| 最近 7 项代码清理修复 | 已完成并已提交为 `99c536b Fix code cleanup issues` | `app/main.py`、`app/ui.py`、`app/services/*`、`app/modules/*` | 高 | 否 |

## 正在进行

| 任务内容 | 当前状态 | 涉及文件 | 优先级 | 是否需要确认 |
| --- | --- | --- | --- | --- |
| 项目上下文文档整理 | 正在进行，本次创建 `PROJECT_CONTEXT.md`、`TODO.md`、`README.md`、`开发记录.md` | 根目录 Markdown 文档 | 高 | 否 |
| README 正式化与中文可读性整理 | 正在进行，保留原有运行/部署信息并重写为 GitHub 友好格式 | `README.md` | 高 | 否 |

## 待完成

| 任务内容 | 当前状态 | 涉及文件 | 优先级 | 是否需要确认 |
| --- | --- | --- | --- | --- |
| 真实端到端手动验收 | 待完成，需要用真实或样例数据逐页验证 | 全系统 | 高 | 否 |
| 自动化测试补充 | 待完成，目前主要依赖手动验证和轻量静态检查 | `app/services/`、可能新增 `tests/` | 高 | 是 |
| 长期多人使用的数据层升级评估 | 待完成，当前仍为 SQLite | `app/services/db.py`、部署配置 | 中 | 是 |
| API Key 加密或外部密钥管理 | 待完成，当前 API Key 存入 SQLite | `app/services/llm.py`、`app/modules/profile.py`、部署环境 | 高 | 是 |
| 运行日志和错误追踪 | 待完成，目前缺少系统化日志 | 全系统、部署脚本 | 中 | 是 |
| 后台任务队列 | 待完成，筛选、BERTopic、PDF 提取仍在 Streamlit 交互流程中执行 | `app/services/screening.py`、`app/services/bertopic_service.py`、`app/services/pdf_service.py` | 中 | 是 |
| 管理员能力和用户配额 | 待完成，当前没有管理员后台 | 新增模块，待设计 | 低 | 是 |
| 部署矩阵整理 | 待完成，需要明确本地、Docker、阿里云、Streamlit Cloud 的适用边界 | `README.md`、`deploy/` | 中 | 否 |

## 需要我确认

| 任务内容 | 当前状态 | 涉及文件 | 优先级 | 是否需要确认 |
| --- | --- | --- | --- | --- |
| 是否继续以绿色主题作为最终 UI 规则 | 待确认；代码全局 CSS 偏绿色 | `app/ui.py` | 中 | 是 |
| `.streamlit/config.toml` 的蓝色主题是否改成绿色 | 待确认；当前 `.streamlit` 配置偏蓝，应用 CSS 偏绿 | `.streamlit/config.toml`、`app/ui.py` | 中 | 是 |
| README 标题使用中文还是英文项目名 | 待确认；当前 README 使用中文主标题和英文技术名词 | `README.md` | 低 | 是 |
| Streamlit Cloud 是否只定位为测试部署 | 建议确认为测试部署，不作为正式生产 | `deploy/STREAMLIT_CLOUD.md`、`README.md` | 高 | 是 |
| 是否将历史目标中的顶部固定导航纳入后续开发 | 待确认；当前代码使用 sidebar 导航 | `app/main.py`、`app/ui.py` | 中 | 是 |

## 可能存在问题或风险

| 风险 | 当前状态 | 涉及文件 | 优先级 | 是否需要确认 |
| --- | --- | --- | --- | --- |
| SQLite 不适合长期多人高并发 | 当前仍使用 SQLite | `app/services/db.py`、部署配置 | 高 | 是 |
| Streamlit Community Cloud 本地文件持久性有限 | 已在部署文档中提示 | `deploy/STREAMLIT_CLOUD.md` | 高 | 否 |
| API Key 当前落库 | 功能可用，但长期使用需要加密或外部密钥管理 | `api_configs`、`app/services/llm.py` | 高 | 是 |
| BERTopic 依赖较重 | 小配置云环境可能运行慢或失败 | `requirements.txt`、`app/services/bertopic_service.py` | 中 | 否 |
| 本地存在被忽略的测试数据库/日志文件 | 不影响 Git，但需要避免误提交 | `.gitignore`、根目录本地文件 | 中 | 否 |
| 目标文档与当前实现可能不完全一致 | `plans/test list.md` 是目标手册，不等于所有功能都已完全实现 | `plans/test list.md`、当前代码 | 中 | 否 |

## 后续优化建议

| 建议 | 当前状态 | 涉及文件 | 优先级 | 是否需要确认 |
| --- | --- | --- | --- | --- |
| SQLite 迁移到 PostgreSQL | 建议长期多人使用前评估 | `app/services/db.py`、部署配置 | 高 | 是 |
| 上传和导出文件迁移到对象存储 | 建议与 PostgreSQL 一起评估 | `app/services/storage.py` | 高 | 是 |
| API Key 加密存储 | 建议优先级较高 | `app/services/llm.py` | 高 | 是 |
| 增加后台任务队列 | 可改善长任务稳定性 | 筛选、BERTopic、PDF 服务 | 中 | 是 |
| 增加系统化测试清单和自动化测试 | 建议逐步补充 | `tests/`、`plans/test list.md` | 高 | 是 |
| 统一部署文档和 README 的部署矩阵 | 建议保持 README 简洁，细节放 `deploy/` | `README.md`、`deploy/` | 中 | 否 |
| 统一 `.streamlit` 主题和应用 CSS 主题 | 待确认后执行 | `.streamlit/config.toml`、`app/ui.py` | 低 | 是 |
