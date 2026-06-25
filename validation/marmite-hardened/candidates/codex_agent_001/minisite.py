#!/usr/bin/env python3
import argparse
import datetime as _dt
import html
import json
import posixpath
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path


DEFAULT_CONFIG = {
    "site_name": "Mini Marmite",
    "base_url": "",
    "pagination": 10,
    "json_feed": True,
    "enable_search": True,
}

MANIFEST_GROUPS = [
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

    def model(self) -> dict:
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


@dataclass
class SiteState:
    config: dict
    items: list[ContentItem]
    posts: list[ContentItem]
    pages: list[ContentItem]
    drafts: list[ContentItem]
    public_by_slug: dict[str, ContentItem]
    public_by_title: dict[str, ContentItem]
    public_by_source: dict[str, ContentItem]

    def public_items(self) -> list[ContentItem]:
        return self.posts + self.pages


def compact_json(value) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def slugify(text: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "-", text.lower()).strip("-")


def strip_quotes(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
        return value[1:-1]
    return value


def parse_bool(value: str, label: str) -> bool:
    raw = strip_quotes(value).strip().lower()
    if raw == "true":
        return True
    if raw == "false":
        return False
    raise MiniSiteError(f"invalid boolean for {label}: {value}")


def parse_date_value(value: str, label: str) -> str:
    raw = strip_quotes(value).strip()
    for fmt in ("%Y-%m-%d", "%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S"):
        try:
            return _dt.datetime.strptime(raw, fmt).strftime("%Y-%m-%d")
        except ValueError:
            pass
    raise MiniSiteError(f"invalid date for {label}: {value}")


def split_csv(value: str) -> list[str]:
    parts = []
    current = []
    quote = None
    for char in value:
        if quote:
            current.append(char)
            if char == quote:
                quote = None
        elif char in ("'", '"'):
            quote = char
            current.append(char)
        elif char == ",":
            parts.append("".join(current))
            current = []
        else:
            current.append(char)
    if quote:
        raise MiniSiteError(f"unterminated quoted value: {value}")
    parts.append("".join(current))
    return parts


def parse_tags(value: str) -> list[str]:
    raw = value.strip()
    if raw.startswith("[") or raw.endswith("]"):
        if not (raw.startswith("[") and raw.endswith("]")):
            raise MiniSiteError(f"invalid tags value: {value}")
        raw = raw[1:-1]
    tags = []
    for part in split_csv(raw):
        cleaned = strip_quotes(part).strip()
        if cleaned:
            tags.append(cleaned)
    return tags


def load_config(input_dir: Path, config_arg: str | None) -> dict:
    config = dict(DEFAULT_CONFIG)
    config_path = Path(config_arg) if config_arg else input_dir / "marmite.yaml"
    if not config_path.exists():
        return config
    if not config_path.is_file():
        raise MiniSiteError(f"config path is not a file: {config_path}")

    try:
        lines = config_path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise MiniSiteError(f"unable to read config: {exc}") from exc

    for number, line in enumerate(lines, start=1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if ":" not in line:
            raise MiniSiteError(f"invalid config line {number}: missing ':'")
        key, value = line.split(":", 1)
        key = key.strip()
        value = value.strip()
        if key == "site_name":
            config[key] = strip_quotes(value)
        elif key == "base_url":
            config[key] = strip_quotes(value)
        elif key == "pagination":
            raw = strip_quotes(value).strip()
            try:
                pagination = int(raw)
            except ValueError as exc:
                raise MiniSiteError(f"invalid pagination value: {value}") from exc
            if pagination <= 0:
                raise MiniSiteError(f"invalid pagination value: {value}")
            config[key] = pagination
        elif key == "json_feed":
            config[key] = parse_bool(value, key)
        elif key == "enable_search":
            config[key] = parse_bool(value, key)
    return config


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
        raise MiniSiteError(f"unterminated frontmatter in {source}")

    meta = {}
    for number, line in enumerate(lines[1:end], start=2):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        key = key.strip()
        value = value.strip()
        if key == "title":
            meta[key] = strip_quotes(value)
        elif key == "slug":
            meta[key] = strip_quotes(value)
        elif key == "date":
            meta[key] = parse_date_value(value, f"{source}:{number}")
        elif key == "tags":
            meta[key] = parse_tags(value)
        elif key == "stream":
            meta[key] = strip_quotes(value)
        elif key == "description":
            meta[key] = strip_quotes(value)
    return meta, "\n".join(lines[end + 1 :])


def valid_ymd(year: str, month: str, day: str) -> str | None:
    try:
        return _dt.date(int(year), int(month), int(day)).strftime("%Y-%m-%d")
    except ValueError:
        return None


def valid_timestamp(parts: tuple[str, str, str, str, str, str]) -> str | None:
    year, month, day, hour, minute, second = parts
    try:
        return _dt.datetime(
            int(year), int(month), int(day), int(hour), int(minute), int(second)
        ).strftime("%Y-%m-%d")
    except ValueError:
        return None


def analyze_filename(stem: str, frontmatter_date: str | None) -> dict:
    info = {
        "date": None,
        "stream": None,
        "slug_base": None,
        "title_stem": stem,
    }

    match = re.match(
        r"^([^-]+)-(\d{4})-(\d{2})-(\d{2})-(\d{2})-(\d{2})-(\d{2})-(.+)$",
        stem,
    )
    if match:
        stream, year, month, day, hour, minute, second, name = match.groups()
        date = valid_timestamp((year, month, day, hour, minute, second))
        if date:
            info.update(
                date=date,
                stream=slugify(stream) or stream.lower(),
                slug_base=f"{stream}-{name}",
                title_stem=name,
            )
            return info

    match = re.match(r"^([^-]+)-(\d{4})-(\d{2})-(\d{2})-(.+)$", stem)
    if match:
        stream, year, month, day, name = match.groups()
        date = valid_ymd(year, month, day)
        if date:
            info.update(
                date=date,
                stream=slugify(stream) or stream.lower(),
                slug_base=f"{stream}-{name}",
                title_stem=name,
            )
            return info

    match = re.match(r"^(\d{4})-(\d{2})-(\d{2})-(\d{2})-(\d{2})-(\d{2})-(.+)$", stem)
    if match:
        year, month, day, hour, minute, second, name = match.groups()
        date = valid_timestamp((year, month, day, hour, minute, second))
        if date:
            info.update(date=date, slug_base=name, title_stem=name)
            return info

    match = re.match(r"^(\d{4})-(\d{2})-(\d{2})-(.+)$", stem)
    if match:
        year, month, day, name = match.groups()
        date = valid_ymd(year, month, day)
        if date:
            info.update(date=date, slug_base=name, title_stem=name)
            return info

    if frontmatter_date:
        parts = stem.split("-", 2)
        if len(parts) == 3 and parts[0] and parts[1] and parts[2]:
            stream, _sequence, name = parts
            info.update(
                stream=slugify(stream) or stream.lower(),
                slug_base=f"{stream}-{name}",
                title_stem=name,
            )

    return info


def first_heading(body: str) -> str | None:
    for line in body.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return None


def normalize_stream(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = strip_quotes(value).strip()
    if not cleaned:
        return None
    return slugify(cleaned) or cleaned.lower()


def parse_content_file(path: Path, content_root: Path) -> ContentItem:
    source = path.relative_to(content_root).as_posix()
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise MiniSiteError(f"unable to read content {source}: {exc}") from exc

    meta, body = parse_frontmatter(text, source)
    file_info = analyze_filename(path.stem, meta.get("date"))
    date = meta.get("date") or file_info["date"]
    kind = "post" if date else "page"
    stream = None
    if kind == "post":
        stream = normalize_stream(meta.get("stream")) or file_info["stream"] or "index"

    title = meta.get("title")
    if title is None:
        title = first_heading(body)
    if title is None:
        title = file_info["title_stem"]

    if "slug" in meta:
        base_slug = slugify(meta["slug"])
    elif file_info["slug_base"] is not None:
        base_slug = slugify(file_info["slug_base"])
    else:
        base_slug = slugify(title)

    if kind == "post" and meta.get("stream") is not None:
        stream_prefix = normalize_stream(meta.get("stream"))
        if stream_prefix and stream_prefix != "index" and not base_slug.startswith(f"{stream_prefix}-"):
            base_slug = f"{stream_prefix}-{base_slug}" if base_slug else stream_prefix

    tags = meta.get("tags", [])
    draft = kind == "post" and stream == "draft"
    description = meta.get("description")

    return ContentItem(
        title=title,
        slug=base_slug,
        source=source,
        kind=kind,
        date=date,
        tags=tags,
        stream=stream if kind == "post" else None,
        description=description,
        draft=draft,
        body=body,
    )


def post_sort_key(item: ContentItem):
    ordinal = _dt.datetime.strptime(item.date or "0001-01-01", "%Y-%m-%d").toordinal()
    return (-ordinal, item.slug)


def page_sort_key(item: ContentItem):
    return (item.title, item.slug)


def load_site(input_arg: str, config_arg: str | None) -> SiteState:
    input_dir = Path(input_arg)
    if not input_dir.exists() or not input_dir.is_dir():
        raise MiniSiteError(f"missing input directory: {input_arg}")
    config = load_config(input_dir, config_arg)
    content_root = input_dir / "content" if (input_dir / "content").is_dir() else input_dir

    markdown_files = sorted(
        (p for p in content_root.rglob("*.md") if not p.name.startswith("_")),
        key=lambda p: p.relative_to(content_root).as_posix(),
    )
    items = [parse_content_file(path, content_root) for path in markdown_files]

    public = [item for item in items if not item.draft]
    public_by_slug = {}
    for item in public:
        if item.slug in public_by_slug:
            raise MiniSiteError(f"duplicate slug among non-draft content: {item.slug}")
        public_by_slug[item.slug] = item

    posts = sorted((item for item in public if item.kind == "post"), key=post_sort_key)
    pages = sorted((item for item in public if item.kind == "page"), key=page_sort_key)
    drafts = sorted((item for item in items if item.draft), key=post_sort_key)

    public_by_title = {}
    for item in sorted(public, key=lambda entry: (entry.title.lower(), entry.slug)):
        public_by_title.setdefault(item.title.lower(), item)

    public_by_source = {item.source: item for item in public}
    state = SiteState(
        config=config,
        items=items,
        posts=posts,
        pages=pages,
        drafts=drafts,
        public_by_slug=public_by_slug,
        public_by_title=public_by_title,
        public_by_source=public_by_source,
    )
    compute_links_and_backlinks(state)
    return state


def markdown_target_slug(source: ContentItem, target: str, state: SiteState) -> str | None:
    stripped = strip_quotes(target).strip()
    if stripped.startswith("http://") or stripped.startswith("https://"):
        return None
    path_part = stripped.split("#", 1)[0]
    if not (path_part.endswith(".md") or path_part.endswith(".html")):
        return None

    source_dir = posixpath.dirname(source.source)
    normalized = posixpath.normpath(posixpath.join(source_dir, path_part))
    if normalized.startswith("../"):
        normalized = path_part.lstrip("/")
    if normalized.startswith("./"):
        normalized = normalized[2:]

    candidates = []
    if normalized.endswith(".md"):
        candidates.append(normalized)
    elif normalized.endswith(".html"):
        candidates.append(normalized[:-5] + ".md")
        output_slug = posixpath.basename(normalized[:-5])
        if output_slug in state.public_by_slug:
            return output_slug

    for candidate in candidates:
        item = state.public_by_source.get(candidate)
        if item:
            return item.slug
    return None


INLINE_RE = re.compile(r"\[([^\]]+)\]\(([^)]+)\)|\[\[([^\]|]+)(?:\|([^\]]+))?\]\]")


def render_inline(text: str, source: ContentItem, state: SiteState, links: list[str] | None = None) -> str:
    output = []
    position = 0
    for match in INLINE_RE.finditer(text):
        output.append(html.escape(text[position : match.start()]))
        if match.group(1) is not None:
            label = match.group(1)
            target = match.group(2).strip()
            href = target
            slug = markdown_target_slug(source, target, state)
            if slug:
                href = f"{slug}.html"
                if links is not None and slug not in links:
                    links.append(slug)
            output.append(
                f'<a href="{html.escape(href, quote=True)}">{html.escape(label)}</a>'
            )
        else:
            title = match.group(3).strip()
            label = (match.group(4) or title).strip()
            target = state.public_by_title.get(title.lower())
            if target:
                if links is not None and target.slug not in links:
                    links.append(target.slug)
                output.append(
                    f'<a href="{html.escape(target.slug, quote=True)}.html">{html.escape(label)}</a>'
                )
            else:
                missing = slugify(title)
                output.append(
                    f'<a data-wikilink="missing" href="{html.escape(missing, quote=True)}.html">'
                    f"{html.escape(label)}</a>"
                )
        position = match.end()
    output.append(html.escape(text[position:]))
    return "".join(output)


def body_links(item: ContentItem, state: SiteState) -> list[str]:
    links: list[str] = []
    for line in item.body.splitlines():
        render_inline(line, item, state, links)
    return links


def compute_links_and_backlinks(state: SiteState) -> None:
    for item in state.items:
        item.links_to = body_links(item, state)
        item.backlinks = []

    for source in state.public_items():
        for slug in source.links_to:
            target = state.public_by_slug.get(slug)
            if target and source.slug not in target.backlinks:
                target.backlinks.append(source.slug)


def render_body(item: ContentItem, state: SiteState) -> str:
    rendered = []
    for line in item.body.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("# "):
            heading = stripped[2:].strip()
            rendered.append(
                f'<h1 id="{html.escape(slugify(heading), quote=True)}">'
                f"{render_inline(heading, item, state)}</h1>"
            )
        elif stripped.startswith("## "):
            heading = stripped[3:].strip()
            rendered.append(
                f'<h2 id="{html.escape(slugify(heading), quote=True)}">'
                f"{render_inline(heading, item, state)}</h2>"
            )
        else:
            rendered.append(f"<p>{render_inline(stripped, item, state)}</p>")
    return "\n".join(rendered)


def plain_text(item: ContentItem) -> str:
    chunks = []
    for line in item.body.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("# "):
            stripped = stripped[2:].strip()
        elif stripped.startswith("## "):
            stripped = stripped[3:].strip()
        stripped = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r"\1", stripped)
        stripped = re.sub(r"\[\[([^\]|]+)\|([^\]]+)\]\]", r"\2", stripped)
        stripped = re.sub(r"\[\[([^\]]+)\]\]", r"\1", stripped)
        chunks.append(html.unescape(stripped))
    return " ".join(chunks)


def document(title: str, body: str) -> str:
    escaped_title = html.escape(title)
    return (
        "<!doctype html>\n"
        "<html><head><meta charset=\"utf-8\">"
        f"<title>{escaped_title}</title>"
        "</head><body>\n"
        f"{body}\n"
        "</body></html>\n"
    )


def render_content_page(item: ContentItem, state: SiteState) -> str:
    body = [render_body(item, state)]
    if item.backlinks:
        links = "\n".join(
            f'<li><a href="{html.escape(slug, quote=True)}.html">{html.escape(slug)}</a></li>'
            for slug in item.backlinks
        )
        body.append(f'<section class="backlinks"><h2>Backlinks</h2><ul>{links}</ul></section>')
    return document(item.title, "\n".join(part for part in body if part))


def render_listing(title: str, entries: list[tuple[str, str]]) -> str:
    items = "\n".join(
        f'<li><a href="{html.escape(path, quote=True)}">{html.escape(label)}</a></li>'
        for path, label in entries
    )
    return document(title, f"<h1>{html.escape(title)}</h1>\n<ul>{items}</ul>")


def chunks(items: list[ContentItem], size: int) -> list[list[ContentItem]]:
    if not items:
        return [[]]
    return [items[index : index + size] for index in range(0, len(items), size)]


def full_url(path: str, config: dict) -> str:
    base = config["base_url"]
    if not base:
        return path
    return f"{base.rstrip('/')}/{path.lstrip('/')}"


def feed_item(item: ContentItem, config: dict) -> dict:
    return {
        "title": item.title,
        "slug": item.slug,
        "url": full_url(f"{item.slug}.html", config),
        "date": item.date,
        "tags": list(item.tags),
        "stream": item.stream,
        "description": item.description,
    }


def feed(title: str, items: list[ContentItem], config: dict) -> str:
    return compact_json({"title": title, "items": [feed_item(item, config) for item in items]})


def search_index(state: SiteState) -> str:
    items = []
    for item in state.public_items():
        items.append(
            {
                "title": item.title,
                "slug": item.slug,
                "url": full_url(f"{item.slug}.html", state.config),
                "kind": item.kind,
                "tags": list(item.tags),
                "stream": item.stream,
                "text": plain_text(item),
            }
        )
    return compact_json(items)


def posts_for_tag(state: SiteState) -> dict[str, list[ContentItem]]:
    tags: dict[str, list[ContentItem]] = {}
    for post in state.posts:
        for tag in post.tags:
            tag_slug = slugify(tag)
            if tag_slug:
                tags.setdefault(tag_slug, []).append(post)
    return {key: tags[key] for key in sorted(tags)}


def posts_for_stream(state: SiteState) -> dict[str, list[ContentItem]]:
    streams: dict[str, list[ContentItem]] = {}
    for post in state.posts:
        if post.stream and post.stream != "draft":
            streams.setdefault(post.stream, []).append(post)
    return {key: streams[key] for key in sorted(streams)}


def posts_for_archive(state: SiteState) -> dict[str, list[ContentItem]]:
    archives: dict[str, list[ContentItem]] = {}
    for post in state.posts:
        year = (post.date or "")[:4]
        if year:
            archives.setdefault(year, []).append(post)
    return {key: archives[key] for key in sorted(archives, reverse=True)}


def add_output(outputs: dict[str, str], manifest: dict, group: str, path: str, content: str) -> None:
    if path in outputs:
        raise MiniSiteError(f"generated path collision: {path}")
    outputs[path] = content
    manifest[group].append(path)


def listing_entries(items: list[ContentItem]) -> list[tuple[str, str]]:
    return [(f"{item.slug}.html", item.title) for item in items]


def add_paginated_listing(
    outputs: dict[str, str],
    manifest: dict,
    group: str,
    first_path: str,
    later_pattern: str,
    title: str,
    items: list[ContentItem],
    pagination: int,
) -> list[str]:
    paths = []
    for index, page_items in enumerate(chunks(items, pagination), start=1):
        path = first_path if index == 1 else later_pattern.format(page=index)
        page_title = title if index == 1 else f"{title} page {index}"
        add_output(outputs, manifest, group, path, render_listing(page_title, listing_entries(page_items)))
        paths.append(path)
    return paths


def generate_site(state: SiteState) -> tuple[dict, dict[str, str]]:
    manifest = {group: [] for group in MANIFEST_GROUPS}
    outputs: dict[str, str] = {}
    pagination = state.config["pagination"]

    for post in state.posts:
        add_output(outputs, manifest, "posts", f"{post.slug}.html", render_content_page(post, state))
    for page in state.pages:
        add_output(outputs, manifest, "pages", f"{page.slug}.html", render_content_page(page, state))

    index_posts = [post for post in state.posts if post.stream == "index"]
    add_paginated_listing(
        outputs,
        manifest,
        "index",
        "index.html",
        "index-{page}.html",
        state.config["site_name"],
        index_posts,
        pagination,
    )

    if state.pages:
        add_output(
            outputs,
            manifest,
            "pages",
            "pages.html",
            render_listing("Pages", listing_entries(state.pages)),
        )

    tag_pages = []
    tag_posts = posts_for_tag(state)
    for tag_slug, posts in tag_posts.items():
        tag_pages.extend(
            add_paginated_listing(
                outputs,
                manifest,
                "tags",
                f"tag-{tag_slug}.html",
                f"tag-{tag_slug}-{{page}}.html",
                f"tag:{tag_slug}",
                posts,
                pagination,
            )
        )
    if tag_pages:
        add_output(
            outputs,
            manifest,
            "tags",
            "tags.html",
            render_listing("Tags", [(path, path[:-5]) for path in tag_pages]),
        )

    stream_pages = []
    stream_posts = posts_for_stream(state)
    for stream, posts in stream_posts.items():
        if stream in ("index", "draft"):
            continue
        stream_pages.extend(
            add_paginated_listing(
                outputs,
                manifest,
                "streams",
                f"{stream}.html",
                f"{stream}-{{page}}.html",
                f"stream:{stream}",
                posts,
                pagination,
            )
        )
    if stream_pages:
        add_output(
            outputs,
            manifest,
            "streams",
            "streams.html",
            render_listing("Streams", [(path, path[:-5]) for path in stream_pages]),
        )

    archive_pages = []
    archive_posts = posts_for_archive(state)
    for year, posts in archive_posts.items():
        archive_pages.extend(
            add_paginated_listing(
                outputs,
                manifest,
                "archives",
                f"archive-{year}.html",
                f"archive-{year}-{{page}}.html",
                f"archive:{year}",
                posts,
                pagination,
            )
        )
    if archive_pages:
        add_output(
            outputs,
            manifest,
            "archives",
            "archive.html",
            render_listing("Archive", [(path, path[:-5]) for path in archive_pages]),
        )

    if state.config["json_feed"]:
        add_output(outputs, manifest, "feeds", "feed.json", feed(state.config["site_name"], index_posts, state.config))
        for tag_slug, posts in tag_posts.items():
            add_output(outputs, manifest, "feeds", f"tag-{tag_slug}.json", feed(f"tag:{tag_slug}", posts, state.config))
        for stream, posts in stream_posts.items():
            if stream in ("index", "draft"):
                continue
            add_output(outputs, manifest, "feeds", f"{stream}.json", feed(f"stream:{stream}", posts, state.config))
        for year, posts in archive_posts.items():
            add_output(outputs, manifest, "feeds", f"archive-{year}.json", feed(f"archive:{year}", posts, state.config))

    if state.config["enable_search"]:
        add_output(outputs, manifest, "search", "search_index.json", search_index(state))

    manifest["misc"].append("urls.json")
    summary = {group: len(manifest[group]) for group in MANIFEST_GROUPS}
    summary["total"] = sum(summary.values()) - 1
    manifest["summary"] = summary
    outputs["urls.json"] = compact_json(manifest)
    return manifest, outputs


def inspect_output(state: SiteState) -> dict:
    tags = {}
    for tag_slug, posts in posts_for_tag(state).items():
        tags[tag_slug] = [post.slug for post in posts]
    streams = {}
    for stream, posts in posts_for_stream(state).items():
        if stream != "draft":
            streams[stream] = [post.slug for post in posts]
    return {
        "posts": [post.model() for post in state.posts],
        "pages": [page.model() for page in state.pages],
        "tags": tags,
        "streams": streams,
        "drafts": [draft.model() for draft in state.drafts],
    }


def write_outputs(output_arg: str, outputs: dict[str, str]) -> None:
    output_dir = Path(output_arg)
    written: list[Path] = []
    try:
        if output_dir.exists() and not output_dir.is_dir():
            raise MiniSiteError(f"output path is not a directory: {output_arg}")
        output_dir.mkdir(parents=True, exist_ok=True)
        for relative, content in outputs.items():
            target = output_dir / relative
            target.write_text(content, encoding="utf-8")
            written.append(target)
    except MiniSiteError:
        raise
    except OSError as exc:
        for path in written:
            try:
                path.unlink()
            except OSError:
                pass
        raise MiniSiteError(f"unable to create or write output directory: {exc}") from exc


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="minisite.py")
    subparsers = parser.add_subparsers(dest="command", required=True)

    build = subparsers.add_parser("build")
    build.add_argument("--input", required=True)
    build.add_argument("--output", required=True)
    build.add_argument("--config")

    inspect = subparsers.add_parser("inspect")
    inspect.add_argument("--input", required=True)
    inspect.add_argument("--config")

    urls = subparsers.add_parser("urls")
    urls.add_argument("--input", required=True)
    urls.add_argument("--config")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        state = load_site(args.input, getattr(args, "config", None))
        if args.command == "inspect":
            print(compact_json(inspect_output(state)))
        elif args.command == "urls":
            manifest, _outputs = generate_site(state)
            print(compact_json(manifest))
        elif args.command == "build":
            manifest, outputs = generate_site(state)
            write_outputs(args.output, outputs)
            print(compact_json(manifest))
        else:
            raise MiniSiteError(f"unsupported command: {args.command}")
        return 0
    except MiniSiteError as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
