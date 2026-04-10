"""
Skill Parser - Parse and manage .claude/skills/ directory
"""

import os
import re
from typing import List, Dict, Optional
from dataclasses import dataclass


@dataclass
class Skill:
    """Represents a single skill with its metadata and guide."""
    name: str
    description: str
    license: str
    content: str
    skill_path: str

    def to_prompt_block(self) -> str:
        """Generate a prompt block describing this skill."""
        return f"- {self.name}: {self.description}"

    def get_full_guide(self) -> str:
        """Get the full skill guide including metadata and content."""
        return f"""## Skill: {self.name}

Description: {self.description}

{self.content}
"""


class SkillParser:
    """Parser for SKILL.md files in .claude/skills/ directory."""

    @staticmethod
    def parse_frontmatter(content: str) -> Dict[str, str]:
        """Parse YAML frontmatter from markdown content."""
        pattern = r'^---\s*\n(.*?)\n---\s*\n'
        match = re.match(pattern, content, re.DOTALL)

        if not match:
            return {}

        frontmatter_text = match.group(1)
        metadata = {}

        for line in frontmatter_text.strip().split('\n'):
            if ':' in line:
                key, value = line.split(':', 1)
                metadata[key.strip()] = value.strip().strip('"').strip("'")

        return metadata

    @staticmethod
    def parse_skill_file(file_path: str) -> Optional[Skill]:
        """Parse a single SKILL.md file."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            metadata = SkillParser.parse_frontmatter(content)

            # Extract markdown content (after frontmatter)
            pattern = r'^---\s*\n.*?\n---\s*\n'
            markdown_content = re.sub(pattern, '', content, count=1, flags=re.DOTALL)

            return Skill(
                name=metadata.get('name', 'unknown'),
                description=metadata.get('description', ''),
                license=metadata.get('license', ''),
                content=markdown_content.strip(),
                skill_path=os.path.dirname(file_path)
            )
        except Exception as e:
            print(f"Error parsing skill file {file_path}: {e}")
            return None

    @staticmethod
    def load_all_skills(skills_dir: str = None) -> List[Skill]:
        """Load all skills from .claude/skills/ directory."""
        if skills_dir is None:
            # Default to .claude/skills/ in project root
            project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            skills_dir = os.path.join(project_root, '.claude', 'skills')

        if not os.path.exists(skills_dir):
            print(f"Skills directory not found: {skills_dir}")
            return []

        skills = []
        for item in os.listdir(skills_dir):
            skill_path = os.path.join(skills_dir, item)
            if os.path.isdir(skill_path):
                skill_file = os.path.join(skill_path, 'SKILL.md')
                if os.path.exists(skill_file):
                    skill = SkillParser.parse_skill_file(skill_file)
                    if skill:
                        skills.append(skill)

        return skills


class SkillRegistry:
    """Registry for managing and matching skills."""

    def __init__(self, skills_dir: str = None):
        self.skills: List[Skill] = SkillParser.load_all_skills(skills_dir)
        self.skills_by_name: Dict[str, Skill] = {s.name: s for s in self.skills}

    def get_all_skills(self) -> List[Skill]:
        """Get all loaded skills."""
        return self.skills

    def get_skill(self, name: str) -> Optional[Skill]:
        """Get a specific skill by name."""
        return self.skills_by_name.get(name)

    def match_skills(self, query: str) -> List[Skill]:
        """
        Match skills based on user query.
        Returns skills sorted by relevance (exact matches first).
        """
        query_lower = query.lower()
        matched = []

        for skill in self.skills:
            score = 0

            # Check skill name
            if skill.name.lower() in query_lower:
                score += 10

            # Check file extensions and keywords in query (English and Chinese)
            if skill.name == 'xlsx' and any(ext in query_lower for ext in ['.xlsx', '.csv', 'excel', 'spreadsheet', 'excel表格', '表格', '电子表格', 'xlsx']):
                score += 20
            if skill.name == 'pdf' and any(ext in query_lower for ext in ['.pdf', 'pdf file', 'pdf']):
                score += 20
            if skill.name == 'docx' and any(ext in query_lower for ext in ['.docx', 'word', 'document', 'word文档', '文档']):
                score += 20
            if skill.name == 'pptx' and any(ext in query_lower for ext in ['.pptx', 'powerpoint', 'presentation', 'ppt', '幻灯片', '演示文稿']):
                score += 20
            if skill.name == 'frontend-design' and any(kw in query_lower for kw in ['html', 'css', 'web', 'frontend', 'ui', 'design', 'page', 'component', '网页', '前端', '设计', '网站', 'web设计']):
                score += 20

            # Check description keywords
            desc_words = set(skill.description.lower().split())
            query_words = set(query_lower.split())
            common_words = desc_words & query_words
            score += len(common_words)

            if score > 0:
                matched.append((score, skill))

        # Sort by score descending
        matched.sort(key=lambda x: x[0], reverse=True)
        return [skill for _, skill in matched]

    def get_relevant_skills_prompt(self, query: str, max_skills: int = 2) -> str:
        """
        Get prompt section with relevant skills for the query.
        Includes full guides for matched skills.
        """
        matched_skills = self.match_skills(query)[:max_skills]

        if not matched_skills:
            return ""

        prompts = ["\n## Relevant Skills\n"]

        for skill in matched_skills:
            prompts.append(skill.get_full_guide())
            prompts.append("\n" + "=" * 60 + "\n")

        return "\n".join(prompts)

    def get_all_skills_metadata(self) -> List[str]:
        """Get metadata for all skills (for tool listing)."""
        return [skill.to_prompt_block() for skill in self.skills]
