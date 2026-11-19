# Agent 项目工作流程

## 任务入口

POST /tasks 接收 task 和 thread_id，用于开始一次 Agent 任务。
模型可以调用工具读取文件、搜索代码和提出文本替换。

如果同一个 thread_id 还有未完成的 Agent 任务，
再次提交新任务会返回 HTTP 409，避免改变尚未处理完的任务状态。

## 会话持久化

Agent 使用 LangGraph 的 SqliteSaver 保存执行状态。
检查点数据库位于 practice/agent_checkpoints.sqlite。

thread_id 用于区分会话。
恢复任务时，需要使用相同的数据库和 thread_id。

## 文件修改确认

模型请求 replace_text 时，程序先生成差异预览，
把替换参数、差异和原文件指纹保存到 State。

review_changes 节点通过 interrupt 暂停，等待用户确认。
POST /tasks/resume 接收 thread_id 和 approved，用于恢复任务。

用户同意后，程序在写入前检查文件指纹。
如果文件与预览时不同，则拒绝写入，并把错误作为工具结果回传模型。

用户拒绝时，不执行替换，而是把拒绝结果回传模型。

## 模型请求次数

默认每个任务最多请求模型 10 次。
request_count 统计模型请求次数，不是图节点的执行次数。

恢复审批不会重置 request_count。
如果写入完成时请求次数已经用完，程序可能返回 request_limit，
表示尚未获得模型的最终回答，并不一定表示文件修改失败。