from pathlib import Path

from errors import ToolError


def resolve_project_path(project_root: str, path: str = ".") -> Path:
    """解析已存在的项目路径，并检查解析符号链接后的目标是否位于根目录内。

    相对路径以 project_root 为基准；绝对路径也必须位于该根目录内。
    这是应用层路径检查，不处理检查后被并发替换的文件或符号链接。
    """
    if not isinstance(project_root, str) or not project_root.strip():
        raise ToolError("project_root 必须是非空字符串")
    if not isinstance(path, str) or not path.strip():
        raise ToolError("path 必须是非空字符串")

    try:
        root = Path(project_root).expanduser().resolve(strict=True)
    except (OSError, RuntimeError, ValueError) as error:
        raise ToolError("项目根目录不存在或无法解析") from error
    if not root.is_dir():
        raise ToolError("项目根路径必须是目录")

    try:
        target = (root / path).resolve(strict=True)
    except (OSError, RuntimeError, ValueError) as error:
        raise ToolError("目标路径不存在或无法解析") from error

    try:
        target.relative_to(root)
    except ValueError as error:
        raise ToolError("路径超出项目根目录") from error

    return target
