# 20260423 Streamlit Literature Screening SaaS Demo

## Summary

从零实现一个 `Streamlit` 多用户文献筛选 SaaS demo，目录为 `e:\vscodeprojects\20260423-system-demo`，不参照现有系统代码。系统以你提供的 3 份文档为准：

- [test list.md](</e:/vscodeprojects/20260423-系统demo3/test list.md>)：页面流程与交互规范
- [20260420-prompt 结构.pdf](</e:/vscodeprojects/20260423-系统demo3/20260420-prompt%20结构.pdf>)：内置筛选 prompt 结构
- [bertopic.txt](</e:/vscodeprojects/20260423-系统demo3/bertopic.txt>)：BERTopic 全流程算法

系统定位明确为 `Streamlit 多用户 SaaS`：
- 公开注册
- 每个用户拥有自己的私有项目
- 暂不做多人协作
- 单服务 `Docker Compose + SQLite`
- 本地代码挂载进容器，网页随代码修改实时更新

## Key Changes

### 1. SaaS account and tenancy model

- 实现公开注册、登录、登出、会话保持。
- 用户隔离按 `user_id` 实现，所有项目、API 配置、数据文件、筛选结果、聚类结果、PDF 结果都归属于当前登录用户。
- 项目为私有项目：
  - 创建者可见、可编辑
  - 其他用户不可见
  - 不做邀请、共享、成员权限
- 页面进入逻辑按 SaaS 方式统一：
  - 未登录只能看到登录/注册页
  - 登录后进入项目列表
  - 任意项目页访问都校验项目归属权

### 2. App architecture

- 新建独立工程：
  - `app/main.py`
  - `app/modules/data_input.py`
  - `app/modules/llm_screening.py`
  - `app/modules/bertopic_analysis.py`
  - `app/modules/pdf_extraction.py`
  - `app/services/` 负责数据库、认证、文件、LLM、BERTopic、导出
  - `app/i18n/` 负责中英文文案
- 技术栈固定：
  - `Streamlit`
  - `SQLite`
  - `pandas`
  - `BERTopic`
  - `sentence-transformers`
- `SQLite` 存用户、项目和运行状态；上传文件与导出文件存磁盘。

### 3. Screening module based on your prompt PDF

- 筛选模块的最终 prompt 使用固定模板骨架，不做自由式 prompt 拼接。
- 模板必须包含：
  - role setting
  - core screening principle
  - non-negotiable rules
  - review topic
  - inclusion / exclusion criteria
  - `D1..Dn` screening dimensions
  - decision logic
  - primary reason code rule
  - confidence guidance
  - output requirements
  - final validation check
- 用户只编辑变量部分：
  - 综述主题
  - 纳入标准
  - 排除标准
  - `D1..Dn` 维度名称与说明
  - AI 扩写后的英文内容
- 执行逻辑严格遵循 PDF：
  - 仅基于 `Title` 和 `Abstract`
  - 缺失信息倾向 `maybe`
  - `exclude` 只在明确 fatal mismatch 时使用
- 原始输出 schema 以 PDF 为准：
  - `record_id`
  - `title`
  - `decision`
  - `confidence`
  - `D1..Dn`
  - `primary_reason_code`
  - `rationale`
- 允许值固定：
  - `decision`: `include / exclude / maybe`
  - `confidence`: `high / medium / low`
  - `D1..Dn`: `yes / no / unclear`
- 仍保留 `test list.md` 要求的三步交互：
  - 标准草稿与 AI 扩写
  - Prompt 组装与双语审阅
  - 执行筛选与导出
- 保存两类历史：
  - 标准快照
  - Prompt 版本

### 4. BERTopic module based on your algorithm

- 聚类分析模块严格按你提供的算法落地：
  - 文本输入：`Title + ". " + Abstract`
  - 空值补空字符串
  - `CountVectorizer(stop_words="english")`
  - `UMAP(n_neighbors=15, n_components=5, min_dist=0.0, metric="cosine", random_state=42)`
  - `BERTopic(language="multilingual", embedding_model=SentenceTransformer("all-MiniLM-L6-v2"), min_topic_size=5, nr_topics=15)`
- 默认输出：
  - `Topic`
  - `Topic_Name`
- 默认图表：
  - 关键词条形图
  - 主题气泡图
  - 层级图
- 参数面板对外暴露：
  - `random_state`
  - `n_neighbors`
  - `n_components`
  - `min_topic_size`
  - `nr_topics`
- 聚类数据源支持：
  - 继承筛选结果
  - 上传新的 `CSV/XLSX`
- BERTopic 主流程不依赖 LLM；LLM 仅用于：
  - 主题命名增强
  - 主题简介
  - 图表解读
- 每个图表的解读独立保存，不互相覆盖。

### 5. Other product modules

- 项目列表页：
  - 显示当前用户自己的项目
  - 创建项目
  - 直接打开项目
- 个人资料/API 配置页：
  - 多供应商 API 配置库
  - 每套配置绑定 `provider/base_url/api_key/model`
  - 配置持久化
- 仪表盘：
  - 文献总量、纳入数、主题数、PDF 提取结果数、筛选分布、最近活动时间
- 数据接入页：
  - 支持 `CSV/XLSX/XLS`
  - 强校验 `Record-id/Title/Abstract`
  - 多文件管理、切换激活文件、删除文件
- PDF 提取页：
  - 先传 PDF
  - 再传模板
  - 先预览模板再保存
  - 只有点击“开始提取”才执行
- 国际化：
  - 中文/英文
  - 不允许界面出现未翻译 key

## Test Plan

- 多用户 SaaS：
  - 用户 A 无法看到用户 B 的项目、文件和结果
  - 未登录访问项目页会被拦回登录
  - 公开注册可正常创建新账号
- 筛选模块：
  - 最终 prompt 结构与 PDF 骨架一致
  - 输出字段名、顺序、allowed values 与 PDF 一致
  - `maybe` 与 `exclude` 的判定符合 recall-oriented 规则
- BERTopic：
  - 默认参数与 `bertopic.txt` 一致
  - 输出包含 `Topic` 和 `Topic_Name`
  - 三类图表都可渲染
- 数据接入：
  - 缺列时准确提示
  - 激活文件切换后后续页面同步更新
- 国际化：
  - 中文模式不出现 key
- Docker：
  - `docker compose up -d` 可启动
  - 修改本地代码后页面自动刷新
  - `/health` 正常返回

## Assumptions

- 这是 SaaS demo，不是生产级 SaaS；不做管理员后台、计费、邮件验证、邀请码、审计日志。
- 多用户范围仅到“公开注册 + 私有项目隔离”，不做团队协作。
- 所有 LLM 功能只接真实 API，不提供 mock。
- 默认嵌入模型固定为 `all-MiniLM-L6-v2`，因为这是你提供算法里明确指定的模型。
- 部署保持单服务 `Streamlit + SQLite`，优先满足 demo 可运行性和热更新。
