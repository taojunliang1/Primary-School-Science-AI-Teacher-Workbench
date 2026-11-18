from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any

from .skill_registry import SkillRegistry
from .skill_runtime.media import MediaService, MediaUnavailable
from .skill_runtime.ppt_master import DeckSpecError, PptMasterService, SkillUnavailable

log = logging.getLogger(__name__)

TOOLS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "list_skills",
            "description": "列出科学教师工作台内置的技能。",
            "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_skill",
            "description": "读取指定技能的 SKILL.md 说明，了解它的能力、输入和限制。只读取，不执行。",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "技能名，例如 ppt-master"},
                },
                "required": ["name"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_images",
            "description": (
                "联网搜索一张可用于课件的真实图片并下载到本机。返回 assetId、来源和授权提示。"
                "适合真实照片、实验器材、动植物、地理现象。query 使用与课件相同的语言："
                "中文课用中文关键词（如“水循环 示意图”），英文课才用英文关键词。"
                "把返回的 assetId 放进 create_ppt_with_ppt_master 对应页面的 image.assetId。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "使用与课件一致的语言，例如 水循环 示意图"},
                    "caption": {"type": "string", "description": "课件中显示的图片说明"},
                },
                "required": ["query"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "draw_image",
            "description": (
                "为课件绘制一张科学示意图。优先使用配置好的图片生成接口；没有接口时由本地绘图器生成"
                "带标题和标签的示意图。返回 assetId，放进 create_ppt 的 image.assetId。"
                "适合水循环、电路、植物结构、实验装置等需要清晰标签的图。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "prompt": {"type": "string", "description": "图画主题，例如 水循环示意图"},
                    "labels": {
                        "type": "array",
                        "maxItems": 4,
                        "items": {"type": "string"},
                        "description": "图中要出现的 2—4 个标签",
                    },
                    "caption": {"type": "string", "description": "课件中显示的图片说明"},
                },
                "required": ["prompt"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_ppt_with_ppt_master",
            "description": (
                "把课程设计导出为可编辑的 16:9 PPTX。每页围绕一个课堂任务，"
                "按内容关系选择不同版式。用 takeaway 写投影结论或引导问题，note 写教师操作和预期观察。"
                "工具返回 artifact 后才说明文件已生成。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "整套 PPT 标题"},
                    "subtitle": {"type": "string", "description": "副标题或一句话说明"},
                    "audience": {"type": "string", "description": "受众，例如小学四年级学生"},
                    "theme": {"type": "string", "enum": ["science", "warm", "ocean"], "description": "青绿科学、暖色自然或深蓝探究"},
                    "slides": {
                        "type": "array",
                        "minItems": 1,
                        "maxItems": 24,
                        "items": {
                            "type": "object",
                            "properties": {
                                "layout": {
                                    "type": "string",
                                    "enum": ["cover", "section", "content", "figure", "compare", "process", "inquiry", "concepts", "quote", "end", "diagram", "record"],
                                    "description": "figure 观察图片，compare 对比，process 顺序，inquiry 实验，diagram 图解，record 观察记录表",
                                },
                                "title": {"type": "string"},
                                "subtitle": {"type": "string"},
                                "bullets": {
                                    "type": "array",
                                    "maxItems": 6,
                                    "description": "content、figure、quote 的投影文字，每条尽量控制在 30 个字",
                                    "items": {"type": "string", "maxLength": 100},
                                },
                                "items": {
                                    "type": "array", "minItems": 2, "maxItems": 4,
                                    "description": "compare 2 项，process 或 record 2–4 项，inquiry 或 concepts 2–3 项。record 的 label 是列名，detail 是填写提示。",
                                    "items": {
                                        "type": "object", "required": ["label", "detail"], "additionalProperties": False,
                                        "properties": {
                                            "label": {"type": "string", "maxLength": 28},
                                            "detail": {"type": "string", "maxLength": 85},
                                        },
                                    },
                                },
                                "takeaway": {"type": "string", "maxLength": 70, "description": "本页的核心结论、证据提示或学生要回答的问题"},
                                "note": {"type": "string", "description": "教师演讲者备注"},
                                "visualPreset": {
                                    "type": "string", "enum": ["silkworm-body", "silkworm-cycle", "air-cup", "water-cycle"],
                                    "description": "用于 diagram，选择与页面主题一致的科学图解。",
                                },
                                "image": {
                                    "type": "object",
                                    "description": "cover、figure 或 content 可配图，figure 必须先取得图片编号",
                                    "properties": {
                                        "assetId": {"type": "string", "description": "search_images 或 draw_image 返回的 assetId"},
                                        "caption": {"type": "string", "description": "图片说明，会显示在图下方"},
                                        "fit": {
                                            "type": "string",
                                            "enum": ["cover", "contain"],
                                            "description": "照片用 cover；带标签的示意图用 contain，避免裁掉文字",
                                        },
                                    },
                                    "required": ["assetId"],
                                    "additionalProperties": False,
                                },
                            },
                            "required": ["layout", "title"],
                            "additionalProperties": False,
                        },
                    },
                },
                "required": ["title", "slides"],
                "additionalProperties": False,
            },
        },
    },
]


@dataclass
class ToolOutcome:
    payload: dict[str, Any]
    trace: dict[str, Any]


class ToolExecutor:
    def __init__(self, registry: SkillRegistry, ppt_master: PptMasterService, media: MediaService,
                 user_id: int, expected_pages: int | None = None,
                 expected_title: str | None = None):
        self.registry = registry
        self.ppt_master = ppt_master
        self.media = media
        self.user_id = user_id
        self.expected_pages = expected_pages
        self.expected_title = expected_title

    def execute(self, name: str, raw_arguments: str | None) -> ToolOutcome:
        try:
            arguments = json.loads(raw_arguments or "{}")
            if not isinstance(arguments, dict):
                raise ValueError("tool arguments must be an object")
        except (TypeError, ValueError) as exc:
            return ToolOutcome(
                {"error": f"工具参数不是有效 JSON：{exc}"},
                {"name": name, "status": "error", "summary": "工具参数格式错误"},
            )

        try:
            if name == "list_skills":
                skills = [
                    {"name": skill.name, "description": skill.description}
                    for skill in self.registry.all()
                ]
                return ToolOutcome(
                    {"skills": skills, "count": len(skills)},
                    {"name": name, "status": "ok", "summary": f"发现 {len(skills)} 个技能"},
                )
            if name == "read_skill":
                skill_name = str(arguments.get("name") or "").strip()
                content = self.registry.read(skill_name)
                skill = self.registry.get(skill_name)
                return ToolOutcome(
                    {"name": skill.name if skill else skill_name, "content": content},
                    {"name": name, "status": "ok", "summary": f"读取 {skill_name}"},
                )
            if name == "search_images":
                asset = self.media.search(
                    str(arguments.get("query") or ""), self.user_id,
                    str(arguments.get("caption") or ""),
                )
                return ToolOutcome(
                    {"asset": {
                        "assetId": asset.id, "source": asset.source,
                        "caption": asset.caption, "attribution": asset.attribution,
                        "width": asset.width, "height": asset.height,
                    }},
                    {"name": name, "status": "ok", "summary": "找到 1 张图片"},
                )
            if name == "draw_image":
                labels = arguments.get("labels") or []
                if not isinstance(labels, list):
                    labels = []
                asset = self.media.draw(
                    str(arguments.get("prompt") or ""), self.user_id,
                    [str(item) for item in labels],
                    str(arguments.get("caption") or ""),
                )
                return ToolOutcome(
                    {"asset": {
                        "assetId": asset.id, "source": asset.source,
                        "caption": asset.caption, "attribution": asset.attribution,
                        "width": asset.width, "height": asset.height,
                    }},
                    {"name": name, "status": "ok", "summary": "已绘制示意图"},
                )
            if name == "create_ppt_with_ppt_master":
                result = self.ppt_master.create(
                    arguments, user_id=self.user_id, expected_pages=self.expected_pages,
                    expected_title=self.expected_title,
                )
                artifact = {
                    "id": result.artifact_id,
                    "filename": result.filename,
                    "size": result.size,
                    "slideCount": result.slide_count,
                    "downloadUrl": f"/api/v1/chat/artifacts/{result.artifact_id}",
                }
                return ToolOutcome(
                    {"artifact": artifact, "message": "PPTX 已生成，可直接下载。"},
                    {
                        "name": name,
                        "status": "ok",
                        "summary": f"已生成 {result.slide_count} 页 PPTX",
                        "artifact": artifact,
                    },
                )
            return ToolOutcome(
                {"error": f"未知工具：{name}"},
                {"name": name, "status": "error", "summary": "未知工具"},
            )
        except KeyError:
            return ToolOutcome(
                {"error": "找不到这个技能，请先调用 list_skills"},
                {"name": name, "status": "error", "summary": "技能不存在"},
            )
        except DeckSpecError as exc:
            return ToolOutcome(
                {"error": str(exc)},
                {"name": name, "status": "error", "summary": str(exc)},
            )
        except MediaUnavailable as exc:
            return ToolOutcome(
                {"error": str(exc)},
                {"name": name, "status": "error", "summary": "图片获取失败"},
            )
        except SkillUnavailable as exc:
            log.warning("ppt-master unavailable: %s", exc)
            return ToolOutcome(
                {"error": str(exc)},
                {"name": name, "status": "error", "summary": "ppt-master 执行失败"},
            )
        except Exception as exc:  # Keep a failed tool from killing the chat turn.
            log.exception("Tool %s failed", name)
            return ToolOutcome(
                {"error": f"工具执行失败：{type(exc).__name__}"},
                {"name": name, "status": "error", "summary": "工具执行失败"},
            )
