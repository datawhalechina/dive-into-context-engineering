"""
工具 Prompt 渲染工具。

主 Agent 还在使用文本 Prompt 描述工具，因此这里负责把 ToolSpec
重新组织成模型可读的说明块。
"""

import json
from typing import Dict, Optional

from .catalog import ToolCatalog
from .types import ToolSpec


class ToolPromptRenderer:
    """把工具元数据渲染成适合放入 Prompt 的文本。"""

    CATEGORY_ALIASES: Dict[str, str] = {
        # 兼容旧调用方仍然使用 xxx_tool 分类名的场景。
        "base_tool": "base",
        "search_tool": "search",
        "skills_tool": "skills",
        "memory_tool": "memory",
    }

    def __init__(self, catalog: ToolCatalog):
        self.catalog = catalog

    def normalize_category(self, category: Optional[str] = None) -> Optional[str]:
        """把旧分类别名转换成新框架内部使用的标准分类名。"""
        if category is None:
            return None
        return self.CATEGORY_ALIASES.get(category, category)

    def render(self, category: Optional[str] = None) -> str:
        """渲染指定分类或全部工具的 Prompt 描述。"""
        normalized_category = self.normalize_category(category)
        specs = self.catalog.list_specs(category=normalized_category)
        return "\n".join(self.render_spec(spec) for spec in specs)

    def render_spec(self, spec: ToolSpec) -> str:
        """把单个 ToolSpec 渲染成旧模板兼容的两行文本。"""
        return (
            f"- {spec.name}: {spec.description}\n"
            f"  Input schema: {json.dumps(spec.input_schema, ensure_ascii=False)}"
        )
