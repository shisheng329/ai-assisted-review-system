# 修复计划：20260423-system-demo 系统问题修复（11项）

## Context（背景）

用户在使用20260423-system-demo（基于Streamlit的文献筛选与分析SaaS平台）时发现了11个新问题，需要修复。系统使用Docker部署，代码通过volume挂载自动同步。

**用户提供的11个问题：**
1. 筛选页面选择历史版本时报错：`st.session_state.screening_1_workflow_mode cannot be modified after widget instantiated`
2. AI扩写时需要确保所有用户输入（包括维度名称和描述）都翻译成英文
3. 系统无法正常调用大模型（已配置API key和模型）
4. 调用大模型速度太慢（如双语审阅加载很久）
5. 选择prompt历史版本时报错：`st.session_state.screening_1_prompt_editor cannot be modified after widget instantiated`
6. 点击开始筛选后一直无法筛选成功
7. BERTopic图表解读应该针对用户数据的分析结果，而不是解释图表类型
8. PDF上传报错：`application/pdf files are not allowed`
9. 模板上传报错：`application/vnd.openxmlformats-officedocument.spreadsheetml.sheet files are not allowed`
10. 结果界面应该在操作部分下方，而不是最上方（影响用户体验）
11. 顶部导航栏被截断，系统名称和按钮显示不完整

---

## 问题分析与修复方案

### 问题1：选择历史版本时workflow_mode报错

**根本原因：**
Streamlit的widget状态管理限制：一旦widget被创建（如`st.radio`），就不能在同一次渲染中修改其对应的session_state值。

**问题代码：** [app/modules/llm_screening.py:292](e:\vscodeprojects\20260423-system-demo\app\modules\llm_screening.py#L292)
```python
st.session_state[f"{prefix}_workflow_mode"] = "use_ai" if snapshot["ai_expanded"] else "skip_ai"
```

这行代码在按钮回调中直接修改了`workflow_mode`，但该值已经被第125-131行的`st.radio`绑定为widget的key。

**修复方案：**
不要在按钮回调中直接修改`workflow_mode`，而是让系统根据`ai_expanded`的状态自动推断。修改逻辑：
1. 移除第292行的直接赋值
2. 在`_ensure_state`函数中根据恢复的数据自动设置workflow_mode

**影响范围：** 仅影响筛选页面的历史版本恢复功能

---

### 问题2：AI扩写时需要翻译所有用户输入为英文

**根本原因：**
当前的AI扩写prompt（[app/services/prompting.py:116-142](e:\vscodeprojects\20260423-system-demo\app\services\prompting.py#L116-L142)）只是要求"expand into polished academic English"，但没有明确要求翻译用户输入的中文内容。

**修复方案：**
修改`build_ai_expansion_prompt`函数，在prompt中明确要求：
1. 将所有中文内容翻译为英文
2. 特别强调维度名称和描述也需要翻译
3. 保持学术规范的英文表达

**影响范围：** 仅影响AI扩写功能的输出质量

---

### 问题3：系统无法正常调用大模型

**需要诊断的方向：**
1. 检查API配置是否正确保存到数据库
2. 检查`get_active_api_config`是否正确返回配置
3. 检查网络请求是否正确构建（headers、endpoint、payload）
4. 检查错误处理是否正确显示错误信息

**诊断方案：**
需要用户提供具体的错误信息或日志。如果没有错误提示，需要在关键位置添加调试日志：
- [app/services/llm.py:220-231](e:\vscodeprojects\20260423-system-demo\app\services\llm.py#L220-L231) `chat_text`函数
- 检查config是否为None
- 检查API请求的实际endpoint和headers

**临时修复：**
在调用LLM的地方添加更详细的错误提示，帮助用户诊断问题。

---

### 问题4：调用大模型速度太慢

**根本原因分析：**
查看代码发现timeout设置为120秒（[app/services/llm.py:200](e:\vscodeprojects\20260423-system-demo\app\services\llm.py#L200)），这是合理的。速度慢可能是：
1. 模型本身响应慢（服务商问题）
2. 网络延迟高
3. prompt太长导致处理时间长

**代码检查结果：**
- 使用了`httpx.Client(timeout=120)`，超时设置合理
- 有重试机制（最多3次）
- 没有明显的性能问题

**结论：**
这不是代码问题，而是模型服务商或网络问题。建议用户：
1. 尝试更换API提供商
2. 检查网络连接
3. 选择更快的模型

**不修改代码**

---

### 问题5：选择prompt历史版本时prompt_editor报错

**根本原因：**
与问题1类似，Streamlit的widget状态管理限制。

**问题代码：** [app/modules/llm_screening.py:54](e:\vscodeprojects\20260423-system-demo\app\modules\llm_screening.py#L54)
```python
st.session_state[f"{prefix}_prompt_editor"] = prompt
```

这个函数在按钮回调中被调用（第319行），但`prompt_editor`已经被第296行的`st.text_area`绑定为widget的key。

**修复方案：**
修改恢复逻辑，不直接修改`prompt_editor`，而是：
1. 先修改`prompt`（非widget绑定的值）
2. 调用`st.rerun()`让页面重新渲染
3. 在渲染时通过第296-297行的逻辑自动同步到`prompt_editor`

**影响范围：** 仅影响prompt历史版本恢复功能

---

### 问题6：点击开始筛选后无法筛选成功

**需要诊断的方向：**
1. 检查是否有错误提示（用户未提供）
2. 检查筛选运行的状态（running/failed/completed）
3. 检查数据库中screening_runs表的记录

**可能的原因：**
1. LLM调用失败（与问题3相关）
2. 数据格式问题
3. CSV解析失败
4. 速率限制问题

**修复方案：**
需要用户提供具体的错误信息。临时方案：
1. 在筛选过程中添加更详细的进度提示
2. 改进错误处理，确保错误信息能正确显示给用户
3. 添加调试日志

---

### 问题7：BERTopic图表解读应针对用户数据结果

**根本原因：**
当前的图表解读prompt可能过于通用，没有强调要针对用户的具体数据结果进行解读。

**问题代码：** [app/services/bertopic_service.py:134](e:\vscodeprojects\20260423-system-demo\app\services\bertopic_service.py#L134)
```python
prompt = f"Explain the BERTopic chart '{chart_key}' for a research user. Use only the provided chart context.\n\n{context_text}"
```

**修复方案：**
修改prompt，明确要求：
1. 基于提供的topic_info数据（包含主题关键词、文档数量等）
2. 解读这些主题在用户数据中的分布和特征
3. 不要解释BERTopic算法或图表类型本身

**影响范围：** 仅影响BERTopic图表解读功能

---

### 问题8-9：PDF和模板上传报错

**根本原因：**
Streamlit的`st.file_uploader`默认有文件类型限制。错误信息显示系统拒绝了这些MIME类型。

**问题代码：**
- [app/modules/pdf_extraction.py:84](e:\vscodeprojects\20260423-system-demo\app\modules\pdf_extraction.py#L84): `type=["csv", "xlsx", "xls"]`
- [app/modules/pdf_extraction.py:148](e:\vscodeprojects\20260423-system-demo\app\modules\pdf_extraction.py#L148): `type=["pdf"]`

**可能的原因：**
Streamlit配置中可能有额外的文件类型限制，或者Docker环境中的Streamlit版本有问题。

**修复方案：**
1. 检查`.streamlit/config.toml`是否有文件类型限制配置
2. 尝试移除`type`参数，改为在后端验证文件类型
3. 或者使用更宽松的type配置

**影响范围：** 影响PDF提取页面的文件上传功能

---

### 问题10：结果界面应该在操作部分下方

**用户需求：**
当前三个页面（筛选/BERTopic/PDF提取）的结果都显示在最上方，用户需要下滑才能使用功能，不符合使用逻辑。

**修复方案：**
调整页面布局顺序，将结果部分移到操作部分下方：
1. **筛选页面**：标准设置 → 最终prompt → 开始筛选 → 筛选结果 → 历史记录
2. **BERTopic页面**：开始分析 → 分析结果
3. **PDF提取页面**：开始提取 → 提取结果

**影响范围：** 影响三个页面的布局顺序

---

### 问题11：顶部导航栏被截断

**根本原因：**
CSS样式问题，topbar的padding或高度设置不合理，导致内容被截断。

**问题代码：** [app/main.py:41-51](e:\vscodeprojects\20260423-system-demo\app\main.py#L41-L51)
```css
.topbar {
    position: sticky;
    top: 0;
    z-index: 999;
    padding: 0.45rem 0.75rem;
    ...
}
```

**修复方案：**
1. 增加topbar的padding，特别是上下padding
2. 确保内容不会被overflow:hidden截断
3. 调整列宽比例，确保所有内容都能完整显示

**影响范围：** 仅影响项目功能页面的顶部导航栏显示

---

## 实施步骤

### 第一步：修复Streamlit widget状态错误（问题1、5）

**文件：** [app/modules/llm_screening.py](e:\vscodeprojects\20260423-system-demo\app\modules\llm_screening.py)

**修改内容：**
1. 移除第292行直接修改`workflow_mode`的代码
2. 修改`_set_prompt_text`函数（第42-45行），只修改非widget绑定的值
3. 在历史版本恢复时使用`st.rerun()`让页面重新渲染

**预期效果：** 选择历史版本时不再报错

---

### 第二步：改进AI扩写prompt（问题2）

**文件：** [app/services/prompting.py](e:\vscodeprojects\20260423-system-demo\app\services\prompting.py)

**修改内容：**
在`build_ai_expansion_prompt`函数中明确要求：
- 将所有中文内容翻译为英文
- 特别强调维度名称和描述也需要翻译
- 保持学术规范的英文表达

**预期效果：** AI扩写时会将用户输入的中文内容翻译为英文

---

### 第三步：改进LLM调用错误提示（问题3、6）

**文件：** [app/services/llm.py](e:\vscodeprojects\20260423-system-demo\app\services\llm.py)

**修改内容：**
1. 在`chat_text`函数中添加更详细的错误提示
2. 检查config是否为None，给出明确提示
3. 在筛选过程中添加进度提示

**预期效果：** 用户能看到更清晰的错误信息，便于诊断问题

---

### 第四步：改进BERTopic图表解读prompt（问题7）

**文件：** [app/services/bertopic_service.py](e:\vscodeprojects\20260423-system-demo\app\services\bertopic_service.py)

**修改内容：**
修改`save_chart_interpretation`函数的prompt，明确要求：
- 基于提供的topic_info数据进行解读
- 解读这些主题在用户数据中的分布和特征
- 不要解释BERTopic算法或图表类型本身

**预期效果：** 图表解读更贴近用户数据的实际分析结果

---

### 第五步：修复文件上传类型限制（问题8、9）

**文件：** [app/modules/pdf_extraction.py](e:\vscodeprojects\20260423-system-demo\app\modules\pdf_extraction.py)

**修改内容：**
检查并修复`st.file_uploader`的type参数配置，或者移除type限制改为后端验证

**预期效果：** PDF和模板文件可以正常上传

---

### 第六步：调整页面布局顺序（问题10）

**文件：**
- [app/modules/llm_screening.py](e:\vscodeprojects\20260423-system-demo\app\modules\llm_screening.py)
- [app/modules/bertopic_analysis.py](e:\vscodeprojects\20260423-system-demo\app\modules\bertopic_analysis.py)
- [app/modules/pdf_extraction.py](e:\vscodeprojects\20260423-system-demo\app\modules\pdf_extraction.py)

**修改内容：**
将结果展示部分移到操作部分下方：
- 筛选页面：标准设置 → 最终prompt → 开始筛选 → 筛选结果 → 历史记录
- BERTopic页面：开始分析 → 分析结果
- PDF提取页面：开始提取 → 提取结果

**预期效果：** 用户打开页面时直接看到操作区域，不需要下滑

---

### 第七步：修复顶部导航栏显示（问题11）

**文件：** [app/main.py](e:\vscodeprojects\20260423-system-demo\app\main.py)

**修改内容：**
1. 增加topbar的padding（特别是上下padding）
2. 调整列宽比例，确保所有内容都能完整显示
3. 确保内容不会被overflow截断

**预期效果：** 顶部导航栏完整显示，不会被截断

---

## 验证清单

修改完成后，需要验证以下功能：

**问题1、5验证：**
- [ ] 筛选页面：点击历史记录中的筛选标准版本，能正常恢复，不报错
- [ ] 筛选页面：点击prompt历史版本，能正常恢复到文本框，不报错

**问题2验证：**
- [ ] 筛选页面：使用AI扩写功能，检查输出的英文内容是否包含了用户输入的中文维度名称和描述的翻译

**问题3、6验证：**
- [ ] 配置API后能正常调用大模型（需要用户提供具体错误信息）
- [ ] 筛选功能能正常运行并完成（需要用户提供具体错误信息）

**问题4验证：**
- [ ] 确认这是模型服务商问题，不是代码问题（无需修改）

**问题7验证：**
- [ ] BERTopic页面：图表解读内容针对用户数据的分析结果，而不是解释图表类型

**问题8、9验证：**
- [ ] PDF提取页面：可以正常上传PDF文件
- [ ] PDF提取页面：可以正常上传模板文件（CSV/Excel）

**问题10验证：**
- [ ] 筛选页面：打开页面时直接看到操作区域（标准设置），结果在下方
- [ ] BERTopic页面：打开页面时直接看到操作区域（开始分析），结果在下方
- [ ] PDF提取页面：打开页面时直接看到操作区域（开始提取），结果在下方

**问题11验证：**
- [ ] 顶部导航栏：系统名称完整显示，不被截断
- [ ] 顶部导航栏：所有按钮完整显示，不被截断
- [ ] 顶部导航栏：整体美观，没有生硬的剪切

---

## 风险评估

**低风险修改：**
- 问题1、5（widget状态错误）：修改恢复逻辑，使用rerun机制
- 问题2（AI扩写翻译）：仅修改prompt文本
- 问题7（图表解读）：仅修改prompt文本
- 问题10（页面布局）：仅移动代码块位置，不改变逻辑
- 问题11（导航栏显示）：仅调整CSS样式

**中风险修改：**
- 问题3、6（LLM调用和筛选失败）：需要用户提供具体错误信息才能诊断
- 问题8、9（文件上传限制）：可能涉及Streamlit配置或版本问题

**高风险修改：**
- 无

**注意事项：**
1. 问题3、6需要用户提供具体的错误信息或日志才能准确诊断
2. 问题4（速度慢）确认为模型服务商问题，不修改代码
3. 所有修改都需要在Docker环境中验证
4. 页面布局调整时注意变量依赖关系，确保代码逻辑不受影响

---

## 需要用户提供的信息

为了更准确地修复问题3和问题6，需要用户提供以下信息：

**问题3（无法调用大模型）：**
1. 配置的API提供商名称（如OpenAI、Anthropic、自定义等）
2. 配置的base_url和model_name
3. 点击调用大模型时是否有任何错误提示？如果有，完整的错误信息是什么？
4. 浏览器控制台是否有错误信息？
5. Docker容器日志中是否有相关错误？

**问题6（筛选无法成功）：**
1. 点击"运行筛选"后是否有错误提示？如果有，完整的错误信息是什么？
2. 筛选运行的状态是什么（running/failed/completed）？
3. 数据库中screening_runs表的最新记录状态是什么？
4. Docker容器日志中是否有相关错误？

如果用户能提供这些信息，可以更精确地定位和修复问题。

---

## 实施优先级

建议按以下优先级实施修复：

**P0（高优先级 - 阻塞性bug）：**
1. 问题1、5：widget状态错误（影响基本功能使用）
2. 问题8、9：文件上传失败（影响基本功能使用）

**P1（中优先级 - 功能问题）：**
3. 问题3、6：LLM调用和筛选失败（需要诊断信息）
4. 问题2：AI扩写翻译（影响输出质量）
5. 问题7：图表解读优化（影响输出质量）

**P2（低优先级 - 体验优化）：**
6. 问题10：页面布局调整（用户体验优化）
7. 问题11：导航栏显示优化（视觉优化）

**不修改：**
- 问题4：速度慢（确认为模型服务商问题）
