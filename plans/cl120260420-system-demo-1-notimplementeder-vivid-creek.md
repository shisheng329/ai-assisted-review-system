# 修改计划：20260423-system-demo 系统问题修复

## Context（背景）

用户在使用20260423-system-demo系统时发现了7个问题，需要在不影响其他功能的前提下进行修复。系统是一个基于Streamlit的文献筛选与分析SaaS平台，使用Docker部署，代码修改需要同步到Docker容器中。

## 问题清单与修复方案

### 问题1：BERTopic SentenceTransformer meta tensor错误

**问题描述：**
```
NotImplementedError: Cannot copy out of meta tensor; no data! 
Please use torch.nn.Module.to_empty() instead of torch.nn.Module.to()
```

**根本原因：**
sentence-transformers 3.0+ 版本与PyTorch在meta tensor处理上存在兼容性问题。

**修复方案：**
在 `app/services/bertopic_service.py:63` 处，修改SentenceTransformer初始化方式：
```python
# 修改前
embedding_model=SentenceTransformer("all-MiniLM-L6-v2")

# 修改后
embedding_model = SentenceTransformer("all-MiniLM-L6-v2", device="cpu")
# 或者使用 trust_remote_code=True 参数
```

**影响范围：** 仅影响BERTopic聚类分析功能的模型加载部分

---

### 问题2：筛选维度"+""-"按钮与文本框未对齐

**问题描述：**
在文献筛选页面，维度增删按钮位于文本框右下角，而不是垂直居中对齐。

**当前代码位置：** `app/modules/llm_screening.py:61-70`

**修复方案：**
调整列布局和按钮样式，使用Streamlit的列对齐参数：
```python
# 当前代码
cols = st.columns([1.3, 3, 4, 0.8, 0.8])

# 修改为使用vertical_alignment参数（如果Streamlit版本支持）
# 或者调整按钮的容器样式使其垂直居中
```

**影响范围：** 仅影响文献筛选页面的UI布局

---

### 问题3：AI扩写流程逻辑问题

**问题描述：**
- 缺少"跳过AI扩写"按钮
- 点击"组装prompt"后，下方的最终prompt文本框没有显示内容
- 点击"AI扩写"后，保存和组装按钮没有移动到扩写后文本框下方

**当前代码位置：** `app/modules/llm_screening.py:52-141`

**根据test list文档要求：**
1. 应该有两条路径：使用AI扩写 / 跳过AI扩写
2. 跳过AI扩写后，点击"保存标准"应自动组装并显示prompt
3. 使用AI扩写时，保存和组装按钮应在扩写结果下方
4. 点击"组装prompt"后应立即在下方文本框显示完整内容

**修复方案：**
1. 添加"跳过AI扩写"选项（单选按钮或复选框）
2. 修改保存标准逻辑：跳过AI扩写时自动组装prompt
3. 调整按钮位置：AI扩写区域后再放置保存和组装按钮
4. 修复组装prompt的显示逻辑，确保点击后立即更新session_state并显示

**影响范围：** 文献筛选页面的交互流程

---

### 问题4：用户个人资料中大模型配置缺少删除选项

**问题描述：**
用户只能"保存为当前配置"，无法删除已保存的API配置。

**当前代码位置：** `app/modules/profile.py:63-72`

**修复方案：**
在每个配置项的列布局中添加"删除"按钮：
```python
cols = st.columns([2, 2, 2, 1, 0.8])  # 增加一列用于删除按钮
# 添加删除按钮和对应的删除逻辑
if cols[4].button(t("delete"), key=f"delete_api_{config['id']}"):
    delete_api_config(int(user["id"]), int(config["id"]))
    st.rerun()
```

需要在 `app/services/llm.py` 中添加 `delete_api_config` 函数。

**影响范围：** 个人资料页面的API配置管理功能

---

### 问题5：功能界面导航栏未固定在顶部

**问题描述：**
用户下滑时，导航栏不可见，需要上滑到顶部才能切换功能界面。

**当前代码位置：** `app/main.py:139-143`

**修复方案：**
使用CSS将导航栏固定在顶部：
```python
# 在 apply_styles() 中添加导航栏固定样式
st.markdown("""
<style>
[data-testid="stSegmentedControl"] {
    position: sticky;
    top: 60px;  /* topbar高度 */
    z-index: 998;
    background: white;
    padding: 0.5rem 0;
}
</style>
""", unsafe_allow_html=True)
```

**影响范围：** 全局导航体验

---

### 问题6：PDF上传失败，413错误

**问题描述：**
上传PDF和模板文件时显示 `AxiosError: Request failed with status code 413`

**根本原因：**
HTTP 413错误表示请求体过大，可能是：
1. Nginx配置的client_max_body_size限制
2. Streamlit的maxUploadSize配置限制

**修复方案：**
1. 检查并修改 `nginx.conf` 中的 `client_max_body_size`
2. 检查Streamlit配置，添加或修改 `.streamlit/config.toml`：
```toml
[server]
maxUploadSize = 200  # 单位MB
```
3. 确保Docker容器重启后配置生效

**影响范围：** PDF提取功能的文件上传

---

### 问题7：界面存在未翻译的英文文本

**问题描述：**
以下文本显示为英文而非中文：
- "AI Expansion"
- "REVIEW_TOPIC"
- "Run Screening"
- "random_state"
- 等等

**当前代码位置：**
- `app/modules/llm_screening.py:52, 115-119`
- `app/modules/bertopic_analysis.py:58`
- 其他模块

**修复方案：**
1. 在 `app/i18n/messages.py` 中添加缺失的翻译键值对
2. 将硬编码的英文文本替换为 `t("key")` 调用

需要添加的翻译：
```python
"zh-CN": {
    "ai_expansion": "AI 扩写",
    "criteria_draft": "初版标准",
    "final_prompt": "最终 Prompt",
    "random_state": "随机种子",
    "n_neighbors": "邻居数",
    "n_components": "降维维度",
    "min_topic_size": "最小主题大小",
    "nr_topics": "主题数量",
    # ... 其他缺失的键
}
```

**影响范围：** 所有界面的中文显示

---

## 实施步骤

### 第一阶段：修复核心功能问题（问题1、3、6）

1. **修复BERTopic tensor错误**
   - 文件：`app/services/bertopic_service.py`
   - 修改SentenceTransformer初始化参数

2. **修复AI扩写流程**
   - 文件：`app/modules/llm_screening.py`
   - 重构步骤2.1的交互逻辑
   - 添加跳过AI扩写选项
   - 修复prompt组装和显示逻辑

3. **修复PDF上传413错误**
   - 文件：`nginx.conf`, `.streamlit/config.toml`
   - 增加上传大小限制
   - 确保Docker配置生效

### 第二阶段：UI/UX改进（问题2、4、5、7）

4. **修复维度按钮对齐**
   - 文件：`app/modules/llm_screening.py`
   - 调整列布局和按钮样式

5. **添加API配置删除功能**
   - 文件：`app/modules/profile.py`, `app/services/llm.py`
   - 添加删除按钮和删除函数

6. **固定导航栏**
   - 文件：`app/main.py`
   - 添加CSS样式固定导航栏

7. **完善中文翻译**
   - 文件：`app/i18n/messages.py`, 各模块文件
   - 添加缺失的翻译键
   - 替换硬编码英文文本

---

## Docker同步策略

由于使用了volume挂载（`./:/app`），本地代码修改会自动同步到容器：
```yaml
volumes:
  - ./:/app  # 代码自动同步
```

**验证步骤：**
1. 修改本地代码
2. 检查Docker容器是否启用了文件监控（已配置 `STREAMLIT_SERVER_RUN_ON_SAVE: "true"`）
3. 如果需要重启：`docker compose restart app`
4. 访问 `http://localhost:8503` 验证修改效果

---

## 验证清单

修改完成后，需要验证以下功能：

- [ ] BERTopic聚类分析可以正常运行，不报meta tensor错误
- [ ] 筛选维度的+/-按钮与文本框垂直对齐
- [ ] 可以选择"跳过AI扩写"，保存后自动显示组装的prompt
- [ ] 使用AI扩写时，按钮位置正确，组装prompt后立即显示内容
- [ ] 个人资料中可以删除API配置
- [ ] 下滑页面时导航栏保持在顶部可见
- [ ] 可以成功上传PDF文件和模板文件（测试大文件）
- [ ] 所有界面的文本都正确显示为中文（无英文key或英文标签）

---

## 风险评估

**低风险修改：**
- 问题1（tensor错误）：仅修改参数，不改变逻辑
- 问题4（删除配置）：新增功能，不影响现有功能
- 问题7（翻译）：仅修改显示文本

**中风险修改：**
- 问题3（AI扩写流程）：涉及交互逻辑重构，需要仔细测试各路径
- 问题6（上传限制）：涉及服务器配置，需要确保Docker重启

**注意事项：**
- 所有修改都需要在Docker环境中验证
- 修改后需要检查test list文档中的相关流程是否符合预期
- 保持代码风格一致，不引入不必要的依赖
- 所有修改都尽可能只针对问题修改，非必要不动其他功能的代码
