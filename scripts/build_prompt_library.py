#!/usr/bin/env python3
import csv
import hashlib
import json
import re
import shutil
from pathlib import Path

from PIL import Image, ImageOps


ROOT = Path(__file__).resolve().parents[1]
CRAWL_ROOT = ROOT.parent / "crawl"
CLEANED_ROOT = CRAWL_ROOT / "output" / "cleaned_data"
IMAGE_DIR = ROOT / "images"
PREVIEW_DIR = ROOT / "previews"
DATA_DIR = ROOT / "data"
TARGET_COUNT = 500
R2_DEV_BASE = "https://pub-911e4fa03f0c4323a80d8f3dc99d1c7f.r2.dev/"
CDN_BASE = "https://cdn.gptimagelab.com/"

WEBSITE_URL = "https://gptimagelab.com"
REPO = "peterRooo/awesome-gpt-image-2-prompts"
WEBSITE_TOTAL_ITEMS = 2985
WEBSITE_PROMPTS = 1060
WEBSITE_TEMPLATES = 1925
DAILY_NEW_ITEMS = 703
DAILY_NEW_PROMPTS = 443
DAILY_NEW_TEMPLATES = 260
DAILY_DATE = "2026-04-26"


CATEGORY_LABELS = {
    "portrait": "Portrait & Photography",
    "general": "General",
    "ui_mockup": "UI Mockup",
    "infographic": "Infographic",
    "editorial_collage": "Editorial Collage",
    "poster_design": "Poster Design",
    "character_illustration": "Character Illustration",
    "illustration": "Illustration",
    "3d_scene": "3D Scene",
    "copy_paste_library": "Copy-paste Library",
    "poster_template": "Poster Template",
    "packaging": "Packaging",
    "infographic_card_template": "Infographic Card Template",
    "text_rendering": "Text Rendering",
    "city_poster_template": "City Poster Template",
    "product_visual": "Product Visual",
    "advertising": "Advertising",
    "ecommerce": "E-commerce",
}


def md5_text(value: str) -> str:
    return hashlib.md5(value.strip().encode("utf-8")).hexdigest()


def md5_file(path: Path) -> str:
    digest = hashlib.md5()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def slug(value: str, fallback: str) -> str:
    value = re.sub(r"[^\w\u4e00-\u9fff.-]+", "-", value.strip().lower())
    value = re.sub(r"-+", "-", value).strip("-")
    return value[:80] or fallback


def clean(value: str) -> str:
    return (value or "").strip()


def language_label(value: str) -> str:
    return {
        "zh": "Chinese",
        "en": "English",
        "ja": "Japanese",
    }.get(clean(value).lower(), clean(value) or "Unknown")


def category_label(value: str) -> str:
    key = clean(value).lower()
    return CATEGORY_LABELS.get(key, key.replace("_", " ").title() or "General")


def cdn_image_url(value: str) -> str:
    value = clean(value)
    if value.startswith(R2_DEV_BASE):
        return CDN_BASE + value[len(R2_DEV_BASE) :]
    return value


def find_dates():
    return sorted(
        path.name
        for path in CLEANED_ROOT.iterdir()
        if path.is_dir() and re.match(r"\d{4}-\d{2}-\d{2}$", path.name)
    )


def load_prompt_rows():
    items = []
    seen = set()
    for date in find_dates():
        csv_path = CLEANED_ROOT / date / "prompts.csv"
        if not csv_path.exists():
            continue
        with csv_path.open(newline="", encoding="utf-8") as handle:
            for row in csv.DictReader(handle):
                prompt = clean(row.get("prompt_text", ""))
                image_path = Path(clean(row.get("primary_local_image_path", "")))
                if not prompt or not image_path.exists():
                    continue
                key = (md5_text(prompt), md5_file(image_path))
                if key in seen:
                    continue
                seen.add(key)
                item = {
                    "id": row.get("id", ""),
                    "source_record_id": row.get("source_record_id", ""),
                    "title": clean(row.get("title", "")) or "GPT Image 2 Prompt",
                    "category": category_label(row.get("use_case", "")),
                    "language": clean(row.get("language", "")) or "en",
                    "quality_grade": clean(row.get("quality_grade", "")),
                    "prompt": prompt,
                    "image_url": cdn_image_url(row.get("primary_image_url", "")),
                    "source_url": clean(row.get("source_url", "")),
                    "author_name": clean(row.get("author_name", "")) or "unknown",
                    "published_at": clean(row.get("published_at", "")) or date,
                    "channel": row.get("source_record_id", "").split("_")[2]
                    if len(row.get("source_record_id", "").split("_")) > 2
                    else "manual",
                    "image_path": image_path,
                    "date": date,
                }
                items.append(item)
    priority = {"A": 0, "B": 1, "C": 2}
    items.sort(
        key=lambda item: (
            priority.get(item["quality_grade"], 9),
            item["date"],
            item["category"],
            item["title"],
        )
    )
    return items[:TARGET_COUNT]


def build_preview_images(items):
    if PREVIEW_DIR.exists():
        shutil.rmtree(PREVIEW_DIR)
    PREVIEW_DIR.mkdir(parents=True, exist_ok=True)

    for index, item in enumerate(items, 1):
        source = item["image_path"]
        name = f"{index:03d}-{slug(source.stem, item['id'])}.jpg"
        dest = PREVIEW_DIR / name

        with Image.open(source) as image:
            image = ImageOps.exif_transpose(image)
            image.thumbnail((720, 720))
            if image.mode in ("RGBA", "LA"):
                background = Image.new("RGB", image.size, (255, 255, 255))
                background.paste(image, mask=image.getchannel("A"))
                image = background
            else:
                image = image.convert("RGB")
            image.save(dest, "JPEG", quality=74, optimize=True, progressive=True)

        item["image"] = f"previews/{name}"
        item["image_url"] = item["image_url"] or item["image"]
        del item["image_path"]


def write_data(items):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    json_items = []
    for index, item in enumerate(items, 1):
        json_items.append({"index": index, **item})
    (DATA_DIR / "gpt-image-2-prompts.json").write_text(
        json.dumps(json_items, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    with (DATA_DIR / "gpt-image-2-prompts.csv").open("w", newline="", encoding="utf-8") as handle:
        fieldnames = [
            "index",
            "title",
            "category",
            "language",
            "quality_grade",
            "prompt",
            "author_name",
            "channel",
            "published_at",
            "source_url",
            "image_url",
            "image",
        ]
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for index, item in enumerate(items, 1):
            writer.writerow({field: (index if field == "index" else item.get(field, "")) for field in fieldnames})


def group_items(items):
    groups = {}
    for index, item in enumerate(items, 1):
        groups.setdefault(item["category"], []).append((index, item))
    return dict(sorted(groups.items(), key=lambda pair: (-len(pair[1]), pair[0])))


def github_badges():
    return f"""[![GitHub stars](https://img.shields.io/github/stars/{REPO}?style=social)](https://github.com/{REPO}/stargazers)
[![GitHub forks](https://img.shields.io/github/forks/{REPO}?style=social)](https://github.com/{REPO}/forks)
[![Last commit](https://img.shields.io/github/last-commit/{REPO}?style=flat-square)](https://github.com/{REPO}/commits/main)
[![Website](https://img.shields.io/badge/website-gptimagelab.com-7c3aed?style=flat-square)]({WEBSITE_URL})
"""


def metric_cards(repo_count: int):
    return f"""| Metric | Count |
| --- | ---: |
| Repository prompts | **{repo_count:,}** |
| Website total prompt library | **{WEBSITE_TOTAL_ITEMS:,}** |
| Website prompts | **{WEBSITE_PROMPTS:,}** |
| Website templates | **{WEBSITE_TEMPLATES:,}** |
| New website items on {DAILY_DATE} | **+{DAILY_NEW_ITEMS:,}** |
"""


def source_line(item):
    parts = [
        f"Author: {item['author_name']}",
        f"Channel: {item['channel']}",
        f"Date: {item['published_at']}",
    ]
    if item["source_url"]:
        safe_url = item["source_url"].replace(")", "%29")
        parts.append(f"Source: [{safe_url}]({safe_url})")
    return "<br>".join(parts)


def build_readme(items):
    groups = group_items(items)
    lines = [
        "<div align=\"center\">",
        "",
        "# Awesome GPT Image 2 Prompts",
        "",
        "A polished, image-backed prompt library for **GPT Image 2** creators, designers, marketers, and builders.",
        "",
        github_badges().strip(),
        "",
        "[Explore the live library](https://gptimagelab.com) · [Prompts](https://gptimagelab.com/prompts) · [Templates](https://gptimagelab.com/templates) · [中文版本](README.zh-CN.md)",
        "",
        "</div>",
        "",
        "## Library Snapshot",
        "",
        metric_cards(len(items)),
        f"> The website added **+{DAILY_NEW_ITEMS:,}** new prompt-library items on **{DAILY_DATE}**: **+{DAILY_NEW_PROMPTS:,}** prompts and **+{DAILY_NEW_TEMPLATES:,}** templates.",
        "",
        "## Why this repo",
        "",
        "- **500 copy-ready GPT Image 2 prompts** with repository-hosted preview images.",
        "- **Professional browsing layout** with categories, compact details, and direct source attribution.",
        "- **Continuously refreshed upstream library** on [GptImageLab](https://gptimagelab.com), where new prompts are added daily.",
        "- **Machine-readable exports** available in [`data/gpt-image-2-prompts.json`](data/gpt-image-2-prompts.json) and [`data/gpt-image-2-prompts.csv`](data/gpt-image-2-prompts.csv).",
        "",
        "## Star Growth",
        "",
        f"[![Star History Chart](https://api.star-history.com/svg?repos={REPO}&type=Date)](https://www.star-history.com/#{REPO}&Date)",
        "",
        "## Prompt Index",
        "",
    ]
    for category, category_items in groups.items():
        anchor = re.sub(r"[^a-z0-9 -]", "", category.lower()).replace(" ", "-")
        lines.append(f"- [{category}](#{anchor}) · {len(category_items)} prompts")
    lines.append("")
    for category, category_items in groups.items():
        lines.extend([f"## {category}", ""])
        for index, item in category_items:
            lines.extend(
                [
                    f"### {index}. {item['title']}",
                    "",
                    f"<img src=\"{item['image']}\" alt=\"{item['title']}\" height=\"360\">",
                    "",
                    f"**Language:** {language_label(item['language'])} · **Quality:** {item['quality_grade'] or 'n/a'} · **Source:** {item['channel']}",
                    "",
                    f"<details><summary>Prompt · {language_label(item['language'])}</summary>",
                    "",
                    "```text",
                    item["prompt"],
                    "```",
                    "",
                    source_line(item),
                    "",
                    "</details>",
                    "",
                ]
            )
    return "\n".join(lines).rstrip() + "\n"


def build_readme_zh(items):
    groups = group_items(items)
    lines = [
        "<div align=\"center\">",
        "",
        "# Awesome GPT Image 2 Prompts",
        "",
        "一个面向设计师、营销人员和 AI 创作者的 **GPT Image 2** 高质量提示词图片库。",
        "",
        github_badges().strip(),
        "",
        "[访问网站](https://gptimagelab.com) · [提示词](https://gptimagelab.com/prompts) · [模板](https://gptimagelab.com/templates) · [English](README.md)",
        "",
        "</div>",
        "",
        "## 数据概览",
        "",
        metric_cards(len(items)).replace("Metric", "指标").replace("Count", "数量").replace("Repository prompts", "本仓库提示词").replace("Website total prompt library", "网站提示词库总量").replace("Website prompts", "网站 prompts").replace("Website templates", "网站 templates").replace(f"New website items on {DAILY_DATE}", f"{DAILY_DATE} 网站新增"),
        f"> 网站在 **{DAILY_DATE}** 新增 **+{DAILY_NEW_ITEMS:,}** 条提示词库内容：**+{DAILY_NEW_PROMPTS:,}** 条 prompts 和 **+{DAILY_NEW_TEMPLATES:,}** 条 templates。",
        "",
        "## 仓库亮点",
        "",
        "- **500 条可直接复制的 GPT Image 2 提示词**，并附带仓库内预览图。",
        "- **更专业的 README 排版**：分类索引、折叠提示词、来源信息清晰展示。",
        "- **网站持续更新**：[GptImageLab](https://gptimagelab.com) 每天补充新的提示词与模板。",
        "- **结构化数据导出**：[`data/gpt-image-2-prompts.json`](data/gpt-image-2-prompts.json) 与 [`data/gpt-image-2-prompts.csv`](data/gpt-image-2-prompts.csv)。",
        "",
        "## Star 增长趋势",
        "",
        f"[![Star History Chart](https://api.star-history.com/svg?repos={REPO}&type=Date)](https://www.star-history.com/#{REPO}&Date)",
        "",
        "## 分类索引",
        "",
    ]
    for category, category_items in groups.items():
        anchor = re.sub(r"[^a-z0-9 -]", "", category.lower()).replace(" ", "-")
        lines.append(f"- [{category}](#{anchor}) · {len(category_items)} 条")
    lines.append("")
    for category, category_items in groups.items():
        lines.extend([f"## {category}", ""])
        for index, item in category_items:
            lines.extend(
                [
                    f"### {index}. {item['title']}",
                    "",
                    f"<img src=\"{item['image']}\" alt=\"{item['title']}\" height=\"360\">",
                    "",
                    f"**语言：** {language_label(item['language'])} · **质量：** {item['quality_grade'] or 'n/a'} · **来源：** {item['channel']}",
                    "",
                    f"<details><summary>提示词 · {language_label(item['language'])}</summary>",
                    "",
                    "```text",
                    item["prompt"],
                    "```",
                    "",
                    source_line(item),
                    "",
                    "</details>",
                    "",
                ]
            )
    return "\n".join(lines).rstrip() + "\n"


def main():
    items = load_prompt_rows()
    if len(items) < TARGET_COUNT:
        raise SystemExit(f"only found {len(items)} usable prompts")
    build_preview_images(items)
    write_data(items)
    (ROOT / "README.md").write_text(build_readme(items), encoding="utf-8")
    (ROOT / "README.zh-CN.md").write_text(build_readme_zh(items), encoding="utf-8")
    print(f"Generated {len(items)} prompts")


if __name__ == "__main__":
    main()
