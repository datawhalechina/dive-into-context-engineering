"""
Skills Tool Module - Invoke skills from .claude/skills/
"""

from .skill_tool import SkillTool, ListSkillsTool, MatchSkillsTool

__all__ = ['SkillTool', 'ListSkillsTool', 'MatchSkillsTool']


def get_all_tools():
    """Get all skills tool instances."""
    return [SkillTool(), ListSkillsTool(), MatchSkillsTool()]


def get_all_metadata():
    """Get metadata for all skills tools."""
    return [tool.prompt_block() for tool in get_all_tools()]
