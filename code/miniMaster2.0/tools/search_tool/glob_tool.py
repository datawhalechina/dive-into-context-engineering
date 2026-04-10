import os
import glob as glob_module
import json


class GlobTool:
    name = "glob"
    description = "Find files matching glob patterns."

    def prompt_block(self) -> str:
        schema = {
            "type": "object",
            "properties": {
                "pattern": {"type": "string"},
                "recursive": {"type": "boolean", "default": True},
                "include_hidden": {"type": "boolean", "default": False},
                "max_results": {"type": "integer", "default": 1000}
            },
            "required": ["pattern"],
            "additionalProperties": False,
        }
        return f"- {self.name}: {self.description}\n  Input schema: {json.dumps(schema, ensure_ascii=False)}"

    def run(self, tool_input: dict) -> dict:
        pattern = str(tool_input["pattern"])
        recursive = tool_input.get("recursive", True)
        include_hidden = tool_input.get("include_hidden", False)
        max_results = int(tool_input.get("max_results", 1000))
        
        try:
            matches = glob_module.glob(pattern, recursive=recursive)
            matches.sort()
            matches = matches[:max_results]
            
            files = []
            directories = []
            
            for match in matches:
                if not include_hidden:
                    parts = match.split(os.sep)
                    if any(part.startswith('.') and part not in ['.', '..'] for part in parts):
                        continue
                
                if os.path.isfile(match):
                    files.append(match)
                elif os.path.isdir(match):
                    directories.append(match)
            
            return {
                "success": True,
                "files": files,
                "directories": directories,
                "total_files": len(files),
                "total_directories": len(directories)
            }
        except Exception as e:
            return {"success": False, "files": [], "directories": [], "total_files": 0, "total_directories": 0, "error": str(e)}
