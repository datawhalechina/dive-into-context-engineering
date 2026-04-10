"""
Skill Tool - Allow the agent to invoke skills from .claude/skills/
"""

import os
import sys
import json

# Add project root to path for importing utils
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from utils.skill_parser import SkillRegistry, SkillParser


class SkillTool:
    """Tool for invoking skills."""
    name = "skill"
    description = "Invoke a skill from .claude/skills/ to solve specialized tasks. Use this when the task involves: PDF processing, Excel/spreadsheet work, Word documents, PowerPoint presentations, or frontend web design."

    def __init__(self):
        self.registry = SkillRegistry()

    def prompt_block(self) -> str:
        """Generate the tool description for LLM prompt."""
        schema = {
            "type": "object",
            "properties": {
                "skill_name": {
                    "type": "string",
                    "description": "Name of the skill to invoke (e.g., 'pdf', 'xlsx', 'docx', 'pptx', 'frontend-design')"
                },
                "task": {
                    "type": "string",
                    "description": "Description of what you want to accomplish with this skill"
                }
            },
            "required": ["skill_name", "task"],
            "additionalProperties": False,
        }
        available_skills = [s.name for s in self.registry.get_all_skills()]
        return f"- {self.name}: {self.description}\n  Available skills: {available_skills}\n  Input schema: {json.dumps(schema, ensure_ascii=False)}"

    def run(self, tool_input: dict) -> dict:
        """
        Invoke a skill.

        Args:
            tool_input: dict with 'skill_name' and 'task'

        Returns:
            dict with skill guide and suggestions
        """
        skill_name = tool_input.get("skill_name", "")
        task = tool_input.get("task", "")

        if not skill_name:
            return {
                "success": False,
                "error": "skill_name is required",
                "available_skills": [s.name for s in self.registry.get_all_skills()]
            }

        skill = self.registry.get_skill(skill_name)

        if not skill:
            return {
                "success": False,
                "error": f"Skill '{skill_name}' not found",
                "available_skills": [s.name for s in self.registry.get_all_skills()]
            }

        # Return the skill guide for the LLM to use
        return {
            "success": True,
            "skill_name": skill.name,
            "skill_description": skill.description,
            "guide": skill.content,
            "suggestion": f"Use the guide above to accomplish the task: {task}. Generate Python code following the patterns in the guide."
        }


class ListSkillsTool:
    """Tool for listing available skills."""
    name = "list_skills"
    description = "List all available skills and their descriptions."

    def __init__(self):
        self.registry = SkillRegistry()

    def prompt_block(self) -> str:
        """Generate the tool description for LLM prompt."""
        schema = {
            "type": "object",
            "properties": {},
            "additionalProperties": False,
        }
        return f"- {self.name}: {self.description}\n  Input schema: {json.dumps(schema, ensure_ascii=False)}"

    def run(self, tool_input: dict) -> dict:
        """List all available skills."""
        skills = self.registry.get_all_skills()

        return {
            "success": True,
            "skills": [
                {
                    "name": s.name,
                    "description": s.description
                }
                for s in skills
            ]
        }


class MatchSkillsTool:
    """Tool for matching skills to a query."""
    name = "match_skills"
    description = "Find the most relevant skills for a given task description."

    def __init__(self):
        self.registry = SkillRegistry()

    def prompt_block(self) -> str:
        """Generate the tool description for LLM prompt."""
        schema = {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The task description to match against available skills"
                }
            },
            "required": ["query"],
            "additionalProperties": False,
        }
        return f"- {self.name}: {self.description}\n  Input schema: {json.dumps(schema, ensure_ascii=False)}"

    def run(self, tool_input: dict) -> dict:
        """Match skills to a query."""
        query = tool_input.get("query", "")

        if not query:
            return {
                "success": False,
                "error": "query is required"
            }

        matched = self.registry.match_skills(query)

        return {
            "success": True,
            "query": query,
            "matched_skills": [
                {
                    "name": s.name,
                    "description": s.description
                }
                for s in matched
            ]
        }
