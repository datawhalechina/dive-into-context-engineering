import subprocess
import json


class BashTool:
    name = "bash"
    description = "Run a shell command."

    def prompt_block(self) -> str:
        schema = {
            "type": "object",
            "properties": {
                "command": {"type": "string"},
                "timeout": {"type": "integer", "default": 30},
            },
            "required": ["command"],
            "additionalProperties": False,
        }
        return f"- {self.name}: {self.description}\n  Input schema: {json.dumps(schema, ensure_ascii=False)}"

    def run(self, tool_input: dict) -> dict:
        command = str(tool_input["command"])
        timeout = int(tool_input.get("timeout", 30))
        
        try:
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=timeout
            )
            return {
                "success": result.returncode == 0,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "returncode": result.returncode
            }
        except subprocess.TimeoutExpired:
            return {"success": False, "stdout": "", "stderr": f"Command timed out after {timeout}s", "returncode": -1}
        except Exception as e:
            return {"success": False, "stdout": "", "stderr": str(e), "returncode": -1}
