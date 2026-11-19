import os
import anthropic
from dotenv import load_dotenv

from typing import TypedDict, Annotated
import operator

from langgraph.graph import StateGraph, START, END
from agent import TOOLS

import json
from pathlib import Path
from executor import exexute_tool

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.types import interrupt, Command


class AgentState(TypedDict):
    messages: Annotated[list[dict], operator.add]
    stop_reason: str | None
    request_count: int
    answer: str

    pending_tool_results: list[dict]
    pending_changes: list[dict]
    approved: bool

def format_result(state: AgentState, max_requests: int) -> dict:
    if state["stop_reason"] == "end_turn":
        return {
            "status": "end_turn",
            "answer": state["answer"],
        }

    if (
        state["stop_reason"] == "tool_use"
        and state["request_count"] >= max_requests
    ):
        return {
            "status": "request_limit",
            "answer": (
                f"已达到 {max_requests} 次模型请求上限，"
                "尚未收到模型的最终回答，请查看最近的工具执行结果。"
            ),
        }

    return {
        "status": "stopped",
        "answer": f"模型停止，原因：{state['stop_reason']}",
    }

def prepare_tools(state: AgentState) -> dict:
    assistant_message = state["messages"][-1]
    project_root = str(Path(__file__).resolve().parent.parent)

    tool_results = []
    pending_changes = []

    for block in assistant_message["content"]:
        if block["type"] != "tool_use":
            continue

        tool_name = block["name"]

        if tool_name == "replace_text":
            result = exexute_tool(
                project_root,
                "preview_replace",
                block["input"],
            )
        else:
            result = exexute_tool(
                project_root,
                tool_name,
                block["input"],
            )

        if tool_name == "replace_text" and result["ok"]:
            preview = result["data"]

            pending_changes.append({
                "tool_use_id": block["id"],
                "path": preview["path"],
                "old_text": block["input"]["old_text"],
                "new_text": block["input"]["new_text"],
                "diff": preview["diff"],
                "original_hash": preview["original_hash"],
            })
            continue

        tool_results.append({
            "type": "tool_result",
            "tool_use_id": block["id"],
            "content": json.dumps(result, ensure_ascii=False),
            "is_error": not result["ok"],
        })

    return {
        "pending_tool_results": tool_results,
        "pending_changes": pending_changes,
        "approved": False,
    }

def review_changes(state: AgentState) -> dict:
    decision = interrupt({
        "question": "是否同意以下文件修改？",
        "changes": [
            {
                "path": change["path"],
                "diff": change["diff"],
            }
            for change in state["pending_changes"]
        ],
    })

    return {
        "approved": decision is True,
    }

def finish_tools(state: AgentState) -> dict:
    project_root = str(Path(__file__).resolve().parent.parent)
    tool_results = list(state["pending_tool_results"])

    for change in state["pending_changes"]:
        if state["approved"] is True:
            result = exexute_tool(
                project_root,
                "replace_text",
                {
                    "path": change["path"],
                    "old_text": change["old_text"],
                    "new_text": change["new_text"],
                    "expected_hash": change["original_hash"],
                },
            )
        else:
            result = {
                "ok": False,
                "error": "用户拒绝本次修改，请不要重复请求相同修改",
            }

        tool_results.append({
            "type": "tool_result",
            "tool_use_id": change["tool_use_id"],
            "content": json.dumps(result, ensure_ascii=False),
            "is_error": not result["ok"],
        })

    return {
        "messages": [
            {
                "role": "user",
                "content": tool_results,
            }
        ],
        "pending_tool_results": [],
        "pending_changes": [],
        "approved": False,
    }

def build_graph(client, model: str,checkpointer,max_requests: int = 10):
    def call_model(state: AgentState) -> dict:
        response = client.messages.create(
            model=model,
            max_tokens=4096,
            tools=TOOLS,
            tool_choice={"type": "auto"},
            messages=state["messages"],
        )

        assistant_message = {
            "role": "assistant",
            "content": [
                block.model_dump(exclude_none=True)
                for block in response.content
            ],
        }

        answer = "\n".join(
            block.text
            for block in response.content
            if block.type == "text"
        )

        return {
              "messages": [assistant_message],
              "stop_reason": response.stop_reason,
              "request_count": state["request_count"] + 1,
              "answer": answer,
              "pending_tool_results": [],
              "pending_changes": [],
              "approved": False,
        }
    
    def execute_tools(state: AgentState) -> dict:
        assistant_message = state["messages"][-1]
        project_root = str(Path(__file__).resolve().parent.parent)

        tool_results = []

        for block in assistant_message["content"]:
            if block["type"] != "tool_use":
              continue

            result = exexute_tool(
                project_root,
                block["name"],
                block["input"],
            )

            tool_results.append({
                "type": "tool_result",
                "tool_use_id": block["id"],
                "content": json.dumps(result, ensure_ascii=False),
                "is_error": not result["ok"],
            })
            
        return {
            "messages": [
                {
                    "role": "user",
                    "content": tool_results,
                }
            ],
        }

    def route_after_model(state: AgentState) -> str:
        if state["stop_reason"] == "tool_use":
            return "tools"

        return "stop"

    def route_after_tools(state: AgentState) -> str:
        if state["request_count"] >= max_requests:
            return "stop"

        return "model"

    def route_after_prepare(state: AgentState) -> str:
        if state["pending_changes"]:
            return "review"
        return "finish"

    builder = StateGraph(AgentState)

    builder.add_node("call_model", call_model)
    builder.add_node("prepare_tools", prepare_tools)
    builder.add_node("review_changes", review_changes)
    builder.add_node("finish_tools", finish_tools)

    builder.add_edge(START, "call_model")

    builder.add_conditional_edges(
        "call_model",
        route_after_model,
        {"tools": "prepare_tools", "stop": END},
    )

    builder.add_conditional_edges(
        "prepare_tools",
        route_after_prepare,
        {"review": "review_changes", "finish": "finish_tools"},
    )

    builder.add_edge("review_changes", "finish_tools")

    builder.add_conditional_edges(
        "finish_tools",
        route_after_tools,
        {"model": "call_model", "stop": END},
    )

    return builder.compile(checkpointer=checkpointer)

    return builder.compile(checkpointer=checkpointer)

def run_graph_agent(task: str,thread_id: str, max_requests: int = 10) -> dict:
    task = task.strip()

    if not task:
        return {
            "status": "invalid_task",
            "answer": "任务不能为空",
        }

    if type(max_requests) is not int or max_requests < 1:
        raise ValueError("max_requests 必须是正整数")

    env_path = Path(__file__).resolve().parent.parent / ".env"
    load_dotenv(env_path)

    initial_state: AgentState = {
        "messages": [
            {
                "role": "user",
                "content": task,
            }
        ],
        "stop_reason": None,
        "request_count": 0,
        "answer": "",
        "pending_tool_results": [],
        "pending_changes": [],
        "approved": False,
    }
    path = Path(__file__).parent / "agent_checkpoints.sqlite"
    with(SqliteSaver.from_conn_string(str(path)) as checkpointer ,
        anthropic.Anthropic(
        auth_token=os.environ["API_KEY"],
        base_url=os.getenv("BASE_URL") or None,
    ) as client):
        graph = build_graph(
            client,
            os.environ["MODEL"],
            checkpointer,
            max_requests=max_requests,
        )
        config = {
            "configurable": {
                "thread_id": thread_id,
            },
            "recursion_limit": 4 * max_requests + 5,
        }

        if graph.get_state(config).next:
            raise ValueError(
                "该会话有未完成的 Agent 任务，请先处理或使用新的 thread_id"
            )

        # state = graph.invoke(
        #     initial_state,
        #     config={
        #         "recursion_limit": 2 * max_requests + 5,
        #     },
        # )

        state = initial_state
        approval_payload = None

        for mode, data in graph.stream(
            initial_state,
            config=config,
            stream_mode=["updates", "values"],
        ):
            if mode == "values":
                state = data

            elif mode == "updates":
                if "__interrupt__" in data:
                    approval_payload = data["__interrupt__"][0].value
                    continue

                for node_name, update in data.items():
                    print(f"[node] {node_name}")

                    for message in update.get("messages", []):
                        for block in message["content"]:
                            if block["type"] == "tool_use":
                                print(
                                    f"[tool_call] name={block['name']} "
                                    f"id={block['id']}"
                                )

                            elif block["type"] == "tool_result":
                                print(
                                    f"[tool_result] id={block['tool_use_id']} "
                                    f"is_error={block['is_error']}"
                                )
    if approval_payload is not None:
        return {
            "status": "waiting_approval",
            "answer": json.dumps(
                approval_payload,
                ensure_ascii=False,
                indent=2,
            ),
        }
    return format_result(state, max_requests)

def resume_graph_agent(
    thread_id: str,
    approved: bool,
    max_requests: int = 10,
) -> dict:
    if type(approved) is not bool:
        raise ValueError("approved 必须是布尔值")

    if type(max_requests) is not int or max_requests < 1:
        raise ValueError("max_requests 必须是正整数")

    env_path = Path(__file__).resolve().parent.parent / ".env"
    load_dotenv(env_path)

    path = Path(__file__).resolve().parent / "agent_checkpoints.sqlite"

    config = {
        "configurable": {
            "thread_id": thread_id,
        },
        "recursion_limit": 4 * max_requests + 5,
    }

    with (
        SqliteSaver.from_conn_string(str(path)) as checkpointer,
        anthropic.Anthropic(
            auth_token=os.environ["API_KEY"],
            base_url=os.getenv("BASE_URL") or None,
        ) as client,
    ):
        graph = build_graph(
            client,
            os.environ["MODEL"],
            checkpointer,
            max_requests=max_requests,
        )

        snapshot = graph.get_state(config)

        if snapshot.next != ("review_changes",):
            raise ValueError("该会话没有等待确认的 Agent 修改")

        state = graph.invoke(
            Command(resume=approved),
            config=config,
        )

    if "__interrupt__" in state:
        payload = state["__interrupt__"][0].value

        return {
            "status": "waiting_approval",
            "answer": json.dumps(
                payload,
                ensure_ascii=False,
                indent=2,
            ),
        }

    return format_result(state, max_requests)