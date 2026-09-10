#!/usr/bin/env python3
"""Extract embedded PDF highlights with character-level QuadPoints matching; no OCR.

Handles this exported-PDF route, not Zotero's database or live sync. Unknown colors,
unsupported annotations and empty regions are retained in the audit, never dropped.
"""
import argparse
import hashlib
import json
import os
from collections import Counter
from pathlib import Path

import pymupdf

from materials import ROOT, encoded, read, validate_material, write_new_records


def sha(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def rgb_hex(values):
    if len(values) != 3 or any(v < 0 or v > 1 for v in values):
        return None
    return "#" + "".join(f"{round(v * 255):02x}" for v in values)


def point_inside(point, quad):
    # MuPDF Quad order: upper-left, upper-right, lower-left, lower-right.
    polygon = [quad[0], quad[1], quad[3], quad[2]]
    crosses = []
    for a, b in zip(polygon, polygon[1:] + polygon[:1]):
        crosses.append((b[0]-a[0])*(point[1]-a[1]) - (b[1]-a[1])*(point[0]-a[0]))
    return min(crosses) >= -1e-5 or max(crosses) <= 1e-5


def text_index(page):
    chars, full, line_id = [], "", 0
    raw = page.get_text("rawdict", flags=pymupdf.TEXTFLAGS_RAWDICT & ~pymupdf.TEXT_PRESERVE_IMAGES)
    for block in raw["blocks"]:
        if block["type"] != 0:
            continue
        for line in block["lines"]:
            if full:
                full += "\n"
            for span in line["spans"]:
                for char in span["chars"]:
                    chars.append({"char": char["c"], "bbox": list(char["bbox"]), "line": line_id,
                                  "offset": len(full), "direction": list(line["dir"])})
                    full += char["c"]
            line_id += 1
    return chars, full


def select_text(chars, quads):
    used, fragments, selected, warnings = set(), [], [], []
    for qi, quad in enumerate(quads):
        current_line, chunk = None, ""
        for ci, char in enumerate(chars):
            x0, y0, x1, y1 = char["bbox"]
            if ci in used or not point_inside(((x0+x1)/2, (y0+y1)/2), quad):
                continue
            if current_line is not None and current_line != char["line"]:
                fragments.append(chunk)
                chunk = ""
            chunk += char["char"]
            current_line = char["line"]
            used.add(ci)
            selected.append({**char, "quad_index": qi})
            if abs(char["direction"][1]) > 0.01:
                warnings.append("含旋转或竖排文字，请核对阅读顺序。")
        if chunk:
            fragments.append(chunk)
        elif not any(point_inside(((c['bbox'][0]+c['bbox'][2])/2, (c['bbox'][1]+c['bbox'][3])/2), quad) for c in chars):
            warnings.append(f"高亮区域 {qi+1} 没有匹配到文字；需要人工核对，未使用 OCR。")
    return "\n".join(fragments), selected, list(dict.fromkeys(warnings))


def extract(pdf_path, title, author=None, root=ROOT):
    pdf_path = Path(pdf_path).resolve()
    digest = hashlib.sha256(pdf_path.read_bytes()).hexdigest()
    palette = read(root / "config/pdf_colors.json")["palette"]
    records = []
    with pymupdf.open(pdf_path) as doc:
        if doc.needs_pass:
            raise ValueError("PDF 需要密码，未读取或修改文件。")
        metadata = doc.metadata
        for page in doc:
            annots = list(page.annots() or [])
            if not annots:
                continue
            chars, full = text_index(page)
            for annot in annots:
                vertices = annot.vertices or []
                is_highlight = annot.type[0] == pymupdf.PDF_ANNOT_HIGHLIGHT
                quads = [vertices[i:i+4] for i in range(0, len(vertices), 4)] if is_highlight and len(vertices) % 4 == 0 else []
                color_raw = list(annot.colors.get("stroke") or [])
                color_hex = rgb_hex(color_raw)
                mapping = palette.get(color_hex, {"color": "unknown", "capture_type": "unknown"})
                original, selected, warnings = select_text(chars, quads) if quads else ("", [], [])
                if not is_highlight:
                    warnings.append("当前适配器仅将 Highlight 文字标注转为素材；本批注保留在原始记录。")
                elif not quads:
                    warnings.append("没有有效 QuadPoints，未用外包矩形猜选区。")
                if is_highlight and not original.strip():
                    warnings.append("没有可用高亮文字，保留批注但不生成空素材。")
                if color_hex not in palette:
                    warnings.append("颜色未配置；保留原始颜色并标 unknown。")
                if annot.info.get("content"):
                    warnings.append("批注 content 已保留，尚未判断它是评论还是复制的原文，不自动写作读者留言。")
                offsets = [c["offset"] for c in selected]
                lo = min(offsets) if offsets else 0
                hi = max(c["offset"] + len(c["char"]) for c in selected) if offsets else 0
                identity = {"pdf_sha256": digest, "page_index": page.number, "annotation_id": annot.info.get("id") or f"xref:{annot.xref}",
                            "vertices": vertices, "colors": annot.colors, "content": annot.info.get("content"), "type": annot.type[1]}
                fingerprint = sha(identity)
                record = {
                    "id": "CAP-" + fingerprint[:16], "fingerprint": fingerprint, "extractor_version": "0.1.0",
                    "source": {"file_sha256": digest, "asset_path": os.path.relpath(pdf_path, root), "title": title,
                               "author": author, "metadata_basis": "标题与作者由调用者提供；PDF元数据另存，不由批注署名推断。"},
                    "page": {"index_zero_based": page.number, "number_one_based": page.number+1,
                             "label_raw": page.get_label() or None, "print_page": None,
                             "rotation": page.rotation, "rect": list(page.rect)},
                    "annotation": {"xref": annot.xref, "type": annot.type[1], "info": annot.info,
                                   "colors": annot.colors, "opacity": annot.opacity, "rect": list(annot.rect),
                                   "vertices": vertices, "quads": quads,
                                   "coordinate_system": "MuPDF unrotated page, points, top-left origin",
                                   "pdf_object_raw": doc.xref_object(annot.xref)},
                    "color_hex": color_hex, "color_normalized": mapping["color"], "capture_type": mapping["capture_type"],
                    "text_original": original, "selected_characters": selected,
                    "context_before": full[max(0, lo-180):lo] if selected else None,
                    "context_after": full[hi:hi+180] if selected else None,
                    "context_note": "上下文来自同页文字层前后各最多180字，可能截断；没有自动扩充原始高亮。",
                    "warnings": warnings, "eligible_material": is_highlight and bool(original.strip())
                }
                records.append(record)
        manifest = {"source_sha256": digest, "source_path": os.path.relpath(pdf_path, root), "page_count": len(doc),
                    "pdf_metadata": metadata, "annotation_count": len(records),
                    "highlight_count": sum(r["annotation"]["type"] == "Highlight" for r in records),
                    "eligible_count": sum(r["eligible_material"] for r in records),
                    "counts_by_color": dict(Counter(r["color_normalized"] for r in records)),
                    "capture_ids": [r["id"] for r in records], "pymupdf_version": pymupdf.VersionBind,
                    "source_unchanged": digest == hashlib.sha256(pdf_path.read_bytes()).hexdigest()}
    return records, manifest


def material_from_capture(r):
    value = {
        "id": "MAT-" + r["fingerprint"][:16], "schema_version": "0.2.0", "status": "inbox",
        "import_fingerprint": r["fingerprint"], "parent_capture_id": r["id"],
        "source_match": {"status": "unchecked", "basis": None, "checked_by": None, "checked_at": None},
        "capture": {
            "text_original": r["text_original"], "context_before": r["context_before"], "context_after": r["context_after"],
            "context_note": r["context_note"], "extraction_method": "pdf_annotation",
            "source": {"title": r["source"]["title"], "author": r["source"]["author"], "edition": None, "url": None,
                       "file_sha256": r["source"]["file_sha256"],
                       "locator": {"kind": "pdf_page_index", "value": str(r["page"]["index_zero_based"]),
                                   "bbox": r["annotation"]["rect"], "coordinate_unit": "PDF point; MuPDF top-left; page index starts at 0",
                                   "asset_path": r["source"]["asset_path"]}},
            "highlight": {"color_raw": r["color_hex"] or json.dumps(r["annotation"]["colors"]),
                          "color_normalized": r["color_normalized"], "capture_type": r["capture_type"]}
        },
        "reader_note": None,
        "analysis": {"paraphrase": None, "primary_theme": None, "secondary_themes": [], "classification_reason": None,
                     "concept_candidates": [], "argument_uses": [], "related_prompts": [], "open_questions": []},
        "review_notes": [f"PDF 第 {r['page']['number_one_based']} 页（零基索引 {r['page']['index_zero_based']}），印刷页码未知。",
                         "按逐行 QuadPoints 与文字层字符中心匹配；未使用 OCR，未经人工认可。",
                         f"原始批注：inbox/captures/{r['id']}.json", *r["warnings"]],
        "reviewed_by": None, "reviewed_at": None
    }
    return value


def import_pdf(pdf_path, title, author=None, root=ROOT):
    records, manifest = extract(pdf_path, title, author, root)
    pending, added, skipped = {}, 0, 0
    for r in records:
        capture_path = root / "inbox/captures" / (r["id"] + ".json")
        if capture_path.exists():
            previous = read(capture_path)
            if previous["fingerprint"] != r["fingerprint"] or previous["text_original"] != r["text_original"]:
                raise ValueError(f"原批注记录冲突：{r['id']}，未写入本批数据。")
        else:
            pending[capture_path] = r
        if not r["eligible_material"]:
            continue
        value = material_from_capture(r)
        validate_material(value, root)
        target = root / "materials" / (value["id"] + ".json")
        if target.exists():
            if read(target).get("import_fingerprint") != r["fingerprint"]:
                raise ValueError(f"素材 ID 冲突：{value['id']}")
            skipped += 1
        else:
            pending[target] = value
            added += 1
    audit_path = root / "inbox/pdf-imports" / (manifest["source_sha256"] + ".json")
    if not audit_path.exists():
        pending[audit_path] = manifest
    write_new_records(pending)
    return {**manifest, "added": added, "existing_materials_preserved": skipped}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pdf", type=Path)
    parser.add_argument("--title", required=True)
    parser.add_argument("--author")
    args = parser.parse_args()
    print(encoded(import_pdf(args.pdf, args.title, args.author)))


if __name__ == "__main__":
    main()
