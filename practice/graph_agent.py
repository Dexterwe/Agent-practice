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



class AgentState(TypedDict):
    messages: Annotated[list[dict], operator.add]
    stop_reason: str | None
    request_count: int
    answer: str

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

    builder = StateGraph(AgentState)

    builder.add_node("call_model", call_model)
    builder.add_node("execute_tools", execute_tools)

    builder.add_edge(START, "call_model")
    builder.add_conditional_edges(
        "call_model",
        route_after_model,
        {
            "tools": "execute_tools",
            "stop": END,
        },
    )

    builder.add_conditional_edges(
        "execute_tools",
        route_after_tools,
        {
            "model": "call_model",
            "stop": END,
        },
    )
    

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

        # state = graph.invoke(
        #     initial_state,
        #     config={
        #         "recursion_limit": 2 * max_requests + 5,
        #     },
        # )

        state = initial_state

        for mode, data in graph.stream(
            initial_state,
            config={
                "configurable": {
                    "thread_id": thread_id,
                },
                "recursion_limit": 2 * max_requests + 5,
            },
            stream_mode=["updates", "values"],
        ):
            if mode == "values":
                state = data

            elif mode == "updates":
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

    return format_result(state, max_requests)