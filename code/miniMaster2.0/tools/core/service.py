"""
组合工具系统各组件的门面层。

ToolService 面向上层暴露一个稳定入口，把发现、实例化、执行和渲染
这些细节都封装起来，便于旧代码渐进迁移。
"""

import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Type

from .base import BaseTool
from .catalog import ToolCatalog
from .discover import PROJECT_ROOT, discover_tools
from .executor import ToolExecutor
from .factory import ToolFactory
from .renderer import ToolPromptRenderer
from .types import ToolContext


class ToolService:
    """为工具发现、渲染和执行提供稳定入口。"""

    def __init__(
        self,
        catalog: ToolCatalog,
        factory: ToolFactory,
        executor: ToolExecutor,
        renderer: ToolPromptRenderer,
    ):
        # 这些组件按职责拆开，Service 只负责把它们组合成一套完整 API。
        self.catalog = catalog
        self.factory = factory
        self.executor = executor
        self.renderer = renderer

    @classmethod
    def bootstrap(cls, workspace: Optional[str] = None) -> "ToolService":
        """按默认约定完成整套工具系统装配。"""
        catalog = ToolCatalog()
        discover_tools(catalog)

        # 若调用方未显式传入工作目录，则退化到当前进程目录或项目根目录。
        default_workspace = workspace or os.getcwd() or str(Path(PROJECT_ROOT))
        context = ToolContext(workspace=default_workspace)
        factory = ToolFactory(catalog=catalog, context=context)
        executor = ToolExecutor(factory)
        renderer = ToolPromptRenderer(catalog)
        return cls(catalog=catalog, factory=factory, executor=executor, renderer=renderer)

    def execute(self, name: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """执行指定工具。"""
        return self.executor.execute(name, params)

    def render_prompt(self, category: Optional[str] = None) -> str:
        """渲染工具说明文本，供 Prompt 直接复用。"""
        return self.renderer.render(category=category)

    def list_tool_names(self) -> List[str]:
        """列出所有已注册工具名称。"""
        return self.catalog.list_tool_names()

    def get_tool(self, name: str) -> BaseTool:
        """返回工具实例，供兼容层或高级调用方直接访问。"""
        return self.factory.create(name)

    def get_tool_class(self, name: str) -> Optional[Type[BaseTool]]:
        """返回工具类本身，而不是实例。"""
        return self.catalog.get_builder(name)

    def get_tool_info(self, name: str) -> Optional[Dict[str, Any]]:
        """把 ToolSpec 转换成旧接口熟悉的字典结构。"""
        spec = self.catalog.get_spec(name)
        if spec is None:
            return None

        return {
            "name": spec.name,
            "description": spec.description,
            "category": spec.category,
            "schema": spec.input_schema,
        }

    def get_tools_by_category(self) -> Dict[str, List[str]]:
        """按原始分类聚合工具名称。"""
        return self.catalog.get_categories()
