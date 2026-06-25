#!/usr/bin/env python3
import argparse
import datetime as _dt
import html
import json
import os
import re
import shutil
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

    def public_model(self) -> dict:
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


def slugify(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "-", value.lower()).strip("-")


def strip_quotes(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value


def parse_bool(value: str, label: str) -> bool:
    lowered = strip_quotes(value).strip().lower()
    if lowered == "true":
        return True
    if lowered == "false":
        return False
    raise MiniSiteError(f"invalid boolean for {label}: {value}")


def parse_date(value: str, label: str) -> str:
    value = strip_quotes(value).strip()
    for fmt in ("%Y-%m-%d", "%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S"):
        try:
            return _dt.datetime.strptime(value, fmt).date().isoformat()
        except ValueError:
            pass
    raise MiniSiteError(f"invalid date for {label}: {value}")


def valid_date_prefix(value: str) -> str | None:
    try:
        return _dt.datetime.strptime(value, "%Y-%m-%d").date().isoformat()
    except ValueError:
        return None


def parse_tags(value: str) -> list[str]:
    raw = strip_quotes(value).strip()
    if raw.startswith("[") and raw.endswith("]"):
        raw_items = raw[1:-1].split(",")
    else:
        raw_items = raw.split(",")
    tags = []
    seen = set()
    for item in raw_items:
        cleaned = strip_quotes(item).strip()
        if cleaned and cleaned not in seen:
            tags.append(cleaned)
            seen.add(cleaned)
    return tags


def read_config(input_dir: Path, config_path: str | None) -> dict:
    config = dict(DEFAULT_CONFIG)
    path = Path(config_path) if config_path else input_dir / "marmite.yaml"
    if not path.exists():
        return config
    if not path.is_file():
        raise MiniSiteError(f"config is not a file: {path}")
    for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if ":" not in stripped:
            raise MiniSiteError(f"invalid config line {lineno}: {line}")
        key, value = stripped.split(":", 1)
        key = key.strip()
        value = value.strip()
        if key == "site_name":
            config[key] = strip_quotes(value)
        elif key == "base_url":
            config[key] = strip_quotes(value).rstrip("/")
        elif key == "pagination":
            try:
                pagination = int(strip_quotes(value))
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


def split_frontmatter(text: str, source: str) -> tuple[dict, str]:
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
    meta: dict[str, object] = {}
    for lineno, line in enumerate(lines[1:end], 2):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if ":" not in stripped:
            raise MiniSiteError(f"invalid frontmatter line {lineno} in {source}")
        key, value = stripped.split(":", 1)
        key = key.strip()
        value = value.strip()
        try:
            if key in {"title", "slug", "stream", "description"}:
                meta[key] = strip_quotes(value)
            elif key == "date":
                meta[key] = parse_date(value, f"date in {source}")
            elif key == "tags":
                meta[key] = parse_tags(value)
        except MiniSiteError:
            raise
        except Exception as exc:
            raise MiniSiteError(f"invalid frontmatter value for {key} in {source}") from exc
    body = "\n".join(lines[end + 1 :])
    if text.endswith("\n"):
        body += "\n"
    return meta, body


def first_heading(body: str) -> str | None:
    for line in body.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return None


def filename_info(stem: str, fm_date: str | None) -> dict:
    info = {
        "date": None,
        "stream": None,
        "base": stem,
        "clean_title": stem,
        "stream_prefixed": False,
    }
    match = re.match(r"^(\d{4}-\d{2}-\d{2})-(\d{2})-(\d{2})-(\d{2})-(.+)$", stem)
    if match and valid_date_prefix(match.group(1)):
        info["date"] = match.group(1)
        info["base"] = match.group(5)
        info["clean_title"] = match.group(5)
        return info
    match = re.match(r"^(\d{4}-\d{2}-\d{2})-(.+)$", stem)
    if match and valid_date_prefix(match.group(1)):
        info["date"] = match.group(1)
        info["base"] = match.group(2)
        info["clean_title"] = match.group(2)
        return info
    match = re.match(r"^([A-Za-z0-9][A-Za-z0-9_-]*)-(\d{4}-\d{2}-\d{2})-(.+)$", stem)
    if match and valid_date_prefix(match.group(2)):
        info["date"] = match.group(2)
        info["stream"] = slugify(match.group(1)) or match.group(1).lower()
        info["base"] = match.group(3)
        info["clean_title"] = match.group(3)
        info["stream_prefixed"] = True
        return info
    parts = stem.split("-")
    if fm_date and len(parts) >= 3 and (parts[1] == "S" or parts[1].isdigit()):
        info["stream"] = slugify(parts[0]) or parts[0].lower()
        info["base"] = "-".join(parts[2:])
        info["clean_title"] = "-".join(parts[2:])
        info["stream_prefixed"] = True
    return info


def content_root(input_dir: Path) -> Path:
    nested = input_dir / "content"
    return nested if nested.is_dir() else input_dir


def iter_markdown_files(root: Path) -> list[Path]:
    paths: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames.sort()
        for filename in sorted(filenames):
            if filename.startswith("_") or not filename.endswith(".md"):
                continue
            paths.append(Path(dirpath) / filename)
    return paths


def parse_items(input_dir: Path, config_path: str | None = None) -> tuple[dict, list[Item]]:
    if not input_dir.exists() or not input_dir.is_dir():
        raise MiniSiteError(f"missing input directory: {input_dir}")
    config = read_config(input_dir, config_path)
    root = content_root(input_dir)
    items: list[Item] = []
    for path in iter_markdown_files(root):
        source = path.relative_to(root).as_posix()
        text = path.read_text(encoding="utf-8")
        meta, body = split_frontmatter(text, source)
        stem = path.stem
        fm_date = meta.get("date")
        info = filename_info(stem, fm_date if isinstance(fm_date, str) else None)
        date = fm_date if isinstance(fm_date, str) else info["date"]
        kind = "post" if date else "page"
        heading = first_heading(body)
        title = str(meta.get("title") or heading or info["clean_title"])
        base_slug = slugify(str(meta.get("slug") or info["base"] if not meta.get("slug") and (info["date"] or info["stream_prefixed"]) else meta.get("slug") or title))
        if not base_slug:
            raise MiniSiteError(f"empty slug for {source}")
        stream: str | None = None
        if kind == "post":
            raw_stream = meta.get("stream") if meta.get("stream") is not None else info["stream"]
            stream = slugify(str(raw_stream)) if raw_stream else "index"
            if not stream:
                stream = "index"
        if kind == "post" and stream and stream != "index":
            if not base_slug.startswith(stream + "-") or meta.get("stream") is not None:
                slug = f"{stream}-{base_slug}"
            else:
                slug = base_slug
        else:
            slug = base_slug
        items.append(
            Item(
                title=title,
                slug=slug,
                source=source,
                kind=kind,
                date=date,
                tags=list(meta.get("tags") or []) if kind == "post" else [],
                stream=stream if kind == "post" else None,
                description=meta.get("description") if isinstance(meta.get("description"), str) else None,
                draft=(kind == "post" and stream == "draft"),
                body=body,
            )
        )
    compute_links(items)
    seen: dict[str, str] = {}
    for item in items:
        if item.draft:
            continue
        if item.slug in seen:
            raise MiniSiteError(f"duplicate slug among non-draft content: {item.slug}")
        seen[item.slug] = item.source
    return config, items


def ordered_posts(items: list[Item]) -> list[Item]:
    return sorted([i for i in items if i.kind == "post" and not i.draft], key=lambda i: (i.date or "", i.slug), reverse=False)[::-1]


def post_sort_key(item: Item) -> tuple[str, str]:
    return (item.date or "", item.slug)


def sorted_posts(items: list[Item]) -> list[Item]:
    return sorted([i for i in items if i.kind == "post" and not i.draft], key=lambda i: (-(int((i.date or "0000-00-00").replace("-", ""))), i.slug))


def sorted_pages(items: list[Item]) -> list[Item]:
    return sorted([i for i in items if i.kind == "page" and not i.draft], key=lambda i: (i.title.lower(), i.slug))


def unique_in_order(values: list[str]) -> list[str]:
    out = []
    seen = set()
    for value in values:
        if value not in seen:
            out.append(value)
            seen.add(value)
    return out


def compute_links(items: list[Item]) -> None:
    title_map = {i.title.lower(): i.slug for i in items}
    source_map = {i.source: i.slug for i in items}
    source_stem_map = {Path(i.source).with_suffix("").as_posix(): i.slug for i in items}
    slug_set = {i.slug for i in items}

    def resolve_local(target: str) -> str:
        clean = target.split("#", 1)[0].split("?", 1)[0]
        if clean.endswith(".md") or clean.endswith(".html"):
            without = str(Path(clean).with_suffix("")).replace("\\", "/")
            base = Path(without).name
            return source_stem_map.get(without) or source_stem_map.get(base) or source_map.get(clean) or slugify(base)
        return slugify(Path(clean).stem or clean)

    for item in items:
        links: list[str] = []
        for match in re.finditer(r"\[([^\]]+)\]\(([^)]+)\)", item.body):
            target = match.group(2).strip()
            if target.startswith("http://") or target.startswith("https://"):
                continue
            links.append(resolve_local(target))
        for match in re.finditer(r"\[\[([^\]|]+)(?:\|([^\]]+))?\]\]", item.body):
            title = match.group(1).strip()
            links.append(title_map.get(title.lower(), slugify(title)))
        item.links_to = unique_in_order(links)
        item.backlinks = []

    public = {i.slug for i in items if not i.draft}
    backlinks: dict[str, list[str]] = {slug: [] for slug in public}
    for source in items:
        if source.draft:
            continue
        for target in source.links_to:
            if target in public and source.slug not in backlinks[target]:
                backlinks[target].append(source.slug)
    for item in items:
        if item.slug in slug_set:
            item.backlinks = sorted(backlinks.get(item.slug, []))


def url_for(slug: str, config: dict) -> str:
    path = f"{slug}.html"
    base = config["base_url"]
    return f"{base}/{path}" if base else path


def resolve_context(items: list[Item]):
    title_map = {i.title.lower(): i.slug for i in items if not i.draft}
    source_stem_map = {Path(i.source).with_suffix("").as_posix(): i.slug for i in items if not i.draft}

    def local_slug(target: str) -> str:
        clean = target.split("#", 1)[0].split("?", 1)[0]
        without = str(Path(clean).with_suffix("")).replace("\\", "/")
        return source_stem_map.get(without) or source_stem_map.get(Path(without).name) or slugify(Path(without).name)

    return title_map, local_slug


def render_inline(text: str, title_map: dict[str, str], local_slug) -> str:
    pattern = re.compile(r"(\[([^\]]+)\]\(([^)]+)\)|\[\[([^\]|]+)(?:\|([^\]]+))?\]\])")
    result: list[str] = []
    pos = 0
    for match in pattern.finditer(text):
        result.append(html.escape(text[pos : match.start()]))
        if match.group(2) is not None:
            label = match.group(2)
            target = match.group(3).strip()
            if target.startswith("http://") or target.startswith("https://"):
                href = target
            else:
                href = f"{local_slug(target)}.html"
            result.append(f'<a href="{html.escape(href, quote=True)}">{html.escape(label)}</a>')
        else:
            title = match.group(4).strip()
            label = (match.group(5) or title).strip()
            slug = title_map.get(title.lower())
            if slug:
                result.append(f'<a href="{html.escape(slug + ".html", quote=True)}">{html.escape(label)}</a>')
            else:
                href = f"{slugify(title)}.html"
                result.append(f'<a data-wikilink="missing" href="{html.escape(href, quote=True)}">{html.escape(label)}</a>')
        pos = match.end()
    result.append(html.escape(text[pos:]))
    return "".join(result)


def plain_inline(text: str) -> str:
    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r"\1", text)
    text = re.sub(r"\[\[([^\]|]+)\|([^\]]+)\]\]", r"\2", text)
    text = re.sub(r"\[\[([^\]]+)\]\]", r"\1", text)
    return text.strip()


def render_body(item: Item, items: list[Item]) -> tuple[str, str]:
    title_map, local_slug = resolve_context(items)
    html_lines: list[str] = []
    plain_lines: list[str] = []
    for raw in item.body.splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith("## "):
            text = line[3:].strip()
            html_lines.append(f'<h2 id="{html.escape(slugify(text), quote=True)}">{render_inline(text, title_map, local_slug)}</h2>')
            plain_lines.append(plain_inline(text))
        elif line.startswith("# "):
            text = line[2:].strip()
            html_lines.append(f'<h1 id="{html.escape(slugify(text), quote=True)}">{render_inline(text, title_map, local_slug)}</h1>')
            plain_lines.append(plain_inline(text))
        else:
            html_lines.append(f"<p>{render_inline(line, title_map, local_slug)}</p>")
            plain_lines.append(plain_inline(line))
    return "\n".join(html_lines), " ".join(p for p in plain_lines if p)


def page_shell(title: str, body: str) -> str:
    return f"<!doctype html>\n<html><head><meta charset=\"utf-8\"><title>{html.escape(title)}</title></head><body>\n{body}\n</body></html>\n"


def content_page(item: Item, items: list[Item]) -> str:
    body, _ = render_body(item, items)
    if item.backlinks:
        links = "".join(f'<li><a href="{html.escape(slug + ".html", quote=True)}">{html.escape(slug)}</a></li>' for slug in item.backlinks)
        body += f'\n<section class="backlinks"><h2 id="backlinks">Backlinks</h2><ul>{links}</ul></section>'
    return page_shell(item.title, body)


def listing_page(title: str, entries: list[Item]) -> str:
    links = "".join(f'<li><a href="{html.escape(item.slug + ".html", quote=True)}">{html.escape(item.title)}</a></li>' for item in entries)
    return page_shell(title, f"<h1>{html.escape(title)}</h1>\n<ul>{links}</ul>")


def hub_page(title: str, entries: list[tuple[str, str]]) -> str:
    links = "".join(f'<li><a href="{html.escape(path, quote=True)}">{html.escape(label)}</a></li>' for label, path in entries)
    return page_shell(title, f"<h1>{html.escape(title)}</h1>\n<ul>{links}</ul>")


def chunks(values: list[Item], size: int) -> list[list[Item]]:
    return [values[i : i + size] for i in range(0, len(values), size)] or [[]]


def feed_item(item: Item, config: dict) -> dict:
    return {
        "title": item.title,
        "slug": item.slug,
        "url": url_for(item.slug, config),
        "date": item.date,
        "tags": item.tags,
        "stream": item.stream,
        "description": item.description,
    }


def build_outputs(config: dict, items: list[Item]) -> tuple[dict[str, str], dict]:
    outputs: dict[str, str] = {}
    manifest = {key: [] for key in ("posts", "pages", "index", "tags", "streams", "feeds", "search", "misc")}
    posts = sorted_posts(items)
    pages = sorted_pages(items)
    pagination = config["pagination"]

    for item in posts:
        path = f"{item.slug}.html"
        outputs[path] = content_page(item, items)
        manifest["posts"].append(path)
    for item in pages:
        path = f"{item.slug}.html"
        outputs[path] = content_page(item, items)
        manifest["pages"].append(path)

    index_posts = [p for p in posts if p.stream == "index"]
    for idx, group in enumerate(chunks(index_posts, pagination), 1):
        path = "index.html" if idx == 1 else f"index-{idx}.html"
        outputs[path] = listing_page(config["site_name"], group)
        manifest["index"].append(path)

    if pages:
        outputs["pages.html"] = listing_page("Pages", pages)
        manifest["pages"].append("pages.html")

    tag_posts: dict[str, list[Item]] = {}
    for post in posts:
        for tag in post.tags:
            tag_slug = slugify(tag)
            if tag_slug:
                tag_posts.setdefault(tag_slug, []).append(post)
    tag_hub: list[tuple[str, str]] = []
    for tag_slug in sorted(tag_posts):
        groups = chunks(tag_posts[tag_slug], pagination)
        tag_hub.append((tag_slug, f"tag-{tag_slug}.html"))
        for idx, group in enumerate(groups, 1):
            path = f"tag-{tag_slug}.html" if idx == 1 else f"tag-{tag_slug}-{idx}.html"
            outputs[path] = listing_page(f"Tag: {tag_slug}", group)
            manifest["tags"].append(path)
    if tag_hub:
        outputs["tags.html"] = hub_page("Tags", tag_hub)
        manifest["tags"].append("tags.html")

    stream_posts: dict[str, list[Item]] = {}
    for post in posts:
        if post.stream and post.stream not in {"index", "draft"}:
            stream_posts.setdefault(post.stream, []).append(post)
    stream_hub: list[tuple[str, str]] = []
    for stream in sorted(stream_posts):
        groups = chunks(stream_posts[stream], pagination)
        stream_hub.append((stream, f"{stream}.html"))
        for idx, group in enumerate(groups, 1):
            path = f"{stream}.html" if idx == 1 else f"{stream}-{idx}.html"
            outputs[path] = listing_page(f"Stream: {stream}", group)
            manifest["streams"].append(path)
    if stream_hub:
        outputs["streams.html"] = hub_page("Streams", stream_hub)
        manifest["streams"].append("streams.html")

    if config["json_feed"]:
        outputs["feed.json"] = compact_json({"title": config["site_name"], "items": [feed_item(p, config) for p in index_posts]})
        manifest["feeds"].append("feed.json")
        for tag_slug in sorted(tag_posts):
            path = f"tag-{tag_slug}.json"
            outputs[path] = compact_json({"title": f"tag:{tag_slug}", "items": [feed_item(p, config) for p in tag_posts[tag_slug]]})
            manifest["feeds"].append(path)
        for stream in sorted(stream_posts):
            path = f"{stream}.json"
            outputs[path] = compact_json({"title": f"stream:{stream}", "items": [feed_item(p, config) for p in stream_posts[stream]]})
            manifest["feeds"].append(path)

    if config["enable_search"]:
        search_items = []
        for item in posts + pages:
            _, plain = render_body(item, items)
            search_items.append(
                {
                    "title": item.title,
                    "slug": item.slug,
                    "url": url_for(item.slug, config),
                    "kind": item.kind,
                    "tags": item.tags,
                    "stream": item.stream,
                    "text": plain,
                }
            )
        outputs["search_index.json"] = compact_json(search_items)
        manifest["search"].append("search_index.json")

    manifest["misc"].append("urls.json")
    summary = {key: len(value) for key, value in manifest.items()}
    summary["total"] = sum(summary.values()) - 1
    manifest["summary"] = summary
    outputs["urls.json"] = compact_json(manifest)
    return outputs, manifest


def compact_json(value) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def inspect_model(items: list[Item]) -> dict:
    posts = sorted_posts(items)
    pages = sorted_pages(items)
    drafts = sorted([i for i in items if i.draft], key=lambda i: (i.date or "", i.slug))
    tags: dict[str, list[str]] = {}
    streams: dict[str, list[str]] = {}
    for post in posts:
        for tag in post.tags:
            tag_slug = slugify(tag)
            if tag_slug:
                tags.setdefault(tag_slug, []).append(post.slug)
        if post.stream and post.stream != "draft":
            streams.setdefault(post.stream, []).append(post.slug)
    return {
        "posts": [p.public_model() for p in posts],
        "pages": [p.public_model() for p in pages],
        "tags": {k: tags[k] for k in sorted(tags)},
        "streams": {k: streams[k] for k in sorted(streams)},
        "drafts": [d.public_model() for d in drafts],
    }


def write_outputs(output_dir: Path, outputs: dict[str, str]) -> None:
    parent = output_dir.parent if output_dir.parent != Path("") else Path(".")
    temp = parent / f".{output_dir.name}.minisite-tmp"
    if temp.exists():
        shutil.rmtree(temp)
    written: list[Path] = []
    try:
        temp.mkdir(parents=True)
        for relpath, content in outputs.items():
            target = temp / relpath
            target.write_text(content, encoding="utf-8")
        output_dir.mkdir(parents=True, exist_ok=True)
        for relpath in sorted(outputs):
            src = temp / relpath
            dest = output_dir / relpath
            os.replace(src, dest)
            written.append(dest)
    except Exception as exc:
        for path in written:
            try:
                path.unlink()
            except OSError:
                pass
        raise MiniSiteError(f"unable to create or write output directory: {output_dir}") from exc
    finally:
        if temp.exists():
            shutil.rmtree(temp, ignore_errors=True)


def do_build(args) -> int:
    config, items = parse_items(Path(args.input), args.config)
    outputs, manifest = build_outputs(config, items)
    write_outputs(Path(args.output), outputs)
    print(compact_json(manifest))
    return 0


def do_inspect(args) -> int:
    _, items = parse_items(Path(args.input), args.config)
    print(compact_json(inspect_model(items)))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="minisite.py")
    subparsers = parser.add_subparsers(dest="command", required=True)
    build = subparsers.add_parser("build")
    build.add_argument("--input", required=True)
    build.add_argument("--output", required=True)
    build.add_argument("--config")
    build.set_defaults(func=do_build)
    inspect = subparsers.add_parser("inspect")
    inspect.add_argument("--input", required=True)
    inspect.add_argument("--config")
    inspect.set_defaults(func=do_inspect)
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except MiniSiteError as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
