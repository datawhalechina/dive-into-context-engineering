"""
System-level Tool Registry
"""

from typing import List


def get_base_tools() -> List[str]:
    """Get all base tools metadata."""
    try:
        from tools.base_tool import get_all_metadata
        return get_all_metadata()
    except ImportError as e:
        print(f"Warning: Could not import base tools: {e}")
        return []


def get_search_tools() -> List[str]:
    """Get all search tools metadata."""
    try:
        from tools.search_tool import get_all_metadata
        return get_all_metadata()
    except ImportError as e:
        print(f"Warning: Could not import search tools: {e}")
        return []


def get_memory_tools() -> List[str]:
    """Get all memory tools metadata."""
    try:
        from tools.memory_tool import get_all_metadata
        return get_all_metadata()
    except ImportError as e:
        print(f"Warning: Could not import memory tools: {e}")
        return []


def get_skills_tools() -> List[str]:
    """Get all skills tools metadata."""
    try:
        from tools.skills_tool import get_all_metadata
        return get_all_metadata()
    except ImportError as e:
        print(f"Warning: Could not import skills tools: {e}")
        return []


def get_all_tools() -> List[str]:
    """Get metadata for all available system tools."""
    all_tools = []
    all_tools.extend(get_base_tools())
    all_tools.extend(get_search_tools())
    all_tools.extend(get_memory_tools())
    all_tools.extend(get_skills_tools())
    return all_tools