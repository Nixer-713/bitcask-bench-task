#!/usr/bin/env python3
import argparse
import datetime as _datetime
import html
import json
import os
import posixpath
import re
import shutil
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path


DEFAULT_CONFIG = {
    "site_name": "Mini Marmite",
    "base_url": "",
    "pagination": 10,
    "json_feed": True,
    "enable_search": True,
}

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

DATE_PREFIX_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})-(.+)$")
DATETIME_PREFIX_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})-\d{2}-\d{2}-\d{2}-(.+)$")
STREAM_DATE_PREFIX_RE = re.compile(r"^([A-Za-z0-9][A-Za-z0-9_-]*)-(\d{4}-\d{2}-\d{2})-(.+)$")
STREAM_DATETIME_PREFIX_RE = re.compile(
    r"^([A-Za-z0-9][A-Za-z0-9_-]*)-(\d{4}-\d{2}-\d{2})-\d{2}-\d{2}-\d{2}-(.+)$"
)
STREAM_FRONTMATTER_RE = re.compile(r"^([A-Za-z0-9][A-Za-z0-9_-]*)-(.+)$")
MARKDOWN_LINK_RE = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
WIKILINK_RE = re.compile(r"\[\[([^\]|]+)(?:\|([^\]]+))?\]\]")
INLINE_RE = re.compile(r"\[\[([^\]|]+)(?:\|([^\]]+))?\]\]|\[([^\]]+)\]\(([^)]+)\)")


class MiniSiteError(Exception):
    pass


@dataclass
class ContentItem:
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

    def model(self):
        return {
            "title": self.title,
            "slug": self.slug,
            "source": self.source,
            "kind": self.kind,
            "date": self.date,
            "tags": list(self.tags),
            "stream": self.stream,
            "description": self.description,
            "draft": self.draft,
            "links_to": list(self.links_to),
            "backlinks": list(self.backlinks),
        }


def compact_json(value):
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def slugify(value):
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug


def public_slug(value, fallback="item"):
    return slugify(value) or fallback


def unquote(value):
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value


def parse_bool(value, key):
    lowered = unquote(value).strip().lower()
    if lowered == "true":
        return True
    if lowered == "false":
        return False
    raise MiniSiteError(f"invalid {key} value: {value}")


def parse_date(value, context):
    raw = unquote(value).strip()
    for fmt in ("%Y-%m-%d", "%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S"):
        try:
            return _datetime.datetime.strptime(raw, fmt).date().isoformat()
        except ValueError:
            pass
    raise MiniSiteError(f"invalid date in {context}: {value}")


def parse_tags(value):
    raw = value.strip()
    if raw.startswith("[") or raw.endswith("]"):
        if not (raw.startswith("[") and raw.endswith("]")):
            raise MiniSiteError(f"invalid tags value: {value}")
        raw = raw[1:-1]
    else:
        raw = unquote(raw)
    tags = []
    for part in raw.split(","):
        tag = unquote(part).strip()
        if tag:
            tags.append(tag)
    return tags


def parse_config(input_dir, config_path):
    config = dict(DEFAULT_CONFIG)
    path = Path(config_path) if config_path else Path(input_dir) / "marmite.yaml"
    if not path.exists():
        return config
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise MiniSiteError(f"unable to read config: {exc}") from exc

    for line_no, line in enumerate(lines, 1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if ":" not in stripped:
            continue
        key, raw_value = stripped.split(":", 1)
        key = key.strip()
        raw_value = raw_value.strip()
        if key == "site_name":
            config[key] = unquote(raw_value)
        elif key == "base_url":
            config[key] = unquote(raw_value).rstrip("/")
        elif key == "pagination":
            try:
                pagination = int(unquote(raw_value))
            except ValueError as exc:
                raise MiniSiteError(f"invalid pagination value on line {line_no}") from exc
            if pagination <= 0:
                raise MiniSiteError(f"invalid pagination value on line {line_no}")
            config[key] = pagination
        elif key == "json_feed":
            config[key] = parse_bool(raw_value, key)
        elif key == "enable_search":
            config[key] = parse_bool(raw_value, key)
    return config


def split_frontmatter(text, source):
    lines = text.splitlines()
    if not lines or lines[0] != "---":
        return {}, text
    end = None
    for idx in range(1, len(lines)):
        if lines[idx] == "---":
            end = idx
            break
    if end is None:
        return {}, text

    metadata = {}
    for line_no, line in enumerate(lines[1:end], 2):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if ":" not in stripped:
            continue
        key, raw_value = stripped.split(":", 1)
        key = key.strip()
        raw_value = raw_value.strip()
        if key == "title":
            metadata[key] = unquote(raw_value)
        elif key == "slug":
            metadata[key] = unquote(raw_value)
        elif key == "date":
            metadata[key] = parse_date(raw_value, f"{source}:{line_no}")
        elif key == "tags":
            metadata[key] = parse_tags(raw_value)
        elif key == "stream":
            metadata[key] = public_slug(unquote(raw_value), "index")
        elif key == "description":
            metadata[key] = unquote(raw_value)

    body = "\n".join(lines[end + 1 :])
    if text.endswith("\n") and body:
        body += "\n"
    return metadata, body


def first_heading(body):
    for line in body.splitlines():
        if line.startswith("# "):
            title = line[2:].strip()
            if title:
                return title
    return None


def filename_parts(stem, frontmatter_date):
    match = STREAM_DATETIME_PREFIX_RE.match(stem)
    if match and valid_date(match.group(2)):
        stream, date, rest = match.groups()
        stream = public_slug(stream, "index")
        return date, stream, f"{stream}-{rest}", rest, True

    match = STREAM_DATE_PREFIX_RE.match(stem)
    if match and valid_date(match.group(2)):
        stream, date, rest = match.groups()
        stream = public_slug(stream, "index")
        return date, stream, f"{stream}-{rest}", rest, True

    match = DATETIME_PREFIX_RE.match(stem)
    if match and valid_date(match.group(1)):
        date, rest = match.groups()
        return date, None, rest, rest, True

    match = DATE_PREFIX_RE.match(stem)
    if match and valid_date(match.group(1)):
        date, rest = match.groups()
        return date, None, rest, rest, True

    if frontmatter_date:
        match = STREAM_FRONTMATTER_RE.match(stem)
        if match:
            stream, rest = match.groups()
            stream = public_slug(stream, "index")
            return None, stream, f"{stream}-{rest}", rest, True

    return None, None, stem, stem, False


def valid_date(value):
    try:
        _datetime.date.fromisoformat(value)
    except ValueError:
        return False
    return True


def collect_markdown_files(input_dir):
    root = Path(input_dir)
    if not root.is_dir():
        raise MiniSiteError(f"missing input directory: {input_dir}")
    content_root = root / "content"
    if not content_root.is_dir():
        content_root = root
    files = []
    for path in content_root.rglob("*.md"):
        if path.name.startswith("_"):
            continue
        if path.is_file():
            files.append(path)
    files.sort(key=lambda p: p.relative_to(content_root).as_posix())
    return content_root, files


def parse_items(input_dir, config_path=None):
    config = parse_config(input_dir, config_path)
    content_root, files = collect_markdown_files(input_dir)
    items = []

    for path in files:
        source = path.relative_to(content_root).as_posix()
        try:
            text = path.read_text(encoding="utf-8")
        except OSError as exc:
            raise MiniSiteError(f"unable to read content {source}: {exc}") from exc
        metadata, body = split_frontmatter(text, source)
        frontmatter_date = metadata.get("date")
        file_date, file_stream, file_slug_base, file_title_base, recognized = filename_parts(
            path.stem, frontmatter_date
        )
        date = frontmatter_date or file_date
        kind = "post" if date else "page"
        title = metadata.get("title") or first_heading(body) or file_title_base

        if "slug" in metadata:
            base_slug = public_slug(metadata["slug"])
        elif recognized:
            base_slug = public_slug(file_slug_base)
        elif metadata.get("title") or first_heading(body):
            base_slug = public_slug(title)
        else:
            base_slug = public_slug(file_slug_base)

        if kind == "post":
            stream = metadata.get("stream") or file_stream or "index"
            if stream != "index" and not base_slug.startswith(f"{stream}-"):
                base_slug = f"{stream}-{base_slug}"
        else:
            stream = None

        draft = kind == "post" and stream == "draft"
        tags = metadata.get("tags", [])
        item = ContentItem(
            title=title,
            slug=base_slug,
            source=source,
            kind=kind,
            date=date,
            tags=tags,
            stream=stream,
            description=metadata.get("description"),
            draft=draft,
            body=body,
        )
        items.append(item)

    seen = {}
    for item in items:
        if item.draft:
            continue
        if item.slug in seen:
            raise MiniSiteError(f"duplicate final slug among non-draft content: {item.slug}")
        seen[item.slug] = item.source

    items = order_items(items)
    compute_links(items)
    return config, items


def order_items(items):
    posts = sorted(
        [item for item in items if item.kind == "post"],
        key=lambda item: (-_datetime.date.fromisoformat(item.date).toordinal(), item.slug),
    )
    pages = sorted(
        [item for item in items if item.kind == "page"],
        key=lambda item: (item.title.lower(), item.slug),
    )
    post_rank = {id(item): idx for idx, item in enumerate(posts)}
    page_rank = {id(item): idx for idx, item in enumerate(pages)}

    def key(item):
        if item.kind == "post":
            return (0, post_rank[id(item)])
        return (1, page_rank[id(item)])

    return sorted(items, key=key)


def public_items(items):
    return [item for item in items if not item.draft]


def public_posts(items):
    return [item for item in items if item.kind == "post" and not item.draft]


def public_pages(items):
    return [item for item in items if item.kind == "page" and not item.draft]


def build_public_maps(items):
    publics = public_items(items)
    title_map = {}
    slug_map = {}
    source_map = {}
    basename_map = {}
    for item in publics:
        title_map.setdefault(item.title.casefold(), item.slug)
        slug_map[item.slug] = item.slug
        source_map[item.source] = item.slug
        basename_map.setdefault(Path(item.source).name, item.slug)
        basename_map.setdefault(Path(item.source).with_suffix(".html").name, item.slug)
        basename_map.setdefault(f"{item.slug}.html", item.slug)
        basename_map.setdefault(f"{item.slug}.md", item.slug)
    return title_map, slug_map, source_map, basename_map


def resolve_local_target(item, target, source_map, basename_map, slug_map):
    target = target.strip()
    target_no_anchor = target.split("#", 1)[0]
    if not target_no_anchor.endswith((".md", ".html")):
        return None
    base_dir = posixpath.dirname(item.source)
    joined = posixpath.normpath(posixpath.join(base_dir, target_no_anchor))
    if joined == ".":
        joined = target_no_anchor
    md_joined = re.sub(r"\.html$", ".md", joined)
    if joined in source_map:
        return source_map[joined]
    if md_joined in source_map:
        return source_map[md_joined]
    name = Path(target_no_anchor).name
    if name in basename_map:
        return basename_map[name]
    stem = Path(target_no_anchor).stem
    if stem in slug_map:
        return slug_map[stem]
    return None


def extract_links(item, title_map, source_map, basename_map, slug_map):
    links = []
    seen = set()

    def add(slug):
        if slug and slug not in seen:
            seen.add(slug)
            links.append(slug)

    for match in WIKILINK_RE.finditer(item.body):
        title = match.group(1).strip()
        add(title_map.get(title.casefold()))

    for match in MARKDOWN_LINK_RE.finditer(item.body):
        target = match.group(2).strip()
        if target.startswith(("http://", "https://")):
            continue
        add(resolve_local_target(item, target, source_map, basename_map, slug_map))

    return links


def compute_links(items):
    title_map, slug_map, source_map, basename_map = build_public_maps(items)
    for item in items:
        item.links_to = extract_links(item, title_map, source_map, basename_map, slug_map)
        item.backlinks = []

    backlink_map = {item.slug: [] for item in public_items(items)}
    for item in public_items(items):
        for slug in item.links_to:
            if slug in backlink_map and item.slug not in backlink_map[slug]:
                backlink_map[slug].append(item.slug)

    for item in public_items(items):
        item.backlinks = backlink_map.get(item.slug, [])


def inspect_payload(items):
    posts = [item.model() for item in public_posts(items)]
    pages = [item.model() for item in public_pages(items)]
    drafts = [item.model() for item in items if item.draft]

    tags = {}
    for item in public_posts(items):
        for tag in item.tags:
            tag_slug = public_slug(tag)
            if tag_slug:
                tags.setdefault(tag_slug, []).append(item.slug)

    streams = {}
    for item in public_posts(items):
        if item.stream == "draft":
            continue
        streams.setdefault(item.stream or "index", []).append(item.slug)

    tags = {key: tags[key] for key in sorted(tags)}
    streams = {key: streams[key] for key in sorted(streams)}
    return {"posts": posts, "pages": pages, "tags": tags, "streams": streams, "drafts": drafts}


def url_for(config, path):
    if not config["base_url"]:
        return path
    return f"{config['base_url'].rstrip('/')}/{path.lstrip('/')}"


def render_inline(text, item, title_map, source_map, basename_map, slug_map):
    out = []
    pos = 0
    for match in INLINE_RE.finditer(text):
        out.append(html.escape(text[pos : match.start()]))
        if match.group(1) is not None:
            title = match.group(1).strip()
            label = match.group(2).strip() if match.group(2) is not None else title
            slug = title_map.get(title.casefold())
            if slug:
                out.append(f'<a href="{html.escape(slug + ".html", quote=True)}">{html.escape(label)}</a>')
            else:
                href = f"{public_slug(title, 'missing')}.html"
                out.append(
                    f'<a data-wikilink="missing" href="{html.escape(href, quote=True)}">'
                    f"{html.escape(label)}</a>"
                )
        else:
            label = match.group(3)
            target = match.group(4).strip()
            if target.startswith(("http://", "https://")):
                href = target
            else:
                slug = resolve_local_target(item, target, source_map, basename_map, slug_map)
                if slug:
                    href = f"{slug}.html"
                else:
                    href = f"{public_slug(Path(target.split('#', 1)[0]).stem, 'missing')}.html"
            out.append(f'<a href="{html.escape(href, quote=True)}">{html.escape(label)}</a>')
        pos = match.end()
    out.append(html.escape(text[pos:]))
    return "".join(out)


def render_markdown(item, maps):
    title_map, slug_map, source_map, basename_map = maps
    rendered = []
    for line in item.body.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("## "):
            text = stripped[3:].strip()
            rendered.append(f'<h2 id="{html.escape(public_slug(text), quote=True)}">{html.escape(text)}</h2>')
        elif stripped.startswith("# "):
            text = stripped[2:].strip()
            rendered.append(f'<h1 id="{html.escape(public_slug(text), quote=True)}">{html.escape(text)}</h1>')
        else:
            rendered.append(f"<p>{render_inline(stripped, item, title_map, source_map, basename_map, slug_map)}</p>")
    return "\n".join(rendered)


def plain_text(item):
    text = item.body
    text = WIKILINK_RE.sub(lambda m: m.group(2) if m.group(2) is not None else m.group(1), text)
    text = MARKDOWN_LINK_RE.sub(lambda m: m.group(1), text)
    lines = []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("## "):
            stripped = stripped[3:].strip()
        elif stripped.startswith("# "):
            stripped = stripped[2:].strip()
        if stripped:
            lines.append(stripped)
    return "\n".join(lines)


def page_shell(title, body):
    escaped_title = html.escape(title)
    return (
        "<!doctype html>\n"
        "<html><head><meta charset=\"utf-8\">"
        f"<title>{escaped_title}</title>"
        "</head><body>\n"
        f"{body}\n"
        "</body></html>\n"
    )


def render_content_page(item, maps):
    parts = [render_markdown(item, maps)]
    if item.backlinks:
        parts.append('<section class="backlinks"><h2 id="backlinks">Backlinks</h2><ul>')
        for slug in item.backlinks:
            parts.append(f'<li><a href="{html.escape(slug + ".html", quote=True)}">{html.escape(slug)}</a></li>')
        parts.append("</ul></section>")
    return page_shell(item.title, "\n".join(parts))


def render_listing(title, entries):
    lines = [f"<h1>{html.escape(title)}</h1>", "<ul>"]
    for href, label in entries:
        lines.append(f'<li><a href="{html.escape(href, quote=True)}">{html.escape(label)}</a></li>')
    lines.append("</ul>")
    return page_shell(title, "\n".join(lines))


def chunks(values, size):
    if not values:
        return [[]]
    return [values[index : index + size] for index in range(0, len(values), size)]


def paginated_paths(prefix, values, page_size):
    paths = []
    for index, _chunk in enumerate(chunks(values, page_size), 1):
        if index == 1:
            paths.append(f"{prefix}.html")
        else:
            paths.append(f"{prefix}-{index}.html")
    return paths


def feed_item(config, item):
    return {
        "title": item.title,
        "slug": item.slug,
        "url": url_for(config, f"{item.slug}.html"),
        "date": item.date,
        "tags": list(item.tags),
        "stream": item.stream,
        "description": item.description,
    }


def write_listing(files, path, title, items):
    entries = [(f"{item.slug}.html", item.title) for item in items]
    files[path] = render_listing(title, entries)


def add_paginated_listing(files, manifest_group, prefix, title, items, page_size):
    for index, chunk in enumerate(chunks(items, page_size), 1):
        path = f"{prefix}.html" if index == 1 else f"{prefix}-{index}.html"
        suffix = "" if index == 1 else f" {index}"
        write_listing(files, path, f"{title}{suffix}", chunk)
        manifest_group.append(path)


def generated_site(config, items):
    files = {}
    manifest = {key: [] for key in MANIFEST_KEYS}
    maps = build_public_maps(items)
    posts = public_posts(items)
    pages = public_pages(items)
    page_size = config["pagination"]

    for item in posts:
        path = f"{item.slug}.html"
        files[path] = render_content_page(item, maps)
        manifest["posts"].append(path)

    for item in pages:
        path = f"{item.slug}.html"
        files[path] = render_content_page(item, maps)
        manifest["pages"].append(path)

    index_posts = [item for item in posts if item.stream == "index"]
    add_paginated_listing(files, manifest["index"], "index", config["site_name"], index_posts, page_size)

    if pages:
        write_listing(files, "pages.html", "Pages", pages)
        manifest["pages"].append("pages.html")

    tag_posts = {}
    for item in posts:
        for tag in item.tags:
            tag_slug = public_slug(tag)
            if tag_slug:
                tag_posts.setdefault(tag_slug, []).append(item)
    for tag_slug in sorted(tag_posts):
        add_paginated_listing(
            files,
            manifest["tags"],
            f"tag-{tag_slug}",
            f"Tag: {tag_slug}",
            tag_posts[tag_slug],
            page_size,
        )
    if tag_posts:
        files["tags.html"] = render_listing(
            "Tags", [(f"tag-{tag}.html", tag) for tag in sorted(tag_posts)]
        )
        manifest["tags"].append("tags.html")

    stream_posts = {}
    for item in posts:
        if item.stream not in {"index", "draft"}:
            stream_posts.setdefault(item.stream, []).append(item)
    for stream in sorted(stream_posts):
        add_paginated_listing(
            files,
            manifest["streams"],
            stream,
            f"Stream: {stream}",
            stream_posts[stream],
            page_size,
        )
    if stream_posts:
        files["streams.html"] = render_listing(
            "Streams", [(f"{stream}.html", stream) for stream in sorted(stream_posts)]
        )
        manifest["streams"].append("streams.html")

    archive_posts = {}
    for item in posts:
        archive_posts.setdefault(item.date[:4], []).append(item)
    for year in sorted(archive_posts, reverse=True):
        add_paginated_listing(
            files,
            manifest["archives"],
            f"archive-{year}",
            f"Archive: {year}",
            archive_posts[year],
            page_size,
        )
    if archive_posts:
        files["archive.html"] = render_listing(
            "Archive", [(f"archive-{year}.html", year) for year in sorted(archive_posts, reverse=True)]
        )
        manifest["archives"].append("archive.html")

    if config["json_feed"]:
        files["feed.json"] = compact_json(
            {"title": config["site_name"], "items": [feed_item(config, item) for item in index_posts]}
        ) + "\n"
        manifest["feeds"].append("feed.json")
        for tag_slug in sorted(tag_posts):
            path = f"tag-{tag_slug}.json"
            files[path] = compact_json(
                {"title": f"tag:{tag_slug}", "items": [feed_item(config, item) for item in tag_posts[tag_slug]]}
            ) + "\n"
            manifest["feeds"].append(path)
        for stream in sorted(stream_posts):
            path = f"{stream}.json"
            files[path] = compact_json(
                {"title": f"stream:{stream}", "items": [feed_item(config, item) for item in stream_posts[stream]]}
            ) + "\n"
            manifest["feeds"].append(path)
        for year in sorted(archive_posts, reverse=True):
            path = f"archive-{year}.json"
            files[path] = compact_json(
                {"title": f"archive:{year}", "items": [feed_item(config, item) for item in archive_posts[year]]}
            ) + "\n"
            manifest["feeds"].append(path)

    if config["enable_search"]:
        search = []
        for item in posts + pages:
            search.append(
                {
                    "title": item.title,
                    "slug": item.slug,
                    "url": url_for(config, f"{item.slug}.html"),
                    "kind": item.kind,
                    "tags": list(item.tags),
                    "stream": item.stream,
                    "text": plain_text(item),
                }
            )
        files["search_index.json"] = compact_json(search) + "\n"
        manifest["search"].append("search_index.json")

    manifest["misc"].append("urls.json")
    add_summary(manifest)
    files["urls.json"] = compact_json(manifest) + "\n"
    return manifest, files


def add_summary(manifest):
    summary = {}
    for key in MANIFEST_KEYS:
        summary[key] = len(manifest[key])
    summary["total"] = sum(summary.values()) - 1
    manifest["summary"] = summary


def previous_manifest_paths(output_dir):
    urls = Path(output_dir) / "urls.json"
    if not urls.exists():
        return set()
    try:
        manifest = json.loads(urls.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"urls.json"}
    paths = set()
    for key in MANIFEST_KEYS:
        value = manifest.get(key)
        if isinstance(value, list):
            paths.update(path for path in value if isinstance(path, str))
    paths.add("urls.json")
    return paths


def write_site(output_dir, files):
    output = Path(output_dir)
    parent = output.parent if str(output.parent) else Path(".")
    try:
        parent.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise MiniSiteError(f"unable to create or write output directory: {exc}") from exc
    temp_dir = Path(tempfile.mkdtemp(prefix=".minisite-", dir=str(parent)))
    written = []
    try:
        for rel_path, content in files.items():
            if "/" in rel_path or rel_path.startswith("."):
                raise MiniSiteError(f"invalid generated path: {rel_path}")
            target = temp_dir / rel_path
            target.write_text(content, encoding="utf-8")
            written.append(rel_path)
        output.mkdir(parents=True, exist_ok=True)
        old_paths = previous_manifest_paths(output)
        current_paths = set(files)
        for rel_path in old_paths | current_paths:
            target = output / rel_path
            if target.exists() and target.is_file():
                target.unlink()
        for rel_path in written:
            os.replace(temp_dir / rel_path, output / rel_path)
    except OSError as exc:
        raise MiniSiteError(f"unable to create or write output directory: {exc}") from exc
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def parse_state(input_path, config_path):
    return parse_items(input_path, config_path)


def command_inspect(args):
    _config, items = parse_state(args.input, args.config)
    return inspect_payload(items)


def command_urls(args):
    config, items = parse_state(args.input, args.config)
    manifest, _files = generated_site(config, items)
    return manifest


def command_build(args):
    config, items = parse_state(args.input, args.config)
    manifest, files = generated_site(config, items)
    write_site(args.output, files)
    return manifest


def make_parser():
    parser = argparse.ArgumentParser(prog="minisite.py")
    subparsers = parser.add_subparsers(dest="command", required=True)

    build = subparsers.add_parser("build")
    build.add_argument("--input", required=True)
    build.add_argument("--output", required=True)
    build.add_argument("--config")
    build.set_defaults(func=command_build)

    inspect_cmd = subparsers.add_parser("inspect")
    inspect_cmd.add_argument("--input", required=True)
    inspect_cmd.add_argument("--config")
    inspect_cmd.set_defaults(func=command_inspect)

    urls = subparsers.add_parser("urls")
    urls.add_argument("--input", required=True)
    urls.add_argument("--config")
    urls.set_defaults(func=command_urls)
    return parser


def main(argv=None):
    parser = make_parser()
    args = parser.parse_args(argv)
    try:
        result = args.func(args)
    except MiniSiteError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(compact_json(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
