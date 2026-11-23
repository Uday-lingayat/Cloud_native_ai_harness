"""Tool definitions and dispatch for one task's sandbox."""

from app.llm.base import Tool, ToolCall
from app.sandbox.base import (
    OUTPUT_HEAD,
    OUTPUT_TAIL,
    TRUNCATION_MARKER,
    ExecResult,
    Sandbox,
)


def _tool(name: str, description: str, **parameters: str) -> Tool:
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": {
                "type": "object",
                "properties": {
                    key: {"type": "string", "description": value}
                    for key, value in parameters.items()
                },
                "required": list(parameters),
                "additionalProperties": False,
            },
        },
    }


DIRECTORY = "Workspace-relative directory. Use . for the workspace root."
FILE = "Workspace-relative UTF-8 file path."
TOOLS = [
    _tool(
        "list_dir", "List immediate entries, including hidden files.", path=DIRECTORY
    ),
    _tool("read_file", "Read a UTF-8 file.", path=FILE),
    _tool(
        "search",
        "Find literal text recursively. Returns path, line number and matching line. Exit 1 means no matches.",
        path=DIRECTORY,
        query="Literal search text.",
    ),
    _tool(
        "write_file",
        "Create or overwrite a UTF-8 file in an existing directory.",
        path=FILE,
        content="Complete new file contents.",
    ),
    _tool(
        "run_command",
        "Run a shell command in the task container, starting in /workspace. Timeout is 30 seconds.",
        cmd="Shell command.",
    ),
]
_PARAMETERS = {
    tool["function"]["name"]: tool["function"]["parameters"]["required"]
    for tool in TOOLS
}


def _result(text: str, exit_code: int = 0) -> ExecResult:
    data = text.encode()
    if len(data) <= OUTPUT_HEAD + OUTPUT_TAIL:
        return ExecResult(exit_code, text, False)
    kept = data[:OUTPUT_HEAD] + TRUNCATION_MARKER + data[-OUTPUT_TAIL:]
    return ExecResult(exit_code, kept.decode(errors="replace"), True)


def execute_tool(call: ToolCall, sandbox: Sandbox) -> ExecResult:
    """Return tool errors to the caller; infrastructure failures propagate."""
    args = call.arguments
    expected = _PARAMETERS.get(call.name)
    if expected is None:
        return _result("Unknown tool", 2)
    if args.keys() != set(expected) or not all(
        isinstance(value, str) for value in args.values()
    ):
        return _result(f"Expected string arguments: {', '.join(expected)}", 2)
    if any("\x00" in value for key, value in args.items() if key != "content"):
        return _result("Unexpected NUL in argument", 2)
    try:
        if call.name == "list_dir":
            return sandbox.list_dir(args["path"])
        if call.name == "search":
            return sandbox.search(args["path"], args["query"])
        if call.name == "read_file":
            return _result(sandbox.read_file(args["path"]))
        if call.name == "write_file":
            sandbox.write_file(args["path"], args["content"])
            return _result("File written")
        return sandbox.exec(args["cmd"], timeout=30)
    except ValueError as error:
        return _result(str(error), 2)
