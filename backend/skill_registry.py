from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from pathlib import Path

import yaml

log = logging.getLogger(__name__)

FRONTMATTER = re.compile(r"^---\s*\r?\n(.*?)\r?\n---\s*(?:\r?\n|$)", re.S)


@dataclass(frozen=True)
class SkillInfo:
    name: str
    description: str
    path: Path
    body: str

    @property
    def entry(self) -> Path:
        return self.path / "SKILL.md"


class SkillRegistry:
    """Read the same folder-shaped SKILL.md packages as DeepSeek Harness."""

    def __init__(self, root: Path):
        self.root = root
        self._skills: dict[str, SkillInfo] | None = None

    def _load(self) -> dict[str, SkillInfo]:
        skills: dict[str, SkillInfo] = {}
        if not self.root.is_dir():
            log.warning("Skill directory does not exist: %s", self.root)
            return skills
        for entry in sorted(self.root.iterdir(), key=lambda item: item.name.lower()):
            if not entry.is_dir() or entry.name.startswith("."):
                continue
            skill_file = entry / "SKILL.md"
            if not skill_file.is_file():
                continue
            try:
                text = skill_file.read_text(encoding="utf-8-sig")
            except OSError as exc:
                log.warning("Cannot read skill %s: %s", skill_file, exc)
                continue
            match = FRONTMATTER.match(text)
            if not match:
                log.warning("Skill has no frontmatter: %s", skill_file)
                continue
            try:
                metadata = yaml.safe_load(match.group(1)) or {}
            except yaml.YAMLError as exc:
                log.warning("Invalid skill frontmatter %s: %s", skill_file, exc)
                continue
            name = str(metadata.get("name") or entry.name).strip()
            description = str(metadata.get("description") or "").strip()
            if not name or not description:
                log.warning("Skill frontmatter needs name and description: %s", skill_file)
                continue
            skills[name] = SkillInfo(name=name, description=description, path=entry, body=text)
        return skills

    def all(self) -> list[SkillInfo]:
        if self._skills is None:
            self._skills = self._load()
        return sorted(self._skills.values(), key=lambda skill: skill.name.lower())

    def get(self, name: str) -> SkillInfo | None:
        if self._skills is None:
            self._skills = self._load()
        if name in self._skills:
            return self._skills[name]
        lowered = name.strip().lower()
        return next((skill for skill in self._skills.values() if skill.name.lower() == lowered), None)

    def catalog_text(self, limit: int = 160) -> str:
        rows = []
        for skill in self.all():
            description = " ".join(skill.description.split())
            if len(description) > limit:
                description = description[: limit - 1].rstrip() + "…"
            rows.append(f"- {skill.name}: {description}")
        return "\n".join(rows) if rows else "（本机未发现技能）"

    def read(self, name: str, max_chars: int = 20000) -> str:
        skill = self.get(name)
        if not skill:
            raise KeyError(name)
        if len(skill.body) > max_chars:
            return skill.body[:max_chars] + "\n\n[内容已截断]"
        return skill.body
