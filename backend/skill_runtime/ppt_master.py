from __future__ import annotations

import json
import re
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from tempfile import TemporaryDirectory

from PIL import Image
from pydantic import ValidationError
from pptx.dml.color import RGBColor
from pptx.util import Emu, Pt

from ..artifacts import ARTIFACT_ID
from .diagram_presets import build_preset
from .media import MediaAsset, MediaService
from .pptx_export import export_presentation
from .slide_design import CONTENT_LAYOUTS, image_panel, render_slide
from .teaching_diagram import TeachingDiagram, fit_labels

MAX_SLIDES = 24
LAYOUTS = {"cover", "section", "content", "quote", "end", *CONTENT_LAYOUTS}

THEMES = {
    "field": {
        "bg": "#FBF6E9", "surface": "#FFFDF5", "primary": "#2F5D3A",
        "secondary": "#7A4B63", "accent": "#A47119", "sun": "#D9A441",
        "ink": "#25352A", "muted": "#56665A", "soft": "#E7EFDC", "tint": "#F1E8D4",
    },
    "science": {
        "bg": "#FBF7EF",
        "surface": "#FFFFFF",
        "primary": "#165B5A",
        "secondary": "#2E7D9A",
        "accent": "#F07E54",
        "sun": "#F2C14E",
        "ink": "#20343A",
        "muted": "#5C6E72",
        "soft": "#E3F1EB",
        "tint": "#FBE1D3",
    },
    "warm": {
        "bg": "#FFF9F2",
        "surface": "#FFFFFF",
        "primary": "#8A4B32",
        "secondary": "#C56A43",
        "accent": "#E0A13B",
        "sun": "#F2C14E",
        "ink": "#352A26",
        "muted": "#75645C",
        "soft": "#F8E7D8",
        "tint": "#F3D7C3",
    },
    "ocean": {
        "bg": "#F1F5FC",
        "surface": "#FFFFFF",
        "primary": "#192D57",
        "secondary": "#285799",
        "accent": "#15B8B0",
        "sun": "#A8E2DE",
        "ink": "#172A45",
        "muted": "#53647E",
        "soft": "#DCE8FA",
        "tint": "#D8F4EF",
    },
}


class DeckSpecError(ValueError):
    """The model supplied a deck that cannot be rendered safely."""


class SkillUnavailable(RuntimeError):
    """A required courseware resource is unavailable."""


@dataclass
class SlideItem:
    label: str
    detail: str


@dataclass
class SlideSpec:
    layout: str
    title: str
    subtitle: str = ""
    bullets: list[str] = field(default_factory=list)
    note: str = ""
    image_asset_id: str = ""
    image_caption: str = ""
    image_fit: str = ""
    items: list[SlideItem] = field(default_factory=list)
    takeaway: str = ""
    diagram: TeachingDiagram | None = None
    value: str = ""


@dataclass
class DeckSpec:
    title: str
    subtitle: str = ""
    audience: str = ""
    theme: str = "science"
    slides: list[SlideSpec] = field(default_factory=list)

    def editable_source(self) -> dict:
        slides = []
        for slide in self.slides:
            source = {
                "layout": slide.layout,
                "title": slide.title,
                "subtitle": slide.subtitle,
                "bullets": slide.bullets,
                "note": slide.note,
                "items": [asdict(item) for item in slide.items],
                "takeaway": slide.takeaway,
                "value": slide.value,
            }
            if slide.diagram:
                source["diagram"] = slide.diagram.model_dump(mode="json")
            if slide.image_asset_id:
                source["image"] = {
                    "assetId": slide.image_asset_id,
                    "caption": slide.image_caption,
                    "fit": slide.image_fit,
                }
            slides.append(source)
        return {"title": self.title, "subtitle": self.subtitle, "audience": self.audience,
                "theme": self.theme, "slides": slides}


@dataclass
class ArtifactResult:
    artifact_id: str
    filename: str
    path: Path
    size: int
    slide_count: int


def _clean(value, limit: int) -> str:
    if value is None:
        return ""
    xml_text = re.sub(r"[\x00-\x08\x0B\x0C\x0E-\x1F\uD800-\uDFFF\uFFFE\uFFFF]", "", str(value))
    text = re.sub(r"\s+", " ", xml_text).strip()
    return text[:limit]


def parse_deck_spec(payload: dict, expected_pages: int | None = None,
                    expected_title: str | None = None) -> DeckSpec:
    if not isinstance(payload, dict):
        raise DeckSpecError("PPT 参数必须是对象")
    title = _clean(payload.get("title"), 120)
    if not title:
        raise DeckSpecError("缺少 PPT 标题")
    theme = _clean(payload.get("theme") or "science", 20)
    if theme not in THEMES:
        theme = "science"
    raw_slides = payload.get("slides")
    if not isinstance(raw_slides, list) or not raw_slides:
        raise DeckSpecError("至少需要一页幻灯片")
    if len(raw_slides) > MAX_SLIDES:
        raise DeckSpecError(f"一次最多生成 {MAX_SLIDES} 页")
    slides: list[SlideSpec] = []
    for index, raw in enumerate(raw_slides, 1):
        if not isinstance(raw, dict):
            raise DeckSpecError(f"第 {index} 页格式不正确")
        layout = _clean(raw.get("layout") or "content", 20).lower()
        if layout not in LAYOUTS:
            layout = "content"
        slide_title = _clean(raw.get("title"), 120)
        if not slide_title:
            raise DeckSpecError(f"第 {index} 页缺少标题")
        bullets = raw.get("bullets") or []
        if not isinstance(bullets, list):
            raise DeckSpecError(f"第 {index} 页的 bullets 必须是数组")
        if len(bullets) > 6:
            raise DeckSpecError(f"第 {index} 页最多 6 条要点")
        clean_bullets = []
        for bullet in bullets:
            text = _clean(bullet, 100)
            if text:
                clean_bullets.append(text)
        image = raw.get("image")
        image_asset_id = ""
        image_caption = ""
        image_fit = ""
        if image:
            if not isinstance(image, dict):
                raise DeckSpecError(f"第 {index} 页的 image 必须是对象")
            image_asset_id = _clean(image.get("assetId"), 64)
            image_caption = _clean(image.get("caption"), 100)
            image_fit = _clean(image.get("fit") or "", 10)
            if image_fit not in {"", "cover", "contain"}:
                image_fit = "cover"
            if layout not in {"cover", "figure", "content"}:
                raise DeckSpecError(f"第 {index} 页：图片可用于 cover、figure 或 content 版式")
            if not re.fullmatch(r"[a-f0-9]{32}", image_asset_id):
                raise DeckSpecError(f"第 {index} 页：图片编号不正确，请先调用找图/绘图工具")
        raw_items = raw.get("items", [])
        if not isinstance(raw_items, list) or len(raw_items) > 4:
            raise DeckSpecError(f"第 {index} 页的 items 必须是包含最多 4 项的数组")
        items = []
        for item in raw_items:
            if not isinstance(item, dict) or not _clean(item.get("label"), 28):
                raise DeckSpecError(f"第 {index} 页的每个信息块需要 label")
            items.append(SlideItem(_clean(item["label"], 28), _clean(item.get("detail"), 85)))
        if layout in {"compare", "process", "inquiry", "concepts", "record"}:
            minimum = 2
            maximum = {"compare": 2, "process": 4, "inquiry": 3, "concepts": 3, "record": 4}[layout]
            if not minimum <= len(items) <= maximum:
                raise DeckSpecError(f"第 {index} 页的 {layout} 版式需要 {minimum}–{maximum} 个 items")
        if layout == "figure" and not image_asset_id:
            raise DeckSpecError(f"第 {index} 页的 figure 版式需要真实配图编号，可改用 content")
        note = "\n".join(filter(None, (_clean(line, 1200) for line in str(raw.get("note") or "").splitlines())))[:1200]
        diagram = None
        if layout == "diagram":
            preset = raw.get("visualPreset")
            try:
                if preset and not raw.get("diagram"):
                    if not isinstance(preset, str):
                        raise KeyError(preset)
                    diagram, source = build_preset(preset)
                    if source not in note:
                        credit = "\n图解参考：" + source
                        note = (note[:1200 - len(credit)] + credit).strip()
                else:
                    diagram = TeachingDiagram.model_validate(fit_labels(raw.get("diagram")))
            except KeyError as exc:
                raise DeckSpecError(f"第 {index} 页原理图预设名称无效") from exc
            except ValidationError as exc:
                issue = exc.errors(include_input=False, include_context=False, include_url=False)[0]
                field_name = ".".join(map(str, issue["loc"]))
                raise DeckSpecError(f"第 {index} 页原理图参数有误：{field_name} {issue['msg']}") from exc
        value = _clean(raw.get("value"), 24)
        if layout == "focus" and not value:
            raise DeckSpecError(f"第 {index} 页的 focus 版式需要 value")
        slides.append(SlideSpec(
            layout=layout,
            title=slide_title,
            subtitle=_clean(raw.get("subtitle"), 180),
            bullets=clean_bullets,
            note=note,
            image_asset_id=image_asset_id,
            image_caption=image_caption,
            image_fit=image_fit,
            items=items,
            takeaway=_clean(raw.get("takeaway"), 70),
            diagram=diagram,
            value=value,
        ))
    if slides[0].layout != "cover" and (expected_pages is None or len(slides) < expected_pages):
        slides.insert(0, SlideSpec(layout="cover", title=title, subtitle=_clean(payload.get("subtitle"), 180)))
    if slides[-1].layout != "end" and (expected_pages is None or len(slides) < expected_pages):
        slides.append(SlideSpec(layout="end", title="用证据解释新现象"))
    if len(slides) > MAX_SLIDES:
        raise DeckSpecError(f"自动补齐封面/结束页后超过 {MAX_SLIDES} 页，请减少页数")
    if expected_pages is not None and len(slides) != expected_pages:
        raise DeckSpecError(
            f"用户要求 {expected_pages} 页，当前大纲是 {len(slides)} 页（含封面和结束页），请调整页数"
        )
    if expected_title and expected_title.strip() not in title:
        raise DeckSpecError(f"标题必须使用用户指定的《{expected_title.strip()}》")
    return DeckSpec(title=title, subtitle=_clean(payload.get("subtitle"), 180),
                    audience=_clean(payload.get("audience"), 120), theme=theme, slides=slides)


def build_svg(slide: SlideSpec, page: int, total: int, deck: DeckSpec) -> str:
    try:
        return render_slide(slide, page, total, deck, THEMES[deck.theme])
    except ValueError as exc:
        raise DeckSpecError(f"第 {page} 页：{exc}。可将详细说明移到教师备注") from exc


class PptMasterService:
    def __init__(self, artifact_dir: Path, media: MediaService | None = None):
        self.artifact_dir = artifact_dir
        self.media = media

    @staticmethod
    def _attach_images(presentation, deck: DeckSpec, assets: dict[int, MediaAsset]) -> None:
        for index, asset in assets.items():
            if index < 1 or index > len(presentation.slides):
                continue
            slide = presentation.slides[index - 1]
            slide_spec = deck.slides[index - 1]
            left, top, panel_width, panel_height = image_panel(slide_spec.layout)
            panel_ratio = panel_width / panel_height
            with Image.open(asset.path) as image:
                width, height = image.size
            if not width or not height:
                continue
            image_ratio = width / height
            fit = "contain" if asset.source == "diagram" else (slide_spec.image_fit or "cover")
            if fit == "contain":
                scale = min(panel_width / width, panel_height / height)
                picture_width = round(width * scale)
                picture_height = round(height * scale)
                picture = slide.shapes.add_picture(
                    str(asset.path),
                    Emu((left + (panel_width - picture_width) // 2) * 9525),
                    Emu((top + (panel_height - picture_height) // 2) * 9525),
                    width=Emu(picture_width * 9525), height=Emu(picture_height * 9525),
                )
            else:
                picture = slide.shapes.add_picture(
                    str(asset.path),
                    Emu(left * 9525), Emu(top * 9525),
                    width=Emu(panel_width * 9525), height=Emu(panel_height * 9525),
                )
                if image_ratio > panel_ratio:
                    crop = (1 - panel_ratio / image_ratio) / 2
                    picture.crop_left = crop
                    picture.crop_right = crop
                else:
                    crop = (1 - image_ratio / panel_ratio) / 2
                    picture.crop_top = crop
                    picture.crop_bottom = crop
            caption = slide_spec.image_caption or asset.caption or asset.attribution
            if asset.source == "web":
                notes = slide.notes_slide.notes_text_frame
                notes.text = "\n".join(filter(None, (notes.text, f"配图来源：{asset.attribution}")))
                caption = f"{caption[:36]} · 来源见备注"
            caption = caption[:60]
            box = slide.shapes.add_textbox(
                Emu(left * 9525), Emu((top + panel_height + 10) * 9525),
                Emu(panel_width * 9525), Emu(32 * 9525),
            )
            frame = box.text_frame
            frame.word_wrap = True
            frame.margin_left = 0
            frame.margin_right = 0
            frame.margin_top = 0
            frame.margin_bottom = 0
            run = frame.paragraphs[0].add_run()
            run.text = caption
            run.font.size = Pt(11)
            run.font.name = "Microsoft YaHei"
            theme = THEMES[deck.theme]
            run.font.color.rgb = RGBColor.from_string(theme["muted"][1:])

    def create(self, payload: dict, user_id: int, artifact_id: str | None = None,
               expected_pages: int | None = None,
               expected_title: str | None = None) -> ArtifactResult:
        deck = parse_deck_spec(payload, expected_pages=expected_pages,
                               expected_title=expected_title)
        image_assets: dict[int, MediaAsset] = {}
        for index, slide in enumerate(deck.slides, 1):
            if slide.image_asset_id:
                if not self.media:
                    raise SkillUnavailable("图片服务尚未配置")
                image_assets[index] = self.media.resolve(user_id, slide.image_asset_id)
        artifact_id = artifact_id or uuid.uuid4().hex
        if not ARTIFACT_ID.fullmatch(artifact_id):
            raise DeckSpecError("课件编号不正确")
        total = len(deck.slides)
        presentation = export_presentation(
            (build_svg(slide, index, total, deck), slide.note)
            for index, slide in enumerate(deck.slides, 1)
        )
        self._attach_images(presentation, deck, image_assets)
        target_dir = self.artifact_dir / str(user_id)
        target_dir.mkdir(parents=True, exist_ok=True)
        safe = re.sub(r"[\\/:*?\"<>|]+", "-", deck.title).strip(" .-")[:60] or "presentation"
        filename = f"{safe}.pptx"
        target = target_dir / f"{artifact_id}.pptx"
        source = target.with_suffix(".source.json")
        metadata = target.with_suffix(".json")
        lock = target_dir / f".{artifact_id}.lock"
        with TemporaryDirectory(dir=target_dir) as stage:
            draft = Path(stage) / target.name
            presentation.save(str(draft))
            size = draft.stat().st_size
            (draft.parent / source.name).write_text(
                json.dumps(deck.editable_source(), ensure_ascii=False), encoding="utf-8",
            )
            (draft.parent / metadata.name).write_text(json.dumps({
                "id": artifact_id, "filename": filename, "title": deck.title, "slides": total, "size": size,
            }, ensure_ascii=False, indent=2), encoding="utf-8")
            try:
                lock.mkdir()
            except FileExistsError as exc:
                raise DeckSpecError("课件编号已存在") from exc
            published = []
            try:
                files = (target, source, metadata)
                if any(path.exists() for path in files):
                    raise DeckSpecError("课件编号已存在")
                # Readers require the metadata file, so publish it only after both payloads exist.
                for path in files:
                    (draft.parent / path.name).replace(path)
                    published.append(path)
            except BaseException:
                for path in published:
                    path.unlink(missing_ok=True)
                raise
            finally:
                lock.rmdir()
        return ArtifactResult(
            artifact_id=artifact_id,
            filename=filename,
            path=target,
            size=size,
            slide_count=total,
        )
