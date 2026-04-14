"""执行 Shell 命令的基础工具。"""

import subprocess

from tools.core import BaseTool, ToolResult, ToolSpec


class BashTool(BaseTool):
    """把命令执行能力适配到统一工具协议。"""

    spec = ToolSpec(
        name="bash",
        description="Run a shell command.",
        category="base",
        input_schema={
            "type": "object",
            "properties": {
                "command": {"type": "string"},
                "timeout": {"type": "integer", "default": 30},
            },
            "required": ["command"],
            "additionalProperties": False,
        },
    )

    def run(self, tool_input: dict) -> ToolResult:
        """在共享工作目录中执行命令，并返回标准化结果。"""
        command = str(tool_input["command"])
        timeout = int(tool_input.get("timeout", 30))

        try:
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=timeout,
                # 所有命令都以 ToolContext.workspace 为当前目录执行，避免跑到未知位置。
                cwd=self.context.workspace,
            )
            return ToolResult(
                success=result.returncode == 0,
                data={
                    "stdout": result.stdout,
                    "stderr": result.stderr,
                    "returncode": result.returncode,
                },
            )
        except subprocess.TimeoutExpired:
            # 超时被视为可恢复失败，交由上层 Agent 决定是否重试或换工具。
            return ToolResult(
                success=False,
                data={
                    "stdout": "",
                    "stderr": f"Command timed out after {timeout}s",
                    "returncode": -1,
                },
            )
