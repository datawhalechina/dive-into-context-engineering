"""
工具统一执行层。

执行层只关心两件事：
1. 通过工厂拿到目标工具实例
2. 把创建失败或运行异常都收敛成统一错误结构返回给上层
"""

from typing import Any, Dict

from .factory import ToolFactory


class ToolExecutor:
    """通过统一入口执行工具。"""

    def __init__(self, factory: ToolFactory):
        self.factory = factory

    def execute(self, name: str, params: Dict[str, Any]) -> Dict[str, Any]:
        try:
            tool = self.factory.create(name)
        except KeyError:
            # 未知工具属于可恢复错误，直接返回失败结果给调用方即可。
            return {"success": False, "error": f"未知工具: '{name}'"}

        try:
            return tool.execute(params)
        except Exception as exc:
            # 这里兜底所有工具内部异常，避免单个工具把整个 Agent 循环打断。
            return {"success": False, "error": f"工具执行失败: {str(exc)}"}
