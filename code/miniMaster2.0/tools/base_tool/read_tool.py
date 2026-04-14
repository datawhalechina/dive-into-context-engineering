"""读取文件内容的基础工具。"""

import os

from tools.core import BaseTool, ToolResult, ToolSpec


class ReadTool(BaseTool):
    """支持整文件读取，也支持按行范围截取。"""

    spec = ToolSpec(
        name="read",
        description="Read the contents of a file.",
        category="base",
        input_schema={
            "type": "object",
            "properties": {
                "file_path": {"type": "string"},
                "start_line": {"type": "integer"},
                "end_line": {"type": "integer"},
            },
            "required": ["file_path"],
            "additionalProperties": False,
        },
    )

    def run(self, tool_input: dict) -> ToolResult:
        """读取指定文件；若传入行号，则按 1-based 行号切片返回。"""
        file_path = str(tool_input["file_path"])
        start_line = tool_input.get("start_line")
        end_line = tool_input.get("end_line")

        if not os.path.exists(file_path):
            return ToolResult(success=False, data={"content": ""}, error=f"File not found: {file_path}")

        if not os.path.isfile(file_path):
            return ToolResult(success=False, data={"content": ""}, error=f"Not a file: {file_path}")

        with open(file_path, "r", encoding="utf-8") as file_obj:
            lines = file_obj.readlines()

        total_lines = len(lines)

        if start_line is not None or end_line is not None:
            # 对外暴露的是更符合直觉的 1-based 行号；内部再换算成 Python slice 下标。
            start_idx = max(0, (start_line or 1) - 1)
            end_idx = min(total_lines, end_line or total_lines)
            content = "".join(lines[start_idx:end_idx])
        else:
            content = "".join(lines)

        return ToolResult(success=True, data={"content": content, "total_lines": total_lines})
