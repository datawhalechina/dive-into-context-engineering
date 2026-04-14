"""
工具实例工厂。

这一层把“工具定义”变成“可运行实例”，并根据 ToolSpec.singleton
控制是否复用已有对象。
"""

from typing import Dict

from .base import BaseTool
from .catalog import ToolCatalog
from .types import ToolContext


class ToolFactory:
    """负责创建工具实例并管理单例缓存。"""

    def __init__(self, catalog: ToolCatalog, context: ToolContext = None):
        self.catalog = catalog
        self.context = context or ToolContext()
        self._singletons: Dict[str, BaseTool] = {}

    def create(self, name: str) -> BaseTool:
        """按名称创建工具实例；默认优先复用单例。"""
        spec = self.catalog.get_spec(name)
        builder = self.catalog.get_builder(name)

        if spec is None or builder is None:
            raise KeyError(name)

        if spec.singleton:
            # 对无状态或共享上下文的工具复用实例，避免频繁重复构造。
            if name not in self._singletons:
                self._singletons[name] = builder(context=self.context)
            return self._singletons[name]

        # 显式关闭单例的工具，每次调用都返回新的对象。
        return builder(context=self.context)
