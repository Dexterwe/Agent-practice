from pathlib import Path
import shutil
import subprocess
import json
from errors import ToolError

IGNORED_DIRS = {".git", "node_modules", ".venv", "venv", "__pycache__", "dist", "build"}


def search_code(path: str,keyword: str, max_results: int = 30) -> dict:
  """通过关键词搜索指定目录下的文件内容，返回匹配的文件路径和行号"""
  directory = Path(path).resolve(strict=True)
  if not directory.is_dir():
    raise ToolError("路径必须是一个目录")
  if not keyword:
    raise ToolError("关键词不能为空")
  results = []
  executable = shutil.which("rg")
  if not executable:
    raise ToolError("未找到 rg 命令")
  command = [executable,"--no-config","--json","--fixed-strings","--hidden"]
  for ignored_dir in sorted(IGNORED_DIRS):
    command.extend([f"--glob",f"!**/{ignored_dir}/**"])
  command.extend(["--max-count",str(max_results),"--",keyword,'.'])
  try:
    completed = subprocess.run(command, cwd=directory, capture_output=True, text=True,encoding="utf-8", errors="replace", timeout=10, check=False)
  except subprocess.TimeoutExpired:
    raise ToolError("搜索超过 10 秒，请缩小 path 范围")
  if completed.returncode not in (0, 1):
    raise ToolError(f"搜索失败：{completed.stderr.strip()[:500]}")
  for line in completed.stdout.splitlines():
    event = json.loads(line)
    if event.get("type") != "match":
      continue
    data = event["data"]
    filename = data["path"].get("text")
    content = data["lines"].get("text")
    if filename is None or content is None:
      continue
    results.append({
      "file": str(Path(directory / filename).resolve(strict=True)),
      "line": data["line_number"],
      "content": content,
    })
    if len(results) >= max_results:
      break

  return {
    "results": results[:max_results],
    "path": str(directory.resolve(strict=True)),
    "truncated": len(results) >= max_results,
  }
  

