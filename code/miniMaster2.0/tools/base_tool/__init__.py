"""
Base Tools Module
"""

from .bash_tool import BashTool
from .read_tool import ReadTool
from .edit_tool import EditTool
from .write_tool import WriteTool

__all__ = ['BashTool', 'ReadTool', 'EditTool', 'WriteTool']


def get_all_tools():
    """Get all base tool instances."""
    return [BashTool(), ReadTool(), EditTool(), WriteTool()]


def get_all_metadata():
    """Get metadata for all base tools."""
    return [tool.prompt_block() for tool in get_all_tools()]
