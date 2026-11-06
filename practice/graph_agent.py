from typing import TypedDict, Annotated
import operator

from langgraph.graph import StateGraph, START, END
from agent import TOOLS

class AgentState(TypedDict):
    messages: Annotated[list[dict], operator.add]
    stop_reason: str | None
    request_count: int
    answer: str

def build_graph(client, model: str):
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

    builder = StateGraph(AgentState)

    builder.add_node("call_model", call_model)

    builder.add_edge(START, "call_model")
    builder.add_edge("call_model", END)

    return builder.compile()