from __future__ import annotations

import base64
import html
import io
import json
import logging
import math
import os
import re
import time
import uuid
from dataclasses import dataclass
from pathlib import Path

import httpx
from PIL import Image, ImageDraw, ImageFont

log = logging.getLogger(__name__)

ASSET_ID = re.compile(r"^[a-f0-9]{32}$")
BING_IMAGES = "https://www.bing.com/images/search"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) ScienceWorkbench/0.1"


class MediaUnavailable(RuntimeError):
    """No image could be sourced or drawn."""


@dataclass
class MediaAsset:
    id: str
    path: Path
    source: str
    attribution: str
    caption: str
    width: int
    height: int


def _clean(value, limit: int) -> str:
    if value is None:
        return ""
    text = re.sub(r"<[^>]+>", " ", str(value))
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text).strip()[:limit]


def _font(size: int) -> ImageFont.FreeTypeFont:
    for path in (r"C:\Windows\Fonts\msyh.ttc", r"C:\Windows\Fonts\msyhbd.ttc",
                 r"C:\Windows\Fonts\arial.ttf"):
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    return ImageFont.load_default()


def _wrap(text: str, width: int) -> list[str]:
    text = re.sub(r"\s+", " ", text).strip()
    lines, current = [], ""
    for char in text:
        if len(current) >= width:
            lines.append(current.strip())
            current = char
        else:
            current += char
    if current:
        lines.append(current.strip())
    return lines


class MediaService:
    """Find web images or draw a schematic, then persist a user-scoped asset."""

    def __init__(self, root: Path):
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def _dir(self, user_id: int) -> Path:
        path = self.root / str(int(user_id))
        path.mkdir(parents=True, exist_ok=True)
        return path

    def resolve(self, user_id: int, asset_id: str) -> MediaAsset:
        if not ASSET_ID.fullmatch(asset_id):
            raise MediaUnavailable("图片编号不正确")
        directory = self._dir(user_id)
        meta_file = directory / f"{asset_id}.json"
        if not meta_file.is_file():
            raise MediaUnavailable("找不到这张图片，请重新搜索或绘制")
        try:
            data = json.loads(meta_file.read_text(encoding="utf-8"))
            path = directory / data["filename"]
            if not path.is_file():
                raise MediaUnavailable("图片文件已被清理")
            return MediaAsset(
                id=asset_id, path=path, source=data.get("source", "web"),
                attribution=data.get("attribution", ""), caption=data.get("caption", ""),
                width=int(data.get("width", 0)), height=int(data.get("height", 0)),
            )
        except (OSError, ValueError, KeyError) as exc:
            raise MediaUnavailable("图片元数据损坏") from exc

    def _save(self, user_id: int, image: Image.Image, source: str,
              attribution: str, caption: str, suffix: str = ".jpg") -> MediaAsset:
        asset_id = uuid.uuid4().hex
        directory = self._dir(user_id)
        filename = f"{asset_id}{suffix}"
        path = directory / filename
        if suffix == ".jpg":
            image.convert("RGB").save(path, "JPEG", quality=91, optimize=True)
        else:
            image.save(path, "PNG", optimize=True)
        data = {
            "id": asset_id, "filename": filename, "source": source,
            "attribution": attribution, "caption": caption,
            "width": image.width, "height": image.height,
        }
        (directory / f"{asset_id}.json").write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        return MediaAsset(asset_id, path, source, attribution, caption, image.width, image.height)

    def search(self, query: str, user_id: int, caption: str = "") -> MediaAsset:
        query = _clean(query, 100)
        if not query:
            raise MediaUnavailable("请提供图片搜索关键词")
        candidates: list[tuple[int, str, str, str]] = []
        last_error: Exception | None = None
        for attempt in range(2):
            try:
                params = {
                    "q": query,
                    "form": "HDRSC2",
                    "qft": "+filterui:license-L2_L3_L4",
                    "first": 1,
                }
                if query.isascii():
                    params["ensearch"] = "1"
                with httpx.Client(timeout=httpx.Timeout(20, connect=8), trust_env=False,
                                  follow_redirects=True,
                                  headers={"User-Agent": USER_AGENT}) as client:
                    response = client.get(BING_IMAGES, params=params)
                response.raise_for_status()
                candidates = self._bing_candidates(response.text, query)
                if candidates:
                    break
            except (httpx.HTTPError, ValueError, json.JSONDecodeError) as exc:
                last_error = exc
                time.sleep(0.8)
        if not candidates:
            raise MediaUnavailable(f"联网找图暂时失败：{type(last_error).__name__ if last_error else '没有匹配结果'}")

        for _, url, title, source_host in candidates[:6]:
            try:
                with httpx.Client(timeout=httpx.Timeout(25, connect=8), trust_env=False,
                                  headers={"User-Agent": USER_AGENT}) as client:
                    with client.stream("GET", url) as downloaded:
                        downloaded.raise_for_status()
                        if not downloaded.headers.get("content-type", "").startswith("image/"):
                            continue
                        image_bytes = bytearray()
                        for part in downloaded.iter_bytes():
                            image_bytes.extend(part)
                            if len(image_bytes) > 8 * 1024 * 1024:
                                raise ValueError("search image is too large")
                image = Image.open(io.BytesIO(image_bytes))
                if image.width * image.height > 16_000_000:
                    continue
                image.load()
                if image.width < 320 or image.height < 240:
                    continue
                image.thumbnail((1800, 1800), Image.Resampling.LANCZOS)
                label = _clean(title, 70)
                attribution = (
                    f"图片：{label + '｜' if label else ''}{source_host or 'Bing 图片搜索'}"
                    f"（免费共享筛选）；使用前请核实来源与授权。"
                )
                return self._save(user_id, image, "web", attribution,
                                  _clean(caption or query, 90))
            except (httpx.HTTPError, OSError, ValueError, Image.DecompressionBombError):
                continue
        raise MediaUnavailable("找到的图片无法下载或尺寸过小，请换一个关键词")

    @staticmethod
    def _bing_candidates(document: str, query: str) -> list[tuple[int, str, str, str]]:
        blocked = (
            "weibo.com", "pinterest.", "facebook.", "xiaohongshu.", "zhihu.com",
            "sohu.com", "sina.com", "sina.cn", "baidu.com", "nipic.com",
            "enagic", "uokon.com",
        )
        tokens = [token.lower() for token in re.split(r"\s+", query) if len(token) >= 2]
        scored: list[tuple[int, str, str, str]] = []
        seen: set[str] = set()
        for raw in re.findall(r'm="(\{.*?\})"', document):
            try:
                item = json.loads(html.unescape(raw))
            except (ValueError, json.JSONDecodeError):
                continue
            try:
                thumbnail = httpx.URL(str(item.get("turl") or ""))
                source = httpx.URL(str(item.get("purl") or ""))
            except httpx.InvalidURL:
                continue
            title = _clean(item.get("t"), 120)
            purl = str(source).lower()
            bing_host = thumbnail.host == "th.bing.com" or re.fullmatch(r"ts[1-4]\.mm\.bing\.net", thumbnail.host)
            image_id = thumbnail.params.get("id", "") if thumbnail.path == "/th" else thumbnail.path.removeprefix("/th/id/")
            if (thumbnail.scheme != "https" or not bing_host
                    or thumbnail.port not in {None, 443} or thumbnail.userinfo
                    or not re.fullmatch(r"OIP\.[A-Za-z0-9_-]+", image_id)):
                continue
            url = str(httpx.URL("https://th.bing.com/th", params={"id": image_id, "w": 800, "pid": "1.7"}))
            if url in seen:
                continue
            if any(domain in purl for domain in blocked):
                continue
            haystack = (title + " " + purl).lower()
            score = sum(2 for token in tokens if token in haystack)
            if any(word in haystack for word in ("示意图", "图解", "结构图", "diagram", "illustration")):
                score += 3
            if score <= 0:
                continue
            seen.add(url)
            scored.append((score, url, title, source.host))
        return sorted(scored, key=lambda item: item[0], reverse=True)

    def draw(self, prompt: str, user_id: int, labels: list[str] | None = None,
             caption: str = "") -> MediaAsset:
        prompt = _clean(prompt, 120)
        if not prompt:
            raise MediaUnavailable("请提供绘图主题")
        labels = [_clean(item, 16) for item in (labels or []) if _clean(item, 16)][:4]
        key = os.getenv("IMAGE_API_KEY", "").strip() or os.getenv("OPENAI_API_KEY", "").strip()
        if key:
            try:
                return self._draw_ai(prompt, labels, user_id, key, caption)
            except Exception as exc:  # Fall back to a deterministic local drawing.
                log.warning("AI image generation failed: %s", type(exc).__name__)
        return self._draw_local(prompt, labels, user_id, caption)

    def _draw_ai(self, prompt: str, labels: list[str], user_id: int, key: str,
                 caption: str) -> MediaAsset:
        base = os.getenv("IMAGE_API_BASE", "https://api.openai.com/v1").rstrip("/")
        model = os.getenv("IMAGE_MODEL", "gpt-image-1")
        label_hint = "，".join(labels) if labels else ""
        full_prompt = (
            f"小学科学课堂插图，主题：{prompt}。"
            f"{'画面中可标注：' + label_hint + '。' if label_hint else ''}"
            "干净、明亮、扁平化、儿童友好，避免复杂背景，不要生成错误文字。"
        )
        payload = {"model": model, "prompt": full_prompt, "size": "1024x1024", "n": 1}
        with httpx.Client(timeout=httpx.Timeout(120, connect=10), trust_env=False) as client:
            response = client.post(f"{base}/images/generations",
                                   headers={"Authorization": f"Bearer {key}"}, json=payload)
        response.raise_for_status()
        item = response.json()["data"][0]
        if item.get("b64_json"):
            raw = base64.b64decode(item["b64_json"])
        elif item.get("url"):
            with httpx.Client(timeout=httpx.Timeout(60, connect=10), trust_env=False) as client:
                raw = client.get(item["url"]).content
        else:
            raise MediaUnavailable("图片接口没有返回图片")
        image = Image.open(io.BytesIO(raw))
        image.load()
        image.thumbnail((1600, 1600), Image.Resampling.LANCZOS)
        return self._save(user_id, image, "ai", "AI 生成插图", _clean(caption or prompt, 90))

    def _draw_local(self, prompt: str, labels: list[str], user_id: int,
                    caption: str) -> MediaAsset:
        if "水循环" in prompt or ("蒸发" in labels and "降水" in labels):
            return self._save(user_id, _water_cycle_diagram(), "diagram", "水循环过程示意图",
                              _clean(caption or prompt, 90), suffix=".png")
        width, height = 1200, 900
        image = Image.new("RGB", (width, height), "#FBF7EF")
        draw = ImageDraw.Draw(image)
        draw.rounded_rectangle((0, 0, width, 180), radius=0, fill="#E3F1EB")
        draw.text((64, 52), "科学示意图", font=_font(26), fill="#165B5A")
        title_text = _clean(caption or prompt, 32)
        title_lines = _wrap(title_text, 16)[:2]
        if len(title_text) > 32 and title_lines:
            title_lines[-1] = title_lines[-1][:15] + "…"
        y = 96
        for line in title_lines:
            draw.text((64, y), line, font=_font(44), fill="#20343A")
            y += 54

        if not labels:
            labels = ["现象", "原理", "应用"]
        colors = [("#E3F1EB", "#165B5A"), ("#FBE1D3", "#C85B35"), ("#FDF1CF", "#8A6A12"),
                  ("#DCECF4", "#2E7D9A")]
        card_h, gap = 440, 28
        card_w = (width - 112 - gap * (len(labels) - 1)) // len(labels)
        start_x = (width - (card_w * len(labels) + gap * (len(labels) - 1))) // 2
        for index, label in enumerate(labels):
            left = start_x + index * (card_w + gap)
            top = 290
            fill, ink = colors[index % len(colors)]
            draw.rounded_rectangle((left, top, left + card_w, top + card_h), radius=26,
                                   fill="#FFFFFF", outline=fill, width=3)
            draw.ellipse((left + 28, top + 30, left + 92, top + 94), fill=fill)
            draw.text((left + 44, top + 44), str(index + 1), font=_font(26), fill=ink)
            draw.rounded_rectangle((left + 28, top + 128, left + card_w - 28, top + 300),
                                   radius=18, fill=fill)
            self._draw_icon(draw, left + card_w // 2, top + 214, ink, index)
            for line_index, line in enumerate(_wrap(label, 7)[:2]):
                draw.text((left + 28, top + 332 + line_index * 42), line,
                          font=_font(28), fill=ink)

        draw.line((64, height - 74, width - 64, height - 74), fill="#D8E3DD", width=2)
        draw.text((64, height - 54), "本地绘图器生成 · 可作为课堂示意图，细节请结合教材核对",
                  font=_font(20), fill="#6F7F83")
        return self._save(user_id, image, "diagram", "本地绘图器生成示意图",
                          _clean(caption or prompt, 90), suffix=".png")

    @staticmethod
    def _draw_icon(draw: ImageDraw.ImageDraw, cx: int, cy: int, color: str, index: int) -> None:
        if index == 0:
            draw.ellipse((cx - 32, cy - 32, cx + 32, cy + 32), outline=color, width=5)
            for dx, dy in ((0, -52), (0, 52), (-52, 0), (52, 0),
                           (-38, -38), (38, -38), (-38, 38), (38, 38)):
                draw.line((cx + dx * 0.72, cy + dy * 0.72, cx + dx, cy + dy), fill=color, width=4)
        elif index == 1:
            draw.ellipse((cx - 54, cy - 22, cx - 6, cy + 22), outline=color, width=4)
            draw.ellipse((cx - 18, cy - 38, cx + 30, cy + 18), outline=color, width=4)
            draw.ellipse((cx + 10, cy - 16, cx + 56, cy + 24), outline=color, width=4)
            for dx in (-28, 0, 28):
                draw.ellipse((cx + dx - 4, cy + 32, cx + dx + 4, cy + 44), fill=color)
        elif index == 2:
            draw.ellipse((cx - 54, cy - 24, cx - 6, cy + 20), outline=color, width=4)
            draw.ellipse((cx - 18, cy - 40, cx + 30, cy + 16), outline=color, width=4)
            draw.ellipse((cx + 10, cy - 18, cx + 56, cy + 22), outline=color, width=4)
            for dx in (-32, -10, 12, 34):
                draw.line((cx + dx, cy + 34, cx + dx - 8, cy + 54), fill=color, width=4)
        else:
            draw.arc((cx - 54, cy - 40, cx + 48, cy + 48), 200, 340, fill=color, width=5)
            draw.line((cx + 36, cy - 6, cx + 52, cy - 2, cx + 44, cy + 14), fill=color, width=5)
            draw.line((cx - 50, cy + 28, cx + 34, cy + 28), fill=color, width=4)


def _water_cycle_diagram():
    image = Image.new("RGB", (1200, 720), "#EDF6FF")
    draw = ImageDraw.Draw(image)
    draw.ellipse((105, 73, 253, 221), fill="#FFD579")
    draw.polygon([(0, 496), (198, 387), (384, 480), (650, 277), (847, 427),
                  (1011, 324), (1200, 474), (1200, 720), (0, 720)], fill="#83BFA7")
    draw.polygon([(0, 610), (189, 553), (390, 564), (704, 484), (925, 502),
                  (1063, 452), (1200, 533), (1200, 720), (0, 720)], fill="#ACD5BB")
    draw.polygon([(0, 558), (220, 555), (401, 605), (533, 613), (366, 720), (0, 720)],
                 fill="#4099CD")
    draw.line([(987, 494), (885, 534), (765, 550), (640, 612), (460, 651)], fill="#4099CD", width=32)
    cloud = "#FFFFFF"
    draw.rounded_rectangle((459, 159, 768, 249), 42, fill=cloud)
    draw.ellipse((482, 116, 628, 240), fill=cloud)
    draw.ellipse((570, 83, 706, 240), fill=cloud)
    draw.ellipse((666, 135, 769, 244), fill=cloud)
    ink = "#174876"

    def arrow(points):
        draw.line(points, fill=ink, width=8, joint="curve")
        x, y = points[-1]
        from_x, from_y = points[-2]
        angle = math.atan2(y - from_y, x - from_x)
        wings = [(x - 25 * math.cos(angle + offset), y - 25 * math.sin(angle + offset))
                 for offset in (-.48, .48)]
        draw.polygon([(x, y), *wings], fill=ink)

    def label(text, x, y):
        draw.rounded_rectangle((x - 74, y - 31, x + 74, y + 31), 19, fill="#FFFFFF")
        draw.text((x, y), text, font=_font(36), anchor="mm", fill=ink)

    arrow([(280, 563), (280, 448), (327, 345), (404, 264), (482, 223)])
    label("蒸发", 239, 388)
    label("凝结", 616, 176)
    arrow([(739, 226), (797, 264), (841, 329), (873, 417)])
    label("降水", 924, 319)
    arrow([(959, 550), (832, 587), (701, 615), (530, 653), (393, 659)])
    label("汇集", 715, 663)
    return image
