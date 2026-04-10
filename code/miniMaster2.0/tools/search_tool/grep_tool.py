import os
import re
import json
import fnmatch


class GrepTool:
    name = "grep"
    description = "Search for text patterns in files using regex."

    def prompt_block(self) -> str:
        schema = {
            "type": "object",
            "properties": {
                "pattern": {"type": "string"},
                "path": {"type": "string", "default": "."},
                "include_pattern": {"type": "string"},
                "case_sensitive": {"type": "boolean", "default": False},
                "recursive": {"type": "boolean", "default": True},
                "max_results": {"type": "integer", "default": 100}
            },
            "required": ["pattern"],
            "additionalProperties": False,
        }
        return f"- {self.name}: {self.description}\n  Input schema: {json.dumps(schema, ensure_ascii=False)}"

    def run(self, tool_input: dict) -> dict:
        pattern = str(tool_input["pattern"])
        path = str(tool_input.get("path", "."))
        include_pattern = tool_input.get("include_pattern")
        case_sensitive = tool_input.get("case_sensitive", False)
        recursive = tool_input.get("recursive", True)
        max_results = int(tool_input.get("max_results", 100))
        
        try:
            flags = 0 if case_sensitive else re.IGNORECASE
            compiled_pattern = re.compile(pattern, flags)
        except re.error as e:
            return {"success": False, "matches": [], "total_matches": 0, "files_searched": 0, "error": f"Invalid regex: {e}"}
        
        matches = []
        files_searched = 0
        
        if os.path.isfile(path):
            files_to_search = [path]
        elif os.path.isdir(path):
            files_to_search = self._collect_files(path, include_pattern, recursive)
        else:
            return {"success": False, "matches": [], "total_matches": 0, "files_searched": 0, "error": f"Path not found: {path}"}
        
        for file_path in files_to_search:
            if len(matches) >= max_results:
                break
            try:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    for line_number, line in enumerate(f, 1):
                        for match in compiled_pattern.finditer(line):
                            matches.append({
                                "file": file_path,
                                "line_number": line_number,
                                "line_content": line.rstrip('\n\r'),
                                "matched_text": match.group()
                            })
                            if len(matches) >= max_results:
                                break
                files_searched += 1
            except (PermissionError, IOError):
                continue
        
        return {"success": True, "matches": matches, "total_matches": len(matches), "files_searched": files_searched}
    
    def _collect_files(self, directory, include_pattern, recursive):
        files = []
        if recursive:
            for root, dirs, filenames in os.walk(directory):
                for filename in filenames:
                    if include_pattern:
                        if fnmatch.fnmatch(filename, include_pattern):
                            files.append(os.path.join(root, filename))
                    else:
                        files.append(os.path.join(root, filename))
        else:
            for item in os.listdir(directory):
                item_path = os.path.join(directory, item)
                if os.path.isfile(item_path):
                    if include_pattern:
                        if fnmatch.fnmatch(item, include_pattern):
                            files.append(item_path)
                    else:
                        files.append(item_path)
        return files
