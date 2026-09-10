#!/usr/bin/env python3
"""Render taxonomy reading views from canonical JSON; never overwrite source data."""
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    pd = json.loads((ROOT / 'taxonomy/prompts.json').read_text(encoding='utf-8'))
    td = json.loads((ROOT / 'taxonomy/themes.json').read_text(encoding='utf-8'))
    prompts, themes = pd['prompts'], td['themes']
    lookup = {t['id']: t for t in themes}
    for folder in ['prompts', 'themes', 'viewer']:
        (ROOT / folder).mkdir(exist_ok=True)
    for p in prompts:
        ids = [p['primary_theme'], *p['secondary_themes']]
        if any(tid not in lookup for tid in ids):
            raise ValueError(f"无效母题：{p['id']}")
        fields = {k: p[k] for k in ['id', 'record_type', 'primary_theme', 'secondary_themes', 'classification_status']}
        body = '---\n' + '\n'.join(f'{k}: {json.dumps(v, ensure_ascii=False)}' for k, v in fields.items()) + '\n---\n'
        body += f"\n# {p['title']}\n\n生成的阅读副本；修改分类请编辑 taxonomy/prompts.json 对应 ID。\n\n"
        source = p['source']
        location = f"附件段落 {source['anchor_paragraph']}" if 'anchor_paragraph' in source else f"补充文件第 {source['anchor_line']} 行"
        body += '来源：' + ' / '.join(source['heading_path']) + f"；{location}。据用户提供文件，未外部核验。\n\n"
        if source.get('url'):
            body += f"[原文件所附来源链接]({source['url']})（未核验）\n\n"
        body += '## 题目原文\n\n' + p['text_original'] + '\n\n## 分类初稿\n\n'
        body += f"核心关系：{p['tension']}\n\n阅读方向：{p['classification_reason']}\n\n"
        body += '母题：' + '、'.join(f"[{lookup[tid]['name']}](../themes/{tid}.md)" for tid in ids) + '\n'
        if p['source_note_paragraphs']:
            body += '\n附注：' + '、'.join(f'[段落 {n}](../sources/附注.md#p{n})' for n in p['source_note_paragraphs']) + '\n'
        if p.get('additional_sources'):
            body += '\n## 相同题干的其他来源\n\n'
            for extra in p['additional_sources']:
                body += f"- [{extra['label']}]({extra['url']})：补充文件第 {extra['anchor_line']} 行；{extra['merge_reason']}\n"
        if p.get('similar_prompts'):
            body += '\n## 相近但分别保留的题目\n\n'
            for link in p['similar_prompts']:
                body += f"- [{link['id']}](../prompts/{link['id']}.md)：{link['reason']}\n"
        if p.get('editor_notes'):
            body += '\n## 来源与整理说明\n\n' + '\n'.join('- '+n for n in p['editor_notes']) + '\n'
        (ROOT / 'prompts' / f"{p['id']}.md").write_text(body, encoding='utf-8')
    for t in themes:
        body = f"# {t['name']}\n\n生成的阅读副本；母题定义以 taxonomy/themes.json 为准。\n\n{t['question']}\n\n边界：{t['boundary']}\n\n"
        body += '子方向：' + '、'.join(t['include']) + '\n\n'
        for label, chosen in [('主归题目', [p for p in prompts if p['primary_theme'] == t['id']]),
                              ('关联题目', [p for p in prompts if t['id'] in p['secondary_themes']])]:
            body += f'## {label}\n\n' + '\n'.join(f"- [{p['title']}](../prompts/{p['id']}.md)" for p in chosen) + '\n\n'
        (ROOT / 'themes' / f"{t['id']}.md").write_text(body, encoding='utf-8')
    shutil.copyfile(ROOT / 'templates/preview.html', ROOT / 'viewer/index.html')
    from materials import write_material_index
    values = write_material_index(ROOT)
    print(f'已更新 {len(values)} 条素材的文件索引；素材正文仍从独立 JSON 读取。')
    print(f'生成 {len(prompts)} 张题目阅读卡、{len(themes)} 个母题索引及无内嵌数据的浏览器；独立 JSON 未被改写。')


if __name__ == '__main__':
    main()
