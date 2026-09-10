#!/usr/bin/env python3
"""Check provenance, coverage, links and data contracts of the generated library."""
import collections
import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(name):
    return json.loads((ROOT / name).read_text(encoding="utf-8"))


def main():
    document = read("taxonomy/prompts.json")
    prompts = document["prompts"]
    theme_document = read("taxonomy/themes.json")
    themes = theme_document["themes"]
    manifest = read("config/source_manifest.json")
    paragraphs = read("sources/paragraphs.json")
    rows = {r["paragraph"]: r for r in paragraphs["paragraphs"]}
    anthology = ROOT / "sources/作文合订本.docx"
    # The public PWA repository intentionally excludes the original anthology.
    # When it is present in a local maintenance checkout, retain the full hash check.
    if anthology.exists():
        assert hashlib.sha256(anthology.read_bytes()).hexdigest() == manifest["sha256"] == paragraphs["sha256"]
    else:
        assert manifest["sha256"] == paragraphs["sha256"]
    assert len(prompts) == len({p["id"] for p in prompts})
    original_prompts = [p for p in prompts if p["source"]["document_id"] == "SRC-001"]
    assert len(original_prompts) == 101
    assert len(themes) == len({t["id"] for t in themes}) == 10
    prompt_ids = {p["id"] for p in prompts}
    theme_ids = {t["id"] for t in themes}
    ownership = collections.Counter()
    for p in prompts:
        source = p["source"]
        if source["document_id"] == "SRC-001":
            start = source["anchor_paragraph"]
            ids = source["text_paragraphs"]
            expected = "\n".join(rows[n]["text"] for n in ids)
            if start == 103:
                expected = expected[expected.index("24."):]
            assert p["text_original"] == expected, p["id"]
            assert source["status"] == "anthology_only_unverified"
            assert not set(ids) & {62, 119, 155, 307}
            ownership.update(set(ids) | {start})
        elif source["document_id"] == "SRC-002":
            assert source["document_id"] == "SRC-002"
            assert source["status"] == "user_supplement_unverified"
        elif source["document_id"] == "SRC-003":
            personal_path = ROOT / source["file"]
            if personal_path.exists():
                assert hashlib.sha256(personal_path.read_bytes()).hexdigest() == source["sha256"]
            else:
                # User-provided source text is intentionally retained only locally.
                assert source["sha256"]
            assert source["status"] == "user_provided"
            assert p["record_type"] == "personal_question"
            assert p["year_label_normalized"] is None and p["region"] is None
        else:
            raise AssertionError(f"未知来源：{source['document_id']}")
        assert p["classification_status"] == "ai_draft"
        assert p["primary_theme"] in theme_ids
        assert len(p["secondary_themes"]) <= 2
        assert len(set(p["secondary_themes"])) == len(p["secondary_themes"])
        assert set(p["secondary_themes"]) <= theme_ids - {p["primary_theme"]}
        assert (ROOT / "prompts" / (p["id"] + ".md")).exists()
    assert all(c == 1 for c in ownership.values())
    assert set(ownership) == {n for n, r in rows.items() if r["role"] == "prompt"}
    assert {n for n, r in rows.items() if r["role"] == "source_note"} == {62, 119, 155, 307}
    assert {n for n, r in rows.items() if r["role"] == "preface"} == {1, 2}
    assert all(r["role"] in {"blank", "preface", "section_heading", "prompt", "source_note"} for r in rows.values())
    by_start = {p["source"]["anchor_paragraph"]: p for p in original_prompts}
    assert by_start[291]["school_original"] == "行知"
    assert by_start[289]["school_original"] == "晋元"
    assert by_start[293]["school_original"] is None and by_start[293]["region"] is None
    assert by_start[295]["record_type"] == "other_region_mock" and by_start[295]["region"] == "深圳"
    assert by_start[103]["district"] == "普陀"
    assert by_start[103]["year_label_normalized"] == 2026
    assert 69 not in by_start
    assert all(by_start[n]["record_type"] == "personal_question" for n in [305, 308, 310, 313, 315, 317])
    supplement = ROOT / "sources/supplements/SRC-002"
    if supplement.exists():
        from import_prompt_supplement import parse_rows
        imported = read("sources/supplements/SRC-002/manifest.json")
        source_bytes = (supplement / "补充题目.md").read_bytes()
        assert hashlib.sha256(source_bytes).hexdigest() == imported["sha256"]
        source_rows = parse_rows(source_bytes.decode("utf-8-sig"))
        assert source_rows == read("sources/supplements/SRC-002/rows.json")
        assert len(source_rows) == len(imported["decisions"]) == 21
        by_id = {p["id"]: p for p in prompts}
        assert len(imported["added_ids"]) == 20
        assert set(imported["added_ids"]) == {f"PR-{n:04d}" for n in range(102,122)}
        assert len(prompts) == 122
        for row, decision in zip(source_rows, imported["decisions"]):
            target = by_id[decision["target_id"]]
            assert target["text_original"] == row["text_original"]
            if decision["action"] == "new":
                origin = target["source"]
            else:
                assert decision["action"] == "exact_duplicate"
                origin = next(x for x in target["additional_sources"] if x["row_number"] == row["row"])
                assert origin["text_original"] == row["text_original"]
            assert origin["anchor_line"] == row["line_number"]
            assert origin["url"] == row["url"] and origin["label"] == row["label"]
        baseline = read("sources/supplements/SRC-002/before-import.snapshot.json")
        for old in baseline["prompts"]:
            # Classification remains editable; preserve identity and source text.
            assert all(by_id[old["id"]][k] == old[k] for k in ["id", "text_original", "source"]), old["id"]
        assert len(by_id["PR-0110"]["additional_sources"]) == 1
        assert by_id["PR-0119"]["text_original"] != by_id["PR-0048"]["text_original"]
        assert by_id["PR-0117"]["record_type"] == "writing_submission"
        assert all(by_id[f"PR-{n:04d}"]["record_type"] == "admission_question" for n in range(118,122))
        for p in prompts:
            for link in p.get("similar_prompts", []):
                assert link["id"] in by_id and link["id"] != p["id"]
                assert any(back["id"] == p["id"] for back in by_id[link["id"]].get("similar_prompts", []))
    personal = [p for p in prompts if p["source"]["document_id"] == "SRC-003"]
    assert len(personal) == 1
    assert personal[0]["id"] == "PR-0122"
    assert personal[0]["text_original"] == "生活中，人们常常追求“更多”；如今，也有越来越多的人开始追求“更少”。对此，你怎么看？"
    for t in themes:
        assert "primary_prompt_ids" not in t and "related_prompt_ids" not in t
    for path in ROOT.rglob("*.md"):
        if any(part in {"legacy-v0.1", ".venv", "__pycache__", "node_modules", "dist", ".git"} for part in path.parts):
            continue
        for target in re.findall(r"\]\(([^)]+)\)", path.read_text(encoding="utf-8")):
            if "://" not in target:
                assert (path.parent / target.split("#")[0]).exists(), (path, target)
    page = (ROOT / "viewer/index.html").read_text(encoding="utf-8")
    assert 'id="library-data"' not in page
    assert '../taxonomy/prompts.json' in page and '../taxonomy/themes.json' in page
    assert 'type="file"' in page
    assert all(p["text_original"] not in page for p in prompts)
    assert page == (ROOT / "templates/preview.html").read_text(encoding="utf-8")
    sample = read("examples/MAT-DEMO-001.json")
    assert sample["capture"]["text_original"] == rows[119]["text"]
    assert sample["capture"]["source"]["author"] is None and sample["reader_note"] is None
    assert sample["status"] == "draft"
    assert all(p["id"] in prompt_ids for p in sample["analysis"]["related_prompts"])
    assert sample["analysis"]["primary_theme"] not in sample["analysis"]["secondary_themes"]
    from materials import validate_material, read as read_material
    validate_material(sample)
    actual = sorted((ROOT / "materials").glob("MAT-*.json"))
    for path in actual:
        value = read_material(path)
        assert path.stem == value["id"]
        validate_material(value)
    print(f"通过：{len(prompts)} 条题目溯源、10 个母题、段落覆盖与阅读链接；浏览器不内嵌题库。")
    print(f"v0.2 Schema 示例及 {len(actual)} 条真实素材字段、状态、交叉引用通过。")


if __name__ == "__main__":
    main()
