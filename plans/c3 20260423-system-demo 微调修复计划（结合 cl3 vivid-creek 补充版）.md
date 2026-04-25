20260423-system-demo 微调修复计划（结合 cl3 vivid-creek 补充版）
Summary
在上一版方案基础上，吸收 cl320260420-system-demo-1-notimplementeder-vivid-creek.md 里新增和明确化的布局约束。这次仍然只做微干扰修复，不改数据库 schema，不重构主流程，不改变筛选与 BERTopic 的核心算法。

相对上一版，新增并锁定的约束有 4 组：

Prompt 页面按钮和区块顺序要继续细化。
BERTopic 页面和 PDF 页面要把“历史结果”放在“开始运行”之前。
“双语审阅 / 保存为新版本”的按钮顺序要固定。
“修改历史”标题统一改成“历史记录”。
同时保留你刚刚确认的 3 条规则：

跳过 AI 扩写时，Prompt 只用用户填写内容。
使用 AI 扩写时，Prompt 只用 AI 扩写后的内容。
PDF 提取结果语言跟随每个 PDF 文件本身语言，不跟随 UI。
Key Changes
1. Prompt 页面：数据源、按钮顺序、区块顺序、历史拆分
Prompt 组装规则固定为二选一，不再混用：
skip_ai 时只读取用户草稿区内容。
use_ai 时只读取当前扩写编辑区内容。
组装后 Prompt 文本框的刷新采用“状态同步 + rerun”，不是只加 st.rerun()：
统一内部 prompt 状态和最终编辑框的 widget key。
在“跳过 AI 扩写自动组装”和“使用 AI 扩写后组装”两条路径都同步刷新。
按钮顺序按 cl3 约束调整：
双语审阅 按钮放在 保存为新版本 之前。
页面区块顺序按 cl3 约束调整：
历史筛选结果区放到“开始筛选”区块之前。
“运行筛选”按钮放到参数设置之前。
参数设置保留，但放在运行按钮之后。
历史记录拆分成两个板块：
用户填写内容历史放在草稿/维度模块最下方。
Prompt 历史版本保留在最终 Prompt 模块附近。
原来 revision_history 的显示文案统一改成 历史记录。
中英文审阅显示层改成支持同步滚动的双栏容器，不再使用两个互不关联的原生 text_area。
2. 筛选执行稳定性修复
修复执行筛选时报 'NoneType' object has no attribute 'strip'：
parse_single_row_csv() 对 None key、空 key、空 value 做容错。
忽略模型返回的畸形表头或多余空列。
不改变筛选字段 contract、decision 规则和输出结构，只修解析稳健性。
3. BERTopic 页面：新增功能和布局重排
保持 BERTopic 基础运行逻辑、参数、导出、CPU embedding 方案不变。
新增两个可选 LLM 功能：
为主题命名
为主题解释
这两个功能以及图表解读继续跟随当前 UI 语言输出。
图表展示改成三列卡片并列：
barchart
topics
hierarchy
每个卡片固定顺序：标题、图表、解读按钮、解读结果框。
页面区块顺序按 cl3 约束调整：
历史分析结果区放在“开始分析”之前。
运行分析 按钮放在参数设置之前。
参数设置保留在运行按钮之后。
修复 ndarray is not JSON serializable：
在 BERTopic 结果落盘前统一做 to_json_compatible() 转换。
包括 topic_info 和图表 artifact 相关序列化链路。
4. PDF 提取页面：单预览框、模板/文件管理、结果重排
模板区只保留一个模板预览框：
上传新模板时，预览框显示当前上传模板。
从现存模板下拉框选择模板时，预览框切换为所选模板。
保存模板后不再出现第二份重复预览。
新增模板管理：
模板下拉选择
删除模板
保存后自动加入下拉列表
切换模板时同步更新活动模板和单一预览框
新增 PDF 文件管理：
上传新 PDF
删除已上传 PDF
选择本次提取使用的 PDF 文件集合
增加运行中提示：
点击开始提取后显示明确的提取中状态
修复提取结果只剩 file_name / error_message：
强化模型返回 JSON 的清洗和字段对齐
最终结果表始终输出模板列
PDF 提取页面区块顺序按 cl3 约束调整：
历史提取结果区放在“开始提取”之前
运行提取 按钮放在参数或控制区之前
PDF 结果语言规则固定为“按文件语言逐行输出”：
中文 PDF 行输出中文值
英文 PDF 行输出英文值
混合语言批量提取时，每行按各自文件语言输出
不根据 UI 语言强制翻译结果值
5. 顶部导航和中文界面补齐
顶部导航继续按你截图要求处理：
删除或压缩顶部无意义的大块白色空区
按钮行保持当前单排样式
固定在最高可行位置
如果 Streamlit 自带 Deploy/菜单栏不可移动，就固定在其正下方
用户滚动到页面中部时仍可见、可切换
中文词典继续修复和补齐：
修正乱码
补齐这轮新增按钮、区块标题、模板/文件管理文案
把残留硬编码英文继续收口到 t(...)
Public Interfaces / Types
不新增数据库表，不做 migration。
允许新增最小服务接口：
list_pdf_templates(project_id, user_id)
set_active_template(project_id, user_id, template_id)
delete_pdf_template(project_id, user_id, template_id)
delete_pdf_file(project_id, user_id, file_id)
run_pdf_extraction(..., pdf_file_ids: list[int])
BERTopic 的主题命名/主题解释辅助接口
parse_single_row_csv() 继续返回 list[dict[str, str]]，但内部增加空 key/空 value 容错。
Prompt 组装入口不改现有业务签名，但内部会显式根据 workflow mode 选用草稿内容或 AI 扩写内容。
revision_history 相关 UI key 可保留内部实现名，但对用户显示统一改成 历史记录。
Test Plan
Prompt：
跳过 AI 扩写时，组装结果只来自用户草稿。
使用 AI 扩写时，组装结果只来自当前扩写编辑内容。
点击组装后 Prompt 文本框立即显示。
双语审阅 在 保存为新版本 之前。
历史筛选结果显示在“开始筛选”区块之前。
运行筛选 按钮在参数设置之前。
“历史记录”标题显示正确。
筛选执行：
不再出现 'NoneType' object has no attribute 'strip'。
BERTopic：
历史分析结果显示在“开始分析”之前。
运行分析 按钮在参数设置之前。
三图并列显示，且各自可解读。
主题命名、主题解释按钮可用。
不再出现 ndarray is not JSON serializable。
PDF：
页面上始终只有一个模板预览框。
切换模板时预览框同步切换。
历史提取结果显示在“开始提取”之前。
运行提取 按钮在参数或控制区之前。
结果表按模板列输出，不再只剩两列。
混合语言 PDF 批量提取时，每行按对应文件语言输出。
导航与中文：
顶部导航在滚动中始终可见。
顶部大块空白被移除或压缩。
中文模式下无乱码、无明显漏翻。
Assumptions
cl3 文件里关于“按钮顺序”和“结果区块顺序”的约束视为必须执行的 UI 规范。
PDF 页面里所谓“参数设置”主要对应模板/文件选择和运行控制区；本轮会按“先结果、后开始区、先运行按钮、后其余控制项”的顺序组织。
BERTopic 解释类文本仍跟随 UI 语言；PDF 抽取值继续跟随文件语言，这两条规则并行存在、不冲突。
顶部最上方 Streamlit 自带系统栏默认视为不可改；导航会固定在它正下方，除非现有 CSS 能安全再上移。