#!/usr/bin/env python3
"""Utilities for the community Chinese localization of rule metadata.

The source of truth remains the English rule.yml.  Chinese translations are
stored inline in the description and rationale fields so existing build tools
and OpenSCAP consumers do not need any localization-specific code changes.
"""

from __future__ import print_function

import argparse
import hashlib
import html
import json
import os
import re
import shutil
import subprocess
import sys
from collections import OrderedDict

import yaml


REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
BASELINE_PATH = os.path.join(REPO_ROOT, "translations", "zh-CN", "baseline.tsv")
RULE_ROOTS = ("linux_os", "applications", "products")
FIELD_NAMES = ("description", "rationale")
EXPECTED_RULE_COUNT = 2566
TOP_LEVEL_KEY_RE = re.compile(r"^([A-Za-z_][A-Za-z0-9_-]*):[ \t]*(.*)$")
CJK_RE = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff]")
JINJA_RE = re.compile(r"\{\{\{.*?\}\}\}", re.DOTALL)
PRE_RE = re.compile(r"<pre\b[^>]*>.*?</pre>", re.DOTALL | re.IGNORECASE)
MARKERS = OrderedDict((
    ("description", "<p><strong>中文说明：</strong></p>"),
    ("rationale", "<p><strong>中文理由：</strong></p>"),
))


class TranslationError(Exception):
    """Raised when a rule cannot be parsed or safely updated."""


def _read_text(path):
    with open(path, "r", encoding="utf-8") as stream:
        return stream.read()


def _write_text(path, text):
    with open(path, "w", encoding="utf-8", newline="\n") as stream:
        stream.write(text)


def _iter_lines_with_offsets(text):
    offset = 0
    for line in text.splitlines(True):
        yield offset, line
        offset += len(line)
    if text and not text.endswith(("\n", "\r")):
        return


def _find_key_line(text, key):
    pattern = re.compile(r"(?m)^{}:[ \t]*(.*)$".format(re.escape(key)))
    match = pattern.search(text)
    if not match:
        raise TranslationError("missing top-level field {!r}".format(key))
    return match


def _find_closing_quote(text, start, quote):
    pos = start
    while pos < len(text):
        char = text[pos]
        if char == quote:
            if quote == "'" and pos + 1 < len(text) and text[pos + 1] == "'":
                pos += 2
                continue
            if quote == '"':
                backslashes = 0
                cursor = pos - 1
                while cursor >= start and text[cursor] == "\\":
                    backslashes += 1
                    cursor -= 1
                if backslashes % 2:
                    pos += 1
                    continue
            return pos
        pos += 1
    return None


def _include_trailing_blank_lines(text, end):
    while end < len(text):
        line_end = text.find("\n", end)
        if line_end == -1:
            line_end = len(text)
        else:
            line_end += 1
        if text[end:line_end].strip():
            break
        end = line_end
    return end


def _field_range(text, key):
    match = _find_key_line(text, key)
    value_start = match.start(1)
    value = match.group(1)
    line_start = match.start()
    line_end = text.find("\n", match.end())
    if line_end == -1:
        line_end = len(text)
    else:
        line_end += 1

    stripped = value.lstrip()
    if stripped.startswith(("'", '"')):
        quote = stripped[0]
        quote_start = value_start + (len(value) - len(stripped))
        quote_end = _find_closing_quote(text, quote_start + 1, quote)
        if quote_end is None:
            raise TranslationError("unterminated quoted scalar in {!r}".format(key))
        end_of_line = text.find("\n", quote_end)
        end = len(text) if end_of_line == -1 else end_of_line + 1
        return line_start, _include_trailing_blank_lines(text, end)

    if stripped.startswith(("|", ">")):
        content_start = line_end
    elif not stripped:
        content_start = line_end
    else:
        return line_start, _include_trailing_blank_lines(text, line_end)

    end = len(text)
    for offset, line in _iter_lines_with_offsets(text[content_start:]):
        absolute_offset = content_start + offset
        if not line.strip():
            continue
        if line.startswith((" ", "\t")):
            continue
        end = absolute_offset
        break
    return line_start, end


def extract_field_value(text, key):
    start, end = _field_range(text, key)
    raw = text[start:end]
    try:
        document = yaml.safe_load(raw)
    except yaml.YAMLError as exc:
        raise TranslationError("cannot parse field {!r}: {}".format(key, exc)) from exc
    if not isinstance(document, dict) or key not in document:
        raise TranslationError("field {!r} did not parse as a mapping".format(key))
    value = document[key]
    if not isinstance(value, str):
        raise TranslationError("field {!r} is not a string".format(key))
    return value


def _block_indent(raw, key):
    lines = raw.splitlines()
    indents = []
    for line in lines[1:]:
        if not line.strip():
            continue
        indents.append(len(line) - len(line.lstrip(" ")))
    if indents:
        return min(indents)
    return 4


def _indent_block(text, indent):
    result = []
    for line in text.splitlines():
        if line:
            result.append(" " * indent + line)
        else:
            result.append("")
    return "\n".join(result)


def _split_english(value, key):
    marker = MARKERS[key]
    if marker in value:
        return value.split(marker, 1)[0].rstrip("\n"), value.split(marker, 1)[1].strip()
    return value.rstrip("\n"), None


def _trailing_newlines(text):
    match = re.search(r"\n*$", text)
    return match.group(0) if match else ""


def _update_block_field(raw, key, translation):
    indent = _block_indent(raw, key)
    marker = MARKERS[key]
    suffix = _trailing_newlines(raw)
    core = raw[: len(raw) - len(suffix)] if suffix else raw
    marker_pattern = re.compile(r"(?m)^[ \t]*{}[ \t]*$".format(re.escape(marker)))
    marker_match = marker_pattern.search(core)
    if marker_match:
        prefix = core[: marker_match.start()].rstrip()
    else:
        prefix = core.rstrip()

    rendered = [
        prefix,
        "",
        " " * indent + marker,
        _indent_block(translation.strip(), indent),
    ]
    return "\n".join(rendered) + suffix


def _rebuild_quoted_field(key, english, translation, suffix):
    marker = MARKERS[key]
    parts = ["{}: |-".format(key)]
    if english.strip():
        parts.append(_indent_block(english.rstrip(), 4))
        parts.append("")
    parts.append("    " + marker)
    parts.append(_indent_block(translation.strip(), 4))
    return "\n".join(parts) + suffix


def inject_translation(text, key, translation):
    if not translation or not CJK_RE.search(translation):
        raise TranslationError("translation for {!r} is empty or has no Chinese text".format(key))
    if MARKERS[key] in translation:
        raise TranslationError("translation for {!r} contains the localization marker".format(key))
    start, end = _field_range(text, key)
    raw = text[start:end]
    value_indicator = raw.splitlines()[0].split(":", 1)[1].strip()
    if value_indicator.startswith(("|", ">")):
        replacement = _update_block_field(raw, key, translation)
    else:
        current_value = extract_field_value(text, key)
        english, _ = _split_english(current_value, key)
        replacement = _rebuild_quoted_field(key, english, translation, _trailing_newlines(raw))
    return text[:start] + replacement + text[end:]


def apply_translations(translations_path, root=REPO_ROOT):
    with open(translations_path, "r", encoding="utf-8") as stream:
        payload = json.load(stream)
    records = payload.get("rules") if isinstance(payload, dict) else payload
    if not isinstance(records, list):
        raise TranslationError("translation JSON must contain a 'rules' list")
    for record in records:
        relative_path = record.get("path")
        if not relative_path:
            raise TranslationError("translation record is missing 'path'")
        absolute_path = os.path.join(root, relative_path)
        if not os.path.isfile(absolute_path):
            raise TranslationError("rule file does not exist: {}".format(relative_path))
        text = _read_text(absolute_path)
        for key in reversed(FIELD_NAMES):
            translation = record.get(key + "_zh")
            if translation is None:
                continue
            text = inject_translation(text, key, translation)
        _write_text(absolute_path, text)
        print("updated {}".format(relative_path))


def governed_rule_paths(root=REPO_ROOT):
    paths = []
    for directory in RULE_ROOTS:
        base = os.path.join(root, directory)
        for current_root, _, filenames in os.walk(base):
            if "tests" in current_root.split(os.sep):
                continue
            if "rule.yml" in filenames:
                paths.append(os.path.relpath(os.path.join(current_root, "rule.yml"), root))
    return sorted(paths)


def _normalize_for_hash(value):
    return value.replace("\r\n", "\n").rstrip("\n")


def _field_hash(value):
    normalized = _normalize_for_hash(value)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _load_baseline(path=BASELINE_PATH):
    rows = {}
    with open(path, "r", encoding="utf-8") as stream:
        for line in stream:
            if not line.strip() or line.startswith("#"):
                continue
            relative_path, description_hash, rationale_hash = line.rstrip("\n").split("\t")
            rows[relative_path] = {
                "description": description_hash,
                "rationale": rationale_hash,
            }
    return rows


def create_baseline(output_path=BASELINE_PATH, root=REPO_ROOT):
    paths = governed_rule_paths(root)
    if len(paths) != EXPECTED_RULE_COUNT:
        raise TranslationError(
            "expected {} production rules, found {}".format(EXPECTED_RULE_COUNT, len(paths))
        )
    lines = [
        "# ComplianceAsCode content Chinese localization baseline",
        "# Base: ComplianceAsCode/content master e4083bb6e9b61bb7aed4981ec12c8e53dda84c4d",
        "# Hash input: parsed English scalar with line endings normalized and trailing newlines stripped",
        "# path\tdescription_sha256\trationale_sha256",
    ]
    for relative_path in paths:
        text = _read_text(os.path.join(root, relative_path))
        hashes = [_field_hash(extract_field_value(text, key)) for key in FIELD_NAMES]
        lines.append("{}\t{}\t{}".format(relative_path, hashes[0], hashes[1]))
    _write_text(output_path, "\n".join(lines) + "\n")
    print("wrote {} rules to {}".format(len(paths), os.path.relpath(output_path, root)))


def _strip_translated_fields(text):
    ranges = sorted((_field_range(text, key) for key in FIELD_NAMES), reverse=True)
    stripped = text
    for start, end in ranges:
        stripped = stripped[:start] + stripped[end:]
    return stripped


def _git_file_at_ref(ref, relative_path, root):
    command = ["git", "-C", root, "show", "{}:{}".format(ref, relative_path)]
    try:
        return subprocess.check_output(command, stderr=subprocess.STDOUT).decode("utf-8")
    except subprocess.CalledProcessError as exc:
        raise TranslationError(
            "cannot read {} at {}: {}".format(relative_path, ref, exc.output.decode("utf-8"))
        ) from exc


def validate_rules(paths=None, strict=False, base_ref=None, root=REPO_ROOT,
                   baseline_path=BASELINE_PATH):
    baseline = _load_baseline(baseline_path)
    all_paths = governed_rule_paths(root)
    if set(all_paths) != set(baseline):
        missing = sorted(set(all_paths) - set(baseline))
        stale = sorted(set(baseline) - set(all_paths))
        raise TranslationError(
            "baseline mismatch; missing={} stale={}".format(missing[:5], stale[:5])
        )
    selected = all_paths if not paths else list(paths)
    errors = []
    warnings = []
    translated_fields = 0
    for relative_path in selected:
        absolute_path = os.path.join(root, relative_path)
        if not os.path.isfile(absolute_path):
            errors.append("{}: file does not exist".format(relative_path))
            continue
        text = _read_text(absolute_path)
        if base_ref:
            base_text = _git_file_at_ref(base_ref, relative_path, root)
            if _strip_translated_fields(text) != _strip_translated_fields(base_text):
                errors.append("{}: non-Description/Rationale content changed".format(relative_path))
        for key in FIELD_NAMES:
            try:
                value = extract_field_value(text, key)
            except TranslationError as exc:
                errors.append("{} {}: {}".format(relative_path, key, exc))
                continue
            english, chinese = _split_english(value, key)
            expected_hash = baseline[relative_path][key]
            if _field_hash(english) != expected_hash:
                errors.append("{} {}: English content differs from baseline".format(
                    relative_path, key))
            if chinese is None:
                if strict:
                    errors.append("{} {}: missing Chinese translation".format(relative_path, key))
                continue
            translated_fields += 1
            if not CJK_RE.search(chinese):
                errors.append("{} {}: Chinese block contains no Chinese text".format(
                    relative_path, key))
            english_pre = PRE_RE.findall(english)
            chinese_pre = PRE_RE.findall(chinese)
            if english_pre != chinese_pre:
                errors.append("{} {}: <pre> blocks differ between English and Chinese".format(
                    relative_path, key))
            if re.search(r"\{\{\{\s*(?:describe_|ocil_|complete_)", chinese):
                warnings.append(
                    "{} {}: Chinese block calls a prose-producing macro".format(
                        relative_path, key)
                )
    for message in warnings:
        print("WARNING: {}".format(message))
    for message in errors:
        print("ERROR: {}".format(message))
    print("validated {} rules, {} translated fields, {} errors, {} warnings".format(
        len(selected), translated_fields, len(errors), len(warnings)))
    return 1 if errors else 0


def _render_preview_fragment(value):
    def replace_macro(match):
        return '<code class="jinja">{}</code>'.format(html.escape(match.group(0)))

    return JINJA_RE.sub(replace_macro, value)


def _html_document(records):
    sections = []
    for record in records:
        sections.append(
            """
<section class="rule" id="{anchor}">
  <h2>{rule_id}</h2>
  <p class="path">{path}</p>
  <div class="field-grid">
    <article><h3>English description</h3><div class="field">{description_en}</div></article>
    <article lang="zh-CN"><h3>中文说明</h3><div class="field">{description_zh}</div></article>
    <article><h3>English rationale</h3><div class="field">{rationale_en}</div></article>
    <article lang="zh-CN"><h3>中文理由</h3><div class="field">{rationale_zh}</div></article>
  </div>
</section>
""".format(
                anchor=html.escape(record["rule_id"].replace("_", "-")),
                rule_id=html.escape(record["rule_id"]),
                path=html.escape(record["path"]),
                description_en=_render_preview_fragment(record["description_en"]),
                description_zh=_render_preview_fragment(record["description_zh"]),
                rationale_en=_render_preview_fragment(record["rationale_en"]),
                rationale_zh=_render_preview_fragment(record["rationale_zh"]),
            )
        )
    return """<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>ComplianceAsCode 中文翻译样板</title>
<style>
body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", sans-serif;
       margin: 0; background: #f5f6f8; color: #202124; }
header { background: #17365d; color: white; padding: 24px 32px; }
main { max-width: 1480px; margin: 0 auto; padding: 24px; }
.rule { background: white; border-radius: 10px; margin-bottom: 24px; padding: 20px;
        box-shadow: 0 1px 4px rgba(0,0,0,.12); }
.path { color: #5f6368; font-family: ui-monospace, SFMono-Regular, Menlo, monospace; }
.field-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
article { border: 1px solid #dadce0; border-radius: 8px; padding: 12px 16px; overflow: auto; }
article[lang="zh-CN"] { background: #f8fbff; }
.field { white-space: pre-wrap; line-height: 1.55; }
pre { background: #f1f3f4; padding: 12px; overflow: auto; white-space: pre; }
code, tt { font-family: ui-monospace, SFMono-Regular, Menlo, monospace; }
code.jinja { color: #b3261e; background: #fce8e6; padding: 1px 4px; border-radius: 3px; }
@media (max-width: 900px) { .field-grid { grid-template-columns: 1fr; } }
</style>
</head>
<body>
<header><h1>ComplianceAsCode 中文翻译样板</h1><p>英文原文与简体中文并排预览</p></header>
<main>__SECTIONS__</main>
</body>
</html>
""".replace("__SECTIONS__", "\n".join(sections))


def _markdown_report(records):
    lines = ["# ComplianceAsCode 中文翻译样板", ""]
    lines.append("共 {} 条规则。中文块使用固定标记，英文与代码保持原文。".format(len(records)))
    lines.append("")
    for record in records:
        lines.extend([
            "## {}".format(record["rule_id"]),
            "",
            "`{}`".format(record["path"]),
            "",
            "### Description",
            "",
            "**English**",
            "",
            "````html",
            record["description_en"],
            "````",
            "",
            "**中文说明**",
            "",
            "````html",
            record["description_zh"],
            "````",
            "",
            "### Rationale",
            "",
            "**English**",
            "",
            "````html",
            record["rationale_en"],
            "````",
            "",
            "**中文理由**",
            "",
            "````html",
            record["rationale_zh"],
            "````",
            "",
        ])
    return "\n".join(lines)


def generate_report(paths, output_dir, root=REPO_ROOT):
    records = []
    for relative_path in paths:
        text = _read_text(os.path.join(root, relative_path))
        record = {
            "path": relative_path,
            "rule_id": os.path.basename(os.path.dirname(relative_path)),
        }
        for key in FIELD_NAMES:
            value = extract_field_value(text, key)
            english, chinese = _split_english(value, key)
            record[key + "_en"] = english
            record[key + "_zh"] = chinese if chinese is not None else ""
        records.append(record)
    if not os.path.isdir(output_dir):
        os.makedirs(output_dir)
    markdown_path = os.path.join(output_dir, "review.md")
    html_path = os.path.join(output_dir, "preview.html")
    manifest_path = os.path.join(output_dir, "sample-manifest.json")
    _write_text(markdown_path, _markdown_report(records))
    _write_text(html_path, _html_document(records))
    _write_text(manifest_path, json.dumps(records, ensure_ascii=False, indent=2) + "\n")
    print(markdown_path)
    print(html_path)
    print(manifest_path)


def _read_rule_list(path):
    with open(path, "r", encoding="utf-8") as stream:
        return [line.strip() for line in stream if line.strip() and not line.startswith("#")]


def _parse_args(argv):
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command")

    baseline = subparsers.add_parser("baseline", help="create the English baseline hash file")
    baseline.add_argument("--output", default=BASELINE_PATH)
    baseline.add_argument("--root", default=REPO_ROOT)

    apply_parser = subparsers.add_parser("apply", help="apply Chinese translations from JSON")
    apply_parser.add_argument("translations")
    apply_parser.add_argument("--root", default=REPO_ROOT)

    validate = subparsers.add_parser("validate", help="validate English preservation and Chinese blocks")
    validate.add_argument("--strict", action="store_true", help="require every rule to be translated")
    validate.add_argument("--base-ref", help="compare non-target content with this Git revision")
    validate.add_argument("--root", default=REPO_ROOT)
    validate.add_argument("--baseline", default=BASELINE_PATH)
    source = validate.add_mutually_exclusive_group()
    source.add_argument("--rules-file", help="file containing one rule.yml path per line")
    source.add_argument("--rule", action="append", default=[], help="rule.yml path to validate")

    report = subparsers.add_parser("report", help="generate Markdown and HTML review artifacts")
    report.add_argument("--rules-file", required=True)
    report.add_argument("--output-dir", required=True)
    report.add_argument("--root", default=REPO_ROOT)
    return parser.parse_args(argv)


def main(argv=None):
    args = _parse_args(argv or sys.argv[1:])
    try:
        if args.command == "baseline":
            create_baseline(args.output, args.root)
        elif args.command == "apply":
            apply_translations(args.translations, args.root)
        elif args.command == "validate":
            paths = None
            if args.rules_file:
                paths = _read_rule_list(args.rules_file)
            elif args.rule:
                paths = args.rule
            return validate_rules(
                paths=paths,
                strict=args.strict,
                base_ref=args.base_ref,
                root=args.root,
                baseline_path=args.baseline,
            )
        elif args.command == "report":
            generate_report(_read_rule_list(args.rules_file), args.output_dir, args.root)
        else:
            raise TranslationError("a command is required")
    except TranslationError as exc:
        print("ERROR: {}".format(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
