#!/usr/bin/env python3
"""Export the question and reading libraries as a self-contained browsing snapshot."""
import base64
import re
import collections
import json
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def main():
    from materials import load_materials, load_material_groups
    materials = load_materials(ROOT)
    prompt_document = read(ROOT / "taxonomy/prompts.json")
    theme_document = read(ROOT / "taxonomy/themes.json")
    source_audit = read(ROOT / "sources/audit.json")
    prompts = prompt_document["prompts"]
    themes = theme_document["themes"]
    counts = dict(collections.Counter(p["record_type"] for p in prompts))
    themes_for_view = []
    for theme in themes:
        themes_for_view.append({
            **theme,
            "primary_prompt_ids": [p["id"] for p in prompts if p["primary_theme"] == theme["id"]],
            "related_prompt_ids": [p["id"] for p in prompts if theme["id"] in p["secondary_themes"]],
        })
    payload = {
        "prompts": prompts,
        "themes": themes_for_view,
        "audit": {**source_audit, "counts_by_type": counts},
        "prompt_document": prompt_document,
        "theme_document": theme_document,
        "materials": materials,
        "material_groups": load_material_groups(ROOT),
    }
    serialized = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    serialized = serialized.replace("<", "\\u003c").replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")

    template = (ROOT / "templates/preview.html").read_text(encoding="utf-8")
    # Keep the single-file edition truly offline, including collection artwork.
    def embed_art(match):
        image = ROOT / 'assets/group-art' / match.group(1)
        encoded = base64.b64encode(image.read_bytes()).decode('ascii')
        return 'data:image/jpeg;base64,' + encoded
    template = re.sub(r"\.\./assets/group-art/([a-z0-9-]+\.jpg)", embed_art, template)
    loader_start = template.index('<div id="data-loader"')
    loader_end = template.index('</div>\n<main id="library-main"', loader_start) + len('</div>')
    template = template[:loader_start] + '<div id="data-loader" hidden></div>' + template[loader_end:]
    script_start = template.index("const fileInput=document.getElementById('data-files');")
    script_end = template.index("\n\n</script>", script_start)
    embedded = f"const EMBEDDED_DATA={serialized};\nmount(EMBEDDED_DATA);"
    template = template[:script_start] + embedded + template[script_end:]
    template = template.replace(
        "题库与素材来自独立数据文件。此页仅供查阅，不改写来源。",
        "这是截至 " + date.today().isoformat() + " 的查阅快照，题库与素材已嵌入，可离线打开。来源数据不随页面操作改写。",
    )
    template = template.replace(
        "此页面用于题库检索。通过本地服务打开时刷新即可读取最新 JSON；素材整理与修订目前使用独立文件。",
        "本页用于查看和搜索快照；后续新增题目请使用 viewer/index.html 读取最新独立数据。",
    )
    template = template.replace("EssayLab v0.3", "EssayLab 最新快照")
    output = ROOT / "EssayLab-最新版.html"
    output.write_text(template, encoding="utf-8")
    print(f"已导出 {output}：{len(prompts)} 题、{len(themes)} 个母题、{len(materials)} 张素材，数据已内嵌。")


if __name__ == "__main__":
    main()
