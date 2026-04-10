import os
import json


class ReadTool:
    name = "read"
    description = "Read the contents of a file."

    def prompt_block(self) -> str:
        schema = {
            "type": "object",
            "properties": {
                "file_path": {"type": "string"},
                "start_line": {"type": "integer"},
                "end_line": {"type": "integer"},
            },
            "required": ["file_path"],
            "additionalProperties": False,
        }
        return f"- {self.name}: {self.description}\n  Input schema: {json.dumps(schema, ensure_ascii=False)}"

    def run(self, tool_input: dict) -> dict:
        file_path = str(tool_input["file_path"])
        start_line = tool_input.get("start_line")
        end_line = tool_input.get("end_line")
        
        try:
            if not os.path.exists(file_path):
                return {"success": False, "content": "", "error": f"File not found: {file_path}"}
            
            if not os.path.isfile(file_path):
                return {"success": False, "content": "", "error": f"Not a file: {file_path}"}
            
            with open(file_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            total_lines = len(lines)
            
            if start_line is not None or end_line is not None:
                start_idx = max(0, (start_line or 1) - 1)
                end_idx = min(total_lines, end_line or total_lines)
                content = ''.join(lines[start_idx:end_idx])
            else:
                content = ''.join(lines)
            
            return {"success": True, "content": content, "total_lines": total_lines}
        
        except Exception as e:
            return {"success": False, "content": "", "error": str(e)}
