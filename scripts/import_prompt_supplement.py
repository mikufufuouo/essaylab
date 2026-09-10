#!/usr/bin/env python3
"""Apply the reviewed SRC-002 supplement once; preserve all existing IDs and text.

Decisions are specific to 补充题目.md. This is not an automatic semantic deduplicator.
Subsequent edits belong in taxonomy/prompts.json, not in this import seed.
"""
import argparse
import hashlib
import html
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def dump(value):
    return json.dumps(value, ensure_ascii=False, indent=2) + '\n'


def parse_rows(text):
    rows = []
    for line_number, line in enumerate(text.splitlines(), 1):
        match = re.fullmatch(r'\|\s*\[(.+?)\]\((https?://[^)]+)\)\s*\|\s*(.*?)\s*\|\s*', line)
        if match:
            label, url, raw = match.groups()
            rows.append({'row': len(rows)+1, 'line_number': line_number, 'label': label,
                         'url': url, 'raw_markdown': line, 'body_markdown': raw,
                         'text_original': html.unescape(re.sub(r'<br\s*/?>', '\n', raw, flags=re.I))})
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    args = parser.parse_args()
    original = args.source.read_bytes()
    digest = hashlib.sha256(original).hexdigest()
    folder = ROOT / 'sources/supplements/SRC-002'
    manifest_path = folder / 'manifest.json'
    destination = ROOT / 'taxonomy/prompts.json'
    document = read(destination)
    if manifest_path.exists():
        manifest = read(manifest_path)
        if digest != manifest['sha256']:
            raise SystemExit('补充文件已变化，请审阅新增/改动内容后建立下一次导入，勿沿用本批决策。')
        if not set(manifest['added_ids']) <= {p['id'] for p in document['prompts']}:
            raise SystemExit('本批导入记录与题库不一致，需要核查。')
        print('本批已纳入，未新增、覆盖或重排任何题目。')
        return
    rows = parse_rows(original.decode('utf-8-sig'))
    plan = read(ROOT / 'config/supplement-002-decisions.json')
    assert len(rows) == len(plan['decisions']) == 21
    assert [r['row'] for r in rows] == [d['row'] for d in plan['decisions']]
    before = read(destination)
    prompt_by_id = {p['id']: p for p in document['prompts']}
    old_ids = list(prompt_by_id)
    assert old_ids == [f'PR-{n:04d}' for n in range(1, 102)]
    theme_ids = {t['id'] for t in read(ROOT / 'taxonomy/themes.json')['themes']}
    added, merged, decisions = [], [], []
    for row, decision in zip(rows, plan['decisions']):
        source = {'document_id': 'SRC-002', 'file': 'sources/supplements/SRC-002/补充题目.md',
                  'sha256': digest, 'heading_path': ['补充题目', row['label']],
                  'anchor_line': row['line_number'], 'row_number': row['row'], 'label': row['label'],
                  'url': row['url'], 'url_kind': 'search_results' if 'search.bilibili.com' in row['url'] else 'provided_link',
                  'status': 'user_supplement_unverified'}
        record_id = decision['id']
        if decision['action'] == 'exact_duplicate':
            target = prompt_by_id[record_id]
            assert row['text_original'] == target['text_original'], '只有逐字相同的题干才能执行本批精确合并'
            target.setdefault('additional_sources', []).append({**source, 'record_type': decision['record_type'],
                'region': '上海', 'district': decision['district'], 'school_original': decision['school'],
                'exam_type': decision['exam'], 'text_original': row['text_original'],
                'relationship': 'exact_text_duplicate', 'merge_reason': decision['reason']})
            target.setdefault('editor_notes', []).append('题干在补充文件中有两个来源标签；仅合并相同文本，不确认来源归属或两场考试之间的关系。')
            merged.append({'row': row['row'], 'target_id': record_id, 'reason': decision['reason']})
        else:
            assert record_id not in prompt_by_id
            assert decision['primary'] in theme_ids and set(decision['secondary']) <= theme_ids
            year = int(re.search(r'20\d{2}', row['label']).group())
            notes = ['题干按用户提供的补充文件保存；来源网页、年份和引语未外部核验。']
            if row['row'] >= 11:
                notes.append('来源仅提供短题干或简述，未补写原文件没有的字数、文体及其他要求。')
            if source['url_kind'] == 'search_results':
                notes.append('所附链接是B站搜索结果页，不是已定位的原始试卷；“作文投稿”单列，不认定为校考。')
            if decision['record_type'] == 'admission_question':
                notes.append('自招题单列；不将其认定为高考或高三模考，具体招生阶段与题目完整性未核验。')
            p = {'id': record_id, 'title_original': row['label'], 'title': decision['title'],
                 'starred_in_source': False, 'record_type': decision['record_type'], 'region': '上海',
                 'district': decision['district'], 'school_original': decision['school'], 'exam_type': decision['exam'],
                 'year_label_normalized': year, 'year_note': '依补充文件标签记录，不推断学年或确切考试日期。',
                 'text_original': row['text_original'], 'source': source,
                 'primary_theme': decision['primary'], 'secondary_themes': decision['secondary'],
                 'tension': decision['tension'], 'classification_reason': decision['reason'],
                 'classification_status': 'ai_draft', 'source_note_paragraphs': [],
                 'text_completeness': 'source_excerpt_only' if row['row'] >= 11 else 'as_supplied_unverified',
                 'editor_notes': notes}
            prompt_by_id[record_id] = p
            document['prompts'].append(p)
            added.append(record_id)
        decisions.append({'row': row['row'], 'line_number': row['line_number'], 'action': decision['action'], 'target_id': record_id})
    for pair in plan['similar_pairs']:
        for left, right in [(pair['left'], pair['right']), (pair['right'], pair['left'])]:
            prompt_by_id[left].setdefault('similar_prompts', []).append({'id': right, 'kind': pair['kind'], 'reason': pair['reason']})
    # All previous fields remain identical; only explicit related-question backlinks may be added.
    for old in before['prompts']:
        current = prompt_by_id[old['id']]
        assert all(current[k] == v for k, v in old.items())
    assert len(document['prompts']) == 121 and len(set(prompt_by_id)) == 121
    document['schema_version'] = '0.2.0'
    document['source_status'] = '依据用户提供的合订本与补充文件；未外部核验官方试卷、来源链接、引语或书籍原文。'
    document.setdefault('imports', []).append({'source_id': 'SRC-002', 'source_sha256': digest,
        'input_rows': 21, 'added_ids': added, 'merged_rows': merged, 'decisions': decisions})
    manifest = {'document_id': 'SRC-002', 'sha256': digest, 'input_rows': 21, 'added_ids': added,
                'duplicate_rows': merged, 'result_prompt_count': 121, 'decisions': decisions,
                'previous_ids': old_ids, 'url_verification': 'not_performed'}
    folder.mkdir(parents=True, exist_ok=False)
    (folder / '补充题目.md').write_bytes(original)
    (folder / 'rows.json').write_text(dump(rows), encoding='utf-8')
    (folder / 'before-import.snapshot.json').write_text(dump(before), encoding='utf-8')
    (folder / 'manifest.json').write_text(dump(manifest), encoding='utf-8')
    temp = destination.with_suffix('.pending.json')
    temp.write_text(dump(document), encoding='utf-8')
    temp.replace(destination)
    print('补充21条来源记录 → 新增20题、合并1条重复来源；总计121题，旧ID保持不变。')


if __name__ == '__main__':
    main()
