#!/usr/bin/env python3
"""Import real manually copied excerpts; validate JSON; render disposable Markdown views."""
import argparse
import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def encoded(value):
    return json.dumps(value, ensure_ascii=False, indent=2) + "\n"


def reading_text(segments):
    """Explicit, source-backed overlap removal; no semantic or fuzzy deduplication."""
    paragraphs = []
    for segment in segments:
        text = segment.get('display_text', segment['text'])
        if not text:
            continue
        if segment.get('join_previous') and paragraphs:
            paragraphs[-1] += text
        else:
            paragraphs.append(text)
    return '\n\n'.join(paragraphs)


def compact_layout(text):
    # PDF line wrapping often inserts spaces inside Chinese words. No word changes.
    return re.sub(r'(?<=[\u3400-\u9fff])[ \t]+(?=[\u3400-\u9fff])', '', text)


def write_new_records(pending):
    """Write prevalidated new records exclusively; roll back this call on ordinary failure."""
    created = []
    try:
        for destination, value in pending.items():
            destination.parent.mkdir(parents=True, exist_ok=True)
            with destination.open("x", encoding="utf-8") as handle:
                created.append(destination)
                handle.write(encoded(value))
    except Exception:
        for path in reversed(created):
            path.unlink()
        raise


def schema_validate(value, name, root=ROOT):
    try:
        from jsonschema import Draft202012Validator
    except ImportError as exc:
        raise ValueError("需要 jsonschema：请在 Python 环境安装 requirements.txt 所列依赖。") from exc
    schema = read(root / "templates" / name)
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema).validate(value)


def validate_material(value, root=ROOT):
    schema_validate(value, "material.schema.json", root)
    a = value["analysis"]
    themes = {t["id"] for t in read(root / "taxonomy/themes.json")["themes"]}
    prompts = {p["id"] for p in read(root / "taxonomy/prompts.json")["prompts"]}
    if a["primary_theme"] is not None and a["primary_theme"] not in themes:
        raise ValueError("主母题不存在")
    if not set(a["secondary_themes"]) <= themes or a["primary_theme"] in a["secondary_themes"]:
        raise ValueError("关联母题无效或与主母题重复")
    links = [p["id"] for p in a["related_prompts"]]
    if not set(links) <= prompts or len(set(links)) != len(links):
        raise ValueError("关联题号不存在或重复")
    if not value["capture"]["text_original"].strip():
        raise ValueError("原文不能是空白")
    segments = value["capture"].get("segments", [])
    keys = [s["annotation_key"] for s in segments]
    if segments:
        if len(keys) != len(set(keys)):
            raise ValueError("同一组合内批注 ID 不得重复")
        if len({s["attachment_key"] for s in segments}) != 1:
            raise ValueError("一组来源批注必须来自同一附件；跨书比较写入分析")
        if segments != sorted(segments, key=lambda s: (s["page_index"], s["sort_index"])):
            raise ValueError("来源片段必须按页内位置排序，不能按创建时间排序")
        for segment in segments:
            display = segment.get('display_text', segment['text'])
            if display == segment['text']:
                continue
            if display not in segment['text'] or not segment.get('cleanup_note'):
                raise ValueError("去重展示只能截取原片段，并须说明依据")
            start = segment['text'].find(display)
            removed = [segment['text'][:start], segment['text'][start + len(display):]]
            neighbors = ''.join(s['text'] for s in segments if s is not segment and
                                abs(s['page_index'] - segment['page_index']) <= 1)
            neighbors = re.sub(r'\s+', '', neighbors)
            if any(re.sub(r'\s+', '', text) not in neighbors for text in removed if text):
                raise ValueError("删去的文字未被相邻来源覆盖，不能当作重叠删除")
        if value["capture"]["text_original"] != reading_text(segments):
            raise ValueError("组合原文必须来自去重后的来源片段，不能补写")
    contexts = value['capture'].get('context_excerpts', [])
    context_keys = {x['id'] for x in contexts}
    if len(context_keys) != len(contexts):
        raise ValueError('补充上下文 ID 不得重复')
    for step in a.get("argument_structure", []):
        if not set(step["annotation_keys"]) <= set(keys):
            raise ValueError("论证结构引用了不在本素材中的批注")
        if not set(step.get('context_keys', [])) <= context_keys:
            raise ValueError('论证结构引用了不存在的补充上下文')
        if not step['annotation_keys'] and not step.get('context_keys'):
            raise ValueError('论证解释必须有原文依据')
    if value["source_match"]["status"] != "unchecked":
        source = value["capture"]["source"]
        if not source["title"] or not source["locator"]["value"] or source["locator"]["kind"] == "unknown":
            raise ValueError("原文核对必须给出可回找的来源和位置")
    if value["status"] == "reviewed" and not (value.get('summary') or a["paraphrase"]):
        raise ValueError("空白整理卡不能标为已认可")


def normalize(item):
    # Hash the entire submitted entry, including notes and provenance. Exact repeats
    # are idempotent; altered notes and identical text from other sources remain separate.
    digest = hashlib.sha256(json.dumps(item, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    color = item.get("color", "unknown")
    location = item.get("location") or None
    return {
        "id": "MAT-" + digest[:16], "schema_version": "0.2.0", "status": "inbox",
        "import_fingerprint": digest, "parent_capture_id": None,
        "source_match": {"status": "unchecked", "basis": None, "checked_by": None, "checked_at": None},
        "capture": {
            "text_original": item["raw_text"], "context_before": item.get("context_before"),
            "context_after": item.get("context_after"), "context_note": None,
            "source": {"title": item.get("source_title"), "author": item.get("author"), "edition": None,
                       "url": item.get("url"), "file_sha256": None,
                       "locator": {"kind": "text_location" if location else "unknown", "value": location}},
            "highlight": {"color_raw": item.get("color"), "color_normalized": color,
                          "capture_type": item.get("type", "unknown")},
            "extraction_method": "manual"
        },
        "reader_note": item.get("reader_note"),
        "analysis": {"paraphrase": None, "primary_theme": None, "secondary_themes": [],
                     "classification_reason": None, "concept_candidates": [], "argument_uses": [],
                     "related_prompts": [], "open_questions": []},
        "review_notes": ["手工录入；原文尚未对照来源核对，未进行 AI 分类或读者确认。"],
        "reviewed_by": None, "reviewed_at": None
    }


def import_batch(path, root=ROOT):
    batch = read(path)
    schema_validate(batch, "manual-batch.schema.json", root)
    pending, seen, skipped = {}, set(), 0
    for item in batch["items"]:
        value = normalize(item)
        validate_material(value, root)
        mid = value["id"]
        destination = root / "materials" / f"{mid}.json"
        if mid in seen:
            skipped += 1
            continue
        seen.add(mid)
        if destination.exists():
            if read(destination).get("import_fingerprint") != value["import_fingerprint"]:
                raise ValueError(f"ID 冲突：{mid}，未写入任何条目")
            skipped += 1
            continue
        pending[destination] = value
        capture_path = root / "inbox/captures" / (value["import_fingerprint"] + ".json")
        if capture_path.exists():
            if read(capture_path) != item:
                raise ValueError("原始摘录记录冲突")
        else:
            pending[capture_path] = item
    # Validate the entire batch before writing. Never overwrite an existing card,
    # including a card already edited or approved by the reader.
    write_new_records(pending)
    added = sum(p.parent.name == "materials" for p in pending)
    return {"added": added, "exact_repeats_skipped": skipped,
            "note": "已创建未整理卡；AI 分类与人工复核尚未发生，HTML 无需重建。"}


def markdown(value):
    a, c = value["analysis"], value["capture"]
    fields = {"id": value["id"], "schema_version": value["schema_version"], "status": value["status"],
              "primary_theme": a["primary_theme"], "secondary_themes": a["secondary_themes"]}
    out = "---\n" + "\n".join(f"{k}: {json.dumps(v, ensure_ascii=False)}" for k, v in fields.items()) + "\n---\n\n"
    out += f"# {value.get('title', value['id'])}\n\n此 Markdown 是自动生成的阅读副本。修订请交给 Codex 更新同名 JSON，再生成本页。\n\n"
    if c.get("segments"):
        cleaned = any('display_text' in s or 'join_previous' in s for s in c['segments'])
        out += ('## 摘录（重叠已去除；段间可能有未划出的文字）\n\n' if cleaned else
                '## 来源片段（不代表连续原文）\n\n')
        out += f"组合理由（AI）：{c['grouping_reason']}\n\n[原始读取快照](../{c['raw_snapshot']})\n\n"
        out += '\n'.join('> ' + line for line in compact_layout(c['text_original']).splitlines()) + '\n\n'
        out += '<details>\n<summary>批注来源、颜色与去重记录</summary>\n\n'
        for segment in c['segments']:
            out += f"- {segment['annotation_key']} · 页码标签 {segment['page_label']} · {segment['color']}"
            if segment.get('cleanup_note'):
                out += f" · {segment['cleanup_note']}"
            out += '\n'
        out += '\n</details>\n\n'
        comments = [s for s in c['segments'] if s['comment']]
        if comments:
            out += '### 你的逐条批注\n\n'
            out += '\n'.join(f"- {s['annotation_key']}：{s['comment']}" for s in comments) + '\n\n'
    else:
        out += "## 原文\n\n" + "\n".join("> " + line for line in c["text_original"].splitlines()) + "\n\n"
    s = c["source"]
    location = s['locator']['value'] or '待补'
    if s['locator']['kind'] == 'pdf_page_index' and str(location).isdigit():
        location = f"PDF 第 {int(location)+1} 页（零基索引 {location}，不是印刷页码）"
    out += f"来源：{s['title'] or '待补'}；作者：{s['author'] or '未知'}；位置：{location}。\n\n"
    if (value.get('parent_capture_id') or '').startswith('CAP-'):
        out += f"[查看原始批注记录](../inbox/captures/{value['parent_capture_id']}.json)\n\n"
    if s["url"]:
        out += f"原链接：{s['url']}\n\n"
    for label, key in [("原始前文", "context_before"), ("原始后文", "context_after"), ("整理者的上下文说明", "context_note")]:
        if c.get(key):
            out += f"{label}：{c[key]}\n\n"
    if c.get('context_excerpts'):
        out += '## 补充上下文（来自 PDF 正文，不是你的高亮）\n\n'
        for context in c['context_excerpts']:
            out += f"### {context['id']} · PDF 第 {context['page_index'] + 1} 页\n\n"
            out += '\n'.join('> ' + line for line in compact_layout(context['text']).splitlines()) + '\n\n'
    if not c.get("segments"):
        out += f"原颜色：{c['highlight']['color_raw'] or '未知'}；类型：{c['highlight']['capture_type']}。\n\n"
    out += "## 读者留言\n\n" + (value["reader_note"] or "未提供。") + "\n\n## 整理草稿\n\n"
    out += (a["paraphrase"] or "尚未整理。") + "\n\n分类理由：" + (a["classification_reason"] or "待整理") + "\n\n"
    if a.get("argument_structure"):
        out += "## 原文论证关系（AI 整理，非作者原话）\n\n"
        for step in a["argument_structure"]:
            refs = [*step['annotation_keys'], *step.get('context_keys', [])]
            out += f"- **{step['role']}**：{step['summary']}（依据：{', '.join(refs)}）\n\n"
    if a["concept_candidates"]:
        out += "概念：\n\n" + "\n".join(f"- {x['name']}（{x['status']}）：{x['reason']}" for x in a["concept_candidates"]) + "\n\n"
    for use in a["argument_uses"]:
        out += f"## 论证用法：{use['claim']}\n\n{use['relation']} / {use['role']}\n\n{use['reasoning']}\n\n"
        out += f"条件：{'；'.join(use['conditions']) or '待讨论'}\n\n边界：{'；'.join(use['limits']) or '待讨论'}\n\n"
        out += f"证据状态：{use['evidence_status']}；核验依据：{use.get('verification_basis') or '未提供'}。\n\n"
    out += "## 关联题目\n\n" + ("\n".join(f"- [{p['id']}](../prompts/{p['id']}.md)：{p['reason']}" for p in a["related_prompts"]) or "暂未关联。") + "\n\n"
    out += "## 三项状态\n\n" + f"原文核对：{value['source_match']['status']}；依据：{value['source_match']['basis'] or '未核对'}。\n\n"
    out += f"人工认可：{value['status'] == 'reviewed'}；确认人：{value['reviewed_by'] or '无'}；日期：{value['reviewed_at'] or '无'}。\n\n"
    out += "事实核验：逐项见论证用法，不随原文核对或人工认可自动改变。\n\n"
    out += "## 待讨论与记录\n\n" + "\n".join("- " + line for line in [*a["open_questions"], *value["review_notes"]]) + "\n"
    return out


def render_all(root=ROOT):
    paths = sorted((root / "materials").glob("MAT-*.json"))
    values = [read(p) for p in paths]
    for p, value in zip(paths, values):
        if p.stem != value["id"]:
            raise ValueError(f"文件名与 ID 不一致：{p}")
        validate_material(value, root)
    for p, value in zip(paths, values):
        # Only derived Markdown is replaced, never canonical JSON or raw captures.
        p.with_suffix(".md").write_text(markdown(value), encoding="utf-8")
    write_material_index(root)
    return len(values)


def load_materials(root=ROOT):
    values = []
    for path in sorted((root / 'materials').glob('MAT-*.json')):
        value = read(path)
        if path.stem != value['id']:
            raise ValueError(f'文件名与素材 ID 不符：{path}')
        validate_material(value, root)
        values.append(value)
    return values


def load_material_groups(root=ROOT):
    path = root / 'materials/groups.json'
    if not path.exists():
        return []
    groups = read(path)['material_groups']
    materials = {m['id']: m for m in load_materials(root)}
    ids, members = set(), set()
    for group in groups:
        if not re.fullmatch(r'GRP-[A-Za-z0-9-]+', group['id']) or group['id'] in ids:
            raise ValueError('素材群 ID 无效或重复')
        ids.add(group['id'])
        if not group['title'].strip() or not group['summary'].strip() or len(group['material_ids']) < 2:
            raise ValueError('素材群须有标题、概括和至少两个部分')
        for mid in group['material_ids']:
            if mid not in materials or mid in members or materials[mid].get('collection_role') == 'technical_test':
                raise ValueError('素材群成员不存在、重复归组或引用了测试卡')
            members.add(mid)
    return groups


def write_material_index(root=ROOT):
    values = load_materials(root)
    folder = root / 'materials'
    folder.mkdir(exist_ok=True)
    (folder / 'index.json').write_text(encoded({
        'material_files': [v['id'] + '.json' for v in values],
        'material_groups': load_material_groups(root)
    }), encoding='utf-8')
    return values


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("render")
    sub.add_parser("validate")
    importer = sub.add_parser("import")
    importer.add_argument("batch", type=Path)
    args = parser.parse_args()
    if args.command == "import":
        print(encoded(import_batch(args.batch)))
    elif args.command == "render":
        print(f"已生成 {render_all()} 张素材阅读卡；未改写 HTML 或素材 JSON。")
    else:
        paths = sorted((ROOT / "materials").glob("MAT-*.json"))
        for p in paths:
            value = read(p)
            if p.stem != value["id"]:
                raise ValueError(f"文件名与 ID 不一致：{p}")
            validate_material(value)
        load_material_groups(ROOT)
        print(f"{len(paths)} 张素材及素材群通过字段与交叉引用校验。")


if __name__ == "__main__":
    main()
