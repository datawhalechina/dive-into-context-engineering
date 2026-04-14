"""
工具定义目录。

这一层只负责“登记有哪些工具可用”，不参与实例创建、Prompt 渲染或实际执行，
因此可以把静态定义与运行时行为明确拆开。
"""

from typing import Dict, List, Optional, Type

from .base import BaseTool
from .types import ToolSpec


class ToolCatalog:
    """保存工具元数据以及对应构造器。"""

    def __init__(self):
        self._specs: Dict[str, ToolSpec] = {}
        self._builders: Dict[str, Type[BaseTool]] = {}

    def register(self, tool_class: Type[BaseTool]) -> None:
        """注册一个具体工具类，并建立名称到构造器的映射。"""
        if not issubclass(tool_class, BaseTool):
            raise TypeError("只允许注册 BaseTool 的子类")

        spec = tool_class.spec
        if spec.name in self._builders:
            raise ValueError(f"工具重复注册: {spec.name}")

        self._specs[spec.name] = spec
        self._builders[spec.name] = tool_class

    def get_spec(self, name: str) -> Optional[ToolSpec]:
        """按名称获取工具的静态定义。"""
        return self._specs.get(name)

    def get_builder(self, name: str) -> Optional[Type[BaseTool]]:
        """按名称获取用于实例化工具的类对象。"""
        return self._builders.get(name)

    def list_tool_names(self) -> List[str]:
        """列出当前目录里所有已注册的工具名称。"""
        return list(self._specs.keys())

    def list_specs(self, category: str = None) -> List[ToolSpec]:
        """返回全部 ToolSpec；如传 category，则只保留对应分类。"""
        specs = list(self._specs.values())
        if category is None:
            return specs
        return [spec for spec in specs if spec.category == category]

    def get_categories(self) -> Dict[str, List[str]]:
        """把工具按原始分类名聚合，供兼容层或渲染层继续处理。"""
        categories: Dict[str, List[str]] = {}
        for spec in self._specs.values():
            categories.setdefault(spec.category, []).append(spec.name)
        return categories
