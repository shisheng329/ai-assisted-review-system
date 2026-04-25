# 20260423-system-demo 定点修复计划（结合 cl2 最终版补充）
Summary
按你提供的 cl2修改计划：20260423-system-demo 系统问题修复（最终版） 补充后，这次仍然只修 5 个问题，并继续遵守“尽量不影响其他功能、微干扰修复”的原则。

我会把你文件里的方向吸收进来，但会做两点实现层修正，避免按字面执行后继续留坑：

413 不只把限制从 100 提到 200，还要确保运行中的容器一定吃到新配置，否则改数字也可能无效。
Prompt 空白不只加 st.rerun()，还要同步修正 text_area 的 widget state 绑定，否则 rerun 后仍可能被旧值覆盖。
Key Changes
1. 顶部导航压缩成单行固定顶栏
重构项目页顶栏，把现在分开的 render_topbar() 和 render_project_nav() 合并成一个 sticky 容器。
顶栏布局固定为一排：
左侧：应用名 + 用户信息
中间：当前项目名
右侧：返回项目列表、功能切换按钮组、退出登录
去掉“项目导航”文字标签，不再额外占一行。
压缩顶栏高度，清掉你图里绿色 × 标出的上方、下方和右侧多余留白。
顶栏背景改成高不透明或纯色，保证下滑时背景不透正文内容。
桌面端严格保持单行，不允许再出现“返回按钮单独一行”的布局。
2. PDF / 模板上传 413 修复
按 cl2 方案，把上传限制提高到 200m / 200：
nginx.conf 的 client_max_body_size = 200m
.streamlit/config.toml 的 server.maxUploadSize = 200
同时修正配置生效链路，确保运行态容器必然读取到仓库中的新配置：
保留 docker-start.sh 的运行时覆盖逻辑
必要时把配置以更直接的方式挂载到容器目标位置
验证目标不是“文件已改”，而是“运行中的服务不再返回 413”。
本轮只修上传限制与配置生效，不改 PDF 提取业务流程。
3. BERTopic ndarray is not JSON serializable 修复
不改 BERTopic 算法、默认参数、输入文本拼接或模型。
修复保存结果时的 numpy / Plotly 序列化问题。
当前优先修复点：
save_json_artifact() 增加对 numpy.ndarray、numpy scalar、Plotly JSON 的兼容转换
bertopic_service.py 中写入 topic_info_json 前，将非原生 Python 类型统一转成 list / int / float / str
保留现有 topic_runs 失败状态回写逻辑。
修复完成后，用你当前这份曾经可正常分析的同一份文件复测，结果应能完成保存并展示，而不是落成 failed。
4. Prompt 组装后文本框为空的修复
保留现有筛选交互结构，不改 prompt 组装逻辑本身。
修复方式采用“状态同步 + rerun”组合，而不是只加 rerun：
统一 st.session_state[f"{prefix}_prompt"] 和最终 text_area 对应的 widget key
在“组装 Prompt”和“跳过 AI 扩写自动组装”路径中，组装完成后同步更新文本框状态
组装后执行 st.rerun()，确保页面以新状态重新渲染
同样修复恢复 Prompt 历史版本时的显示一致性。
验证标准是：点击后下方文本框立即出现内容，不再为空白。
5. 中文翻译全面检查和补齐
直接修复当前中文词典和语言选项中的乱码源：
app/i18n/messages.py
app/services/i18n.py
把中文模式下仍残留的硬编码英文进一步收口到 t(...)。
对照模块至少检查：
顶部导航/认证页
文献筛选页
BERTopic 页
PDF 页
个人资料页
允许保留术语 API、BERTopic，其余界面文案以正常中文为准。
Public Interfaces / Types
不新增数据库表，不做 migration。
最小接口变更：
save_json_artifact() 支持 numpy / Plotly 兼容序列化
顶部导航渲染函数重组，但页面入口不变
筛选页最终 Prompt 编辑框的 session key 绑定方式调整
业务服务接口尽量保持不变，避免影响已有功能调用链。
Test Plan
导航：
返回项目列表 与模块切换按钮在同一排
顶栏只占一行，无明显上下留白
下滑后仍固定且不透出背景正文
上传：
上传 PDF 文件不再报 AxiosError 413
上传模板文件不再报 AxiosError 413
配置修改后通过重启容器验证实际生效
BERTopic：
用你当前那份文件重新运行
不再报 Object of type ndarray is not JSON serializable
topic_runs 状态不再直接是 failed
图表和结果导出仍可用
Prompt：
点击 组装 Prompt 后文本框立即显示
跳过 AI 扩写后自动显示最终 Prompt
恢复 Prompt 历史版本后文本框同步更新
中文：
中文模式下无乱码
不再出现未翻译 key 或明显英文残留
Assumptions
顶部导航的优先目标是“单行、低高度、无大块留白”，优先级高于装饰性留白。
413 的主因仍视为运行态配置未真正生效；因此这次必须包含容器重启后的验证。
BERTopic 失败的主因视为序列化兼容问题，而不是你上传文件的格式问题。
Prompt 空白问题视为 Streamlit 状态绑定问题，单独加 st.rerun() 不足以彻底解决，因此本轮会一并修状态同步。
当前对外访问端口以现有 Compose 映射为准，即主机侧继续按 8503 验证，而不是旧的 8501。
