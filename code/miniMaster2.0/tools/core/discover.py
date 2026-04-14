"""
自动发现并注册工具类。

这里负责扫描 tools/ 目录下的各个工具分类，把符合 BaseTool 协议的类
批量放入 ToolCatalog，减少手工维护注册表的成本。
"""

import importlib
import inspect
import sys
from pathlib import Path

from .base import BaseTool
from .catalog import ToolCatalog

# tools/core 位于 tools/ 目录内部，因此向上两级就是 miniMaster2.0 的项目根目录。
PROJECT_ROOT = Path(__file__).resolve().parents[2]
TOOLS_DIR = PROJECT_ROOT / "tools"

if str(PROJECT_ROOT) not in sys.path:
    # 确保后续可以通过 tools.xxx 的包路径稳定导入模块。
    sys.path.insert(0, str(PROJECT_ROOT))


def discover_tools(catalog: ToolCatalog, tools_dir: Path = None) -> ToolCatalog:
    """扫描工具目录并注册 BaseTool 子类。"""
    target_dir = tools_dir or TOOLS_DIR

    if not target_dir.exists():
        return catalog

    for category_dir in target_dir.iterdir():
        # core 目录存放框架基础设施，本身不是可执行工具分类。
        if not category_dir.is_dir() or category_dir.name.startswith("__") or category_dir.name == "core":
            continue

        for file_path in category_dir.glob("*_tool.py"):
            module_path = f"tools.{category_dir.name}.{file_path.stem}"
            module = importlib.import_module(module_path)

            for _, obj in inspect.getmembers(module, inspect.isclass):
                # 只注册当前模块中真正定义的 BaseTool 子类，避免把导入进来的类重复登记。
                if obj is BaseTool:
                    continue
                if not issubclass(obj, BaseTool):
                    continue
                if obj.__module__ != module.__name__:
                    continue
                catalog.register(obj)

    return catalog
