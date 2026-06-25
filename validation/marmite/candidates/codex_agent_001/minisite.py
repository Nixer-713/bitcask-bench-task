#!/usr/bin/env python3
import argparse
import datetime as _dt
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


class MiniSiteError(Exception):
    pass


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
            "tags": list(self.tags),
            "stream": self.stream,
            "description": self.description,
            "draft": self.draft,
            "links_to": list(self.links_to),
            "backlinks": list(self.backlinks),
        }


def compact_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def slugify(text: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "-", text.lower()).strip("-")


def clean_scalar(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
        return value[1:-1]
    return value


def parse_bool(value: str, key: str) -> bool:
    cleaned = clean_scalar(value).strip().lower()
    if cleaned == "true":
        return True
    if cleaned == "false":
        return False
    raise MiniSiteError(f"invalid boolean value for {key}: {value}")


def normalize_date(value: str, key: str = "date") -> str:
    value = clean_scalar(value).strip()
    formats = ["%Y-%m-%d", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"]
    for fmt in formats:
        try:
            return _dt.datetime.strptime(value, fmt).strftime("%Y-%m-%d")
        except ValueError:
            pass
    raise MiniSiteError(f"invalid {key} value: {value}")


def parse_config(input_root: Path, config_path: str | None) -> dict:
    config = {
        "site_name": "Mini Marmite",
        "base_url": "",
        "pagination": 10,
        "json_feed": True,
        "enable_search": True,
    }
    path = Path(config_path) if config_path else input_root / "marmite.yaml"
    if not path.exists():
        return config
    if not path.is_file():
        raise MiniSiteError(f"config path is not a file: {path}")
    for lineno, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        key = key.strip()
        value = value.strip()
        if key == "site_name":
            config[key] = clean_scalar(value)
        elif key == "base_url":
            config[key] = clean_scalar(value).rstrip("/")
        elif key == "pagination":
            try:
                pagination = int(clean_scalar(value))
            except ValueError as exc:
                raise MiniSiteError(f"invalid pagination value on line {lineno}") from exc
            if pagination <= 0:
                raise MiniSiteError("pagination must be a positive integer")
            config[key] = pagination
        elif key == "json_feed":
            config[key] = parse_bool(value, key)
        elif key == "enable_search":
            config[key] = parse_bool(value, key)
    return config


def split_frontmatter(text: str) -> tuple[dict, str]:
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
    meta = {}
    for lineno, raw in enumerate(lines[1:end], 2):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        key = key.strip()
        value = value.strip()
        if key in {"title", "slug", "stream", "description"}:
            meta[key] = clean_scalar(value)
        elif key == "date":
            meta[key] = normalize_date(value)
        elif key == "tags":
            meta[key] = parse_tags(value)
    body = "\n".join(lines[end + 1 :])
    return meta, body


def parse_tags(value: str) -> list[str]:
    value = value.strip()
    if value.startswith("[") and value.endswith("]"):
        inside = value[1:-1]
        raw_parts = inside.split(",")
    else:
        raw_parts = value.split(",")
    tags = []
    for part in raw_parts:
        tag = clean_scalar(part).strip()
        if tag:
            tags.append(tag)
    return tags


def first_heading(body: str) -> str | None:
    for line in body.splitlines():
        if line.startswith("# "):
            heading = line[2:].strip()
            if heading:
                return heading
    return None


def discover_content_root(input_root: Path) -> Path:
    if not input_root.exists() or not input_root.is_dir():
        raise MiniSiteError(f"missing input directory: {input_root}")
    content = input_root / "content"
    return content if content.exists() and content.is_dir() else input_root


def posix_rel(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def filename_info(source: str, date_from_meta: str | None) -> dict:
    stem = posixpath.splitext(posixpath.basename(source))[0]
    info = {
        "date": None,
        "stream": None,
        "slug_base": None,
        "title_base": stem,
        "recognized": False,
    }
    match = re.match(r"^(\d{4}-\d{2}-\d{2})-(\d{2})-(\d{2})-(\d{2})-(.+)$", stem)
    if match:
        date = normalize_date(f"{match.group(1)} {match.group(2)}:{match.group(3)}:{match.group(4)}", "filename date")
        base = match.group(5)
        info.update({"date": date, "slug_base": base, "title_base": base, "recognized": True})
        return info
    match = re.match(r"^([A-Za-z0-9_-]+)-(\d{4}-\d{2}-\d{2})-(.+)$", stem)
    if match:
        stream = slugify(match.group(1))
        date = normalize_date(match.group(2), "filename date")
        base = match.group(3)
        info.update({
            "date": date,
            "stream": stream,
            "slug_base": f"{stream}-{slugify(base)}",
            "title_base": base,
            "recognized": True,
        })
        return info
    match = re.match(r"^(\d{4}-\d{2}-\d{2})-(.+)$", stem)
    if match:
        date = normalize_date(match.group(1), "filename date")
        base = match.group(2)
        info.update({"date": date, "slug_base": base, "title_base": base, "recognized": True})
        return info
    match = re.match(r"^([A-Za-z0-9_-]+)-S-(.+)$", stem)
    if match and date_from_meta:
        stream = slugify(match.group(1))
        base = match.group(2)
        info.update({
            "stream": stream,
            "slug_base": f"{stream}-{slugify(base)}",
            "title_base": base,
            "recognized": True,
        })
    return info


def read_items(input_root: Path, config_path: str | None) -> tuple[dict, list[Item], Path]:
    config = parse_config(input_root, config_path)
    content_root = discover_content_root(input_root)
    items = []
    for path in sorted(content_root.rglob("*.md"), key=lambda p: p.relative_to(content_root).as_posix()):
        if path.name.startswith("_"):
            continue
        source = posix_rel(path, content_root)
        text = path.read_text(encoding="utf-8")
        meta, body = split_frontmatter(text)
        finfo = filename_info(source, meta.get("date"))
        date = meta.get("date") or finfo["date"]
        kind = "post" if date else "page"
        stream = None
        if kind == "post":
            stream = slugify(meta["stream"]) if meta.get("stream") else finfo["stream"] or "index"
        heading = first_heading(body)
        fallback_title = finfo["title_base"]
        title = meta.get("title") or heading or fallback_title
        if meta.get("slug"):
            base_slug = meta["slug"]
        elif finfo["slug_base"] and kind == "post":
            base_slug = slugify(finfo["slug_base"])
        else:
            base_slug = slugify(fallback_title if not (meta.get("title") or heading) else title)
        final_slug = base_slug
        if kind == "post" and stream and stream != "index" and meta.get("stream"):
            prefix = f"{stream}-"
            if not final_slug.startswith(prefix):
                final_slug = prefix + final_slug
        if not final_slug:
            raise MiniSiteError(f"empty slug for {source}")
        item = Item(
            title=title,
            slug=final_slug,
            source=source,
            kind=kind,
            date=date,
            tags=meta.get("tags", []) if kind == "post" else [],
            stream=stream if kind == "post" else None,
            description=meta.get("description"),
            draft=(kind == "post" and stream == "draft"),
            body=body,
        )
        items.append(item)
    public_slugs = {}
    for item in items:
        if item.draft:
            continue
        if item.slug in public_slugs:
            raise MiniSiteError(f"duplicate final slug among non-draft content: {item.slug}")
        public_slugs[item.slug] = item.source
    resolve_links(items)
    return config, items, content_root


def make_link_context(items: list[Item]) -> dict:
    by_slug = {item.slug: item for item in items}
    by_title = {}
    by_source = {}
    for item in items:
        by_title.setdefault(item.title.lower(), item)
        by_source[item.source] = item
    return {"by_slug": by_slug, "by_title": by_title, "by_source": by_source}


def resolve_target_slug(target: str, current: Item, context: dict) -> str:
    clean = target.split("#", 1)[0].split("?", 1)[0]
    if clean.endswith(".html"):
        candidate_slug = posixpath.splitext(posixpath.basename(clean))[0]
        if candidate_slug in context["by_slug"]:
            return candidate_slug
        md_target = posixpath.splitext(clean)[0] + ".md"
    else:
        md_target = clean
    if md_target.endswith(".md"):
        joined = posixpath.normpath(posixpath.join(posixpath.dirname(current.source), md_target))
        if joined in context["by_source"]:
            return context["by_source"][joined].slug
        return slugify(posixpath.splitext(posixpath.basename(md_target))[0])
    return slugify(posixpath.splitext(posixpath.basename(clean))[0])


def collect_links(body: str, item: Item, context: dict) -> list[str]:
    links = []
    for match in re.finditer(r"\[([^\]]+)\]\(([^)]+)\)", body):
        target = match.group(2).strip()
        if target.startswith("http://") or target.startswith("https://"):
            continue
        if target.endswith(".md") or target.endswith(".html"):
            links.append(resolve_target_slug(target, item, context))
    for match in re.finditer(r"\[\[([^\]|]+)(?:\|([^\]]+))?\]\]", body):
        title = match.group(1).strip()
        target = context["by_title"].get(title.lower())
        links.append(target.slug if target else slugify(title))
    seen = set()
    unique = []
    for slug in links:
        if slug and slug not in seen:
            seen.add(slug)
            unique.append(slug)
    return unique


def resolve_links(items: list[Item]) -> None:
    context = make_link_context(items)
    for item in items:
        item.links_to = collect_links(item.body, item, context)
        item.backlinks = []
    public = [item for item in items if not item.draft]
    by_slug = {item.slug: item for item in public}
    for source in public:
        for target_slug in source.links_to:
            target = by_slug.get(target_slug)
            if target and source.slug not in target.backlinks:
                target.backlinks.append(source.slug)
    for item in items:
        item.backlinks.sort()


def sorted_posts(items: list[Item]) -> list[Item]:
    def key(item: Item) -> tuple[int, str]:
        ordinal = _dt.date.fromisoformat(item.date or "0001-01-01").toordinal()
        return (-ordinal, item.slug)

    return sorted([i for i in items if i.kind == "post" and not i.draft], key=key)


def sorted_pages(items: list[Item]) -> list[Item]:
    return sorted([i for i in items if i.kind == "page" and not i.draft], key=lambda i: (i.title, i.slug))


def public_url(config: dict, path: str) -> str:
    base = config["base_url"]
    if not base:
        return path
    return base.rstrip("/") + "/" + path.lstrip("/")


def render_inline(text: str, item: Item, context: dict) -> str:
    pattern = re.compile(r"(\[([^\]]+)\]\(([^)]+)\)|\[\[([^\]|]+)(?:\|([^\]]+))?\]\])")
    out = []
    last = 0
    for match in pattern.finditer(text):
        out.append(html.escape(text[last : match.start()]))
        if match.group(2) is not None:
            label = html.escape(match.group(2))
            target = match.group(3).strip()
            if target.startswith("http://") or target.startswith("https://"):
                href = target
            elif target.endswith(".md") or target.endswith(".html"):
                href = resolve_target_slug(target, item, context) + ".html"
            else:
                href = target
            out.append(f'<a href="{html.escape(href, quote=True)}">{label}</a>')
        else:
            title = match.group(4).strip()
            label = match.group(5).strip() if match.group(5) else title
            target = context["by_title"].get(title.lower())
            if target:
                out.append(f'<a href="{html.escape(target.slug + ".html", quote=True)}">{html.escape(label)}</a>')
            else:
                href = slugify(title) + ".html"
                out.append(f'<a href="{html.escape(href, quote=True)}" data-wikilink="missing">{html.escape(label)}</a>')
        last = match.end()
    out.append(html.escape(text[last:]))
    return "".join(out)


def render_body(item: Item, context: dict) -> tuple[str, str]:
    parts = []
    plain = []
    for raw in item.body.splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith("# "):
            text = line[2:].strip()
            parts.append(f'<h1 id="{html.escape(slugify(text), quote=True)}">{render_inline(text, item, context)}</h1>')
            plain.append(text)
        elif line.startswith("## "):
            text = line[3:].strip()
            parts.append(f'<h2 id="{html.escape(slugify(text), quote=True)}">{render_inline(text, item, context)}</h2>')
            plain.append(text)
        else:
            parts.append(f"<p>{render_inline(line, item, context)}</p>")
            plain.append(re.sub(r"\[\[([^\]|]+)\|([^\]]+)\]\]", r"\2", re.sub(r"\[\[([^\]]+)\]\]", r"\1", re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r"\1", line))))
    return "\n".join(parts), " ".join(plain)


def html_document(title: str, body: str) -> str:
    return f"<!doctype html>\n<html><head><meta charset=\"utf-8\"><title>{html.escape(title)}</title></head><body>\n{body}\n</body></html>\n"


def render_content_page(item: Item, context: dict) -> tuple[str, str]:
    body, plain = render_body(item, context)
    if item.backlinks:
        links = "".join(f'<li><a href="{html.escape(slug + ".html", quote=True)}">{html.escape(slug)}</a></li>' for slug in item.backlinks)
        body += f'\n<section class="backlinks"><h2 id="backlinks">Backlinks</h2><ul>{links}</ul></section>'
    return html_document(item.title, body), plain


def render_listing(title: str, items: list[Item]) -> str:
    links = "".join(f'<li><a href="{html.escape(item.slug + ".html", quote=True)}">{html.escape(item.title)}</a></li>' for item in items)
    return html_document(title, f"<h1>{html.escape(title)}</h1>\n<ul>{links}</ul>")


def render_named_links(title: str, paths: list[tuple[str, str]]) -> str:
    links = "".join(f'<li><a href="{html.escape(path, quote=True)}">{html.escape(label)}</a></li>' for label, path in paths)
    return html_document(title, f"<h1>{html.escape(title)}</h1>\n<ul>{links}</ul>")


def paginate(items: list[Item], size: int) -> list[list[Item]]:
    return [items[i : i + size] for i in range(0, len(items), size)] or [[]]


def feed(config: dict, title: str, items: list[Item]) -> str:
    payload = {
        "title": title,
        "items": [
            {
                "title": item.title,
                "slug": item.slug,
                "url": public_url(config, item.slug + ".html"),
                "date": item.date,
                "tags": list(item.tags),
                "stream": item.stream,
                "description": item.description,
            }
            for item in items
        ],
    }
    return compact_json(payload) + "\n"


def build_outputs(config: dict, items: list[Item]) -> tuple[dict, dict[str, str]]:
    posts = sorted_posts(items)
    pages = sorted_pages(items)
    context = make_link_context(items)
    outputs = {}
    manifest = {
        "posts": [],
        "pages": [],
        "index": [],
        "tags": [],
        "streams": [],
        "feeds": [],
        "search": [],
        "misc": ["urls.json"],
        "summary": {},
    }
    plain_text = {}
    for item in posts:
        path = item.slug + ".html"
        outputs[path], plain_text[item.slug] = render_content_page(item, context)
        manifest["posts"].append(path)
    for item in pages:
        path = item.slug + ".html"
        outputs[path], plain_text[item.slug] = render_content_page(item, context)
        manifest["pages"].append(path)

    index_posts = [p for p in posts if p.stream == "index"]
    for page_no, chunk in enumerate(paginate(index_posts, config["pagination"]), 1):
        if page_no == 1:
            path = "index.html"
        else:
            path = f"index-{page_no}.html"
        outputs[path] = render_listing(config["site_name"], chunk)
        manifest["index"].append(path)

    if pages:
        outputs["pages.html"] = render_listing("Pages", pages)
        manifest["pages"].append("pages.html")

    tag_map = build_tag_map(posts)
    tag_page_links = []
    for tag_slug in sorted(tag_map):
        tag_posts = tag_map[tag_slug]
        first_path = f"tag-{tag_slug}.html"
        tag_page_links.append((tag_slug, first_path))
        for page_no, chunk in enumerate(paginate(tag_posts, config["pagination"]), 1):
            path = first_path if page_no == 1 else f"tag-{tag_slug}-{page_no}.html"
            outputs[path] = render_listing(f"tag:{tag_slug}", chunk)
            manifest["tags"].append(path)
    if tag_page_links:
        outputs["tags.html"] = render_named_links("Tags", tag_page_links)
        manifest["tags"].append("tags.html")

    stream_map = build_stream_map(posts)
    stream_page_links = []
    for stream in sorted(s for s in stream_map if s not in {"index", "draft"}):
        stream_posts = stream_map[stream]
        first_path = f"{stream}.html"
        stream_page_links.append((stream, first_path))
        for page_no, chunk in enumerate(paginate(stream_posts, config["pagination"]), 1):
            path = first_path if page_no == 1 else f"{stream}-{page_no}.html"
            outputs[path] = render_listing(f"stream:{stream}", chunk)
            manifest["streams"].append(path)
    if stream_page_links:
        outputs["streams.html"] = render_named_links("Streams", stream_page_links)
        manifest["streams"].append("streams.html")

    if config["json_feed"]:
        outputs["feed.json"] = feed(config, config["site_name"], index_posts)
        manifest["feeds"].append("feed.json")
        for tag_slug in sorted(tag_map):
            path = f"tag-{tag_slug}.json"
            outputs[path] = feed(config, f"tag:{tag_slug}", tag_map[tag_slug])
            manifest["feeds"].append(path)
        for stream in sorted(s for s in stream_map if s not in {"index", "draft"}):
            path = f"{stream}.json"
            outputs[path] = feed(config, f"stream:{stream}", stream_map[stream])
            manifest["feeds"].append(path)

    if config["enable_search"]:
        search = []
        for item in posts + pages:
            search.append({
                "title": item.title,
                "slug": item.slug,
                "url": public_url(config, item.slug + ".html"),
                "kind": item.kind,
                "tags": list(item.tags),
                "stream": item.stream,
                "text": plain_text.get(item.slug, ""),
            })
        outputs["search_index.json"] = compact_json(search) + "\n"
        manifest["search"].append("search_index.json")

    for key in ["posts", "pages", "index", "tags", "streams", "feeds", "search", "misc"]:
        manifest["summary"][key] = len(manifest[key])
    manifest["summary"]["total"] = sum(manifest["summary"][key] for key in ["posts", "pages", "index", "tags", "streams", "feeds", "search", "misc"]) - 1
    outputs["urls.json"] = compact_json(manifest) + "\n"
    return manifest, outputs


def build_tag_map(posts: list[Item]) -> dict[str, list[Item]]:
    tag_map = {}
    for post in posts:
        for tag in post.tags:
            tag_slug = slugify(tag)
            if tag_slug:
                tag_map.setdefault(tag_slug, []).append(post)
    return tag_map


def build_stream_map(posts: list[Item]) -> dict[str, list[Item]]:
    stream_map = {}
    for post in posts:
        stream_map.setdefault(post.stream or "index", []).append(post)
    return stream_map


def write_outputs(output: Path, outputs: dict[str, str]) -> None:
    parent = output.parent if output.parent != Path("") else Path(".")
    parent.mkdir(parents=True, exist_ok=True)
    if output.exists() and not output.is_dir():
        raise MiniSiteError(f"output exists and is not a directory: {output}")
    tmp = Path(tempfile.mkdtemp(prefix=".minisite-", dir=str(parent)))
    try:
        for rel, text in outputs.items():
            if "/" in rel or rel.startswith("."):
                raise MiniSiteError(f"invalid output path: {rel}")
            (tmp / rel).write_text(text, encoding="utf-8")
        if output.exists():
            shutil.rmtree(output)
        os.replace(tmp, output)
    except Exception:
        if tmp.exists():
            shutil.rmtree(tmp, ignore_errors=True)
        raise


def inspect_payload(items: list[Item]) -> dict:
    posts = sorted_posts(items)
    pages = sorted_pages(items)
    drafts = sorted([i for i in items if i.draft], key=lambda i: (-_dt.date.fromisoformat(i.date or "0001-01-01").toordinal(), i.slug))
    tags = {tag: [item.slug for item in posts_for_tag] for tag, posts_for_tag in sorted(build_tag_map(posts).items())}
    streams = {stream: [item.slug for item in posts_for_stream] for stream, posts_for_stream in sorted(build_stream_map(posts).items()) if stream != "draft"}
    return {
        "posts": [item.public_dict() for item in posts],
        "pages": [item.public_dict() for item in pages],
        "tags": tags,
        "streams": streams,
        "drafts": [item.public_dict() for item in drafts],
    }


def run(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="minisite.py")
    subparsers = parser.add_subparsers(dest="command", required=True)
    build_parser = subparsers.add_parser("build")
    build_parser.add_argument("--input", required=True)
    build_parser.add_argument("--output", required=True)
    build_parser.add_argument("--config")
    inspect_parser = subparsers.add_parser("inspect")
    inspect_parser.add_argument("--input", required=True)
    inspect_parser.add_argument("--config")
    args = parser.parse_args(argv)
    try:
        input_root = Path(args.input)
        config, items, _ = read_items(input_root, getattr(args, "config", None))
        if args.command == "inspect":
            print(compact_json(inspect_payload(items)))
            return 0
        if args.command == "build":
            manifest, outputs = build_outputs(config, items)
            write_outputs(Path(args.output), outputs)
            print(compact_json(manifest))
            return 0
        raise MiniSiteError(f"unsupported command: {args.command}")
    except MiniSiteError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    except OSError as exc:
        print(f"I/O error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(run(sys.argv[1:]))
