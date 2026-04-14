"""
重构后工具系统的兼容门面。

内部实现已经切换到 tools/core 分层结构：
- ToolCatalog：保存工具定义和构造器
- ToolFactory：创建工具实例
- ToolExecutor：统一执行工具
- ToolPromptRenderer：渲染工具说明文本
- ToolService：对外提供稳定入口

这个模块继续保留 main_agent.py 当前依赖的旧接口。
"""

import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Type

# 把项目根目录加入导入路径
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from tools.core import ToolPromptRenderer, ToolService


class ToolRegistry:
    """基于 ToolService 的向后兼容注册表门面。

    旧代码仍然把这里当作“总注册表”使用；内部实际已经委托给新的 ToolService。
    """

    def __init__(self, service: Optional[ToolService] = None):
        # 兼容层自己持有一个 ToolService，调用方无需理解新的分层结构。
        self._service = service or ToolService.bootstrap(workspace=str(project_root))

    def get_tool(self, name: str) -> Optional[Any]:
        """返回工具实例；若不存在则兼容旧行为返回 None。"""
        try:
            return self._service.get_tool(name)
        except KeyError:
            return None

    def get_tool_class(self, name: str) -> Optional[Type]:
        """返回工具类本身，常用于反射或调试。"""
        return self._service.get_tool_class(name)

    def list_tools(self) -> List[str]:
        """列出所有已注册工具名称。"""
        return self._service.list_tool_names()

    def get_tool_info(self, name: str) -> Optional[Dict[str, Any]]:
        """返回旧接口习惯使用的工具信息字典。"""
        return self._service.get_tool_info(name)

    def get_all_tools_prompt(self, category: Optional[str] = None) -> str:
        """渲染所有工具或指定分类工具的 Prompt 描述。"""
        return self._service.render_prompt(category=category)

    def get_tools_by_category(self) -> Dict[str, List[str]]:
        """把底层分类结果整理成旧代码熟悉的固定分类桶。"""
        category_map = {
            "base": [],
            "search": [],
            "memory": [],
            "skills": [],
            "other": [],
        }

        for raw_category, tool_names in self._service.get_tools_by_category().items():
            # 新旧分类名可能不一致，先统一成标准名再归桶。
            normalized_category = ToolPromptRenderer.CATEGORY_ALIASES.get(raw_category, raw_category)
            if normalized_category not in category_map:
                category_map["other"].extend(tool_names)
                continue
            category_map[normalized_category].extend(tool_names)

        return category_map

    def execute(self, name: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """执行指定工具。"""
        return self._service.execute(name, parameters)

    def __contains__(self, name: str) -> bool:
        return name in self.list_tools()

    def __len__(self) -> int:
        return len(self.list_tools())


# 全局单例兼容旧实现，避免每次 import 都重新扫描 tools 目录。
_registry: Optional[ToolRegistry] = None


def get_registry() -> ToolRegistry:
    """获取全局 ToolRegistry 门面实例。"""
    global _registry
    if _registry is None:
        _registry = ToolRegistry()
    return _registry


def _get_tools_by_category_name(category: str) -> List[Dict[str, Any]]:
    """按标准分类名筛选工具元数据。"""
    registry = get_registry()
    tools = []

    for name in registry.list_tools():
        info = registry.get_tool_info(name)
        if not info:
            continue
        if info.get("category") != category:
            continue
        tools.append(info)

    return tools


def get_base_tools() -> List[Dict[str, Any]]:
    """获取所有基础工具的元数据。"""
    return _get_tools_by_category_name("base")


def get_search_tools() -> List[Dict[str, Any]]:
    """获取所有搜索工具的元数据。"""
    return _get_tools_by_category_name("search")


def get_memory_tools() -> List[Dict[str, Any]]:
    """获取所有记忆工具的元数据。"""
    return _get_tools_by_category_name("memory")


def get_skills_tools() -> List[Dict[str, Any]]:
    """获取所有技能工具的元数据。"""
    return _get_tools_by_category_name("skills")


def get_all_tools() -> List[Dict[str, Any]]:
    """获取所有已注册工具的元数据。"""
    registry = get_registry()
    return [registry.get_tool_info(name) for name in registry.list_tools()]


def get_all_tools_prompt(category: Optional[str] = None) -> str:
    """渲染全部工具说明，可按类别过滤。"""
    return get_registry().get_all_tools_prompt(category=category)


def execute_tool(name: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
    """按名称执行工具。"""
    return get_registry().execute(name, parameters)


def format_tools_for_llm(tools: List[Dict[str, Any]]) -> str:
    """把工具元数据格式化成适合放入 Prompt 的文本。"""
    lines = []
    for tool in tools:
        name = tool.get("name", "unknown")
        description = tool.get("description", "No description")
        schema = tool.get("schema", {})

        lines.append(f"- {name}: {description}")
        if schema:
            # schema 直接序列化为 JSON，方便模型按结构化方式理解参数要求。
            lines.append(f"  Input schema: {json.dumps(schema, ensure_ascii=False)}")
        lines.append("")

    return "\n".join(lines)


def get_tools_by_names(names: List[str]) -> str:
    """按名称渲染指定工具的说明文本。"""
    registry = get_registry()
    blocks = []

    for name in names:
        tool = registry.get_tool(name)
        if tool and hasattr(tool, "prompt_block"):
            # 这里复用工具实例自己的 prompt_block，保持输出格式与旧版完全兼容。
            blocks.append(tool.prompt_block())

    return "\n".join(blocks)
