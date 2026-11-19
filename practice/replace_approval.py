from langgraph.checkpoint.memory import InMemorySaver
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.types import Command
from errors import ToolError

from langgraph.graph import StateGraph, START, END
from replace_text import replace_text

from pathlib import Path
from typing import TypedDict

from paths import resolve_project_path
from preview_replace import preview_replace
from langgraph.types import interrupt

PROJECT_ROOT = Path(__file__).resolve().parent.parent


class ReplaceApprovalState(TypedDict):
    path: str
    old_text: str
    new_text: str
    diff: str
    original_hash: str
    approved: bool
    result: str


def prepare_preview(state: ReplaceApprovalState) -> dict:
    target = resolve_project_path(
        str(PROJECT_ROOT),
        state["path"],
    )

    preview = preview_replace(
        path=str(target),
        old_text=state["old_text"],
        new_text=state["new_text"],
    )

    return {
        "path": str(target),
        "diff": preview["diff"],
        "original_hash": preview["original_hash"],
    }

def review_approval(state: ReplaceApprovalState) -> dict:
    decision = interrupt({
        "question": "是否同意本次替换操作？",
        "diff": state["diff"],
        "path": state["path"],
    })

    return {
        "approved": decision is True,
    }

def apply_change(state: ReplaceApprovalState) -> dict:
    target = resolve_project_path(
        str(PROJECT_ROOT),
        state["path"],
    )

    result = replace_text(
        path=str(target),
        old_text=state["old_text"],
        new_text=state["new_text"],
        expected_hash=state["original_hash"],
    )

    return {
        "result": f"修改完成，共替换 {result['replacements']} 处",
    }


def cancel_change(state: ReplaceApprovalState) -> dict:
    return {
        "result": "已取消，未修改文件",
    }

def route_after_review(state: ReplaceApprovalState) -> str:
    if state["approved"] is True:
        return "apply_change"
    return "cancel_change"


builder = StateGraph(ReplaceApprovalState)

builder.add_node("prepare_preview", prepare_preview)
builder.add_node("review_approval", review_approval)
builder.add_node("apply_change", apply_change)
builder.add_node("cancel_change", cancel_change)

builder.add_edge(START, "prepare_preview")
builder.add_edge("prepare_preview", "review_approval")

builder.add_conditional_edges(
    "review_approval",
    route_after_review,
    {
        "apply_change": "apply_change",
        "cancel_change": "cancel_change",
    },
)

builder.add_edge("apply_change", END)
builder.add_edge("cancel_change", END)


db_path = Path(__file__).resolve().parent / "replace_checkpoints.sqlite"


def start_replace_approval(
    path: str,
    old_text: str,
    new_text: str,
    thread_id: str,
) -> dict:
    config = {
        "configurable": {
            "thread_id": thread_id,
        }
    }

    initial_state = {
        "path": path,
        "old_text": old_text,
        "new_text": new_text,
        "diff": "",
        "original_hash": "",
        "approved": False,
        "result": "",
    }

    with SqliteSaver.from_conn_string(str(db_path)) as checkpointer:
        graph = builder.compile(checkpointer=checkpointer)

        if graph.get_state(config).next:
            raise ValueError("该会话有未结束的修改，请使用新的 thread_id")

        paused = graph.invoke(initial_state, config=config)
        payload = paused["__interrupt__"][0].value

        return {
            "status": "waiting_approval",
            "answer": (
                f"{payload['question']}\n"
                f"文件：{payload['path']}\n"
                f"{payload['diff']}"
            ),
        }


def resume_replace_approval(thread_id: str, approved: bool) -> dict:
    config = {
        "configurable": {
            "thread_id": thread_id,
        }
    }

    with SqliteSaver.from_conn_string(str(db_path)) as checkpointer:
        graph = builder.compile(checkpointer=checkpointer)

        snapshot = graph.get_state(config)

        if snapshot.next != ("review_approval",):
            raise ValueError("该会话没有等待确认的修改")

        result = graph.invoke(
            Command(resume=approved),
            config=config,
        )

        return {
            "status": "completed" if result["approved"] else "cancelled",
            "answer": result["result"],
        }


if __name__ == "__main__":
    graph = builder.compile(checkpointer=InMemorySaver())

    config = {
        "configurable": {
            "thread_id": "replace-practice-01",
        }
    }

    initial_state = {
        "path": "practice/approval_target.txt",
        "old_text": "hello",
        "new_text": "你好",
        "diff": "",
        "original_hash": "",
        "approved": False,
        "result": "",
    }

    paused = graph.invoke(initial_state, config=config)
    payload = paused["__interrupt__"][0].value

    print(payload["question"])
    print(f"文件：{payload['path']}")
    print(payload["diff"])

    approved = input("输入 y 同意，其他输入取消：").strip().lower() == "y"

    try:
        final_state = graph.invoke(
            Command(resume=approved),
            config=config,
        )
        print(final_state["result"])
    except ToolError as error:
        print(f"修改未完成：{error}")