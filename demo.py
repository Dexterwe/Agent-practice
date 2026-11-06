"""Run one local tool without invoking a model."""

import argparse
import json

from local_tools import ProjectTools, ToolError


def main():
    parser = argparse.ArgumentParser(description="运行一个本地项目工具")
    parser.add_argument("project_root", help="允许访问的项目根目录")
    parser.add_argument("tool", choices=["list_files", "search_code", "read_file"])
    parser.add_argument("arguments", nargs="?", default="{}", help="JSON 格式工具参数")
    args = parser.parse_args()

    try:
        arguments = json.loads(args.arguments)
        project = ProjectTools(args.project_root)
        result = project.execute(args.tool, arguments)
    except (ToolError, ValueError, OSError) as error:
        result = {"ok": False, "error": str(error)}

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
