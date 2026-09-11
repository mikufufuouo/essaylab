# Material 阅读卡模板说明

v0.2 的素材 JSON 是唯一编辑版本，Markdown 由 `scripts/materials.py render` 生成。请不要同时手填两份完整内容。

录入请使用 [手工摘录模板](手工摘录.md)，完整字段参考 [Material Schema](material.schema.json)，生成结果参考 [示范阅读卡](../examples/MAT-DEMO-001.md)。

阅读卡包含原文与来源、读者留言、AI 转述和分类、具体论证用法、关联题、三项核验与确认状态。可直接把你的修改意见告诉 Codex，由它更新 JSON 并重建阅读卡。

2026-09-09：Zotero 原生批注优先直接只读采集。多条相关批注可组合为一张素材，保留各条颜色、comment 与位置；颜色不自动决定类型。组合流程见 Zotero批注整理（本地文件 `../Zotero批注整理.md`）。阅读卡由 JSON 生成，包含可回溯到具体批注的原文论证关系。
