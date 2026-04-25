修改计划：20260423-system-demo 系统问题修复（最终版）
Context（背景）
用户在使用20260423-system-demo系统时发现了5个关键问题，需要在不影响其他功能的前提下进行修复。系统是一个基于Streamlit的文献筛选与分析SaaS平台，使用Docker部署，代码修改需要同步到Docker容器中。

当前需要解决的问题：

导航栏布局重构：将"返回项目列表"按钮和功能切换按钮放在同一行，固定在顶部，移除"项目导航"标签
PDF/模板上传413错误：上传文件时显示 AxiosError: Request failed with status code 413
BERTopic分析失败：运行时报错 Object of type ndarray is not JSON serializable
组装prompt后文本框未显示内容：点击"组装prompt"按钮后，下方文本框没有显示组装好的内容
检查并补充所有中文翻译：确保界面上没有未翻译的英文文本
问题清单与修复方案
问题1：导航栏布局重构
问题描述： 当前项目导航栏的布局是：

"返回项目列表"按钮单独一行
功能切换按钮（dashboard、data_input等）在下一行
有"项目导航"标签显示
用户希望：

将"返回项目列表"按钮和功能切换按钮放在同一行
固定在顶部，下滑时保持可见
移除"项目导航"标签
当前代码位置： app/main.py:145-162

修复方案：

重构 render_project_nav() 函数，将返回按钮和segmented_control放在同一个容器中
使用CSS将整个导航区域固定在顶部（已有sticky样式框架）
移除segmented_control的label参数或传入空字符串
影响范围： 项目功能页面的导航体验

问题2：PDF/模板上传413错误
问题描述： 上传PDF和模板文件时显示 AxiosError: Request failed with status code 413

根本原因： HTTP 413错误表示请求体过大。已检查配置：

nginx.conf: client_max_body_size 100m
.streamlit/config.toml: maxUploadSize = 100
配置看起来合理，但可能需要：

增加限制到更大的值（如200MB）
确保Docker容器正确加载了配置
检查是否有其他中间层限制
修复方案：

将 nginx.conf 的 client_max_body_size 增加到 200m
将 .streamlit/config.toml 的 maxUploadSize 增加到 200
提醒用户重启Docker容器：docker compose restart
影响范围： PDF提取功能的文件上传

问题3：BERTopic分析失败 - ndarray JSON序列化错误
问题描述： 运行BERTopic分析时报错：Object of type ndarray is not JSON serializable

根本原因： 在 app/services/bertopic_service.py:102 处，topic_info.fillna("").to_dict(orient="records") 返回的字典中包含numpy数组，无法直接JSON序列化。

修复方案： 在序列化前将numpy类型转换为Python原生类型：

# 修改前
json_dumps(topic_info.fillna("").to_dict(orient="records"))

# 修改后
topic_info_dict = topic_info.fillna("").to_dict(orient="records")
# 转换numpy类型为Python原生类型
for record in topic_info_dict:
    for key, value in record.items():
        if hasattr(value, 'item'):  # numpy scalar
            record[key] = value.item()
        elif isinstance(value, np.ndarray):  # numpy array
            record[key] = value.tolist()
json_dumps(topic_info_dict)
影响范围： 仅影响BERTopic聚类分析结果的保存

问题4：组装prompt后文本框未显示内容
问题描述： 在文献筛选页面，点击"组装prompt"按钮后，下方的"最终prompt"文本框没有显示组装好的内容。

当前代码位置： app/modules/llm_screening.py:185-191

根本原因： 点击"组装prompt"按钮时调用 _assemble_from_state() 更新了 st.session_state[f"{prefix}_prompt"]，但由于Streamlit的执行顺序，text_area在按钮点击前已经渲染，使用的是旧值。需要在按钮点击后触发 st.rerun() 来重新渲染页面。

修复方案： 在第186行的按钮点击处理中，调用 _assemble_from_state() 后添加 st.rerun()：

if ai_col2.button(t("assemble_prompt"), use_container_width=True, key=f"{prefix}_assemble_ai"):
    _assemble_from_state(prefix, dimensions, use_ai_expanded=True)
    st.rerun()  # 添加这一行
同样在第136行的跳过AI扩写路径也需要添加。

影响范围： 文献筛选页面的prompt组装交互

问题5：检查并补充所有中文翻译
问题描述： 界面上可能存在未翻译的英文文本，需要全面检查并补充翻译。

修复方案：

检查所有模块文件中的硬编码英文字符串
在 app/i18n/messages.py 中添加缺失的翻译键
将硬编码文本替换为 t("key") 调用
需要重点检查的文件：

app/modules/llm_screening.py
app/modules/bertopic_analysis.py
其他模块文件
影响范围： 所有界面的中文显示

实施步骤
第一步：修复导航栏布局
文件：app/main.py
重构 render_project_nav() 函数
将返回按钮和功能切换按钮放在同一行
移除"项目导航"标签
确保整个导航区域固定在顶部
第二步：增加文件上传大小限制
文件：nginx.conf, .streamlit/config.toml
将 client_max_body_size 从 100m 增加到 200m
将 maxUploadSize 从 100 增加到 200
提醒用户重启Docker容器
第三步：修复BERTopic JSON序列化错误
文件：app/services/bertopic_service.py
在第102行处理numpy类型转换
将numpy数组和标量转换为Python原生类型
第四步：修复prompt组装显示问题
文件：app/modules/llm_screening.py
在第136行和第186行的按钮点击处理中添加 st.rerun()
确保组装后的prompt立即显示在文本框中
第五步：检查并补充中文翻译
检查所有模块文件中的硬编码英文字符串
在需要时添加翻译键到 app/i18n/messages.py
替换硬编码文本为 t("key") 调用
验证清单
修改完成后，需要验证以下功能：

 导航栏布局：返回按钮和功能切换按钮在同一行，固定在顶部，无"项目导航"标签
 PDF/模板文件上传：可以成功上传大文件（测试50MB+的文件）
 BERTopic分析：可以正常运行并保存结果，不报JSON序列化错误
 Prompt组装：点击"组装prompt"后，下方文本框立即显示组装好的内容
 中文翻译：所有界面文本都正确显示为中文，无英文key或未翻译的标签
Docker同步与验证
由于使用了volume挂载（./:/app），本地代码修改会自动同步到容器。

验证步骤：

修改本地代码
Streamlit已配置自动重载（runOnSave = true）
如果配置文件修改（nginx.conf, config.toml），需要重启：docker compose restart
访问 http://localhost:8501 验证修改效果
风险评估
低风险修改：

问题3（JSON序列化）：仅添加类型转换逻辑，不改变业务流程
问题4（prompt显示）：仅添加rerun调用，不改变组装逻辑
问题5（翻译）：仅修改显示文本
中风险修改：

问题1（导航栏重构）：涉及UI结构调整，需要仔细测试各页面的导航体验
问题2（上传限制）：涉及服务器配置，需要确保Docker重启后配置生效
注意事项：

所有修改都需要在Docker环境中验证
保持代码风格一致，不引入不必要的依赖
导航栏重构需要确保不影响现有的sticky定位逻辑