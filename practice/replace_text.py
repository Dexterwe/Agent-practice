from pathlib import Path
from errors import ToolError
from hashlib import sha256

def replace_text( path:str , old_text: str, new_text: str, expected_hash: str | None = None):
    if not isinstance(path, str) or not path.strip():
        raise ToolError("path 必须是非空字符串")

    if not isinstance(new_text, str):
        raise ToolError("new_text 必须是字符串")
    requested = Path(path)

    if not isinstance(old_text, str) or not old_text:
        raise ToolError("old_text 必须是非空字符串")
    
    if expected_hash is not None and not isinstance(expected_hash, str):
        raise ToolError("expected_hash 必须是字符串")

    raw = requested.read_bytes()

    if (
        expected_hash is not None
        and sha256(raw).hexdigest() != expected_hash
    ):
        raise ToolError("文件指纹与预览不一致，请重新预览并确认")

    try:
        context = raw.decode("utf-8")
    except UnicodeDecodeError as error:
        raise ToolError("本工具仅支持 UTF-8 文本文件") from error

    match_count = context.count(old_text)

    if match_count == 0:
        raise ToolError("未找到 old_text，请先读取文件并确认原文")

    if match_count > 1:
        raise ToolError(f"old_text 匹配到 {match_count} 处，请提供更具体的原文")
    
    new_context = context.replace(old_text,new_text,1)

    requested.write_bytes(new_context.encode("utf-8"))

    return {
        "path": str(requested),
        "replacements": 1,
    }

