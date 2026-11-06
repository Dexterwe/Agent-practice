from fastapi import FastAPI,HTTPException
from pydantic import BaseModel, Field
from agent import run_agent
from anthropic import APIError

app = FastAPI()

class TaskRequest(BaseModel):
    task: str = Field(min_length=1)

class TaskResponse(BaseModel):
    status: str
    answer: str

@app.post("/tasks",response_model=TaskResponse)
def create_task(body: TaskRequest):
    try:
        return run_agent(body.task)
    except APIError as error:
        raise HTTPException(
          status_code=502,
          detail="调用模型服务失败，请稍后重试或检查服务配置"
        ) from error