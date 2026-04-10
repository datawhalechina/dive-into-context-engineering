"""
System-level Tool Registry

提供统一的工具注册、发现和执行功能，使模型能够调用 tools/ 目录下的所有工具。
"""

import os
import sys
import json
import importlib
import inspect
from typing import Dict, List, Type, Optional, Any, Callable
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))


class ToolRegistry:
    """
    统一的工具注册表，管理所有可用工具。

    功能：
    1. 自动发现和注册 tools/ 目录下的所有工具
    2. 根据工具名称获取工具实例
    3. 生成 LLM 可用的工具描述
    4. 执行指定名称的工具

    使用方法：
        registry = ToolRegistry()

        # 获取所有工具元数据（用于 LLM prompt）
        tools_info = registry.get_all_tools_prompt()

        # 执行工具
        result = registry.execute("read", {"file_path": "test.txt"})
    """

    def __init__(self):
        self._tools: Dict[str, Any] = {}  # name -> tool instance
        self._tool_classes: Dict[str, Type] = {}  # name -> tool class
        self._discover_and_register()

    def _discover_and_register(self):
        """自动发现并注册所有工具。"""
        tools_dir = project_root / "tools"

        if not tools_dir.exists():
            return

        # 遍历 tools/ 下的子目录
        for category_dir in tools_dir.iterdir():
            if not category_dir.is_dir() or category_dir.name.startswith("__"):
                continue

            # 尝试导入该模块的 __init__.py 中的 get_all_tools
            try:
                module_path = f"tools.{category_dir.name}"
                module = importlib.import_module(module_path)

                # 如果模块有 get_all_tools 函数，使用它
                if hasattr(module, "get_all_tools"):
                    tools = module.get_all_tools()
                    for tool in tools:
                        self.register(tool)
                else:
                    # 否则手动扫描目录中的工具类
                    self._scan_directory(category_dir, module_path)

            except ImportError as e:
                print(f"Warning: Could not import {category_dir.name}: {e}")
                continue

    def _scan_directory(self, directory: Path, module_prefix: str):
        """扫描目录中的工具类文件。"""
        for file_path in directory.glob("*_tool.py"):
            try:
                module_name = file_path.stem
                full_module_path = f"{module_prefix}.{module_name}"
                module = importlib.import_module(full_module_path)

                # 查找模块中的工具类
                for name, obj in inspect.getmembers(module):
                    if (inspect.isclass(obj) and
                        hasattr(obj, "name") and
                        hasattr(obj, "description") and
                        hasattr(obj, "run") and
                        not name.startswith("_")):
                        self.register(obj())

            except ImportError as e:
                print(f"Warning: Could not import {file_path}: {e}")

    def register(self, tool_instance: Any) -> None:
        """
        注册一个工具实例。

        Args:
            tool_instance: 工具实例，必须包含 name, description, run 属性/方法
        """
        name = getattr(tool_instance, "name", None)
        if not name:
            return

        self._tools[name] = tool_instance
        self._tool_classes[name] = tool_instance.__class__

    def get_tool(self, name: str) -> Optional[Any]:
        """
        获取指定名称的工具实例。

        Args:
            name: 工具名称

        Returns:
            工具实例，如果不存在则返回 None
        """
        return self._tools.get(name)

    def get_tool_class(self, name: str) -> Optional[Type]:
        """
        获取指定名称的工具类。

        Args:
            name: 工具名称

        Returns:
            工具类，如果不存在则返回 None
        """
        return self._tool_classes.get(name)

    def list_tools(self) -> List[str]:
        """
        获取所有已注册的工具名称列表。

        Returns:
            工具名称列表
        """
        return list(self._tools.keys())

    def get_tool_info(self, name: str) -> Optional[Dict[str, Any]]:
        """
        获取工具的详细信息。

        Args:
            name: 工具名称

        Returns:
            工具信息字典，包含 name, description, schema
        """
        tool = self._tools.get(name)
        if not tool:
            return None

        info = {
            "name": getattr(tool, "name", name),
            "description": getattr(tool, "description", ""),
        }

        # 如果有 prompt_block 方法，获取 schema
        if hasattr(tool, "prompt_block"):
            prompt_text = tool.prompt_block()
            # 尝试解析 JSON schema
            try:
                schema_start = prompt_text.find('{"type"')
                if schema_start != -1:
                    schema = json.loads(prompt_text[schema_start:])
                    info["schema"] = schema
            except json.JSONDecodeError:
                pass

        return info

    def get_all_tools_prompt(self, category: Optional[str] = None) -> str:
        """
        生成所有工具的 LLM prompt 描述。

        Args:
            category: 可选，只返回指定类别的工具 (base_tool, search_tool, skills_tool)

        Returns:
            格式化的工具描述字符串
        """
        blocks = []

        for name, tool in self._tools.items():
            # 如果指定了类别，进行过滤
            if category:
                tool_module = tool.__class__.__module__
                if category not in tool_module:
                    continue

            if hasattr(tool, "prompt_block"):
                blocks.append(tool.prompt_block())
            else:
                # 基本描述
                desc = getattr(tool, "description", "No description")
                blocks.append(f"- {name}: {desc}")

        return "\n".join(blocks)

    def get_tools_by_category(self) -> Dict[str, List[str]]:
        """
        按类别获取工具列表。

        Returns:
            字典，键为类别名，值为工具名称列表
        """
        categories = {
            "base": [],
            "search": [],
            "skills": [],
            "other": []
        }

        for name, tool in self._tools.items():
            module = tool.__class__.__module__
            if "base_tool" in module:
                categories["base"].append(name)
            elif "search_tool" in module:
                categories["search"].append(name)
            elif "skills_tool" in module:
                categories["skills"].append(name)
            else:
                categories["other"].append(name)

        return categories

    def execute(self, name: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        执行指定名称的工具。

        Args:
            name: 工具名称
            parameters: 工具参数字典

        Returns:
            工具执行结果
        """
        tool = self._tools.get(name)
        if not tool:
            return {
                "success": False,
                "error": f"Unknown tool: '{name}'. Available tools: {self.list_tools()}"
            }

        try:
            if hasattr(tool, "run"):
                result = tool.run(parameters)
                return result
            else:
                return {"success": False, "error": f"Tool '{name}' has no run method"}
        except Exception as e:
            return {"success": False, "error": f"Tool execution failed: {str(e)}"}

    def __contains__(self, name: str) -> bool:
        """检查工具是否已注册。"""
        return name in self._tools

    def __len__(self) -> int:
        """返回已注册工具数量。"""
        return len(self._tools)


# ============================================================
# 全局注册表实例（单例模式）
# ============================================================
_registry: Optional[ToolRegistry] = None


def get_registry() -> ToolRegistry:
    """获取全局 ToolRegistry 实例。"""
    global _registry
    if _registry is None:
        _registry = ToolRegistry()
    return _registry


# ============================================================
# 向后兼容的函数接口
# ============================================================

def get_base_tools() -> List[Dict]:
    """获取所有基础工具的元数据。"""
    registry = get_registry()
    tools = []
    for name in registry.list_tools():
        tool = registry.get_tool(name)
        if tool and "base_tool" in tool.__class__.__module__:
            info = registry.get_tool_info(name)
            if info:
                tools.append(info)
    return tools


def get_search_tools() -> List[Dict]:
    """获取所有搜索工具的元数据。"""
    registry = get_registry()
    tools = []
    for name in registry.list_tools():
        tool = registry.get_tool(name)
        if tool and "search_tool" in tool.__class__.__module__:
            info = registry.get_tool_info(name)
            if info:
                tools.append(info)
    return tools


def get_memory_tools() -> List[Dict]:
    """获取所有内存工具的元数据。"""
    registry = get_registry()
    tools = []
    for name in registry.list_tools():
        tool = registry.get_tool(name)
        if tool and "memory_tool" in tool.__class__.__module__:
            info = registry.get_tool_info(name)
            if info:
                tools.append(info)
    return tools


def get_skills_tools() -> List[Dict]:
    """获取所有技能工具的元数据。"""
    registry = get_registry()
    tools = []
    for name in registry.list_tools():
        tool = registry.get_tool(name)
        if tool and "skills_tool" in tool.__class__.__module__:
            info = registry.get_tool_info(name)
            if info:
                tools.append(info)
    return tools


def get_all_tools() -> List[Dict]:
    """获取所有可用工具的元数据。"""
    registry = get_registry()
    return [registry.get_tool_info(name) for name in registry.list_tools()]


def get_all_tools_prompt() -> str:
    """获取所有工具的 LLM prompt 描述。"""
    return get_registry().get_all_tools_prompt()


def execute_tool(name: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
    """
    执行指定名称的工具。

    Args:
        name: 工具名称
        parameters: 工具参数

    Returns:
        工具执行结果
    """
    return get_registry().execute(name, parameters)


# ============================================================
# 便捷函数：生成特定格式的工具描述
# ============================================================

def format_tools_for_llm(tools: List[Dict]) -> str:
    """
    将工具元数据列表格式化为 LLM 可用的字符串。

    Args:
        tools: 工具信息字典列表

    Returns:
        格式化的工具描述
    """
    lines = []
    for tool in tools:
        name = tool.get("name", "unknown")
        description = tool.get("description", "No description")
        schema = tool.get("schema", {})

        lines.append(f"- {name}: {description}")
        if schema:
            lines.append(f"  Input schema: {json.dumps(schema, ensure_ascii=False)}")
        lines.append("")

    return "\n".join(lines)


def get_tools_by_names(names: List[str]) -> str:
    """
    获取指定名称工具的 prompt 描述。

    Args:
        names: 工具名称列表

    Returns:
        格式化的工具描述
    """
    registry = get_registry()
    blocks = []

    for name in names:
        tool = registry.get_tool(name)
        if tool and hasattr(tool, "prompt_block"):
            blocks.append(tool.prompt_block())

    return "\n".join(blocks)

