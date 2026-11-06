import json
import anthropic
from pathlib import Path
from dotenv import load_dotenv
import os
from executor import exexute_tool

TOOLS = [
  {
    "name":"list_files",
    "description":(
      "列出项目中指定目录下的直接子文件和子目录"
      "用于了解项目结构，不递归遍历"
    ),
    "input_schema":{
      "type":"object",
      "properties":{
        "path": {"type":"string", "description":"相对于项目根目录的路径,省略时使用项目根目录"},
        "max_entries":{
          "type":"integer",
          "minimum": 1,
          "maximum": 100,
          "description":"最多返回的文件和目录数量，省略时使用 100，取值范围为 1 到 100"
        }
      },
      "required":[],
      "additionalProperties":False
    }
  },
  {
    "name":"read_file",
    "description":(
      "读取项目内 UTF-8 文本文件的指定行，返回带行号的内容，用于查看和理解代码。"
      "请求行数 end_line - start_line + 1 不能超过 max_lines。"
      ),
    "input_schema":{
      "type":"object",
      "properties":{
        "path":{
          "type":"string",
          "description":"相对于项目根目录的文件路径"
        },
        "start_line":{
          "type":"integer",
          "minimum": 1,
          "maximum": 10000,
          "description":"起始行号，省略时使用 1，取值范围为 1 到 10000"
        },
        "end_line":{
          "type":"integer",
          "minimum": 1,
          "maximum": 10000,
          "description":"结束行号，省略时使用 200，取值范围为 1 到 10000"
        },
        "max_lines":{
          "type":"integer",
          "minimum": 1,
          "maximum": 1000,
          "description":"本次允许请求的最大行数，取值范围为 1 到 1000，如果end_line - start_line + 1 大于 max_lines，则调整 end_line 以满足限制"
        }
      },
      "required":["path","max_lines"],
      "additionalProperties":False
    }
  },
  {
    "name":"search_code",
    "description":("在项目指定目录中按字面匹配关键词，返回匹配的文件路径、行号和该行内容。"
    "用于定位相关代码；需要上下文时，再使用 read_file 读取。"),
    "input_schema":{
      "type":"object",
      "properties":{
        "path":{
          "type":"string",
          "description":"要搜索的目录，相对于项目根目录；使用 . 表示项目根目录"
        },
        "keyword":{
          "type":"string",
          "description":"搜索关键词"
        },
        "max_results":{
          "type":"integer",
          "minimum": 1,
          "maximum": 100,
          "description":"最多返回的匹配结果数量，省略时使用 30，取值范围为 1 到 100"
        }
      },
      "required":["path","keyword"],
      "additionalProperties":False
      }
  },
  {
    "name": "preview_replace",
    "description": (
        "预览指定文件中一处文本替换的差异，不写入文件。"
        "old_text 必须恰好匹配一次，否则返回错误。"
    ),
    "input_schema":{
      "type": "object",
      "properties": {
        "path":{
          "type": "string",
          "description": "指定目录文件路径",
        },
        "old_text":{
          "type": "string",
          "description": ("需要替换的原始文本，必须在文件中恰好匹配一次")
        },
        "new_text":{
          "type": "string",
          "description": "要替换的新内容"
        }
      },
      "required":["path","old_text","new_text"],
      "additionalProperties":False
    }
  },
  {
    "name":"replace_text",
    "description":(
        "替换项目内指定文件中的一处原文，并实际写回文件。"
        "old_text 必须恰好匹配一次，否则返回错误且不写入。"
        "仅需预览差异时使用 preview_replace。"
      ),
    "input_schema":{
      "type":"object",
      "properties":{
        "path":{
          "type": "string",
          "description": "指定目录文件路径",
        },
        "old_text":{
          "type": "string",
          "description": ("需要替换的原始文本，必须在文件中恰好匹配一次")
        },
        "new_text":{
          "type": "string",
          "description": "要替换的新内容"
        }
      },
      "required": ["path", "old_text", "new_text"],
      "additionalProperties": False
    }
  },
  {
    "name": "run_tests",
    "description": (
        "运行当前项目 practice 目录下的 test_*.py 单元测试，"
        "返回测试进程的退出码、标准输出和标准错误输出。"
        "用于检查代码修改后的行为。"
        "returncode 为 0 表示测试命令成功；"
        "非零时应查看报告，判断失败原因。"
        "此工具不接受参数，项目根目录由程序提供。"
    ),
    "input_schema": {
        "type": "object",
        "properties": {},
        "required": [],
        "additionalProperties": False,
    },
  }
]


num = 0
def run_agent(task: str) -> dict:
    task = task.strip()
    if not task:
        return {
            "status": "invalid_task",
            "answer": "任务不能为空",
        }

    env_path = Path(__file__).resolve().parent.parent / ".env"
    load_dotenv(env_path)
    Client = anthropic.Anthropic(
      auth_token=os.environ["API_KEY"],
      base_url=os.getenv("BASE_URL") or None,
    )
    # task = input("请输入任务：").strip()
    # if not task:
    #   print("任务不能为空")
    #   return
    messages = [
      {
        "role": "user",
        "content": task
      }
    ]

    max_requests = 10

    for round_index in range(max_requests):
      response = Client.messages.create(
        model=os.environ.get("MODEL"),
        max_tokens=4096,
        tools=TOOLS,
        tool_choice={
          "type": "auto",
        },
        messages=messages,
      )
      project_root = str(Path(__file__).resolve().parent.parent)
      messages.append({
          "role": "assistant",
          "content": [
              block.model_dump(exclude_none=True)
              for block in response.content
          ],
      }) 

      if response.stop_reason == "end_turn":
          answer = "\n".join(
              block.text
              for block in response.content
              if block.type == "text"
          )
          return {
              "status": "end_turn",
              "answer": answer,
          }

      if response.stop_reason != "tool_use":
          print(f"模型停止，原因：{response.stop_reason}")
          return {
              "status": "stopped",
              "answer": f"模型停止，原因：{response.stop_reason}",
          }

      tool_results = []   

      for block in response.content:
          if block.type != "tool_use":
              continue
              # tool_name = block["name"]
              # tool_input = block["input"]
          
          print(
              f"[tool_call] name={block.name} id={block.id} "
              f"input={json.dumps(block.input, ensure_ascii=False)}"
          )
          result = exexute_tool(
              project_root,
              block.name,
              block.input,
          )
          
          tool_results.append({
            "type": "tool_result",
            "tool_use_id": block.id,
            "content": json.dumps(result, ensure_ascii=False),
            "is_error": not result["ok"],
          })
      if tool_results:
          messages.append({
              "role": "user",
              "content": tool_results,
          })
          print(json.dumps(
              tool_results,
              ensure_ascii=False,
              indent=2,
          ))
    return {
        "status": "request_limit",
        "answer": (
            f"已达到 {max_requests} 次模型请求上限，"
            "尚未收到模型的最终回答，请查看最近的工具执行结果。"
        ),
    }

def main():
    task = input("请输入任务：")
    result = run_agent(task)
    print(result["answer"])

if __name__ == "__main__":
    main()
