from pathlib import Path
from errors import ToolError


def list_files(path: str = ".", max_entries: int = 100) -> dict:
  """用于获取一个目录下的文件列表，做多获取 max_entries 个文件"""
  requested = Path(path)
  if not requested.is_dir():
    raise ToolError("路径必须是一个目录")
  resquested = requested.resolve(strict=True)
  entries = []
  for child in sorted(resquested.iterdir(),key=lambda item:item.name):
    if not child.is_dir() and not child.is_file():
      continue
    entries.append({
      "path": child.relative_to(resquested).as_posix(),
      "type": "directory" if child.is_dir() else "file",
    })
    if len(entries) > max_entries:
      break
  return {
    "entries": entries[:max_entries],
    "path": resquested.relative_to(resquested).as_posix(),
    "truncated": len(entries) > max_entries
  }