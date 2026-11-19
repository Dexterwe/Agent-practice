from fastapi import FastAPI,HTTPException
from pydantic import BaseModel, Field, StrictBool
# from agent import run_agent
from graph_agent import run_graph_agent, resume_graph_agent
from anthropic import APIError

from replace_approval import start_replace_approval, resume_replace_approval
from errors import ToolError

app = FastAPI()

class TaskRequest(BaseModel):
    task: str = Field(min_length=1)
    thread_id: str = Field(min_length=1, description="用于区分不同会话的唯一标识符，建议使用 UUID 或类似的唯一字符串。")

class TaskResponse(BaseModel):
    status: str
    answer: str

class ApprovalDecisionRequest(BaseModel):
    thread_id: str = Field(min_length=1)
    approved: StrictBool

class ReplaceApprovalRequest(BaseModel):
    path: str = Field(min_length=1)
    old_text: str = Field(min_length=1)
    new_text: str
    thread_id: str = Field(min_length=1)

@app.post("/approvals", response_model=TaskResponse)
def create_approval(body: ReplaceApprovalRequest):
    try:
        return start_replace_approval(
            path=body.path,
            old_text=body.old_text,
            new_text=body.new_text,
            thread_id=body.thread_id,
        )
    except ValueError as error:
        raise HTTPException(
            status_code=409,
            detail=str(error),
        ) from error
    except ToolError as error:
        raise HTTPException(
            status_code=400,
            detail=str(error),
        ) from error

@app.post("/approvals/resume", response_model=TaskResponse)
def decide_approval(body: ApprovalDecisionRequest):
    try:
        return resume_replace_approval(
            thread_id=body.thread_id,
            approved=body.approved,
        )
    except (ValueError, ToolError) as error:
        raise HTTPException(
            status_code=409,
            detail=str(error),
        ) from error

@app.post("/tasks",response_model=TaskResponse)
def create_task(body: TaskRequest):
    try:
        return run_graph_agent(body.task, thread_id=body.thread_id)
    except ValueError as error:
        raise HTTPException(
            status_code=409,
            detail=str(error),
        ) from error
    except APIError as error:
        raise HTTPException(
            status_code=502,
            detail="调用模型服务失败，请稍后重试或检查服务配置",
        ) from error

@app.post("/tasks/resume", response_model=TaskResponse)
def resume_task(body: ApprovalDecisionRequest):
    try:
        return resume_graph_agent(
            thread_id=body.thread_id,
            approved=body.approved,
        )
    except ValueError as error:
        raise HTTPException(
            status_code=409,
            detail=str(error),
        ) from error
    except APIError as error:
        raise HTTPException(
            status_code=502,
            detail="调用模型服务失败，请稍后重试或检查服务配置",
        ) from error