#!/usr/bin/env python3
import argparse
import html
import json
import os
import re
import shutil
import sys
import tempfile
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path, PurePosixPath


class MiniSiteError(Exception):
    pass


SUPPORTED_CONFIG = {
    "site_name",
    "base_url",
    "pagination",
    "json_feed",
    "enable_search",
}

SUPPORTED_META = {
    "title",
    "slug",
    "date",
    "tags",
    "stream",
    "description",
}


@dataclass
class Config:
    site_name: str = "Mini Marmite"
    base_url: str = ""
    pagination: int = 10
    json_feed: bool = True
    enable_search: bool = True


@dataclass
class Item:
    title: str
    slug: str
    source: str
    kind: str
    date: str | None
    tags: list[str]
    stream: str | None
    description: str | None
    draft: bool
    body: str
    links_to: list[str] = field(default_factory=list)
    backlinks: list[str] = field(default_factory=list)

    def public_dict(self) -> dict:
        return {
            "title": self.title,
            "slug": self.slug,
            "source": self.source,
            "kind": self.kind,
            "date": self.date,
            "tags": self.tags,
            "stream": self.stream,
            "description": self.description,
            "draft": self.draft,
            "links_to": self.links_to,
            "backlinks": self.backlinks,
        }


def fail(message: str) -> None:
    raise MiniSiteError(message)


def compact_json(value) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=False)


def strip_quotes(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value


def slugify(text: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "-", text.lower()).strip("-")


def parse_bool(value: str, context: str) -> bool:
    raw = strip_quotes(value).strip().lower()
    if raw == "true":
        return True
    if raw == "false":
        return False
    fail(f"invalid boolean for {context}: {value}")


def parse_date(value: str, context: str) -> str:
    raw = strip_quotes(value).strip()
    formats = ["%Y-%m-%d", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"]
    for fmt in formats:
        try:
            return datetime.strptime(raw, fmt).strftime("%Y-%m-%d")
        except ValueError:
            pass
    fail(f"invalid date for {context}: {value}")


def parse_config(path: Path) -> Config:
    config = Config()
    if not path.exists():
        return config
    if not path.is_file():
        fail(f"config path is not a file: {path}")
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        fail(f"unable to read config: {exc}")
    for lineno, line in enumerate(lines, 1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        key = key.strip()
        value = value.strip()
        if key not in SUPPORTED_CONFIG:
            continue
        if key == "site_name":
            config.site_name = strip_quotes(value)
        elif key == "base_url":
            config.base_url = strip_quotes(value).rstrip("/")
        elif key == "pagination":
            raw = strip_quotes(value).strip()
            if not re.fullmatch(r"[0-9]+", raw):
                fail(f"invalid pagination value on line {lineno}")
            config.pagination = int(raw)
            if config.pagination <= 0:
                fail("pagination must be positive")
        elif key == "json_feed":
            config.json_feed = parse_bool(value, key)
        elif key == "enable_search":
            config.enable_search = parse_bool(value, key)
    return config


def parse_tags(value: str, context: str) -> list[str]:
    raw = value.strip()
    if raw.startswith("["):
        if not raw.endswith("]"):
            fail(f"invalid tags for {context}: {value}")
        raw = raw[1:-1]
    else:
        raw = strip_quotes(raw)
    tags = []
    for part in raw.split(","):
        tag = strip_quotes(part).strip()
        if tag:
            tags.append(tag)
    return tags


def parse_frontmatter(text: str, source: str) -> tuple[dict, str]:
    lines = text.splitlines()
    if not lines or lines[0] != "---":
        return {}, text
    end = None
    for index in range(1, len(lines)):
        if lines[index] == "---":
            end = index
            break
    if end is None:
        return {}, text
    meta = {}
    for lineno, line in enumerate(lines[1:end], 2):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        key = key.strip()
        value = value.strip()
        if key not in SUPPORTED_META:
            continue
        if key in {"title", "slug", "stream", "description"}:
            meta[key] = strip_quotes(value)
        elif key == "date":
            meta[key] = parse_date(value, f"{source}:{lineno}")
        elif key == "tags":
            meta[key] = parse_tags(value, f"{source}:{lineno}")
    body = "\n".join(lines[end + 1 :])
    if text.endswith("\n"):
        body += "\n"
    return meta, body


def first_heading(body: str) -> str | None:
    for line in body.splitlines():
        if line.startswith("# "):
            title = line[2:].strip()
            if title:
                return title
    return None


def filename_info(source: str, meta_date: str | None) -> dict:
    stem = PurePosixPath(source).stem
    info = {
        "date": None,
        "stream": None,
        "slug_base": stem,
        "title_base": stem,
        "recognized": False,
    }

    stream_datetime = re.fullmatch(
        r"([A-Za-z0-9]+)-(\d{4})-(\d{2})-(\d{2})-(\d{2})-(\d{2})-(\d{2})-(.+)",
        stem,
    )
    if stream_datetime:
        stream = slugify(stream_datetime.group(1))
        name = stream_datetime.group(8)
        info.update(
            {
                "date": f"{stream_datetime.group(2)}-{stream_datetime.group(3)}-{stream_datetime.group(4)}",
                "stream": stream,
                "slug_base": f"{stream}-{slugify(name)}",
                "title_base": name,
                "recognized": True,
            }
        )
        return info

    stream_date = re.fullmatch(r"([A-Za-z0-9]+)-(\d{4})-(\d{2})-(\d{2})-(.+)", stem)
    if stream_date:
        stream = slugify(stream_date.group(1))
        name = stream_date.group(5)
        info.update(
            {
                "date": f"{stream_date.group(2)}-{stream_date.group(3)}-{stream_date.group(4)}",
                "stream": stream,
                "slug_base": f"{stream}-{slugify(name)}",
                "title_base": name,
                "recognized": True,
            }
        )
        return info

    datetime_prefix = re.fullmatch(
        r"(\d{4})-(\d{2})-(\d{2})-(\d{2})-(\d{2})-(\d{2})-(.+)", stem
    )
    if datetime_prefix:
        name = datetime_prefix.group(7)
        info.update(
            {
                "date": f"{datetime_prefix.group(1)}-{datetime_prefix.group(2)}-{datetime_prefix.group(3)}",
                "slug_base": slugify(name),
                "title_base": name,
                "recognized": True,
            }
        )
        return info

    date_prefix = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})-(.+)", stem)
    if date_prefix:
        name = date_prefix.group(4)
        info.update(
            {
                "date": f"{date_prefix.group(1)}-{date_prefix.group(2)}-{date_prefix.group(3)}",
                "slug_base": slugify(name),
                "title_base": name,
                "recognized": True,
            }
        )
        return info

    stream_name = re.fullmatch(r"([A-Za-z0-9]+)-(.+)", stem)
    if meta_date and stream_name:
        stream = slugify(stream_name.group(1))
        name = stream_name.group(2)
        info.update(
            {
                "stream": stream,
                "slug_base": f"{stream}-{slugify(name)}",
                "title_base": name,
                "recognized": True,
            }
        )
        return info

    info["slug_base"] = slugify(stem)
    return info


def content_root(input_path: Path) -> Path:
    if not input_path.exists() or not input_path.is_dir():
        fail(f"missing input directory: {input_path}")
    nested = input_path / "content"
    return nested if nested.exists() and nested.is_dir() else input_path


def iter_markdown_files(root: Path) -> list[Path]:
    files = []
    for current, dirs, names in os.walk(root):
        dirs[:] = sorted(dirs)
        for name in sorted(names):
            if name.startswith("_") or not name.endswith(".md"):
                continue
            files.append(Path(current) / name)
    return files


def read_items(input_path: Path, config: Config) -> list[Item]:
    root = content_root(input_path)
    items = []
    for path in iter_markdown_files(root):
        try:
            text = path.read_text(encoding="utf-8")
        except OSError as exc:
            fail(f"unable to read content file {path}: {exc}")
        source = path.relative_to(root).as_posix()
        meta, body = parse_frontmatter(text, source)
        info = filename_info(source, meta.get("date"))
        date = meta.get("date") or info["date"]
        kind = "post" if date else "page"

        title = meta.get("title") or first_heading(body)
        if not title:
            title = info["title_base"].replace("-", " ").replace("_", " ").strip() or PurePosixPath(source).stem

        base_slug = slugify(meta["slug"]) if "slug" in meta else info["slug_base"]
        if not base_slug:
            base_slug = slugify(title)
        stream = None
        if kind == "post":
            stream = slugify(meta["stream"]) if "stream" in meta else info["stream"]
            stream = stream or "index"
        if kind == "post" and "stream" in meta and stream not in {"", "index"}:
            plain_base = base_slug
            if info["stream"] and plain_base.startswith(info["stream"] + "-"):
                plain_base = plain_base[len(info["stream"]) + 1 :]
            base_slug = f"{stream}-{plain_base}"
        slug = base_slug
        if not slug:
            fail(f"empty slug for {source}")

        tags = meta.get("tags", [])
        description = meta.get("description")
        draft = kind == "post" and stream == "draft"
        items.append(
            Item(
                title=title,
                slug=slug,
                source=source,
                kind=kind,
                date=date,
                tags=tags,
                stream=stream if kind == "post" else None,
                description=description if description != "" else None,
                draft=draft,
                body=body,
            )
        )
    ensure_unique_public_slugs(items)
    fill_links(items)
    return items


def ensure_unique_public_slugs(items: list[Item]) -> None:
    seen = {}
    for item in items:
        if item.draft:
            continue
        if item.slug in seen:
            fail(f"duplicate slug among public content: {item.slug}")
        seen[item.slug] = item.source


def source_target_key(source: str, target: str) -> str:
    base = PurePosixPath(source).parent
    joined = (base / target).as_posix()
    parts = []
    for part in joined.split("/"):
        if part in {"", "."}:
            continue
        if part == "..":
            if parts:
                parts.pop()
            continue
        parts.append(part)
    return "/".join(parts)


def build_lookup(items: list[Item]) -> tuple[dict[str, str], dict[str, str]]:
    title_map = {}
    target_map = {}
    for item in items:
        title_map.setdefault(item.title.lower(), item.slug)
        target_map[item.source] = item.slug
        target_map[PurePosixPath(item.source).with_suffix(".html").as_posix()] = item.slug
        target_map[PurePosixPath(item.source).name] = item.slug
        target_map[PurePosixPath(item.source).with_suffix(".html").name] = item.slug
        target_map[item.slug + ".html"] = item.slug
        target_map[item.slug + ".md"] = item.slug
    return title_map, target_map


def resolve_local_target(source: str, target: str, target_map: dict[str, str]) -> str:
    clean = target.split("#", 1)[0].split("?", 1)[0]
    key = source_target_key(source, clean)
    if key in target_map:
        return target_map[key]
    if clean in target_map:
        return target_map[clean]
    name = PurePosixPath(clean).name
    if name in target_map:
        return target_map[name]
    return slugify(PurePosixPath(clean).stem)


def extract_links(item: Item, title_map: dict[str, str], target_map: dict[str, str]) -> list[str]:
    links = []
    seen = set()

    def add(slug: str) -> None:
        if slug and slug not in seen:
            seen.add(slug)
            links.append(slug)

    for match in re.finditer(r"\[\[([^\]]+)\]\]", item.body):
        raw = match.group(1)
        title = raw.split("|", 1)[0].strip()
        add(title_map.get(title.lower(), slugify(title)))
    for match in re.finditer(r"\[([^\]]+)\]\(([^)]+)\)", item.body):
        target = match.group(2).strip()
        if target.startswith("http://") or target.startswith("https://"):
            continue
        if target.endswith(".md") or target.endswith(".html") or ".md#" in target or ".html#" in target:
            add(resolve_local_target(item.source, target, target_map))
    return links


def fill_links(items: list[Item]) -> None:
    title_map, target_map = build_lookup(items)
    by_slug = {item.slug: item for item in items}
    for item in items:
        item.links_to = extract_links(item, title_map, target_map)
        item.backlinks = []
    for item in items:
        for slug in item.links_to:
            target = by_slug.get(slug)
            if target and item.slug not in target.backlinks:
                target.backlinks.append(item.slug)
    for item in items:
        item.backlinks.sort()


def post_sort_key(item: Item):
    return (item.date or "", item.slug)


def sorted_posts(items: list[Item], include_drafts: bool = False) -> list[Item]:
    posts = [item for item in items if item.kind == "post" and (include_drafts or not item.draft)]
    return sorted(posts, key=lambda item: (item.date or "", item.slug), reverse=False)[::-1]


def public_posts(items: list[Item]) -> list[Item]:
    return sorted(
        [item for item in items if item.kind == "post" and not item.draft],
        key=lambda item: (-(int(item.date.replace("-", "")) if item.date else 0), item.slug),
    )


def public_pages(items: list[Item]) -> list[Item]:
    return sorted(
        [item for item in items if item.kind == "page" and not item.draft],
        key=lambda item: (item.title.lower(), item.slug),
    )


def inspect_output(items: list[Item]) -> dict:
    posts = public_posts(items)
    pages = public_pages(items)
    drafts = sorted(
        [item for item in items if item.draft],
        key=lambda item: (-(int(item.date.replace("-", "")) if item.date else 0), item.slug),
    )
    tags = {}
    streams = {}
    for post in posts:
        streams.setdefault(post.stream or "index", []).append(post.slug)
        for tag in post.tags:
            tag_slug = slugify(tag)
            if tag_slug:
                tags.setdefault(tag_slug, []).append(post.slug)
    return {
        "posts": [item.public_dict() for item in posts],
        "pages": [item.public_dict() for item in pages],
        "tags": dict(sorted(tags.items())),
        "streams": dict(sorted(streams.items())),
        "drafts": [item.public_dict() for item in drafts],
    }


def absolute_url(config: Config, slug: str) -> str:
    path = f"{slug}.html"
    if not config.base_url:
        return path
    return config.base_url.rstrip("/") + "/" + path


def render_inline(text: str, item: Item, title_map: dict[str, str], target_map: dict[str, str]) -> str:
    pattern = re.compile(r"\[\[([^\]]+)\]\]|\[([^\]]+)\]\(([^)]+)\)")
    out = []
    pos = 0
    for match in pattern.finditer(text):
        out.append(html.escape(text[pos : match.start()]))
        if match.group(1) is not None:
            raw = match.group(1)
            title, label = (raw.split("|", 1) + [None])[:2] if "|" in raw else (raw, raw)
            title = title.strip()
            label = (label if label is not None else title).strip()
            slug = title_map.get(title.lower())
            if slug:
                out.append(f'<a href="{html.escape(slug)}.html">{html.escape(label)}</a>')
            else:
                href = slugify(title) + ".html"
                out.append(
                    f'<a data-wikilink="missing" href="{html.escape(href)}">{html.escape(label)}</a>'
                )
        else:
            label = match.group(2)
            target = match.group(3).strip()
            if target.startswith("http://") or target.startswith("https://"):
                href = target
            elif target.endswith(".md") or target.endswith(".html") or ".md#" in target or ".html#" in target:
                href = resolve_local_target(item.source, target, target_map) + ".html"
            else:
                href = target
            out.append(f'<a href="{html.escape(href)}">{html.escape(label)}</a>')
        pos = match.end()
    out.append(html.escape(text[pos:]))
    return "".join(out)


def render_markdown(item: Item, title_map: dict[str, str], target_map: dict[str, str]) -> str:
    parts = []
    paragraph = []

    def flush() -> None:
        if paragraph:
            text = " ".join(line.strip() for line in paragraph)
            parts.append(f"<p>{render_inline(text, item, title_map, target_map)}</p>")
            paragraph.clear()

    for line in item.body.splitlines():
        if not line.strip():
            flush()
            continue
        if line.startswith("# "):
            flush()
            heading = line[2:].strip()
            parts.append(f'<h1 id="{html.escape(slugify(heading))}">{html.escape(heading)}</h1>')
        elif line.startswith("## "):
            flush()
            heading = line[3:].strip()
            parts.append(f'<h2 id="{html.escape(slugify(heading))}">{html.escape(heading)}</h2>')
        else:
            paragraph.append(line)
    flush()
    return "\n".join(parts)


def plain_text(item: Item) -> str:
    lines = []
    for line in item.body.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("# "):
            stripped = stripped[2:].strip()
        elif stripped.startswith("## "):
            stripped = stripped[3:].strip()
        stripped = re.sub(r"\[\[([^|\]]+)\|([^\]]+)\]\]", r"\2", stripped)
        stripped = re.sub(r"\[\[([^\]]+)\]\]", r"\1", stripped)
        stripped = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", stripped)
        lines.append(stripped)
    return " ".join(lines)


def page_html(title: str, body: str) -> str:
    return (
        "<!doctype html>\n"
        "<html><head>"
        f"<meta charset=\"utf-8\"><title>{html.escape(title)}</title>"
        "</head><body>\n"
        f"{body}\n"
        "</body></html>\n"
    )


def content_page(item: Item, title_map: dict[str, str], target_map: dict[str, str], public_slugs: set[str]) -> str:
    body = [render_markdown(item, title_map, target_map)]
    backlinks = [slug for slug in item.backlinks if slug in public_slugs]
    if backlinks:
        body.append("<section class=\"backlinks\"><h2>Backlinks</h2><ul>")
        for slug in backlinks:
            body.append(f'<li><a href="{html.escape(slug)}.html">{html.escape(slug)}</a></li>')
        body.append("</ul></section>")
    return page_html(item.title, "\n".join(body))


def listing_page(title: str, items: list[Item]) -> str:
    rows = [f"<h1>{html.escape(title)}</h1>", "<ul>"]
    for item in items:
        rows.append(f'<li><a href="{html.escape(item.slug)}.html">{html.escape(item.title)}</a></li>')
    rows.append("</ul>")
    return page_html(title, "\n".join(rows))


def simple_link_page(title: str, links: list[tuple[str, str]]) -> str:
    rows = [f"<h1>{html.escape(title)}</h1>", "<ul>"]
    for href, label in links:
        rows.append(f'<li><a href="{html.escape(href)}">{html.escape(label)}</a></li>')
    rows.append("</ul>")
    return page_html(title, "\n".join(rows))


def chunks(items: list[Item], size: int) -> list[list[Item]]:
    return [items[index : index + size] for index in range(0, len(items), size)] or [[]]


def feed_item(config: Config, item: Item) -> dict:
    return {
        "title": item.title,
        "slug": item.slug,
        "url": absolute_url(config, item.slug),
        "date": item.date,
        "tags": item.tags,
        "stream": item.stream,
        "description": item.description,
    }


def build_files(items: list[Item], config: Config) -> tuple[dict[str, str], dict]:
    files = {}
    manifest = {
        "posts": [],
        "pages": [],
        "index": [],
        "tags": [],
        "streams": [],
        "feeds": [],
        "search": [],
        "misc": [],
        "summary": {},
    }
    title_map, target_map = build_lookup([item for item in items if not item.draft])
    posts = public_posts(items)
    pages = public_pages(items)
    public_slugs = {item.slug for item in posts + pages}

    for item in posts:
        path = item.slug + ".html"
        files[path] = content_page(item, title_map, target_map, public_slugs)
        manifest["posts"].append(path)
    for item in pages:
        path = item.slug + ".html"
        files[path] = content_page(item, title_map, target_map, public_slugs)
        manifest["pages"].append(path)

    if pages:
        files["pages.html"] = listing_page("Pages", pages)
        manifest["pages"].append("pages.html")

    index_posts = [post for post in posts if post.stream == "index"]
    for page_num, group in enumerate(chunks(index_posts, config.pagination), 1):
        path = "index.html" if page_num == 1 else f"index-{page_num}.html"
        files[path] = listing_page(config.site_name, group)
        manifest["index"].append(path)

    tag_map = {}
    for post in posts:
        for tag in post.tags:
            tag_slug = slugify(tag)
            if tag_slug:
                tag_map.setdefault(tag_slug, []).append(post)
    tag_page_links = []
    for tag_slug in sorted(tag_map):
        tag_posts = tag_map[tag_slug]
        first_path = f"tag-{tag_slug}.html"
        tag_page_links.append((first_path, tag_slug))
        for page_num, group in enumerate(chunks(tag_posts, config.pagination), 1):
            path = first_path if page_num == 1 else f"tag-{tag_slug}-{page_num}.html"
            files[path] = listing_page(f"Tag: {tag_slug}", group)
            manifest["tags"].append(path)
    if tag_page_links:
        files["tags.html"] = simple_link_page("Tags", tag_page_links)
        manifest["tags"].append("tags.html")

    stream_map = {}
    for post in posts:
        if post.stream not in {None, "index", "draft"}:
            stream_map.setdefault(post.stream, []).append(post)
    stream_page_links = []
    for stream in sorted(stream_map):
        stream_posts = stream_map[stream]
        first_path = f"{stream}.html"
        stream_page_links.append((first_path, stream))
        for page_num, group in enumerate(chunks(stream_posts, config.pagination), 1):
            path = first_path if page_num == 1 else f"{stream}-{page_num}.html"
            files[path] = listing_page(f"Stream: {stream}", group)
            manifest["streams"].append(path)
    if stream_page_links:
        files["streams.html"] = simple_link_page("Streams", stream_page_links)
        manifest["streams"].append("streams.html")

    if config.json_feed:
        files["feed.json"] = compact_json(
            {"title": config.site_name, "items": [feed_item(config, post) for post in index_posts]}
        ) + "\n"
        manifest["feeds"].append("feed.json")
        for tag_slug in sorted(tag_map):
            path = f"tag-{tag_slug}.json"
            files[path] = compact_json(
                {"title": f"tag:{tag_slug}", "items": [feed_item(config, post) for post in tag_map[tag_slug]]}
            ) + "\n"
            manifest["feeds"].append(path)
        for stream in sorted(stream_map):
            path = f"{stream}.json"
            files[path] = compact_json(
                {"title": f"stream:{stream}", "items": [feed_item(config, post) for post in stream_map[stream]]}
            ) + "\n"
            manifest["feeds"].append(path)

    if config.enable_search:
        search_items = []
        for item in posts + pages:
            search_items.append(
                {
                    "title": item.title,
                    "slug": item.slug,
                    "url": absolute_url(config, item.slug),
                    "kind": item.kind,
                    "tags": item.tags,
                    "stream": item.stream,
                    "text": plain_text(item),
                }
            )
        files["search_index.json"] = compact_json(search_items) + "\n"
        manifest["search"].append("search_index.json")

    manifest["misc"].append("urls.json")
    for key in ["posts", "pages", "index", "tags", "streams", "feeds", "search", "misc"]:
        manifest["summary"][key] = len(manifest[key])
    manifest["summary"]["total"] = sum(manifest["summary"][key] for key in ["posts", "pages", "index", "tags", "streams", "feeds", "search", "misc"]) - 1
    files["urls.json"] = compact_json(manifest) + "\n"
    return files, manifest


def previous_manifest_paths(output: Path) -> set[str]:
    path = output / "urls.json"
    if not path.exists():
        return set()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return set()
    paths = set()
    if isinstance(data, dict):
        for key in ["posts", "pages", "index", "tags", "streams", "feeds", "search", "misc"]:
            values = data.get(key, [])
            if isinstance(values, list):
                paths.update(value for value in values if isinstance(value, str))
    return paths


def write_site(output: Path, files: dict[str, str]) -> None:
    old_paths = previous_manifest_paths(output)
    try:
        output.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        fail(f"unable to create output directory: {exc}")
    if not output.is_dir():
        fail(f"output path is not a directory: {output}")
    try:
        with tempfile.TemporaryDirectory(prefix=".minisite-", dir=output) as tmp_name:
            tmp = Path(tmp_name)
            for name, content in files.items():
                if "/" in name or name.startswith("."):
                    fail(f"invalid output path: {name}")
                (tmp / name).write_text(content, encoding="utf-8")
            for name in sorted(files):
                os.replace(tmp / name, output / name)
    except OSError as exc:
        fail(f"unable to write output directory: {exc}")
    for stale in sorted(old_paths - set(files)):
        target = output / stale
        try:
            if target.is_file():
                target.unlink()
        except OSError:
            pass


def command_inspect(args) -> dict:
    input_path = Path(args.input)
    config_path = Path(args.config) if args.config else input_path / "marmite.yaml"
    config = parse_config(config_path)
    items = read_items(input_path, config)
    return inspect_output(items)


def command_build(args) -> dict:
    input_path = Path(args.input)
    config_path = Path(args.config) if args.config else input_path / "marmite.yaml"
    config = parse_config(config_path)
    items = read_items(input_path, config)
    files, manifest = build_files(items, config)
    write_site(Path(args.output), files)
    return manifest


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(prog="minisite.py")
    sub = root.add_subparsers(dest="command", required=True)
    build = sub.add_parser("build")
    build.add_argument("--input", required=True)
    build.add_argument("--output", required=True)
    build.add_argument("--config")
    inspect_cmd = sub.add_parser("inspect")
    inspect_cmd.add_argument("--input", required=True)
    inspect_cmd.add_argument("--config")
    return root


def main(argv: list[str] | None = None) -> int:
    try:
        args = parser().parse_args(argv)
        if args.command == "build":
            result = command_build(args)
        elif args.command == "inspect":
            result = command_inspect(args)
        else:
            fail(f"unsupported command: {args.command}")
        sys.stdout.write(compact_json(result) + "\n")
        return 0
    except MiniSiteError as exc:
        sys.stderr.write(str(exc) + "\n")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
