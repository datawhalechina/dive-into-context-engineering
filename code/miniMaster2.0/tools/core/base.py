"""
所有工具共享的统一基类。

这个基类把工具系统里最容易重复的三件事集中处理：
1. 持有并暴露静态 ToolSpec 元信息
2. 在进入具体 run() 逻辑前做轻量参数校验
3. 把不同风格的返回值统一整理成上层可直接消费的 dict
"""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from typing import Any, Dict

from .types import ToolContext, ToolResult, ToolSpec


class BaseTool(ABC):
    """集中处理参数校验和结果归一化的工具基类。

    子类只需要声明 spec 并实现 run()，不必重复编写公共控制流。
    """

    # 子类必须覆盖这个类属性，用来声明工具名称、分类、参数结构等静态信息。
    spec: ToolSpec = None

    def __init__(self, context: ToolContext = None):
        """挂载共享上下文，例如工作目录、环境变量和扩展状态。"""
        if not isinstance(self.spec, ToolSpec):
            raise ValueError(f"{self.__class__.__name__} 必须定义名为 spec 的 ToolSpec")
        self.context = context or ToolContext()

    @property
    def name(self) -> str:
        return self.spec.name

    @property
    def description(self) -> str:
        return self.spec.description

    @property
    def category(self) -> str:
        return self.spec.category

    @property
    def input_schema(self) -> Dict[str, Any]:
        return self.spec.input_schema

    def prompt_block(self) -> str:
        """把工具信息渲染成旧 Prompt 模板仍可直接使用的文本块。"""
        return (
            f"- {self.name}: {self.description}\n"
            f"  Input schema: {json.dumps(self.input_schema, ensure_ascii=False)}"
        )

    def validate(self, params: Dict[str, Any]) -> None:
        """按照 ToolSpec 中声明的简化 schema 做运行前校验。"""
        if not isinstance(params, dict):
            raise TypeError("工具参数必须是字典")

        schema = self.input_schema
        properties = schema.get("properties", {})
        required_fields = schema.get("required", [])

        # 先检查缺失的必填字段，避免具体工具内部再做重复空值判断。
        for field_name in required_fields:
            if field_name not in params:
                raise ValueError(f"缺少必填字段: {field_name}")

        # 如果 schema 明确禁止额外字段，则在这里提前拦截拼写错误或脏参数。
        if schema.get("additionalProperties") is False:
            unexpected = sorted(set(params.keys()) - set(properties.keys()))
            if unexpected:
                raise ValueError(f"存在未定义字段: {unexpected}")

        for field_name, value in params.items():
            field_schema = properties.get(field_name)
            if not field_schema:
                continue
            self._validate_field(field_name, value, field_schema)

    def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """执行标准流程：校验参数 -> 运行工具 -> 归一化结果。"""
        self.validate(params)
        result = self.run(dict(params))
        return self.normalize_result(result)

    def normalize_result(self, result: Any) -> Dict[str, Any]:
        """兼容新旧两类返回格式，统一整理成带 success 字段的 dict。"""
        if isinstance(result, ToolResult):
            # ToolResult 是新框架推荐的标准结构，额外信息放在 data 中统一展开。
            payload = {"success": result.success, **result.data}
            if result.error is not None:
                payload["error"] = result.error
            return payload

        if isinstance(result, dict):
            # 兼容历史工具直接返回 dict 的写法；若未显式声明 success，则默认为成功。
            if "success" not in result:
                return {"success": True, **result}
            return result

        raise TypeError(
            f"{self.__class__.__name__}.run() 必须返回 ToolResult 或 dict，实际返回 {type(result).__name__}"
        )

    def _validate_field(self, field_name: str, value: Any, field_schema: Dict[str, Any]) -> None:
        """校验单个字段的类型和枚举范围。"""
        expected_type = field_schema.get("type")
        if expected_type and not self._matches_type(expected_type, value):
            raise TypeError(
                f"字段 '{field_name}' 期望类型为 '{expected_type}'，实际为 '{type(value).__name__}'"
            )

        enum_values = field_schema.get("enum")
        if enum_values is not None and value not in enum_values:
            raise ValueError(f"字段 '{field_name}' 必须是 {enum_values} 之一")

    def _matches_type(self, expected_type: str, value: Any) -> bool:
        """实现一套覆盖当前工具系统需求的基础 JSON 类型映射。"""
        if expected_type == "string":
            return isinstance(value, str)
        if expected_type == "integer":
            return isinstance(value, int) and not isinstance(value, bool)
        if expected_type == "number":
            return (isinstance(value, int) and not isinstance(value, bool)) or isinstance(value, float)
        if expected_type == "boolean":
            return isinstance(value, bool)
        if expected_type == "array":
            return isinstance(value, list)
        if expected_type == "object":
            return isinstance(value, dict)
        return True

    @abstractmethod
    def run(self, params: Dict[str, Any]) -> Any:
        """执行工具自身的具体逻辑。"""
        raise NotImplementedError
