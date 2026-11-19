from pathlib import Path
from typing import TypedDict

from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.types import interrupt, Command

class ApprovalState(TypedDict):
    task: str
    result: str

def review_task(state:ApprovalState) -> dict:

    approved = interrupt({
      "question": "是否同意本次模拟操作？",
      "task": state["task"],
    })

    if approved is True:
        return {
            "result": "已同意，本次模拟操作可以继续",
        }

    return {
        "result": "已拒绝，本次操作取消",
    }

builder = StateGraph(ApprovalState)
builder.add_node("review_task", review_task)
builder.add_edge(START, "review_task")
builder.add_edge("review_task", END)

db_path = Path(__file__).resolve().parent / "approval_checkpoints.sqlite"


def start_approval(task: str, thread_id:str) -> dict:
    config = {
        "configurable": {
            "thread_id": thread_id,
        }
    }

    with SqliteSaver.from_conn_string(str(db_path)) as checkpointer:
        graph = builder.compile(checkpointer=checkpointer)
        
        if graph.get_state(config).next:
            raise ValueError("该会话已有等待确认的操作，请先处理。")

        paused = graph.invoke({"task": task , "result": ""}, config=config)

        payload = paused["__interrupt__"][0].value

        return {
            "status": "waiting_approval",
            "answer": f"{payload['question']} 任务：{payload['task']}",
        }
    
def resume_approval(thread_id: str, approved: bool) -> dict:
    config = {
        "configurable": {
            "thread_id": thread_id,
        }
    }

    with SqliteSaver.from_conn_string(str(db_path)) as checkpointer:
        graph = builder.compile(checkpointer=checkpointer)

        if not graph.get_state(config).next:
            raise ValueError("该会话没有等待确认的操作")

        result = graph.invoke(
            Command(resume=approved),
            config=config,
        )

        return {
            "status": "completed" if approved is True else "cancelled",
            "answer": result["result"],
        }


