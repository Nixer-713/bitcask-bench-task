#!/usr/bin/env python3
import argparse
import datetime as _dt
import html
import json
import os
import re
import shutil
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Optional


MANIFEST_KEYS = [
    "posts",
    "pages",
    "index",
    "tags",
    "streams",
    "archives",
    "feeds",
    "search",
    "misc",
]


class MiniSiteError(Exception):
    pass


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
    date: Optional[str]
    tags: list[str]
    stream: Optional[str]
    description: Optional[str]
    draft: bool
    body: str
    links_to: list[str] = field(default_factory=list)
    backlinks: list[str] = field(default_factory=list)

    def public_dict(self):
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


def slugify(value):
    slug = re.sub(r"[^A-Za-z0-9]+", "-", value.lower()).strip("-")
    return slug


def strip_quotes(value):
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value


def parse_bool(value, name):
    cleaned = strip_quotes(value).strip().lower()
    if cleaned == "true":
        return True
    if cleaned == "false":
        return False
    raise MiniSiteError(f"invalid config value for {name}: {value}")


def parse_date(value, where):
    cleaned = strip_quotes(value).strip()
    for fmt in ("%Y-%m-%d", "%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S"):
        try:
            return _dt.datetime.strptime(cleaned, fmt).date().isoformat()
        except ValueError:
            pass
    raise MiniSiteError(f"invalid date value in {where}: {value}")


def parse_config(path):
    config = Config()
    if not path.exists():
        return config
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise MiniSiteError(f"unable to read config: {exc}") from exc
    for line_number, raw in enumerate(lines, 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        key = key.strip()
        value = value.strip()
        if key == "site_name":
            config.site_name = strip_quotes(value)
        elif key == "base_url":
            config.base_url = strip_quotes(value).strip()
        elif key == "pagination":
            cleaned = strip_quotes(value).strip()
            try:
                pagination = int(cleaned)
            except ValueError as exc:
                raise MiniSiteError(f"invalid pagination value on line {line_number}") from exc
            if pagination <= 0:
                raise MiniSiteError(f"invalid pagination value on line {line_number}")
            config.pagination = pagination
        elif key == "json_feed":
            config.json_feed = parse_bool(value, key)
        elif key == "enable_search":
            config.enable_search = parse_bool(value, key)
    return config


def parse_tag_value(value):
    cleaned = strip_quotes(value.strip())
    if value.strip().startswith("[") and value.strip().endswith("]"):
        inner = value.strip()[1:-1]
        parts = split_commas(inner)
    else:
        parts = split_commas(cleaned)
    tags = []
    for part in parts:
        tag = strip_quotes(part.strip()).strip()
        if tag:
            tags.append(tag)
    return tags


def split_commas(value):
    parts = []
    current = []
    quote = None
    escape = False
    for char in value:
        if escape:
            current.append(char)
            escape = False
            continue
        if char == "\\" and quote:
            escape = True
            current.append(char)
            continue
        if char in {"'", '"'}:
            if quote is None:
                quote = char
            elif quote == char:
                quote = None
            current.append(char)
            continue
        if char == "," and quote is None:
            parts.append("".join(current))
            current = []
            continue
        current.append(char)
    parts.append("".join(current))
    return parts


def split_frontmatter(text, source):
    lines = text.splitlines()
    if not lines or lines[0] != "---":
        return {}, text
    closing = None
    for index in range(1, len(lines)):
        if lines[index] == "---":
            closing = index
            break
    if closing is None:
        raise MiniSiteError(f"unterminated frontmatter in {source}")
    metadata = {}
    for line_number, line in enumerate(lines[1:closing], 2):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        key = key.strip()
        if key not in {"title", "slug", "date", "tags", "stream", "description"}:
            continue
        value = value.strip()
        if key == "date":
            metadata[key] = parse_date(value, f"{source}:{line_number}")
        elif key == "tags":
            metadata[key] = parse_tag_value(value)
        else:
            metadata[key] = strip_quotes(value)
    body = "\n".join(lines[closing + 1 :])
    if text.endswith("\n"):
        body += "\n"
    return metadata, body


def first_heading(body):
    for line in body.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return None


def filename_info(stem, frontmatter_date):
    match = re.match(r"^(\d{4})-(\d{2})-(\d{2})-(.+)$", stem)
    if match:
        date_text = "-".join(match.group(i) for i in range(1, 4))
        try:
            _dt.date.fromisoformat(date_text)
        except ValueError:
            pass
        else:
            return {"date": date_text, "stream": None, "base": match.group(4), "recognized": True}

    match = re.match(r"^(\d{4})-(\d{2})-(\d{2})-(\d{2})-(\d{2})-(\d{2})-(.+)$", stem)
    if match:
        date_text = "-".join(match.group(i) for i in range(1, 4))
        time_parts = [int(match.group(i)) for i in range(4, 7)]
        try:
            _dt.datetime(
                int(match.group(1)),
                int(match.group(2)),
                int(match.group(3)),
                *time_parts,
            )
        except ValueError:
            pass
        else:
            return {"date": date_text, "stream": None, "base": match.group(7), "recognized": True}

    match = re.match(r"^([^-]+)-(\d{4})-(\d{2})-(\d{2})-(.+)$", stem)
    if match:
        date_text = "-".join(match.group(i) for i in range(2, 5))
        try:
            _dt.date.fromisoformat(date_text)
        except ValueError:
            pass
        else:
            return {
                "date": date_text,
                "stream": match.group(1),
                "base": match.group(5),
                "recognized": True,
            }

    if frontmatter_date and "-" in stem:
        stream, rest = stem.split("-", 1)
        if stream and rest:
            return {"date": None, "stream": stream, "base": rest, "recognized": True}

    return {"date": None, "stream": None, "base": stem, "recognized": False}


def load_items(input_path):
    input_path = Path(input_path)
    if not input_path.is_dir():
        raise MiniSiteError(f"missing input directory: {input_path}")
    content_root = input_path / "content" if (input_path / "content").is_dir() else input_path
    items = []
    for path in sorted(content_root.rglob("*.md")):
        if path.name.startswith("_"):
            continue
        source = path.relative_to(content_root).as_posix()
        try:
            text = path.read_text(encoding="utf-8")
        except OSError as exc:
            raise MiniSiteError(f"unable to read content file {source}: {exc}") from exc
        metadata, body = split_frontmatter(text, source)
        info = filename_info(path.stem, metadata.get("date"))
        date = metadata.get("date") or info["date"]
        kind = "post" if date else "page"
        stream = None
        if kind == "post":
            stream = metadata.get("stream") or info["stream"] or "index"
        title = metadata.get("title") or first_heading(body) or info["base"]

        if "slug" in metadata:
            base_slug = metadata["slug"].strip()
        elif info["recognized"] and kind == "post":
            base_slug = slugify(info["base"])
        elif metadata.get("title") or first_heading(body):
            base_slug = slugify(title)
        else:
            base_slug = slugify(info["base"])
        if not base_slug:
            base_slug = "untitled"

        if kind == "post" and metadata.get("stream") and metadata["stream"] != "index":
            slug = f"{metadata['stream']}-{base_slug}"
        elif kind == "post" and info["stream"] and not metadata.get("stream"):
            slug = f"{info['stream']}-{base_slug}"
        else:
            slug = base_slug

        item = Item(
            title=title,
            slug=slug,
            source=source,
            kind=kind,
            date=date,
            tags=metadata.get("tags", []) if kind == "post" else [],
            stream=stream if kind == "post" else None,
            description=metadata.get("description"),
            draft=(kind == "post" and stream == "draft"),
            body=body,
        )
        items.append(item)
    validate_public_slugs(items)
    apply_link_graph(items)
    return items


def validate_public_slugs(items):
    seen = {}
    for item in items:
        if item.draft:
            continue
        if item.slug in seen:
            raise MiniSiteError(f"duplicate final slug among non-draft content: {item.slug}")
        seen[item.slug] = item.source


def post_order(item):
    return (-int(item.date.replace("-", "")), item.slug)


def page_order(item):
    return (item.title.lower(), item.slug)


def ordered_items(items):
    posts = sorted([item for item in items if item.kind == "post" and not item.draft], key=post_order)
    pages = sorted([item for item in items if item.kind == "page" and not item.draft], key=page_order)
    drafts = sorted([item for item in items if item.draft], key=lambda item: (item.date or "", item.slug))
    return posts, pages, drafts


def apply_link_graph(items):
    public_items = [item for item in items if not item.draft]
    title_map = {}
    slug_map = {item.slug: item for item in public_items}
    source_map = {item.source: item for item in public_items}
    for item in public_items:
        title_map.setdefault(item.title.lower(), item)

    for item in items:
        item.links_to = extract_links_to(item, title_map, slug_map, source_map)
        item.backlinks = []

    public_by_slug = {item.slug: item for item in public_items}
    for source in public_items:
        for target_slug in source.links_to:
            target = public_by_slug.get(target_slug)
            if target and source.slug not in target.backlinks:
                target.backlinks.append(source.slug)


def extract_links_to(item, title_map, slug_map, source_map):
    links = []

    def add(slug):
        if slug and slug not in links:
            links.append(slug)

    for match in re.finditer(r"\[\[([^\]|]+)(?:\|([^\]]+))?\]\]", item.body):
        title = match.group(1).strip()
        target = title_map.get(title.lower())
        if target:
            add(target.slug)

    for match in re.finditer(r"\[([^\]]+)\]\(([^)]+)\)", item.body):
        target = match.group(2).strip()
        if target.startswith(("http://", "https://")):
            continue
        resolved = resolve_local_link(item.source, target, slug_map, source_map)
        if resolved:
            add(resolved)
    return links


def resolve_local_link(source, target, slug_map, source_map):
    target = target.split("#", 1)[0].split("?", 1)[0]
    suffix = Path(target).suffix.lower()
    if suffix not in {".md", ".html"}:
        return None
    source_parent = PurePosixPath(source).parent
    normalized = (source_parent / target).as_posix()
    while normalized.startswith("./"):
        normalized = normalized[2:]
    parts = []
    for part in normalized.split("/"):
        if part in {"", "."}:
            continue
        if part == "..":
            if parts:
                parts.pop()
            continue
        parts.append(part)
    normalized = "/".join(parts)
    if suffix == ".md":
        item = source_map.get(normalized)
        return item.slug if item else None
    md_candidate = str(PurePosixPath(normalized).with_suffix(".md"))
    item = source_map.get(md_candidate)
    if item:
        return item.slug
    stem = PurePosixPath(normalized).stem
    if stem in slug_map:
        return stem
    return None


def render_inline(text, item, title_map, slug_map, source_map):
    pattern = re.compile(r"(\[\[([^\]|]+)(?:\|([^\]]+))?\]\]|\[([^\]]+)\]\(([^)]+)\))")
    output = []
    position = 0
    for match in pattern.finditer(text):
        output.append(html.escape(text[position : match.start()]))
        if match.group(2) is not None:
            title = match.group(2).strip()
            label = match.group(3).strip() if match.group(3) is not None else title
            target = title_map.get(title.lower())
            if target:
                output.append(
                    f'<a href="{html.escape(target.slug + ".html", quote=True)}">{html.escape(label)}</a>'
                )
            else:
                href = f"{slugify(title)}.html"
                output.append(
                    f'<a href="{html.escape(href, quote=True)}" data-wikilink="missing">{html.escape(label)}</a>'
                )
        else:
            label = match.group(4)
            target = match.group(5).strip()
            if target.startswith(("http://", "https://")):
                href = target
            else:
                resolved = resolve_local_link(item.source, target, slug_map, source_map)
                href = f"{resolved}.html" if resolved else target
            output.append(f'<a href="{html.escape(href, quote=True)}">{html.escape(label)}</a>')
        position = match.end()
    output.append(html.escape(text[position:]))
    return "".join(output)


def render_body(item, title_map, slug_map, source_map):
    parts = []
    paragraph = []

    def flush():
        if paragraph:
            text = " ".join(paragraph)
            parts.append(f"<p>{render_inline(text, item, title_map, slug_map, source_map)}</p>")
            paragraph.clear()

    for raw in item.body.splitlines():
        line = raw.strip()
        if not line:
            flush()
            continue
        if line.startswith("# "):
            flush()
            text = line[2:].strip()
            parts.append(f'<h1 id="{html.escape(slugify(text), quote=True)}">{html.escape(text)}</h1>')
        elif line.startswith("## "):
            flush()
            text = line[3:].strip()
            parts.append(f'<h2 id="{html.escape(slugify(text), quote=True)}">{html.escape(text)}</h2>')
        else:
            paragraph.append(line)
    flush()
    return "\n".join(parts)


def render_context(items):
    public_items = [item for item in items if not item.draft]
    title_map = {}
    slug_map = {item.slug: item for item in public_items}
    source_map = {item.source: item for item in public_items}
    for item in public_items:
        title_map.setdefault(item.title.lower(), item)
    return title_map, slug_map, source_map


def plain_text_from_body(item, context):
    rendered = render_body(item, *context)
    text = re.sub(r"<[^>]+>", " ", rendered)
    return " ".join(html.unescape(text).split())


def full_url(config, path):
    if not config.base_url:
        return path
    return config.base_url.rstrip("/") + "/" + path.lstrip("/")


def paginate(items, size):
    if not items:
        return [[]]
    return [items[index : index + size] for index in range(0, len(items), size)]


def html_document(title, body):
    return (
        "<!doctype html>\n"
        "<html>\n"
        "<head>\n"
        f"<meta charset=\"utf-8\">\n<title>{html.escape(title)}</title>\n"
        "</head>\n"
        f"<body>\n{body}\n</body>\n"
        "</html>\n"
    )


def link_list(items):
    lines = ["<ul>"]
    for item in items:
        lines.append(
            f'<li><a href="{html.escape(item.slug + ".html", quote=True)}">{html.escape(item.title)}</a></li>'
        )
    lines.append("</ul>")
    return "\n".join(lines)


def path_link_list(paths):
    lines = ["<ul>"]
    for path in paths:
        lines.append(f'<li><a href="{html.escape(path, quote=True)}">{html.escape(path)}</a></li>')
    lines.append("</ul>")
    return "\n".join(lines)


def build_listing_files(files, manifest_group, base_name, title, items, config):
    pages = paginate(items, config.pagination)
    paths = []
    for index, page_items in enumerate(pages, 1):
        if index == 1:
            filename = f"{base_name}.html"
        else:
            filename = f"{base_name}-{index}.html"
        files[filename] = html_document(title, link_list(page_items))
        paths.append(filename)
    manifest_group.extend(paths)
    return paths


def feed_item(item, config):
    return {
        "title": item.title,
        "slug": item.slug,
        "url": full_url(config, f"{item.slug}.html"),
        "date": item.date,
        "tags": item.tags,
        "stream": item.stream,
        "description": item.description,
    }


def compact_json(value):
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def compute_site(items, config):
    posts, pages, drafts = ordered_items(items)
    context = render_context(items)
    title_map, slug_map, source_map = context
    files = {}
    manifest = {key: [] for key in MANIFEST_KEYS}

    for item in posts:
        body = render_body(item, title_map, slug_map, source_map)
        if item.backlinks:
            backlink_lines = ["<section><h2>Backlinks</h2>", "<ul>"]
            for slug in item.backlinks:
                backlink_lines.append(
                    f'<li><a href="{html.escape(slug + ".html", quote=True)}">{html.escape(slug)}</a></li>'
                )
            backlink_lines.extend(["</ul>", "</section>"])
            body = body + "\n" + "\n".join(backlink_lines)
        files[f"{item.slug}.html"] = html_document(item.title, body)
        manifest["posts"].append(f"{item.slug}.html")

    for item in pages:
        body = render_body(item, title_map, slug_map, source_map)
        if item.backlinks:
            backlink_lines = ["<section><h2>Backlinks</h2>", "<ul>"]
            for slug in item.backlinks:
                backlink_lines.append(
                    f'<li><a href="{html.escape(slug + ".html", quote=True)}">{html.escape(slug)}</a></li>'
                )
            backlink_lines.extend(["</ul>", "</section>"])
            body = body + "\n" + "\n".join(backlink_lines)
        files[f"{item.slug}.html"] = html_document(item.title, body)
        manifest["pages"].append(f"{item.slug}.html")

    index_posts = [item for item in posts if item.stream == "index"]
    build_listing_files(files, manifest["index"], "index", config.site_name, index_posts, config)

    if pages:
        files["pages.html"] = html_document("Pages", link_list(pages))
        manifest["pages"].append("pages.html")

    tag_posts = collect_tag_posts(posts)
    generated_tag_pages = []
    for tag_slug in sorted(tag_posts):
        paths = build_listing_files(
            files,
            manifest["tags"],
            f"tag-{tag_slug}",
            f"tag:{tag_slug}",
            tag_posts[tag_slug],
            config,
        )
        generated_tag_pages.extend(paths)
    if generated_tag_pages:
        files["tags.html"] = html_document("Tags", path_link_list(generated_tag_pages))
        manifest["tags"].append("tags.html")

    stream_posts = collect_stream_posts(posts)
    generated_stream_pages = []
    for stream in sorted(stream_posts):
        paths = build_listing_files(
            files,
            manifest["streams"],
            stream,
            f"stream:{stream}",
            stream_posts[stream],
            config,
        )
        generated_stream_pages.extend(paths)
    if generated_stream_pages:
        files["streams.html"] = html_document("Streams", path_link_list(generated_stream_pages))
        manifest["streams"].append("streams.html")

    archive_posts = collect_archive_posts(posts)
    generated_archive_pages = []
    for year in sorted(archive_posts, reverse=True):
        paths = build_listing_files(
            files,
            manifest["archives"],
            f"archive-{year}",
            f"archive:{year}",
            archive_posts[year],
            config,
        )
        generated_archive_pages.extend(paths)
    if generated_archive_pages:
        files["archive.html"] = html_document("Archive", path_link_list(generated_archive_pages))
        manifest["archives"].append("archive.html")

    if config.json_feed:
        feed = {"title": config.site_name, "items": [feed_item(item, config) for item in index_posts]}
        files["feed.json"] = compact_json(feed) + "\n"
        manifest["feeds"].append("feed.json")
        for tag_slug in sorted(tag_posts):
            filename = f"tag-{tag_slug}.json"
            feed = {"title": f"tag:{tag_slug}", "items": [feed_item(item, config) for item in tag_posts[tag_slug]]}
            files[filename] = compact_json(feed) + "\n"
            manifest["feeds"].append(filename)
        for stream in sorted(stream_posts):
            filename = f"{stream}.json"
            feed = {"title": f"stream:{stream}", "items": [feed_item(item, config) for item in stream_posts[stream]]}
            files[filename] = compact_json(feed) + "\n"
            manifest["feeds"].append(filename)
        for year in sorted(archive_posts, reverse=True):
            filename = f"archive-{year}.json"
            feed = {"title": f"archive:{year}", "items": [feed_item(item, config) for item in archive_posts[year]]}
            files[filename] = compact_json(feed) + "\n"
            manifest["feeds"].append(filename)

    if config.enable_search:
        search = []
        for item in posts + pages:
            search.append(
                {
                    "title": item.title,
                    "slug": item.slug,
                    "url": full_url(config, f"{item.slug}.html"),
                    "kind": item.kind,
                    "tags": item.tags,
                    "stream": item.stream,
                    "text": plain_text_from_body(item, context),
                }
            )
        files["search_index.json"] = compact_json(search) + "\n"
        manifest["search"].append("search_index.json")

    manifest["misc"].append("urls.json")
    add_summary(manifest)
    files["urls.json"] = compact_json(manifest) + "\n"
    return manifest, files


def collect_tag_posts(posts):
    tag_posts = {}
    for post in posts:
        seen = set()
        for tag in post.tags:
            tag_slug = slugify(tag)
            if not tag_slug or tag_slug in seen:
                continue
            seen.add(tag_slug)
            tag_posts.setdefault(tag_slug, []).append(post)
    return tag_posts


def collect_stream_posts(posts):
    stream_posts = {}
    for post in posts:
        if post.stream in {None, "index", "draft"}:
            continue
        stream_posts.setdefault(post.stream, []).append(post)
    return stream_posts


def collect_archive_posts(posts):
    archive_posts = {}
    for post in posts:
        year = post.date[:4]
        archive_posts.setdefault(year, []).append(post)
    return archive_posts


def add_summary(manifest):
    summary = {}
    for key in MANIFEST_KEYS:
        summary[key] = len(manifest[key])
    summary["total"] = sum(summary[key] for key in MANIFEST_KEYS) - 1
    manifest["summary"] = summary


def inspect_data(items):
    posts, pages, drafts = ordered_items(items)
    tags = {}
    for tag_slug, tag_items in collect_tag_posts(posts).items():
        tags[tag_slug] = [item.slug for item in tag_items]
    streams = {}
    for post in posts:
        if post.stream == "draft":
            continue
        streams.setdefault(post.stream or "index", []).append(post.slug)
    return {
        "posts": [item.public_dict() for item in posts],
        "pages": [item.public_dict() for item in pages],
        "tags": {key: tags[key] for key in sorted(tags)},
        "streams": {key: streams[key] for key in sorted(streams)},
        "drafts": [item.public_dict() for item in drafts],
    }


def load_state(input_arg, config_arg):
    input_path = Path(input_arg)
    config_path = Path(config_arg) if config_arg else input_path / "marmite.yaml"
    config = parse_config(config_path)
    items = load_items(input_path)
    return items, config


def write_site(output_arg, files):
    output = Path(output_arg)
    parent = output.parent if output.parent != Path("") else Path(".")
    temp_dir = Path(tempfile.mkdtemp(prefix=".minisite-", dir=str(parent)))
    try:
        for relative, content in files.items():
            target = temp_dir / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
        output.mkdir(parents=True, exist_ok=True)
        old_paths = read_old_manifest_paths(output)
        new_paths = set(files)
        for relative in sorted(old_paths | new_paths):
            target = output / relative
            if target.exists() and target.is_file():
                target.unlink()
        for relative in sorted(files):
            shutil.move(str(temp_dir / relative), str(output / relative))
    except OSError as exc:
        for relative in files:
            target = output / relative
            try:
                if target.exists() and target.is_file():
                    target.unlink()
            except OSError:
                pass
        raise MiniSiteError(f"unable to create or write output directory: {exc}") from exc
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def read_old_manifest_paths(output):
    manifest_path = output / "urls.json"
    if not manifest_path.exists():
        return set()
    try:
        old = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"urls.json"}
    paths = set()
    if isinstance(old, dict):
        for key in MANIFEST_KEYS:
            value = old.get(key, [])
            if isinstance(value, list):
                paths.update(path for path in value if isinstance(path, str))
    paths.add("urls.json")
    return paths


def command_inspect(args):
    items, _config = load_state(args.input, args.config)
    print(compact_json(inspect_data(items)))


def command_urls(args):
    items, config = load_state(args.input, args.config)
    manifest, _files = compute_site(items, config)
    print(compact_json(manifest))


def command_build(args):
    items, config = load_state(args.input, args.config)
    manifest, files = compute_site(items, config)
    write_site(args.output, files)
    print(compact_json(manifest))


def make_parser():
    parser = argparse.ArgumentParser(prog="minisite.py")
    subparsers = parser.add_subparsers(dest="command", required=True)

    build = subparsers.add_parser("build")
    build.add_argument("--input", required=True)
    build.add_argument("--output", required=True)
    build.add_argument("--config")
    build.set_defaults(func=command_build)

    inspect = subparsers.add_parser("inspect")
    inspect.add_argument("--input", required=True)
    inspect.add_argument("--config")
    inspect.set_defaults(func=command_inspect)

    urls = subparsers.add_parser("urls")
    urls.add_argument("--input", required=True)
    urls.add_argument("--config")
    urls.set_defaults(func=command_urls)

    return parser


def main(argv=None):
    parser = make_parser()
    args = parser.parse_args(argv)
    try:
        args.func(args)
    except MiniSiteError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
