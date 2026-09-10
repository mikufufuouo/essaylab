#!/usr/bin/env python3
"""Synthetic PDF tests in temporary folders; no artificial texts enter the real library."""
import hashlib
import shutil
import tempfile
import unittest
from pathlib import Path

import pymupdf
from materials import ROOT, encoded, read
from pdf_annotations import extract, import_pdf, point_inside


class PDFTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        for folder in ["taxonomy", "templates", "config"]:
            shutil.copytree(ROOT / folder, self.root / folder)
        self.pdf = self.root / "synthetic.pdf"
        with pymupdf.open() as doc:
            page = doc.new_page()
            page.insert_text((60, 80), 'LEFT ALPHA OMIT\nOMIT BETA RIGHT\nGAMMA', fontsize=12)
            quads = [page.search_for(word, quads=True)[0] for word in ['ALPHA', 'BETA']]
            a = page.add_highlight_annot(quads)
            a.set_colors(stroke=(1, 212/255, 0))
            a.set_info(content='Comment is not the highlighted text')
            a.update()
            a = page.add_highlight_annot(page.search_for('GAMMA', quads=True))
            a.set_colors(stroke=(0.5, 0, 0.5))
            a.update()
            page.add_text_annot((200, 200), 'A standalone note')
            blank = doc.new_page()
            blank.add_highlight_annot(pymupdf.Rect(20, 20, 100, 40))
            doc.save(self.pdf)

    def tearDown(self):
        self.tmp.cleanup()

    def test_quad_extraction_not_enclosing_rectangle(self):
        before = hashlib.sha256(self.pdf.read_bytes()).hexdigest()
        records, audit = extract(self.pdf, 'Synthetic fixture', root=self.root)
        self.assertEqual(len(records), 4)
        first = records[0]
        self.assertEqual(first['text_original'], 'ALPHA\nBETA')
        self.assertNotIn('OMIT', first['text_original'])
        self.assertEqual(first['color_normalized'], 'yellow')
        self.assertEqual(first['page']['index_zero_based'], 0)
        self.assertEqual(first['page']['number_one_based'], 1)
        self.assertEqual(len(first['annotation']['quads']), 2)
        self.assertEqual(audit['eligible_count'], 2)
        self.assertEqual(hashlib.sha256(self.pdf.read_bytes()).hexdigest(), before)

    def test_unknown_empty_and_nonhighlight_retained(self):
        records, _ = extract(self.pdf, 'Synthetic fixture', root=self.root)
        unknown = next(r for r in records if r['text_original'] == 'GAMMA')
        self.assertEqual(unknown['color_normalized'], 'unknown')
        self.assertTrue(unknown['eligible_material'])
        empty = next(r for r in records if r['page']['index_zero_based'] == 1)
        self.assertFalse(empty['eligible_material'])
        self.assertTrue(empty['warnings'])
        note = next(r for r in records if r['annotation']['type'] == 'Text')
        self.assertFalse(note['eligible_material'])

    def test_reimport_preserves_interpretation_and_comments_are_not_assumed(self):
        result = import_pdf(self.pdf, 'Synthetic fixture', root=self.root)
        self.assertEqual(result['added'], 2)
        paths = list((self.root / 'materials').glob('MAT-*.json'))
        path = next(p for p in paths if read(p)['capture']['highlight']['color_normalized'] == 'yellow')
        value = read(path)
        self.assertEqual(value['capture']['extraction_method'], 'pdf_annotation')
        self.assertEqual(value['source_match']['status'], 'unchecked')
        self.assertIsNone(value['reader_note'])
        value['analysis']['paraphrase'] = 'Edited after import'
        path.write_text(encoded(value))
        before = path.read_bytes()
        result = import_pdf(self.pdf, 'Synthetic fixture', root=self.root)
        self.assertEqual(result['added'], 0)
        self.assertEqual(result['existing_materials_preserved'], 2)
        self.assertEqual(path.read_bytes(), before)
        self.assertEqual(len(list((self.root / 'inbox/captures').glob('CAP-*.json'))), 4)

    def test_polygon_does_not_accept_enclosing_box_corners(self):
        quad = [(0, 1), (1, 0), (1, 2), (2, 1)]
        self.assertTrue(point_inside((1, 1), quad))
        self.assertFalse(point_inside((0.1, 0.1), quad))


if __name__ == '__main__':
    unittest.main(verbosity=2)
