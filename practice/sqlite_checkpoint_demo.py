from pathlib import Path
from typing import TypedDict, Annotated

from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.sqlite import SqliteSaver


class CounterState(TypedDict):
    count: int


def increment_count(state: CounterState) -> dict:
    return {
        "count": state["count"] + 1,
    }


path = Path(__file__).parent / "checkpoints.sqlite"

builder = StateGraph(CounterState)


builder.add_node("increment_count", increment_count)
builder.add_edge(START, "increment_count")
builder.add_edge("increment_count", END)

config = {
    "configurable": {
        "thread_id": "sqlite-demo-1",
    }
}

with SqliteSaver.from_conn_string(str(path)) as checkpointer:
    graph = builder.compile(checkpointer=checkpointer)

    snapshot = graph.get_state(config)
    print("读取保存的状态：", snapshot.values)

    if snapshot.values:
        initial_count = {}
    else:
        initial_count = {"count": 0}
    
    result = graph.invoke(initial_count, config=config)
    print("执行结果：", result)
