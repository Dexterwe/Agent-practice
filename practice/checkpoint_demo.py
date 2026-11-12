
from typing import TypedDict

from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import InMemorySaver

class CounterState(TypedDict):
    count: int

def increment_count(state: CounterState) -> dict:
    return {
        "count": state["count"] + 1,
    }

memory = InMemorySaver()
builder = StateGraph(CounterState)

builder.add_node("increment_count", increment_count)
builder.add_edge(START,"increment_count")
builder.add_edge("increment_count",END)

graph = builder.compile(checkpointer=memory)

config = {
    "configurable": {
        "thread_id": "demo-1",
    }
}

# 第一次执行，从 0 开始
result1 = graph.invoke({"count": 0}, config=config)
print("第一次执行：", result1)

# 读取保存的状态，不执行节点
snapshot = graph.get_state(config)
print("保存的状态：", snapshot.values)


# 使用同一个会话，再执行一次图
result2 = graph.invoke({}, config=config)
print("第二次执行：", result2)