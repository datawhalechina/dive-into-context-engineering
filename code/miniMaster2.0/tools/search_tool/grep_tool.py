"""基于正则表达式的文本搜索工具。"""

import fnmatch
import os
import re

from tools.core import BaseTool, ToolResult, ToolSpec


class GrepTool(BaseTool):
    """在单个文件或目录树中搜索文本模式。"""

    spec = ToolSpec(
        name="grep",
        description="Search for text patterns in files using regex.",
        category="search",
        input_schema={
            "type": "object",
            "properties": {
                "pattern": {"type": "string"},
                "path": {"type": "string", "default": "."},
                "include_pattern": {"type": "string"},
                "case_sensitive": {"type": "boolean", "default": False},
                "recursive": {"type": "boolean", "default": True},
                "max_results": {"type": "integer", "default": 100},
            },
            "required": ["pattern"],
            "additionalProperties": False,
        },
    )

    def run(self, tool_input: dict) -> ToolResult:
        """编译正则后遍历文件，并把每个命中整理成结构化记录。"""
        pattern = str(tool_input["pattern"])
        path = str(tool_input.get("path", "."))
        include_pattern = tool_input.get("include_pattern")
        case_sensitive = tool_input.get("case_sensitive", False)
        recursive = tool_input.get("recursive", True)
        max_results = int(tool_input.get("max_results", 100))

        try:
            flags = 0 if case_sensitive else re.IGNORECASE
            compiled_pattern = re.compile(pattern, flags)
        except re.error as exc:
            # 非法正则不抛异常到框架外，而是作为普通失败结果返回给 Agent。
            return ToolResult(
                success=False,
                data={"matches": [], "total_matches": 0, "files_searched": 0},
                error=f"Invalid regex: {exc}",
            )

        matches = []
        files_searched = 0

        if os.path.isfile(path):
            files_to_search = [path]
        elif os.path.isdir(path):
            files_to_search = self._collect_files(path, include_pattern, recursive)
        else:
            return ToolResult(
                success=False,
                data={"matches": [], "total_matches": 0, "files_searched": 0},
                error=f"Path not found: {path}",
            )

        for file_path in files_to_search:
            if len(matches) >= max_results:
                break
            try:
                with open(file_path, "r", encoding="utf-8", errors="ignore") as file_obj:
                    for line_number, line in enumerate(file_obj, 1):
                        for match in compiled_pattern.finditer(line):
                            # 保留文件、行号、整行文本和实际命中文本，便于后续推理或定位。
                            matches.append(
                                {
                                    "file": file_path,
                                    "line_number": line_number,
                                    "line_content": line.rstrip("\n\r"),
                                    "matched_text": match.group(),
                                }
                            )
                            if len(matches) >= max_results:
                                break
                files_searched += 1
            except (PermissionError, IOError):
                # 对不可读文件直接跳过，避免一次权限问题终止整个搜索。
                continue

        return ToolResult(
            success=True,
            data={"matches": matches, "total_matches": len(matches), "files_searched": files_searched},
        )

    def _collect_files(self, directory, include_pattern, recursive):
        """根据递归开关和文件名过滤模式收集待搜索文件列表。"""
        files = []
        if recursive:
            for root, _, filenames in os.walk(directory):
                for filename in filenames:
                    if include_pattern and not fnmatch.fnmatch(filename, include_pattern):
                        continue
                    files.append(os.path.join(root, filename))
            return files

        for item in os.listdir(directory):
            item_path = os.path.join(directory, item)
            if not os.path.isfile(item_path):
                continue
            if include_pattern and not fnmatch.fnmatch(item, include_pattern):
                continue
            files.append(item_path)
        return files
