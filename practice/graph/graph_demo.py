from typing import TypedDict,Annotated
import operator
from langgraph.graph import StateGraph, START, END

# 1. 描述状态中有哪些字段
class DemoState(TypedDict):
    task: str
    answer: str
    round_count: int
    history: Annotated[list[str], operator.add]


# 2. 节点：读取 task，返回更新后的 task
def normalize_task(state: DemoState) -> dict:
    return {
        "task": state["task"].strip(),
    }

# 3. 节点：读取 task，返回 answer
def build_answer(state: DemoState) -> dict:
    round_count = state["round_count"] + 1

    print(f"build_answer 第 {round_count} 次执行")

    return {
        "answer": f"收到任务：{state['task']}",
        "round_count": round_count,
        "history": [f"第 {round_count} 次执行"],
    }

def route_task(state: DemoState) -> str:
    if not state['task']:
        return 'empty'
    
    return 'ready'

def route_after_answer(state: DemoState) -> str:
    if state["round_count"] >= 3:
        return 'finish'

    return "again"
        

# 4. 创建图，注册节点
builder = StateGraph(DemoState)

builder.add_node("normalize_task", normalize_task)
builder.add_node("build_answer", build_answer)

# 5. 连接执行顺序
builder.add_edge(START, "normalize_task")

builder.add_conditional_edges(
    "normalize_task",
    route_task,
    {
      "empty":END,
      "ready": "build_answer"
    }
)
# builder.add_edge("normalize_task", "build_answer")
# builder.add_edge("build_answer", END)
builder.add_conditional_edges(
    "build_answer",
    route_after_answer,
    {
      "finish": END,
      "again": "build_answer"
    }
)

# 6. 编译并执行
graph = builder.compile()

result = graph.invoke({
    "task": "   查看项目目录   ",
    "answer": "",
    "round_count": 0,
    "history": [],
})

print(result)