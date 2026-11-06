from pathlib import Path
from diff_file import diff_file
from errors import ToolError


def preview_replace(path : str ,old_text : str ,new_text : str) -> dict:
    if not isinstance(path, str) or not path.strip():
        raise ToolError("path 必须是非空字符串")
    if not isinstance(old_text, str) or not old_text:
        raise ToolError("old_text 必须是非空字符串")
    if not isinstance(new_text, str):
        raise ToolError("new_text 必须是字符串")

    # 2. 读取原始内容
    requested = Path(path)

    try:
        origin_text = requested.read_text(encoding="utf-8")
    except UnicodeDecodeError as error:
        raise ToolError("本工具仅支持 UTF-8 文本文件") from error
    
    match_count = origin_text.count(old_text)

    if match_count == 0:
        raise ToolError("未找到 old_text，请先读取文件并确认原文")
    if match_count > 1:
        raise ToolError(
            f"old_text 匹配到 {match_count} 处，请提供更具体的原文"
        )
    
    update_text = origin_text.replace(old_text,new_text,1)

    return {
        "path": str(requested),
        "diff": diff_file(origin_text, update_text),
    }

if __name__ == "__main__":
    result = preview_replace(
        path="practice/readfile.py",
        old_text="start_line 不能大于 end_line",
        new_text="起始行不能大于结束行",
    )

    print(result["diff"], end="")
