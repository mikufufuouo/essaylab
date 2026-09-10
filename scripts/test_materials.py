#!/usr/bin/env python3
"""Focused ingestion tests run entirely in temporary libraries; never seed user data."""
import copy
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from materials import ROOT, encoded, import_batch, normalize, read, render_all, validate_material


class ImportTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        for folder in ["templates", "taxonomy"]:
            shutil.copytree(ROOT / folder, self.root / folder)
        self.batch = self.root / "batch.json"

    def tearDown(self):
        self.tmp.cleanup()

    def run_batch(self, items):
        self.batch.write_text(encoded({"items": items}), encoding="utf-8")
        return import_batch(self.batch, self.root)

    def cards(self):
        return sorted((self.root / "materials").glob("MAT-*.json"))

    def test_raw_capture_unknowns_and_status(self):
        text = '  测试文本，不是实际阅读素材。\n第二行。  '
        self.assertEqual(self.run_batch([{"raw_text": text}])["added"], 1)
        card = read(self.cards()[0])
        self.assertEqual(card["capture"]["text_original"], text)
        self.assertIsNone(card["capture"]["source"]["title"])
        self.assertEqual(card["capture"]["highlight"]["color_normalized"], "unknown")
        self.assertEqual(card["source_match"]["status"], "unchecked")
        self.assertEqual(card["status"], "inbox")
        self.assertIsNone(card["analysis"]["primary_theme"])
        self.assertEqual(len(list((self.root / "inbox/captures").glob('*.json'))), 1)

    def test_reimport_preserves_human_changes(self):
        item = {"raw_text": "测试文本", "source_title": "测试来源"}
        self.run_batch([item])
        path = self.cards()[0]
        card = read(path)
        card["reader_note"] = "导入后新增的想法，不得被重复导入覆盖。"
        path.write_text(encoded(card), encoding="utf-8")
        before = path.read_bytes()
        result = self.run_batch([item, item])
        self.assertEqual(result["added"], 0)
        self.assertEqual(result["exact_repeats_skipped"], 2)
        self.assertEqual(path.read_bytes(), before)

    def test_different_sources_and_notes_remain_separate(self):
        self.assertEqual(self.run_batch([
            {"raw_text": "相同测试文本", "source_title": "来源甲"},
            {"raw_text": "相同测试文本", "source_title": "来源乙"},
            {"raw_text": "相同测试文本", "source_title": "来源甲", "reader_note": "新的留言"}
        ])["added"], 3)

    def test_invalid_batch_writes_nothing(self):
        with self.assertRaises(Exception):
            self.run_batch([{"raw_text": "有效测试文本"}, {"raw_text": " \n "}])
        self.assertFalse(self.cards())
        self.assertFalse((self.root / "inbox/captures").exists())

    def test_invalid_links_and_unearned_verification_fail(self):
        card = normalize({"raw_text": "测试文本"})
        invalid = copy.deepcopy(card)
        invalid["analysis"]["related_prompts"] = [{"id": "PR-9999", "reason": "不存在"}]
        with self.assertRaises(ValueError):
            validate_material(invalid, self.root)
        invalid = copy.deepcopy(card)
        invalid["source_match"]["status"] = "matched"
        with self.assertRaises(Exception):
            validate_material(invalid, self.root)
        invalid = copy.deepcopy(card)
        invalid["status"] = "reviewed"
        with self.assertRaises(Exception):
            validate_material(invalid, self.root)
        invalid = read(ROOT / "examples/MAT-DEMO-001.json")
        invalid["analysis"]["argument_uses"][0]["evidence_status"] = "fact_verified"
        with self.assertRaises(Exception):
            validate_material(invalid, self.root)

    def test_render_is_a_disposable_view(self):
        self.run_batch([{"raw_text": "测试文本", "color": "yellow"}])
        path = self.cards()[0]
        before = path.read_bytes()
        viewer = self.root / "viewer/index.html"
        viewer.parent.mkdir()
        viewer.write_text('viewer must stay unchanged', encoding='utf-8')
        self.assertEqual(render_all(self.root), 1)
        self.assertEqual(path.read_bytes(), before)
        self.assertEqual(viewer.read_text(), 'viewer must stay unchanged')
        self.assertIn('测试文本', path.with_suffix('.md').read_text())
        card = read(path)
        self.assertEqual(card['capture']['highlight']['capture_type'], 'unknown')
        self.assertIsNone(card['analysis']['primary_theme'])

    def grouped_card(self):
        card = normalize({'raw_text': '测试前提\n\n测试例子'})
        card['capture'].update({
            'raw_snapshot': 'inbox/zotero/test.json', 'grouping_reason': '测试同一论证',
            'segments': [
                {'annotation_key': key, 'attachment_key': 'PDFTEST1', 'page_label': '1',
                 'page_index': 0, 'sort_index': order, 'position': {'pageIndex': 0},
                 'text': text, 'comment': comment, 'color': color}
                for key, order, text, comment, color in [
                    ('ANN00001', '00000|000001', '测试前提', '', '#ffd400'),
                    ('ANN00002', '00000|000002', '测试例子', '读者质疑', '#2ea8e5')]
            ]})
        card['analysis']['argument_structure'] = [
            {'role': '例子', 'summary': '测试解释', 'annotation_keys': ['ANN00002']}]
        return card

    def test_group_retains_mixed_colors_comments_and_relations(self):
        from materials import markdown
        card = self.grouped_card()
        validate_material(card, self.root)
        view = markdown(card)
        for text in ['#ffd400', '#2ea8e5', '读者质疑', 'ANN00002', '不代表连续原文', '测试解释']:
            self.assertIn(text, view)

    def test_group_rejects_lost_provenance_and_silent_reconstruction(self):
        for mutation in ['duplicate', 'wrong_attachment', 'reverse', 'rewrite', 'dangling']:
            with self.subTest(mutation=mutation):
                card = self.grouped_card()
                segments = card['capture']['segments']
                if mutation == 'duplicate':
                    segments[1]['annotation_key'] = segments[0]['annotation_key']
                elif mutation == 'wrong_attachment':
                    segments[1]['attachment_key'] = 'OTHERPDF'
                elif mutation == 'reverse':
                    segments.reverse()
                elif mutation == 'rewrite':
                    card['capture']['text_original'] += '模型补写的过渡'
                else:
                    card['analysis']['argument_structure'][0]['annotation_keys'] = ['MISSING']
                with self.assertRaises(ValueError):
                    validate_material(card, self.root)

    def test_dedup_joins_overlap_and_keeps_comment_on_hidden_segment(self):
        from materials import markdown, reading_text
        card = self.grouped_card()
        first, second = card['capture']['segments']
        first['text'] = '甲乙丙'
        second.update(text='乙丙', display_text='', cleanup_note='同一处已包含在前条中')
        card['capture']['text_original'] = reading_text(card['capture']['segments'])
        validate_material(card, self.root)
        view = markdown(card)
        self.assertIn('读者质疑', view)
        self.assertIn('ANN00002', view)
        self.assertNotIn('> 乙丙', view)
        second.update(text='丙丁', display_text='丁', join_previous=True,
                      cleanup_note='前条已包含丙')
        card['capture']['text_original'] = reading_text(card['capture']['segments'])
        self.assertEqual(card['capture']['text_original'], '甲乙丙丁')
        validate_material(card, self.root)

    def test_dedup_cannot_drop_unique_text_or_invent_text(self):
        from materials import reading_text
        for display in ['', '不存在的新句子']:
            card = self.grouped_card()
            card['capture']['segments'][1].update(display_text=display, cleanup_note='声称是重复')
            card['capture']['text_original'] = reading_text(card['capture']['segments'])
            with self.assertRaises(ValueError):
                validate_material(card, self.root)

    def test_context_only_step_requires_real_context_reference(self):
        card = self.grouped_card()
        card['capture']['context_excerpts'] = [
            {'id': 'CTX-TEST', 'page_index': 0, 'text': '真实上下文测试', 'method': 'pdf_text'}]
        step = card['analysis']['argument_structure'][0]
        step.update(annotation_keys=[], context_keys=['CTX-TEST'])
        validate_material(card, self.root)
        step['context_keys'] = ['MISSING']
        with self.assertRaises(ValueError):
            validate_material(card, self.root)

    def test_layout_cleanup_preserves_gaps_between_excerpts(self):
        from materials import compact_layout
        self.assertEqual(compact_layout('生活在水 里\n\n思想内在于现实'),
                         '生活在水里\n\n思想内在于现实')

    def test_simple_reviewed_card_does_not_require_classification_or_links(self):
        card = normalize({'raw_text': '测试素材原文', 'source_title': '测试来源', 'location': '第1页'})
        card.update(title='测试标题', summary='已整理的一句话概括', status='reviewed',
                    reviewed_by='测试读者', reviewed_at='2026-09-09')
        validate_material(card, self.root)
        self.assertIsNone(card['analysis']['primary_theme'])
        self.assertEqual(card['analysis']['argument_uses'], [])
        self.assertEqual(card['analysis']['related_prompts'], [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
