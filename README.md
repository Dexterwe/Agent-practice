# 第一个 Python Agent 练习：三个本地工具

这一阶段先实现工具执行层。没有接入模型，不需要 SDK、API Key 或向量数据库。

## 文件

- `local_tools.py`：项目根目录校验、三个工具、统一执行入口。
- `demo.py`：通过命令行模拟模型发出的工具名和参数。
- `test_local_tools.py`：在临时项目中验证路径边界、排除规则和搜索行为。

## 环境

当前实现使用 Python 3.9+ 标准库；搜索工具另外需要 `rg`（ripgrep）。
可以运行 `python3 --version`、`rg --version` 检查环境。macOS 若没有 rg，可用 Homebrew 安装 `ripgrep`。

## 直接运行

在本目录执行，项目根目录用 `.`，先读取这个练习自身：

```sh
python3 demo.py . list_files '{}'
python3 demo.py . search_code '{"keyword":"def read_file","path":"local_tools.py"}'
python3 demo.py . read_file '{"path":"local_tools.py","start_line":1,"end_line":30}'
```

第一个参数换成你要读取的项目绝对路径，就可以操作那个项目；工具的 `path` 参数仍然使用项目内相对路径。

## 三个工具的责任

### list_files

只返回一个目录层级。目录返回 `type: directory`，文件返回 `type: file`。
模型看到 `src` 后，可以再次请求 `list_files({"path":"src"})`。
这是控制返回量的设计选择，并不是所有编码 Agent 都必须采用的做法。

### search_code

用 subprocess 执行 rg，返回匹配文件、行号和代码片段。
`--fixed-strings` 表示按字面文本搜索；`a+b` 不会被当作正则表达式。
命令以参数数组执行，没有启用 shell；`--` 将关键字与命令选项分开。
没有匹配是成功结果，返回空的 matches；rg 的退出码 1 不当作执行失败。
默认尊重项目的 gitignore，并额外排除依赖、构建目录和默认私密文件。

### read_file

读取指定行，返回行号和文件总行数，便于模型定位与继续读取。
只支持 UTF-8 文本文件，单次最多 200 行，文件不超过 1 MiB。
文件行数少于 end_line 时，正常返回剩余内容。

## 为什么共享项目根目录

模型给出的路径属于需要校验的工具输入。
`_resolve()` 检查请求路径以及解析符号链接后的真实路径，要求它们处于指定项目内。
默认排除 `.git`、`node_modules`、虚拟环境、构建目录、`.env` / `.env.*`、`apikeys.js` / `apikeys.py`、`.pem`、`.key`。
这些只是本练习的排除规则，不会自动识别所有包含凭据或私密内容的文件；用于其他项目时需要补充规则。

这是应用层路径校验，并不是操作系统沙箱，也未处理恶意并发更换文件或符号链接的场景。
搜索当前会先捕获 rg 输出，再截取结果；大型仓库后续可以改成流式读取并限制输出字节数。

## 接入模型时的对应关系

模型返回 `{name, input, id}` 后，本地执行：

```python
result = project.execute(tool_call.name, tool_call.input)

tool_result = {
    "type": "tool_result",
    "tool_use_id": tool_call.id,
    "is_error": not result["ok"],
    "content": json.dumps(result, ensure_ascii=False),
}
```

这段需要与模型 SDK、工具 Schema、完整 assistant 消息和后续模型请求一起接入；本练习暂时没有实现 API 调用。
工具目前是同步函数，接入异步服务时可通过 `asyncio.to_thread` 等方式执行，避免阻塞事件循环。

## 验证

```sh
python3 -m unittest -v
```

学习顺序：先阅读 `execute()`，再读三个工具，最后看 `_resolve()` 和对应边界测试。
三个工具全部是只读操作，不负责修改代码或运行项目脚本。
