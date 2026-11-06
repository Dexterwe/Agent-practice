from pathlib import Path
from errors import ToolError


def vailed_int(value,name,maximum) -> None:
    if type(value) is not int or not 1<= value <= maximum:
        raise ToolError(f"{name} 必须是 1 到 {maximum} 之间的整数")

def read_file(path:str, max_lines:int, start_line: int = 1,end_line:int = 200) -> dict:
    vailed_int(max_lines, "max_lines", 1000)
    vailed_int(start_line, "start_line", 10000)
    vailed_int(end_line, "end_line", 10000)

    if start_line > end_line:
      raise ToolError("start_line 不能大于 end_line")
      
    requested = Path(path)

    try:
      text = requested.read_text(encoding="utf-8")
    except UnicodeDecodeError:
      raise ToolError("本工具仅支持 UTF-8 文本文件")
    if end_line - start_line + 1 > max_lines:
        raise ToolError(f"请求的行数超过 max_lines 限制，最多可请求 {max_lines} 行")
    lines = text.splitlines()
    if lines and start_line > len(lines):
        raise ToolError(f"start_line 超出文件范围，文件共 {len(lines)} 行")
    selected = lines[start_line - 1:end_line]
    return {
        "lines": len(selected), 
        "total_lines": len(lines),
        "content": "\n".join(
            f"{number}:{line}"
            for number,line in enumerate(selected, start = start_line)
        )
    }