#!/usr/bin/env python3
"""Restore a continuous PDF passage and highlights from native Zotero rectangles."""
import argparse
import hashlib
import json
from pathlib import Path

import fitz
from materials import ROOT, encoded, validate_material


def restore(document, segments, digest):
    blocks = []
    found = set()
    for number in range(min(s['page_index'] for s in segments), max(s['page_index'] for s in segments) + 1):
        page = document[number]
        selections = []
        for s in segments:
            if s['page_index'] != number:
                continue
            if s['position'].get('pageIndex') != number or not s['position'].get('rects'):
                raise ValueError(f"Missing native rectangles: {s['annotation_key']}")
            selections.append((s, [fitz.Rect(r) * page.transformation_matrix for r in s['position']['rects']]))
        for block in page.get_text('rawdict', sort=True)['blocks']:
            if block['type'] != 0:
                continue
            chars = []
            for line in block['lines']:
                for span in line['spans']:
                    for char in span['chars']:
                        box = fitz.Rect(char['bbox'])
                        center = (box.tl + box.br) / 2
                        owners = [s for s, rects in selections if any(r.contains(center) for r in rects)]
                        found.update(s['annotation_key'] for s in owners)
                        chars.append((char['c'], owners))
            blocks.append(chars)
    expected = {s['annotation_key'] for s in segments}
    if found != expected:
        raise ValueError(f"No PDF characters for annotations: {sorted(expected - found)}")
    occupied = [i for i, chars in enumerate(blocks) if any(owners for _, owners in chars)]
    text, ranges = '', []
    for block in blocks[occupied[0]:occupied[-1] + 1]:
        if text:
            text += '\n\n'
        for char, owners in block:
            start = len(text)
            text += char
            if not owners:
                continue
            keys = sorted(s['annotation_key'] for s in owners)
            color = owners[0]['color']
            if ranges and ranges[-1]['end'] == start and ranges[-1]['annotation_keys'] == keys and ranges[-1]['color'] == color:
                ranges[-1]['end'] = len(text)
            else:
                ranges.append(dict(start=start, end=len(text), annotation_keys=keys, color=color))
    return dict(text=text, highlight_ranges=ranges, method='pdf_rects', file_sha256=digest,
                page_start=min(s['page_index'] for s in segments), page_end=max(s['page_index'] for s in segments))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('pdf', type=Path)
    parser.add_argument('--attachment', required=True)
    args = parser.parse_args()
    digest = hashlib.sha256(args.pdf.read_bytes()).hexdigest()
    pending = []
    with fitz.open(args.pdf) as document:
        for path in sorted((ROOT / 'materials').glob('MAT-*.json')):
            material = json.loads(path.read_text())
            capture = material['capture']
            segments = capture.get('segments', [])
            if not segments or {s['attachment_key'] for s in segments} != {args.attachment}:
                continue
            if capture['source']['file_sha256'] != digest:
                raise ValueError(f'{path.name}: PDF fingerprint mismatch')
            capture['reading'] = restore(document, segments, digest)
            validate_material(material)
            pending.append((path, material))
    for path, material in pending:
        path.write_text(encoded(material))
    print(f'Restored {len(pending)} materials from PDF rectangles; original snapshots retained.')


if __name__ == '__main__':
    main()
