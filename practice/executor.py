import argparse
import json
from errors import ToolError
from list_file import list_files
from search_code import search_code
from readfile import read_file
from paths import resolve_project_path
from preview_replace import preview_replace
from replace_text import replace_text
from run_tests import run_tests

def exexute_tool(project_root: str, tool: str, arguments: dict) -> dict:
    """统一工具分发；通过此入口调用的路径会先经过项目根目录检查。"""
    handlers = {
      "list_files": list_files,
      "search_code": search_code,
      "read_file": read_file,
      "preview_replace":preview_replace,
      "replace_text":replace_text,
      "run_tests":run_tests
    }
    if not isinstance(tool, str) or tool not in handlers:
        return {"ok": False, "error": "未知工具"}
    if not isinstance(arguments, dict):
        return {"ok": False,"error":"工具参数必须是对象"}
    try:
        # 复制参数，避免修改调用方保存的原始工具请求。
        tool_arguments = arguments.copy()

        if tool == "run_tests":
            if tool_arguments:
                raise ToolError("run_tests 不接受参数")

            root = resolve_project_path(project_root, ".")

            return {
                "ok": True,
                "data": handlers[tool](project_root=str(root)),
            }

        if tool == "read_file" and "path" not in tool_arguments:
            raise ToolError("read_file 必须提供 path")

        # 列目录和搜索省略 path 时使用项目根目录，而不是进程当前目录。
        target = resolve_project_path(project_root, tool_arguments.get("path", "."))
        tool_arguments["path"] = str(target)
        return {"ok": True, "data": handlers[tool](**tool_arguments)}
    except (ToolError, OSError, TypeError, ValueError) as error:
        return {"ok": False, "error": str(error)}

def main():
    parser = argparse.ArgumentParser(description="运行一个本地项目工具")
    parser.add_argument("project_root", help="允许访问的项目根目录")
    parser.add_argument("tool", choices=["list_files", "search_code", "read_file","preview_replace","replace_text","run_tests"])
    parser.add_argument("arguments", nargs="?", default="{}", help="JSON 格式工具参数")
    
    args = parser.parse_args()

    try:
        arguments = json.loads(args.arguments)
        result = exexute_tool(args.project_root, args.tool, arguments)
    except (ToolError, ValueError, OSError) as error:
        result = {"ok": False, "error": str(error)}

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
