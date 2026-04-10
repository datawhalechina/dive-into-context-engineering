import os
import json


class EditTool:
    name = "edit"
    description = "Edit a file by replacing text."

    def prompt_block(self) -> str:
        schema = {
            "type": "object",
            "properties": {
                "file_path": {"type": "string"},
                "replacements": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "original_text": {"type": "string"},
                            "new_text": {"type": "string"},
                            "replace_all": {"type": "boolean", "default": False}
                        },
                        "required": ["original_text", "new_text"]
                    }
                }
            },
            "required": ["file_path", "replacements"],
            "additionalProperties": False,
        }
        return f"- {self.name}: {self.description}\n  Input schema: {json.dumps(schema, ensure_ascii=False)}"

    def run(self, tool_input: dict) -> dict:
        file_path = str(tool_input["file_path"])
        replacements = tool_input["replacements"]
        
        try:
            if not os.path.exists(file_path):
                return {"success": False, "message": "", "replacements_made": 0, "error": f"File not found: {file_path}"}
            
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            original_content = content
            total_replacements = 0
            
            for replacement in replacements:
                original_text = replacement.get('original_text', '')
                new_text = replacement.get('new_text', '')
                replace_all = replacement.get('replace_all', False)
                
                if not original_text:
                    continue
                
                if replace_all:
                    count = content.count(original_text)
                    content = content.replace(original_text, new_text)
                    total_replacements += count
                else:
                    if original_text in content:
                        content = content.replace(original_text, new_text, 1)
                        total_replacements += 1
            
            if content == original_content:
                return {"success": True, "message": "No changes made", "replacements_made": 0}
            
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            
            return {"success": True, "message": f"Edited {file_path}", "replacements_made": total_replacements}
        
        except Exception as e:
            return {"success": False, "message": "", "replacements_made": 0, "error": str(e)}
