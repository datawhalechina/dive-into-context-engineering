"""
Search Tools Module
"""

from .grep_tool import GrepTool
from .glob_tool import GlobTool

__all__ = ['GrepTool', 'GlobTool']


def get_all_tools():
    """Get all search tool instances."""
    return [GrepTool(), GlobTool()]


def get_all_metadata():
    """Get metadata for all search tools."""
    return [tool.prompt_block() for tool in get_all_tools()]
