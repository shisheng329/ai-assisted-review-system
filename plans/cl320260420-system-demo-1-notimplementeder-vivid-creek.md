# 修改计划：20260423-system-demo 系统功能微调（13项优化）

## Context（背景）

用户正处于系统功能微调阶段，需要对20260423-system-demo（基于Streamlit的文献筛选与分析SaaS平台）进行13项细节优化。系统使用Docker部署，代码通过volume挂载自动同步。所有修改需要：
- 最小化对其他代码的干扰
- 保持现有功能稳定
- 必须获得用户批准后才能执行

**用户提供的13个问题：**
1. 导航栏布局：返回按钮和功能切换按钮应在同一行，固定顶部，移除"项目导航"标签
2. PDF/模板上传413错误：`AxiosError: Request failed with status code 413`
3. BERTopic分析失败：`Object of type ndarray is not JSON serializable`
4. 组装prompt后文本框未显示内容
5. 检查并补充所有中文翻译
6. 筛选页面"保存为新版本"按钮应在"双语审阅"按钮之前
7. 筛选页面"运行筛选"按钮应在参数设置之前
8. 筛选页面"筛选结果"应显示在"开始筛选"之前
9. 筛选页面"修订历史"应改为"历史记录"
10. BERTopic页面"运行分析"按钮应在参数设置之前
11. BERTopic页面"分析结果"应显示在"开始分析"之前
12. PDF提取页面"运行提取"按钮应在参数设置之前
13. PDF提取页面"提取结果"应显示在"开始提取"之前

---

## 问题分析与修复方案

### 问题1：导航栏布局重构

**当前代码：** [app/main.py:134-160](e:\vscodeprojects\20260423-system-demo\app\main.py#L134-L160)

**问题：**
- "返回项目列表"按钮单独一行
- 功能切换按钮在下一行
- 有"项目导航"标签

**修复方案：**
重构 `render_project_topbar()` 函数，将返回按钮和segmented_control整合到topbar的列布局中：
```python
# 在topbar内部使用columns布局
title_col, project_col, back_col, nav_col, action_col = st.columns([...])
# back_col放返回按钮
# nav_col放segmented_control（label_visibility="collapsed"）
```

**影响范围：** 仅影响项目功能页面的顶部导航栏布局

---

### 问题2：PDF/模板上传413错误

**当前配置：**
- [nginx.conf:12](e:\vscodeprojects\20260423-system-demo\nginx.conf#L12): `client_max_body_size 100m`
- [.streamlit/config.toml:7](e:\vscodeprojects\20260423-system-demo\.streamlit\config.toml#L7): `maxUploadSize = 100`

**修复方案：**
1. 将 `nginx.conf` 的 `client_max_body_size` 增加到 `200m`
2. 将 `.streamlit/config.toml` 的 `maxUploadSize` 增加到 `200`
3. 修改后需要重启Docker容器：`docker compose restart`

**影响范围：** 所有文件上传功能

---

### 问题3：BERTopic分析失败 - ndarray JSON序列化错误

**问题代码：** [app/services/bertopic_service.py:23-24](e:\vscodeprojects\20260423-system-demo\app\services\bertopic_service.py#L23-L24)

**根本原因：**
`_topic_info_records()` 函数中，`topic_info.to_dict(orient="records")` 返回的字典包含numpy数组，无法JSON序列化。已有 `to_json_compatible()` 工具函数但未正确处理。

**修复方案：**
修改 `_topic_info_records()` 函数，确保numpy类型转换：
```python
def _topic_info_records(topic_info: pd.DataFrame) -> list[dict[str, Any]]:
    records = topic_info.fillna("").to_dict(orient="records")
    return to_json_compatible(records)  # 已有的工具函数会处理numpy类型
```

**影响范围：** 仅影响BERTopic分析结果的保存

---

### 问题4：组装prompt后文本框未显示内容

**问题代码：** [app/modules/llm_screening.py:191-192](e:\vscodeprojects\20260423-system-demo\app\modules\llm_screening.py#L191-L192)

**根本原因：**
Streamlit的执行顺序问题，按钮点击更新session_state后需要rerun才能在text_area中显示。

**修复方案：**
在两处按钮点击后添加 `st.rerun()`：
- 第139行：跳过AI扩写路径的"组装prompt"按钮
- 第191行：使用AI扩写路径的"组装prompt"按钮

**影响范围：** 仅影响筛选页面的prompt组装交互

---

### 问题5：检查并补充所有中文翻译

**需要检查的文件：**
- [app/modules/llm_screening.py](e:\vscodeprojects\20260423-system-demo\app\modules\llm_screening.py)
- [app/modules/bertopic_analysis.py](e:\vscodeprojects\20260423-system-demo\app\modules\bertopic_analysis.py)
- [app/modules/pdf_extraction.py](e:\vscodeprojects\20260423-system-demo\app\modules\pdf_extraction.py)

**修复方案：**
1. 搜索所有硬编码的英文字符串
2. 在 [app/i18n/messages.py](e:\vscodeprojects\20260423-system-demo\app\i18n\messages.py) 中添加缺失的翻译键
3. 替换硬编码文本为 `t("key")` 调用

**影响范围：** 所有界面的中文显示

---

### 问题6：筛选页面按钮顺序调整

**问题代码：** [app/modules/llm_screening.py:199-208](e:\vscodeprojects\20260423-system-demo\app\modules\llm_screening.py#L199-L208)

**当前顺序：**
```python
col4, col5 = st.columns(2)
if col4.button(t("save_as_new_version"), ...):  # 保存为新版本
if col5.button(t("bilingual_review"), ...):     # 双语审阅
```

**修复方案：**
交换两个按钮的位置，让"双语审阅"在左，"保存为新版本"在右：
```python
col4, col5 = st.columns(2)
if col4.button(t("bilingual_review"), ...):     # 双语审阅
if col5.button(t("save_as_new_version"), ...):  # 保存为新版本
```

**影响范围：** 仅影响筛选页面的按钮布局

---

### 问题7-8：筛选页面内容顺序调整

**问题代码：** [app/modules/llm_screening.py:216-258](e:\vscodeprojects\20260423-system-demo\app\modules\llm_screening.py#L216-L258)

**当前顺序：**
1. "开始筛选"标题
2. 参数设置（batch_size, rate_limit, temperature）
3. "运行筛选"按钮
4. "筛选结果"部分

**修复方案：**
重新组织代码顺序：
1. 先显示"筛选结果"部分（如果有历史运行记录）
2. 再显示"开始筛选"标题
3. "运行筛选"按钮
4. 参数设置

**影响范围：** 仅影响筛选页面的内容布局顺序

---

### 问题9：筛选页面"修订历史"改为"历史记录"

**问题代码：** [app/modules/llm_screening.py:260](e:\vscodeprojects\20260423-system-demo\app\modules\llm_screening.py#L260)

**修复方案：**
1. 在 [app/i18n/messages.py](e:\vscodeprojects\20260423-system-demo\app\i18n\messages.py) 中添加新的翻译键 `"history_records": "历史记录"`
2. 将 `t("revision_history")` 改为 `t("history_records")`

**影响范围：** 仅影响筛选页面的expander标题

---

### 问题10-11：BERTopic页面内容顺序调整

**问题代码：** [app/modules/bertopic_analysis.py](e:\vscodeprojects\20260423-system-demo\app\modules\bertopic_analysis.py) 中的render函数

**当前顺序：**
1. "开始分析"标题
2. 参数设置
3. "运行分析"按钮
4. "分析结果"部分

**修复方案：**
重新组织代码顺序：
1. 先显示"分析结果"部分（如果有历史运行记录）
2. 再显示"开始分析"标题
3. "运行分析"按钮
4. 参数设置

**影响范围：** 仅影响BERTopic页面的内容布局顺序

---

### 问题12-13：PDF提取页面内容顺序调整

**问题代码：** [app/modules/pdf_extraction.py](e:\vscodeprojects\20260423-system-demo\app\modules\pdf_extraction.py) 中的render函数

**当前顺序：**
1. "开始提取"标题
2. 参数设置
3. "运行提取"按钮
4. "提取结果"部分

**修复方案：**
重新组织代码顺序：
1. 先显示"提取结果"部分（如果有历史运行记录）
2. 再显示"开始提取"标题
3. "运行提取"按钮
4. 参数设置

**影响范围：** 仅影响PDF提取页面的内容布局顺序

---

## 实施步骤

### 第一步：修复配置文件（问题2）
- 文件：[nginx.conf](e:\vscodeprojects\20260423-system-demo\nginx.conf), [.streamlit/config.toml](e:\vscodeprojects\20260423-system-demo\.streamlit\config.toml)
- 增加上传大小限制到200MB
- 需要重启Docker容器

### 第二步：修复核心bug（问题3、4）
- 文件：[app/services/bertopic_service.py](e:\vscodeprojects\20260423-system-demo\app\services\bertopic_service.py)
- 修复JSON序列化错误
- 文件：[app/modules/llm_screening.py](e:\vscodeprojects\20260423-system-demo\app\modules\llm_screening.py)
- 添加st.rerun()调用

### 第三步：修复导航栏布局（问题1）
- 文件：[app/main.py](e:\vscodeprojects\20260423-system-demo\app\main.py)
- 重构render_project_topbar()函数

### 第四步：调整筛选页面布局（问题6、7、8、9）
- 文件：[app/modules/llm_screening.py](e:\vscodeprojects\20260423-system-demo\app\modules\llm_screening.py)
- 调整按钮顺序和内容顺序
- 更新翻译键

### 第五步：调整BERTopic页面布局（问题10、11）
- 文件：[app/modules/bertopic_analysis.py](e:\vscodeprojects\20260423-system-demo\app\modules\bertopic_analysis.py)
- 调整内容顺序

### 第六步：调整PDF提取页面布局（问题12、13）
- 文件：[app/modules/pdf_extraction.py](e:\vscodeprojects\20260423-system-demo\app\modules\pdf_extraction.py)
- 调整内容顺序

### 第七步：检查并补充中文翻译（问题5）
- 文件：[app/i18n/messages.py](e:\vscodeprojects\20260423-system-demo\app\i18n\messages.py)
- 检查所有模块文件，补充缺失的翻译

---

## 验证清单

修改完成后，需要验证以下功能：

- [ ] 导航栏：返回按钮和功能切换在同一行，固定顶部，无"项目导航"标签
- [ ] 文件上传：可以成功上传大文件（50MB+）
- [ ] BERTopic分析：正常运行并保存结果，无JSON序列化错误
- [ ] Prompt组装：点击按钮后文本框立即显示内容
- [ ] 筛选页面：按钮顺序正确，结果在参数之前，"历史记录"标题正确
- [ ] BERTopic页面：按钮在参数之前，结果在参数之前
- [ ] PDF提取页面：按钮在参数之前，结果在参数之前
- [ ] 中文翻译：所有界面文本正确显示为中文

---

## 风险评估

**低风险修改：**
- 问题2（上传限制）：仅修改配置值
- 问题3（JSON序列化）：使用已有工具函数
- 问题4（prompt显示）：仅添加rerun调用
- 问题6、9（文本和按钮顺序）：仅调整UI顺序
- 问题7、8、10、11、12、13（内容顺序）：仅移动代码块位置

**中风险修改：**
- 问题1（导航栏重构）：涉及topbar结构调整，需要仔细测试
- 问题5（翻译补充）：需要全面检查，确保无遗漏

**注意事项：**
- 所有修改都需要在Docker环境中验证
- 保持代码风格一致
- 内容顺序调整时注意变量依赖关系
