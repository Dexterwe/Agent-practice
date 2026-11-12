from fastapi import FastAPI,HTTPException
from pydantic import BaseModel, Field
# from agent import run_agent
from graph_agent import run_graph_agent
from anthropic import APIError

app = FastAPI()

class TaskRequest(BaseModel):
    task: str = Field(min_length=1)
    thread_id: str = Field(min_length=1, description="用于区分不同会话的唯一标识符，建议使用 UUID 或类似的唯一字符串。")

class TaskResponse(BaseModel):
    status: str
    answer: str

@app.post("/tasks",response_model=TaskResponse)
def create_task(body: TaskRequest):
    try:
        return run_graph_agent(body.task, thread_id=body.thread_id)
    except APIError as error:
        raise HTTPException(
          status_code=502,
          detail="调用模型服务失败，请稍后重试或检查服务配置"
        ) from error