import copy
import unittest
import fitz
from restore_reading import restore
from materials import ROOT, read, validate_material


class ReadingTests(unittest.TestCase):
    def test_geometry_distinguishes_repeats_and_overlaps_across_pages(self):
        doc = fitz.open()
        for _ in range(2):
            page = doc.new_page()
            page.insert_text((72, 100), 'ALPHA OMIT ALPHA')
        segments = []
        for page_index, index, key in [(0, 1, 'FIRST'), (0, 1, 'OVERLAP'), (1, 0, 'SECOND')]:
            page = doc[page_index]
            rect = page.search_for('ALPHA')[index] * ~page.transformation_matrix
            segments.append(dict(page_index=page_index, annotation_key=key, color='#ffd400',
                                 position=dict(pageIndex=page_index, rects=[list(rect)])))
        result = restore(doc, segments, 'a' * 64)
        self.assertEqual(result['text'], 'ALPHA OMIT ALPHA\n\nALPHA OMIT ALPHA')
        self.assertEqual([(r['start'], r['end']) for r in result['highlight_ranges']], [(11, 16), (18, 23)])
        self.assertEqual(result['highlight_ranges'][0]['annotation_keys'], ['FIRST', 'OVERLAP'])
        segments[0]['position']['rects'] = [[0, 0, 1, 1]]
        with self.assertRaisesRegex(ValueError, 'FIRST'):
            restore(doc, segments, 'a' * 64)
        doc.close()

    def test_rejects_broken_ranges_and_provenance(self):
        original = read(ROOT / 'materials/MAT-ZOTERO-6LF72SCC-001.json')
        for change in ['bounds', 'overlap', 'unknown', 'missing', 'fingerprint', 'pages']:
            card = copy.deepcopy(original)
            reading = card['capture']['reading']
            if change == 'bounds': reading['highlight_ranges'][0]['end'] = len(reading['text']) + 1
            if change == 'overlap': reading['highlight_ranges'][1]['start'] = 0
            if change == 'unknown': reading['highlight_ranges'][0]['annotation_keys'] = ['UNKNOWN']
            if change == 'missing': reading['highlight_ranges'] = reading['highlight_ranges'][1:]
            if change == 'fingerprint': reading['file_sha256'] = 'a' * 64
            if change == 'pages': reading['page_end'] += 1
            with self.subTest(change=change), self.assertRaises(ValueError):
                validate_material(card)


if __name__ == '__main__':
    unittest.main()
