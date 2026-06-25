#!/usr/bin/env python3
import argparse
import html
import json
import re
import shutil
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path


def slugify(text):
    slug = re.sub(r"[^A-Za-z0-9]+", "-", text.lower()).strip("-")
    return slug or "item"


def clean_value(value):
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value


def parse_bool(value):
    value = clean_value(value).lower()
    if value == "true":
        return True
    if value == "false":
        return False
    raise ValueError("invalid boolean value")


def parse_date(value):
    value = clean_value(value)
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        return value
    if re.fullmatch(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}(:\d{2})?", value):
        return value[:10]
    raise ValueError("invalid date value")


def parse_tags(value):
    value = clean_value(value)
    if value.startswith("[") and value.endswith("]"):
        raw = value[1:-1].split(",")
    else:
        raw = value.split(",")
    tags = []
    for tag in raw:
        cleaned = clean_value(tag).strip()
        if cleaned:
            tags.append(cleaned)
    return tags


def parse_simple_yaml(path, config=False):
    data = {}
    if not path.exists():
        return data
    for line_no, line in enumerate(path.read_text().splitlines(), 1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if ":" not in stripped:
            raise ValueError(f"invalid config line {line_no}" if config else f"invalid frontmatter line {line_no}")
        key, value = stripped.split(":", 1)
        data[key.strip()] = value.strip()
    return data


def parse_config(input_dir, explicit_config):
    cfg = {
        "site_name": "Mini Marmite",
        "base_url": "",
        "pagination": 10,
        "json_feed": True,
        "enable_search": True,
    }
    path = Path(explicit_config) if explicit_config else Path(input_dir) / "marmite.yaml"
    raw = parse_simple_yaml(path, config=True)
    for key, value in raw.items():
        if key == "site_name":
            cfg[key] = clean_value(value)
        elif key == "base_url":
            cfg[key] = clean_value(value).rstrip("/")
        elif key == "pagination":
            try:
                cfg[key] = int(clean_value(value))
            except ValueError as exc:
                raise ValueError("invalid pagination value") from exc
            if cfg[key] <= 0:
                raise ValueError("invalid pagination value")
        elif key in {"json_feed", "enable_search"}:
            cfg[key] = parse_bool(value)
    return cfg


def split_frontmatter(text):
    lines = text.splitlines()
    if lines and lines[0] == "---":
        for i in range(1, len(lines)):
            if lines[i] == "---":
                raw = "\n".join(lines[1:i])
                body = "\n".join(lines[i + 1 :])
                data = {}
                for line_no, line in enumerate(raw.splitlines(), 1):
                    stripped = line.strip()
                    if not stripped or stripped.startswith("#"):
                        continue
                    if ":" not in stripped:
                        raise ValueError(f"invalid frontmatter line {line_no}")
                    key, value = stripped.split(":", 1)
                    data[key.strip()] = value.strip()
                return data, body
        raise ValueError("unterminated frontmatter")
    return {}, text


def heading_title(body):
    for line in body.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return None


def filename_parts(stem):
    stream = None
    date = None
    base = stem
    filename_slug_base = False
    m = re.fullmatch(r"([A-Za-z0-9_-]+)-(\d{4}-\d{2}-\d{2})-(.+)", stem)
    if m and not re.fullmatch(r"\d{4}", m.group(1)):
        stream, date, base = m.group(1), m.group(2), m.group(3)
        return stream, date, base, True
    m = re.fullmatch(r"([A-Za-z0-9_-]+)-S-(.+)", stem)
    if m:
        stream, base = m.group(1), m.group(2)
        return stream, None, base, True
    m = re.fullmatch(r"(\d{4}-\d{2}-\d{2})-(.+)", stem)
    if m:
        date, base = m.group(1), m.group(2)
        return None, date, base, True
    m = re.fullmatch(r"(\d{4}-\d{2}-\d{2})-\d{2}-\d{2}-\d{2}-(.+)", stem)
    if m:
        date, base = m.group(1), m.group(2)
        filename_slug_base = True
    return stream, date, base, filename_slug_base


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

    def public(self):
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


def load_items(input_dir):
    root = Path(input_dir)
    if not root.exists():
        raise ValueError("missing input directory")
    content_root = root / "content" if (root / "content").is_dir() else root
    items = []
    for path in sorted(content_root.rglob("*.md")):
        if path.name.startswith("_"):
            continue
        rel = path.relative_to(content_root).as_posix()
        fm, body = split_frontmatter(path.read_text())
        for key in list(fm):
            if key not in {"title", "slug", "date", "tags", "stream", "description"}:
                fm.pop(key)
        file_stream, file_date, file_base, filename_slug_base = filename_parts(path.stem)
        date = parse_date(fm["date"]) if "date" in fm else file_date
        stream = clean_value(fm["stream"]) if "stream" in fm else file_stream
        title = clean_value(fm["title"]) if "title" in fm else heading_title(body)
        if not title:
            title = file_base
        if "slug" in fm:
            slug_source = clean_value(fm["slug"])
        elif filename_slug_base:
            slug_source = file_base
        elif heading_title(body) or "title" in fm:
            slug_source = title
        else:
            slug_source = file_base
        base_slug = slugify(slug_source)
        if stream and stream != "index":
            final_slug = f"{slugify(stream)}-{base_slug}"
            stream = slugify(stream)
        else:
            final_slug = base_slug
            stream = "index" if date else None
        kind = "post" if date else "page"
        if kind == "page":
            stream = None
        tags = parse_tags(fm["tags"]) if "tags" in fm else []
        item = Item(
            title=title,
            slug=final_slug,
            source=rel,
            kind=kind,
            date=date,
            tags=tags if kind == "post" else [],
            stream=stream,
            description=clean_value(fm["description"]) if "description" in fm else None,
            draft=(kind == "post" and stream == "draft"),
            body=body,
        )
        items.append(item)
    non_draft_slugs = {}
    for item in items:
        if item.draft:
            continue
        if item.slug in non_draft_slugs:
            raise ValueError(f"duplicate slug: {item.slug}")
        non_draft_slugs[item.slug] = item
    title_map = {item.title.lower(): item.slug for item in items if not item.draft}
    source_map = {item.source: item.slug for item in items if not item.draft}
    source_map.update({Path(item.source).name: item.slug for item in items if not item.draft})
    for item in items:
        if item.draft:
            continue
        item.links_to = find_links(item.body, title_map, source_map)
    by_slug = {item.slug: item for item in items if not item.draft}
    for item in items:
        if item.draft:
            continue
        for target in item.links_to:
            if target in by_slug:
                by_slug[target].backlinks.append(item.slug)
    for item in items:
        item.links_to = sorted(set(item.links_to))
        item.backlinks = sorted(set(item.backlinks))
    return sort_items(items)


def sort_items(items):
    posts = sorted([i for i in items if i.kind == "post" and not i.draft], key=lambda x: (x.date or "", x.slug), reverse=True)
    posts = sorted(posts, key=lambda x: (-(int((x.date or "0000-00-00").replace("-", ""))), x.slug))
    pages = sorted([i for i in items if i.kind == "page" and not i.draft], key=lambda x: (x.title, x.slug))
    drafts = sorted([i for i in items if i.draft], key=lambda x: (x.date or "", x.slug), reverse=True)
    return posts + pages + drafts


def find_links(body, title_map, source_map):
    links = []
    for m in re.finditer(r"\[[^\]]+\]\(([^)]+)\)", body):
        target = m.group(1)
        if target.startswith("http://") or target.startswith("https://"):
            continue
        target = target.replace("\\", "/")
        if target.endswith(".md") or target.endswith(".html"):
            key = target[:-5] + ".md" if target.endswith(".html") else target
            if key in source_map:
                links.append(source_map[key])
            elif Path(key).name in source_map:
                links.append(source_map[Path(key).name])
    for m in re.finditer(r"\[\[([^\]|]+)(?:\|([^\]]+))?\]\]", body):
        title = m.group(1).strip().lower()
        if title in title_map:
            links.append(title_map[title])
    return sorted(set(links))


def inspect_state(items):
    posts = [i for i in items if i.kind == "post" and not i.draft]
    pages = [i for i in items if i.kind == "page" and not i.draft]
    drafts = [i for i in items if i.draft]
    tags = {}
    streams = {}
    for item in posts:
        streams.setdefault(item.stream or "index", []).append(item.slug)
        for tag in item.tags:
            tags.setdefault(slugify(tag), []).append(item.slug)
    return {
        "posts": [i.public() for i in posts],
        "pages": [i.public() for i in pages],
        "tags": tags,
        "streams": streams,
        "drafts": [i.public() for i in drafts],
    }


def render_inline(text, title_map, source_map):
    pieces = []
    pos = 0
    pattern = re.compile(r"(\[[^\]]+\]\([^)]+\)|\[\[[^\]]+\]\])")
    for m in pattern.finditer(text):
        pieces.append(html.escape(text[pos : m.start()]))
        token = m.group(0)
        if token.startswith("[["):
            inner = token[2:-2]
            title, label = (inner.split("|", 1) + [None])[:2] if "|" in inner else (inner, None)
            label = label or title
            slug = title_map.get(title.strip().lower())
            if slug:
                pieces.append(f'<a href="{slug}.html">{html.escape(label)}</a>')
            else:
                missing = slugify(title)
                pieces.append(f'<a href="{missing}.html" data-wikilink="missing">{html.escape(label)}</a>')
        else:
            mm = re.fullmatch(r"\[([^\]]+)\]\(([^)]+)\)", token)
            label, target = mm.group(1), mm.group(2)
            href = target
            if not (target.startswith("http://") or target.startswith("https://")):
                key = target[:-5] + ".md" if target.endswith(".html") else target
                slug = source_map.get(key) or source_map.get(Path(key).name)
                if slug:
                    href = f"{slug}.html"
            pieces.append(f'<a href="{html.escape(href)}">{html.escape(label)}</a>')
        pos = m.end()
    pieces.append(html.escape(text[pos:]))
    return "".join(pieces)


def render_body(item, title_map, source_map):
    out = []
    for line in item.body.splitlines():
        if not line.strip():
            continue
        if line.startswith("# "):
            text = line[2:].strip()
            out.append(f'<h1 id="{slugify(text)}">{html.escape(text)}</h1>')
        elif line.startswith("## "):
            text = line[3:].strip()
            out.append(f'<h2 id="{slugify(text)}">{html.escape(text)}</h2>')
        else:
            out.append(f"<p>{render_inline(line.strip(), title_map, source_map)}</p>")
    return "\n".join(out)


def plain_text(item):
    lines = []
    for line in item.body.splitlines():
        if not line.strip():
            continue
        line = re.sub(r"^#+\s*", "", line.strip())
        line = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", line)
        line = re.sub(r"\[\[([^\]|]+)\|([^\]]+)\]\]", r"\2", line)
        line = re.sub(r"\[\[([^\]]+)\]\]", r"\1", line)
        lines.append(line)
    return " ".join(lines)


def write_text(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def page_html(item, body):
    parts = [f"<html><head><title>{html.escape(item.title)}</title></head><body>", body]
    if item.backlinks:
        parts.append("<section>")
        parts.extend(f'<a href="{html.escape(src)}.html">{html.escape(src)}</a>' for src in item.backlinks)
        parts.append("</section>")
    parts.append("</body></html>")
    return "\n".join(parts)


def list_html(title, items):
    links = "".join(f'<li><a href="{i.slug}.html">{html.escape(i.title)}</a></li>' for i in items)
    return f"<html><head><title>{html.escape(title)}</title></head><body><ul>{links}</ul></body></html>"


def chunks(seq, n):
    return [seq[i : i + n] for i in range(0, len(seq), n)] or [[]]


def paginated_names(base, items, per_page):
    pages = chunks(items, per_page)
    names = []
    for idx, _ in enumerate(pages, 1):
        names.append(f"{base}.html" if idx == 1 else f"{base}-{idx}.html")
    return names, pages


def feed_url(base_url, slug):
    return f"{base_url.rstrip('/')}/{slug}.html" if base_url else f"{slug}.html"


def feed_item(item, base_url):
    return {
        "title": item.title,
        "slug": item.slug,
        "url": feed_url(base_url, item.slug),
        "date": item.date,
        "tags": item.tags,
        "stream": item.stream,
        "description": item.description,
    }


def build(input_dir, output_dir, config_path=None):
    cfg = parse_config(input_dir, config_path)
    items = load_items(input_dir)
    posts = [i for i in items if i.kind == "post" and not i.draft]
    pages = [i for i in items if i.kind == "page" and not i.draft]
    title_map = {i.title.lower(): i.slug for i in posts + pages}
    source_map = {i.source: i.slug for i in posts + pages}
    source_map.update({Path(i.source).name: i.slug for i in posts + pages})
    out = Path(output_dir)
    tmp = out.parent / (out.name + ".tmp_minisite")
    if tmp.exists():
        shutil.rmtree(tmp)
    tmp.mkdir(parents=True)
    manifest = {k: [] for k in ["posts", "pages", "index", "tags", "streams", "archives", "feeds", "search", "misc"]}
    try:
        for item in posts + pages:
            write_text(tmp / f"{item.slug}.html", page_html(item, render_body(item, title_map, source_map)))
            manifest[item.kind + "s"].append(f"{item.slug}.html")
        index_posts = [i for i in posts if i.stream == "index"]
        names, page_groups = paginated_names("index", index_posts, cfg["pagination"])
        for name, group in zip(names, page_groups):
            write_text(tmp / name, list_html("Index", group))
            manifest["index"].append(name)
        if pages:
            write_text(tmp / "pages.html", list_html("Pages", pages))
            manifest["pages"].append("pages.html")
        tag_groups = {}
        for item in posts:
            for tag in item.tags:
                tag_groups.setdefault(slugify(tag), []).append(item)
        for tag in sorted(tag_groups):
            names, page_groups = paginated_names(f"tag-{tag}", tag_groups[tag], cfg["pagination"])
            for name, group in zip(names, page_groups):
                write_text(tmp / name, list_html(f"Tag {tag}", group))
                manifest["tags"].append(name)
        if tag_groups:
            write_text(tmp / "tags.html", "<html><body>" + "".join(f'<a href="tag-{t}.html">{t}</a>' for t in sorted(tag_groups)) + "</body></html>")
            manifest["tags"].append("tags.html")
        stream_groups = {}
        for item in posts:
            if item.stream not in {"index", "draft", None}:
                stream_groups.setdefault(item.stream, []).append(item)
        for stream in sorted(stream_groups):
            names, page_groups = paginated_names(stream, stream_groups[stream], cfg["pagination"])
            for name, group in zip(names, page_groups):
                write_text(tmp / name, list_html(f"Stream {stream}", group))
                manifest["streams"].append(name)
        if stream_groups:
            write_text(tmp / "streams.html", "<html><body>" + "".join(f'<a href="{s}.html">{s}</a>' for s in sorted(stream_groups)) + "</body></html>")
            manifest["streams"].append("streams.html")
        archive_groups = {}
        for item in posts:
            archive_groups.setdefault(item.date[:4], []).append(item)
        for year in sorted(archive_groups, reverse=True):
            names, page_groups = paginated_names(f"archive-{year}", archive_groups[year], cfg["pagination"])
            for name, group in zip(names, page_groups):
                write_text(tmp / name, list_html(f"Archive {year}", group))
                manifest["archives"].append(name)
        if archive_groups:
            write_text(tmp / "archive.html", "<html><body>" + "".join(f'<a href="archive-{y}.html">{y}</a>' for y in sorted(archive_groups, reverse=True)) + "</body></html>")
            manifest["archives"].append("archive.html")
        if cfg["json_feed"]:
            write_json(tmp / "feed.json", {"title": cfg["site_name"], "items": [feed_item(i, cfg["base_url"]) for i in index_posts]})
            manifest["feeds"].append("feed.json")
            for tag in sorted(tag_groups):
                name = f"tag-{tag}.json"
                write_json(tmp / name, {"title": f"tag:{tag}", "items": [feed_item(i, cfg["base_url"]) for i in tag_groups[tag]]})
                manifest["feeds"].append(name)
            for stream in sorted(stream_groups):
                name = f"{stream}.json"
                write_json(tmp / name, {"title": f"stream:{stream}", "items": [feed_item(i, cfg["base_url"]) for i in stream_groups[stream]]})
                manifest["feeds"].append(name)
            for year in sorted(archive_groups, reverse=True):
                name = f"archive-{year}.json"
                write_json(tmp / name, {"title": f"archive:{year}", "items": [feed_item(i, cfg["base_url"]) for i in archive_groups[year]]})
                manifest["feeds"].append(name)
        if cfg["enable_search"]:
            search = []
            for item in posts + pages:
                search.append({
                    "title": item.title,
                    "slug": item.slug,
                    "url": feed_url(cfg["base_url"], item.slug),
                    "kind": item.kind,
                    "tags": item.tags,
                    "stream": item.stream,
                    "text": plain_text(item),
                })
            write_json(tmp / "search_index.json", search)
            manifest["search"].append("search_index.json")
        manifest["misc"].append("urls.json")
        manifest["summary"] = {k: len(v) for k, v in manifest.items() if isinstance(v, list)}
        manifest["summary"]["total"] = sum(manifest["summary"].values()) - 1
        write_json(tmp / "urls.json", manifest)
        if out.exists():
            for child in out.iterdir():
                if child.is_file() and child.name in {p for vals in manifest.values() if isinstance(vals, list) for p in vals}:
                    child.unlink()
        else:
            out.mkdir(parents=True)
        for child in tmp.iterdir():
            target = out / child.name
            if target.exists():
                target.unlink()
            child.replace(target)
    except Exception:
        if tmp.exists():
            shutil.rmtree(tmp)
        raise
    if tmp.exists():
        shutil.rmtree(tmp)
    return manifest


def preview_urls(input_dir, config_path=None):
    with tempfile.TemporaryDirectory(prefix="minisite_urls_") as td:
        return build(input_dir, Path(td) / "out", config_path)


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, separators=(",", ":"), sort_keys=False) + "\n")


def main(argv=None):
    parser = argparse.ArgumentParser(add_help=False)
    sub = parser.add_subparsers(dest="command")
    build_p = sub.add_parser("build")
    build_p.add_argument("--input", required=True)
    build_p.add_argument("--output", required=True)
    build_p.add_argument("--config")
    inspect_p = sub.add_parser("inspect")
    inspect_p.add_argument("--input", required=True)
    inspect_p.add_argument("--config")
    urls_p = sub.add_parser("urls")
    urls_p.add_argument("--input", required=True)
    urls_p.add_argument("--config")
    try:
        args = parser.parse_args(argv)
        if args.command == "inspect":
            parse_config(args.input, args.config)
            result = inspect_state(load_items(args.input))
        elif args.command == "build":
            result = build(args.input, args.output, args.config)
        elif args.command == "urls":
            result = preview_urls(args.input, args.config)
        else:
            raise ValueError("unsupported command")
        print(json.dumps(result, separators=(",", ":"), sort_keys=False))
        return 0
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
