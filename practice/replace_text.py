from pathlib import Path
from errors import ToolError

def replace_text( path:str , old_text: str, new_text: str):
    if not isinstance(path, str) or not path.strip():
        raise ToolError("path 必须是非空字符串")

    if not isinstance(new_text, str):
        raise ToolError("new_text 必须是字符串")
    requested = Path(path)

    if not isinstance(old_text, str) or not old_text:
        raise ToolError("old_text 必须是非空字符串")
    
    context = requested.read_text(encoding="utf-8")

    match_count = context.count(old_text)

    if match_count == 0:
        raise ToolError("未找到 old_text，请先读取文件并确认原文")

    if match_count > 1:
        raise ToolError(f"old_text 匹配到 {match_count} 处，请提供更具体的原文")
    
    new_context = context.replace(old_text,new_text,1)

    requested.write_text(new_context,encoding="utf-8")

    return {
        "path": str(requested),
        "replacements": 1,
    }


