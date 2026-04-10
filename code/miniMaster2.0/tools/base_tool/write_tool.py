import os
import json


class WriteTool:
    name = "write"
    description = "Write content to a file."

    def prompt_block(self) -> str:
        schema = {
            "type": "object",
            "properties": {
                "file_path": {"type": "string"},
                "content": {"type": "string"},
                "mode": {"type": "string", "enum": ["overwrite", "append", "create"], "default": "overwrite"}
            },
            "required": ["file_path", "content"],
            "additionalProperties": False,
        }
        return f"- {self.name}: {self.description}\n  Input schema: {json.dumps(schema, ensure_ascii=False)}"

    def run(self, tool_input: dict) -> dict:
        file_path = str(tool_input["file_path"])
        content = str(tool_input["content"])
        mode = str(tool_input.get("mode", "overwrite"))
        
        try:
            file_exists = os.path.exists(file_path)
            
            if mode == 'create' and file_exists:
                return {"success": False, "message": "", "bytes_written": 0, "error": f"File exists: {file_path}"}
            
            directory = os.path.dirname(file_path)
            if directory and not os.path.exists(directory):
                os.makedirs(directory, exist_ok=True)
            
            file_mode = 'a' if mode == 'append' else 'w'
            
            with open(file_path, file_mode, encoding='utf-8') as f:
                f.write(content)
            
            bytes_written = len(content.encode('utf-8'))
            
            if mode == 'append' and file_exists:
                message = f"Appended {bytes_written} bytes to {file_path}"
            elif file_exists:
                message = f"Overwrote {file_path} ({bytes_written} bytes)"
            else:
                message = f"Created {file_path} ({bytes_written} bytes)"
            
            return {"success": True, "message": message, "bytes_written": bytes_written}
        
        except Exception as e:
            return {"success": False, "message": "", "bytes_written": 0, "error": str(e)}
