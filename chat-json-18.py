import argparse
import json
import re
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path


VERSION_SUFFIX = re.compile(r"^(?P<base>.+)-v(?P<version>\d+)$")
CHATGPT_MARKER_RE = re.compile(r"\ue200([a-zA-Z_]+)\ue202(.*?)\ue201", re.DOTALL)
MARKER_FIELD_SEPARATOR = "\ue202"
PRIVATE_TEXT_MARKS = {
    "\ue203": "",
    "\ue204": "",
    "\ue205": "",
    "\ue206": "",
}
JSON_TOOL_KEYS = {
    "click",
    "finance",
    "find",
    "image_query",
    "open",
    "screenshot",
    "search_query",
    "sports",
    "time",
    "weather",
}
RESERVED_WINDOWS_NAMES = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    "COM1",
    "COM2",
    "COM3",
    "COM4",
    "COM5",
    "COM6",
    "COM7",
    "COM8",
    "COM9",
    "LPT1",
    "LPT2",
    "LPT3",
    "LPT4",
    "LPT5",
    "LPT6",
    "LPT7",
    "LPT8",
    "LPT9",
}


def sanitize_filename(filename):
    if filename is None or str(filename).strip() == "":
        filename = "noname"

    filename = str(filename)
    invalid_characters = '<>:"/\\|?*\n\r\t'
    for char in invalid_characters:
        filename = filename.replace(char, "")

    filename = " ".join(filename.split()).strip().strip(".")
    if not filename:
        filename = "noname"
    if filename.upper() in RESERVED_WINDOWS_NAMES:
        filename = f"{filename}_"

    return filename[:160].rstrip() or "noname"


def iter_json_files(input_path):
    path = Path(input_path)
    if path.is_dir():
        files = sorted(item for item in path.glob("*.json") if item.is_file())
        if not files:
            raise FileNotFoundError(f"No JSON files found in {path}")
        return files
    if path.is_file():
        return [path]
    raise FileNotFoundError(f"Input path not found: {path}")


def conversations_from_json(data, source_path):
    if isinstance(data, list):
        for item in data:
            if isinstance(item, dict):
                yield item, source_path
        return

    if isinstance(data, dict):
        if "mapping" in data:
            yield data, source_path
            return

        conversations = data.get("conversations")
        if isinstance(conversations, list):
            for item in conversations:
                if isinstance(item, dict):
                    yield item, source_path
            return

    raise ValueError(f"Unsupported JSON export shape in {source_path}")


def load_conversations(input_path):
    conversations = []
    source_paths = iter_json_files(input_path)
    for source_path in source_paths:
        with source_path.open("r", encoding="utf-8") as infile:
            data = json.load(infile)
        conversations.extend(conversations_from_json(data, source_path))
    return conversations, source_paths


def numeric_timestamp(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def conversation_sort_key(entry):
    item, source_path = entry
    timestamp = numeric_timestamp(item.get("create_time") or item.get("update_time"))
    title = sanitize_filename(item.get("title"))
    conversation_id = item.get("conversation_id") or item.get("id") or ""
    return timestamp, title.lower(), str(conversation_id), source_path.name


def timestamp_to_date(timestamp):
    timestamp = numeric_timestamp(timestamp)
    if timestamp <= 0:
        return "unknown-date"
    return datetime.fromtimestamp(timestamp).date().isoformat()


def resolve_output_dir(output_dir, auto_version_output):
    output_path = Path(output_dir)
    if not auto_version_output:
        output_path.mkdir(parents=True, exist_ok=True)
        return output_path

    match = VERSION_SUFFIX.match(output_path.name)
    if match:
        version_base = output_path.with_name(match.group("base"))
    else:
        version_base = output_path

    version = 1
    while True:
        candidate = version_base.with_name(f"{version_base.name}-v{version}")
        if not candidate.exists() or not any(candidate.iterdir()):
            candidate.mkdir(parents=True, exist_ok=True)
            return candidate
        version += 1


def generate_unique_filename(base_path, title, used_names):
    safe_title = sanitize_filename(title)
    version = 0
    while True:
        suffix = "" if version == 0 else f"_v{version}"
        filename = f"{safe_title}{suffix}.md"
        file_path = base_path / filename
        normalized = filename.casefold()
        if normalized not in used_names and not file_path.exists():
            used_names.add(normalized)
            return file_path
        version += 1


def code_fence(text, language=None):
    text = "" if text is None else str(text)
    fence = "```"
    while fence in text:
        fence += "`"

    language = "" if language in (None, "unknown") else str(language).strip()
    return f"{fence}{language}\n{text}\n{fence}"


def extension_from_asset(value):
    for key in ("mime_type", "mimeType"):
        mime_type = value.get(key)
        if isinstance(mime_type, str) and "/" in mime_type:
            subtype = mime_type.rsplit("/", 1)[-1].split(";", 1)[0].lower()
            if subtype == "jpeg":
                return ".jpg"
            if subtype:
                return f".{subtype}"

    metadata = value.get("metadata") or {}
    for key in ("mime_type", "mimeType"):
        mime_type = metadata.get(key)
        if isinstance(mime_type, str) and "/" in mime_type:
            subtype = mime_type.rsplit("/", 1)[-1].split(";", 1)[0].lower()
            if subtype == "jpeg":
                return ".jpg"
            if subtype:
                return f".{subtype}"

    return ""


def asset_placeholder_name(pointer, value):
    pointer = str(pointer or "image")
    name = pointer.rstrip("/").rsplit("/", 1)[-1] or "image"
    name = name.split("?", 1)[0].split("#", 1)[0]
    name = sanitize_filename(name)
    if "." not in Path(name).name:
        extension = extension_from_asset(value)
        if extension:
            return f"{name}{extension}"
    return name


def render_asset_pointer(value):
    pointer = value.get("asset_pointer") or value.get("url") or value.get("ref_id") or "unknown"
    content_type = value.get("content_type") or "asset"
    label = "image" if "image" in content_type else content_type.replace("_asset_pointer", "") or "asset"
    lines = [f"[{label}: {asset_placeholder_name(pointer, value)}]"]

    metadata = value.get("metadata") or {}
    dalle = metadata.get("dalle") or {}
    prompt = dalle.get("prompt")
    if prompt:
        lines.append(f"Prompt: {prompt}")

    return "\n\n".join(lines)


def render_part(part):
    if part is None:
        return ""
    if isinstance(part, str):
        return part
    if isinstance(part, dict):
        if part.get("content_type") == "image_asset_pointer" or "asset_pointer" in part:
            return render_asset_pointer(part)
        if "text" in part:
            return str(part.get("text") or "")
        if "content" in part and isinstance(part.get("content"), str):
            return part["content"]
        return code_fence(json.dumps(part, ensure_ascii=False, indent=2), "json")
    return str(part)


def parse_json_text(text):
    stripped = str(text or "").strip()
    if not stripped or stripped[0] not in "[{":
        return None
    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        return None


def bullet_list(items):
    cleaned = [str(item).strip() for item in items if str(item).strip()]
    if not cleaned:
        return ""
    return "\n".join(f"- {item}" for item in cleaned)


def render_search_items(title, items):
    queries = []
    for item in items or []:
        if isinstance(item, dict):
            query = item.get("q") or item.get("query")
            if query:
                queries.append(query)
    bullets = bullet_list(queries)
    return f"{title}:\n{bullets}" if bullets else ""


def render_tool_call_summary(text):
    payload = parse_json_text(text)
    if not isinstance(payload, dict) or not JSON_TOOL_KEYS.intersection(payload):
        return ""

    sections = []

    if "search_query" in payload:
        section = render_search_items("Searched queries", payload.get("search_query"))
        if section:
            sections.append(section)

    if "image_query" in payload:
        section = render_search_items("Image searches", payload.get("image_query"))
        if section:
            sections.append(section)

    if "open" in payload:
        refs = []
        for item in payload.get("open") or []:
            if isinstance(item, dict):
                ref = item.get("ref_id") or item.get("url")
                if ref:
                    refs.append(ref)
        bullets = bullet_list(refs)
        if bullets:
            sections.append(f"Opened pages:\n{bullets}")

    if "click" in payload:
        clicks = []
        for item in payload.get("click") or []:
            if isinstance(item, dict):
                ref = item.get("ref_id")
                link_id = item.get("id")
                if ref is not None and link_id is not None:
                    clicks.append(f"{ref}, link {link_id}")
                elif ref is not None:
                    clicks.append(ref)
        bullets = bullet_list(clicks)
        if bullets:
            sections.append(f"Clicked links:\n{bullets}")

    if "find" in payload:
        finds = []
        for item in payload.get("find") or []:
            if isinstance(item, dict):
                pattern = item.get("pattern")
                ref = item.get("ref_id")
                if pattern and ref:
                    finds.append(f"{pattern} in {ref}")
                elif pattern:
                    finds.append(pattern)
        bullets = bullet_list(finds)
        if bullets:
            sections.append(f"Searched within pages:\n{bullets}")

    if "screenshot" in payload:
        shots = []
        for item in payload.get("screenshot") or []:
            if isinstance(item, dict):
                ref = item.get("ref_id")
                page = item.get("pageno")
                if ref is not None and page is not None:
                    shots.append(f"{ref}, page {page}")
                elif ref is not None:
                    shots.append(ref)
        bullets = bullet_list(shots)
        if bullets:
            sections.append(f"Captured screenshots:\n{bullets}")

    if "finance" in payload:
        tickers = []
        for item in payload.get("finance") or []:
            if isinstance(item, dict):
                ticker = item.get("ticker")
                market = item.get("market")
                if ticker and market:
                    tickers.append(f"{ticker} ({market})")
                elif ticker:
                    tickers.append(ticker)
        bullets = bullet_list(tickers)
        if bullets:
            sections.append(f"Looked up finance data:\n{bullets}")

    if "weather" in payload:
        locations = []
        for item in payload.get("weather") or []:
            if isinstance(item, dict) and item.get("location"):
                locations.append(item["location"])
        bullets = bullet_list(locations)
        if bullets:
            sections.append(f"Checked weather:\n{bullets}")

    if "sports" in payload:
        requests = []
        for item in payload.get("sports") or []:
            if isinstance(item, dict):
                league = item.get("league")
                fn = item.get("fn")
                team = item.get("team")
                parts = [part for part in (league, fn, team) if part]
                if parts:
                    requests.append(" ".join(parts))
        bullets = bullet_list(requests)
        if bullets:
            sections.append(f"Checked sports data:\n{bullets}")

    if "time" in payload:
        offsets = []
        for item in payload.get("time") or []:
            if isinstance(item, dict) and item.get("utc_offset"):
                offsets.append(item["utc_offset"])
        bullets = bullet_list(offsets)
        if bullets:
            sections.append(f"Checked times:\n{bullets}")

    return "\n\n".join(sections)


def render_legacy_tool_call_summary(text):
    stripped = str(text or "").strip()
    search_match = re.fullmatch(r"search\((['\"])(.*?)\1\)", stripped, flags=re.DOTALL)
    if search_match:
        return f"Searched queries:\n- {search_match.group(2)}"

    click_match = re.fullmatch(r"mclick\(\[(.*?)\]\)", stripped, flags=re.DOTALL)
    if click_match:
        return f"Clicked search results:\n- {click_match.group(1).strip()}"

    return ""


def render_parts(parts):
    rendered_parts = []
    for part in parts or []:
        rendered = render_part(part).strip()
        if rendered:
            rendered_parts.append(rendered)
    return "\n\n".join(rendered_parts)


def render_thoughts(content):
    thoughts = content.get("thoughts")
    if not isinstance(thoughts, list):
        return ""

    lines = []
    for thought in thoughts:
        if not isinstance(thought, dict):
            continue
        summary = thought.get("summary")
        if summary:
            lines.append(str(summary))
        elif thought.get("content"):
            lines.append(str(thought["content"]))
    return "\n\n".join(lines)


def render_content(content):
    if not isinstance(content, dict):
        return ""

    if isinstance(content.get("parts"), list):
        return render_parts(content["parts"])

    content_type = content.get("content_type")

    if content_type == "code":
        text = content.get("text") or ""
        tool_summary = render_tool_call_summary(text) or render_legacy_tool_call_summary(text)
        if tool_summary:
            return tool_summary
        return code_fence(text, content.get("language"))

    if content_type in {"text", "execution_output", "system_error"}:
        return str(content.get("text") or "")

    if content_type == "reasoning_recap":
        return str(content.get("content") or "")

    if content_type == "thoughts":
        return render_thoughts(content)

    if content_type == "tether_browsing_display":
        return str(content.get("result") or "")

    if content_type == "tether_quote":
        domain = content.get("domain")
        text = content.get("text") or ""
        if domain:
            return f"Source: {domain}\n\n{text}".strip()
        return str(text)

    if content_type == "sonic_webpage":
        lines = []
        title = content.get("title")
        url = content.get("url")
        snippet = content.get("snippet")
        text = content.get("text")
        if title:
            lines.append(f"Title: {title}")
        if url:
            lines.append(f"URL: {url}")
        if snippet:
            lines.append(str(snippet))
        if text and text != snippet:
            lines.append(str(text))
        return "\n\n".join(lines)

    if content_type == "computer_output":
        lines = []
        state = content.get("state") or {}
        if state.get("title"):
            lines.append(f"Title: {state['title']}")
        if state.get("url"):
            lines.append(f"URL: {state['url']}")
        screenshot = content.get("screenshot")
        if isinstance(screenshot, dict):
            lines.append(render_asset_pointer(screenshot))
        return "\n\n".join(lines)

    if content_type == "user_editable_context":
        lines = []
        if content.get("user_profile"):
            lines.append(f"User profile:\n\n{content['user_profile']}")
        if content.get("user_instructions"):
            lines.append(f"User instructions:\n\n{content['user_instructions']}")
        return "\n\n".join(lines)

    for key in ("text", "result", "content"):
        value = content.get(key)
        if isinstance(value, str):
            return value

    return code_fence(json.dumps(content, ensure_ascii=False, indent=2), "json")


def parse_marker_payload(payload):
    parsed = parse_json_text(payload)
    if parsed is not None:
        return parsed
    return payload


def render_products_marker(payload):
    parsed = parse_marker_payload(payload)
    if not isinstance(parsed, dict):
        return ""

    selections = parsed.get("selections")
    if not isinstance(selections, list):
        return ""

    names = []
    for selection in selections:
        if isinstance(selection, list) and len(selection) >= 2:
            names.append(selection[1])
        elif isinstance(selection, dict):
            names.append(selection.get("name") or selection.get("title") or "")

    bullets = bullet_list(names)
    if not bullets:
        return ""
    return f"Products referenced:\n{bullets}"


def marker_fields(payload):
    return [field.strip() for field in str(payload or "").split(MARKER_FIELD_SEPARATOR) if field.strip()]


def first_human_marker_field(payload):
    fields = marker_fields(payload)
    for field in fields:
        if not re.fullmatch(r"turn\d+[a-zA-Z_]*\d*", field):
            return field
    return fields[0] if fields else ""


def render_entity_marker(payload):
    parsed = parse_marker_payload(payload)
    if isinstance(parsed, list):
        if len(parsed) >= 2 and parsed[1]:
            return str(parsed[1])
        return " ".join(str(item) for item in parsed if item)
    if isinstance(parsed, dict):
        for key in ("name", "title", "text"):
            if parsed.get(key):
                return str(parsed[key])
    return first_human_marker_field(payload)


def render_query_group_marker(payload, title):
    parsed = parse_marker_payload(payload)
    if not isinstance(parsed, dict):
        return ""

    queries = parsed.get("query")
    if isinstance(queries, str):
        queries = [queries]
    if not isinstance(queries, list):
        return ""

    bullets = bullet_list(queries)
    return f"{title}:\n{bullets}" if bullets else ""


def render_businesses_map_marker(payload):
    businesses = []
    for field in marker_fields(payload):
        parsed = parse_json_text(field)
        if not isinstance(parsed, dict):
            continue
        name = parsed.get("name")
        location = parsed.get("location")
        if name and location:
            businesses.append(f"{name} ({location})")
        elif name:
            businesses.append(name)

    bullets = bullet_list(businesses)
    return f"Businesses referenced:\n{bullets}" if bullets else ""


def render_url_marker(payload):
    fields = marker_fields(payload)
    if not fields:
        return ""
    label = fields[0]
    url = next((field for field in fields[1:] if field.startswith(("http://", "https://"))), "")
    return f"{label} ({url})" if url else label


def replace_chatgpt_marker(match):
    marker_type = match.group(1)
    payload = match.group(2)

    if marker_type == "entity":
        return render_entity_marker(payload)
    if marker_type == "products":
        rendered = render_products_marker(payload)
        return f"\n\n{rendered}\n\n" if rendered else ""
    if marker_type in {"product", "product_entity"}:
        return render_entity_marker(payload)
    if marker_type in {"image_group", "entity_group"}:
        rendered = render_query_group_marker(payload, "Images referenced")
        return f"\n\n{rendered}\n\n" if rendered else "[images referenced]"
    if marker_type == "businesses_map":
        rendered = render_businesses_map_marker(payload)
        return f"\n\n{rendered}\n\n" if rendered else ""
    if marker_type == "url":
        return render_url_marker(payload)
    if marker_type in {"link", "link_title", "summary", "tlwm"}:
        return first_human_marker_field(payload)
    if marker_type == "i":
        return "[images referenced]"
    if marker_type == "video":
        return "[video referenced]"
    if marker_type in {"cite", "entity_metadata", "filecite", "finance", "genui", "navlist"}:
        return ""

    rendered = render_entity_marker(payload)
    return rendered if rendered else ""


def clean_chatgpt_markup(text):
    text = str(text or "")
    previous = None
    while previous != text:
        previous = text
        text = CHATGPT_MARKER_RE.sub(replace_chatgpt_marker, text)
    for private_mark, replacement in PRIVATE_TEXT_MARKS.items():
        text = text.replace(private_mark, replacement)
    text = re.sub(r"[\ue200-\ue20f]", "", text)
    text = re.sub(r"\s+([.,;:!?])", r"\1", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text


def should_skip_message(message, include_system, include_hidden, include_reasoning):
    if not isinstance(message, dict):
        return True

    author = message.get("author") or {}
    role = author.get("role")
    if role == "system" and not include_system:
        return True

    metadata = message.get("metadata") or {}
    if metadata.get("is_visually_hidden_from_conversation") and not include_hidden:
        return True

    content = message.get("content") or {}
    if content.get("content_type") in {"thoughts", "reasoning_recap"} and not include_reasoning:
        return True

    return False


def find_root_nodes(mapping):
    roots = [
        node_id
        for node_id, node in mapping.items()
        if isinstance(node, dict) and node.get("parent") is None
    ]
    return roots or list(mapping.keys())[:1]


def ordered_node_ids(mapping):
    seen = set()
    ordered = []

    def walk_from(start_id):
        stack = [start_id]
        while stack:
            node_id = stack.pop()
            if node_id in seen or node_id not in mapping:
                continue
            seen.add(node_id)
            ordered.append(node_id)
            node = mapping.get(node_id) or {}
            children = node.get("children") or []
            stack.extend(reversed(children))

    for root_id in find_root_nodes(mapping):
        walk_from(root_id)

    for node_id in mapping:
        walk_from(node_id)

    return ordered


def get_conversation(item, include_system=False, include_hidden=False, include_reasoning=False):
    mapping = item.get("mapping") or {}
    chunks = []
    last_author = None

    for node_id in ordered_node_ids(mapping):
        node = mapping.get(node_id) or {}
        message = node.get("message")
        if should_skip_message(message, include_system, include_hidden, include_reasoning):
            continue

        author = message.get("author") or {}
        author_role = author.get("role") or "unknown"
        rendered = clean_chatgpt_markup(render_content(message.get("content") or {})).strip()
        if not rendered:
            continue

        if author_role != last_author:
            chunks.append(f"## {author_role}\n\n{rendered}")
        else:
            chunks.append(rendered)
        last_author = author_role

    return "\n\n".join(chunks)


def main(
    input_path,
    output_dir,
    use_date_folders,
    auto_version_output=False,
    include_system=False,
    include_hidden=False,
    include_reasoning=False,
    progress_interval=250,
):
    final_output_dir = resolve_output_dir(output_dir, auto_version_output)
    conversations, source_paths = load_conversations(input_path)
    conversations = sorted(conversations, key=conversation_sort_key)
    used_names_by_dir = defaultdict(set)
    written_count = 0
    total_count = len(conversations)
    start_time = time.monotonic()

    print(f"Input JSON files: {len(source_paths)}", flush=True)
    print(f"Conversations: {total_count}", flush=True)
    print(f"Output directory: {final_output_dir}", flush=True)

    for item, _source_path in conversations:
        title = sanitize_filename(item.get("title"))
        target_dir = final_output_dir
        if use_date_folders:
            date_iso = timestamp_to_date(item.get("create_time") or item.get("update_time"))
            target_dir = final_output_dir / date_iso
            target_dir.mkdir(parents=True, exist_ok=True)

        file_path = generate_unique_filename(target_dir, title, used_names_by_dir[target_dir])
        markdown = get_conversation(
            item,
            include_system=include_system,
            include_hidden=include_hidden,
            include_reasoning=include_reasoning,
        )
        with file_path.open("w", encoding="utf-8", newline="\n") as outfile:
            outfile.write(markdown)
            if markdown:
                outfile.write("\n")
        written_count += 1
        if should_print_progress(written_count, total_count, progress_interval):
            print_progress(written_count, total_count, start_time)

    print(f"Wrote {written_count} conversations to: {final_output_dir}")


def format_duration(seconds):
    seconds = max(0, int(seconds))
    minutes, seconds = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours}h {minutes}m {seconds}s"
    if minutes:
        return f"{minutes}m {seconds}s"
    return f"{seconds}s"


def should_print_progress(written_count, total_count, progress_interval):
    if written_count in {1, total_count}:
        return True
    return progress_interval > 0 and written_count % progress_interval == 0


def print_progress(written_count, total_count, start_time):
    elapsed = time.monotonic() - start_time
    percent = (written_count / total_count * 100) if total_count else 100
    rate = written_count / elapsed if elapsed > 0 else 0
    remaining = total_count - written_count
    eta = remaining / rate if rate > 0 else 0
    print(
        f"Progress: {written_count}/{total_count} ({percent:.1f}%) | "
        f"{rate:.1f} files/sec | ETA {format_duration(eta)}",
        flush=True,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Process ChatGPT conversation exports.")
    parser.add_argument("input_path", help="JSON file or directory containing JSON export files")
    parser.add_argument("output_dir", help="Directory to save output Markdown files")
    parser.add_argument("--use-date-folders", action="store_true", help="Store files under date-based folders")
    parser.add_argument(
        "--auto-version-output",
        action="store_true",
        help="Use the first empty/new -vN folder derived from output_dir, such as chats-parsed-md-v1",
    )
    parser.add_argument("--include-system", action="store_true", help="Include system messages")
    parser.add_argument("--include-hidden", action="store_true", help="Include visually hidden messages")
    parser.add_argument(
        "--include-reasoning",
        action="store_true",
        help="Include exported reasoning/thought summary records",
    )
    parser.add_argument(
        "--progress-interval",
        type=int,
        default=250,
        help="Print progress after this many written Markdown files; use 0 to only print start and finish",
    )

    args = parser.parse_args()
    main(
        args.input_path,
        args.output_dir,
        args.use_date_folders,
        auto_version_output=args.auto_version_output,
        include_system=args.include_system,
        include_hidden=args.include_hidden,
        include_reasoning=args.include_reasoning,
        progress_interval=args.progress_interval,
    )
