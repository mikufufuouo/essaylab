# EssayLab · 题目库与素材库

当前重点是 **查题与回看素材两个简单入口**。122 条题库与十个母题已经是独立数据；HTML 只负责浏览。现已接入带原生批注的 PDF；视觉颜色识别与 OCR 仍留待需要时再考虑。

## 先做什么

日常执行与模型交接统一使用 日常整理 SOP（本地文件 `日常整理SOP.md`）：沿用当前执行模型直接批量整理。包含可复制指令、正反例、批注去向核对和完成标准；尚不是自动调度流水线。

素材整理完成后默认执行 `.venv/bin/python scripts/refresh_library.py`，同时更新单文件阅读版与 `dist/` PWA，并核对构建包中的素材数据；本地通过不代表正式网站已经发布。页面设计更新和素材整理默认还须提交、推送，并等待 GitHub Actions 构建与部署成功后检查正式网址（用户明确要求暂不发布时除外）。

直接告诉 Codex 读取哪本书的 Zotero 批注即可，无需复制粘贴。保留现有颜色，按论证关系组合相关批注，保留理解所需的上下文。默认只整理标题、摘录、一句话概括、出处和已有备注；深入解读与题目匹配在需要时再做。

- Zotero 批注整理（本地文件 `Zotero批注整理.md`）：只读采集、片段保留与组合规则。
- [刘擎本次整理总览](试运行/刘擎本次整理.md)：70 条批注整理为 8 张素材，重复划线已去重。

- [手工摘录模板](templates/手工摘录.md)：无需自己写 JSON。
- Material 数据规范（本地文件 `素材数据规范.md`）：输入轻量，整理结果结构化。
- [20 条试运行记录](试运行/20条试运行.md)：检验分类是否合用、字段是否过多、是否帮助写作。
- [示范素材卡](examples/MAT-DEMO-001.md)：附件片段，仅示范格式，不计入真实阅读试运行。

**截至 2026-09-11 有 39 张 Zotero 组合草稿，另保留此前 4 条 PDF 高亮测试草稿，人工认可 0 条。** 2026-09-10 新增 173 条刘擎书籍批注经质量复核重整为 20 张素材卡，已补足必要上下文；详见[本次批次记录](试运行/刘擎-2026-09-10-6LF72SCC.md)。查看 [四色测试报告](试运行/刘擎四色测试/四色测试报告.html) 与 PDF 导入说明（本地文件 `PDF批注导入.md`）。工具测试数据仍只存在于临时目录。

## 哪些文件是数据本体

```text
EssayLab/
├── taxonomy/
│   ├── themes.json        母题定义的唯一版本
│   └── prompts.json       题目与分类的唯一版本
├── inbox/captures/        导入时保留的原始摘录记录
├── materials/
│   ├── MAT-….json         素材的唯一编辑版本，含状态
│   └── MAT-….md           从 JSON 生成的阅读副本
├── sources/              作文附件与来源核对记录
├── concepts/             概念组织留待试运行之后
├── viewer/index.html     读取独立 JSON 的题目与素材浏览器
└── 试运行/               本轮观察与反馈
```

阶段 1 以 JSON 保存可校验的素材数据，Markdown 提供阅读卡。你可以直接对 Codex 说哪里需要改，由它更新同名 JSON 并生成阅读副本，不用自己维护两份。Obsidian 的双向编辑和组织方式在试运行之后再确定。

`materials` 同时容纳未整理、草稿和已认可的卡片，使用 `status` 区分。`inbox/captures` 保留录入原貌；分析变化不会改写它。素材 ID 不因标题或主题变化而改变。

## 浏览器如何使用

**可安装的 PWA**：运行 `.venv/bin/python scripts/build_pwa.py`，将生成的 `dist/` 发布到 HTTPS 静态站点即可安装。首次联网完整缓存后可断网启动；首页立即显示本地版本，后台完整校验新版后自动更新，下次打开生效，不刷新正在阅读的页面。页面 UI 和原有生成流程保持一致。构建、安装、缓存淘汰及自动发布说明见 [PWA 使用与发布](pwa/README.md)。

直接打开 EssayLab-最新版.html（本地文件 `EssayLab-最新版.html`）：题库与素材已嵌入，离线也能查阅。

- **题目库**：直接显示原题，按年份、来源和关键词查找；已有主题筛选按需展开。
- **素材库**：首次打开默认进入，并记住上次所在栏目。首页采用暖纸底色与开放式双列条目，窄屏自动单列；只展示标题、概括和必要元信息，素材群内部为有序的单列目录。来源筛选按需展开，已生效的条件始终可见；早期标注测试开关移至“索引与说明 → 数据与文件”。一级显示 6 个素材群与 10 条独立素材。铁笼、祛魅等完整概念点击后进入二级总览，再选择各部分阅读；合计保留 28 张阅读素材。搜索覆盖组内原文与补充上下文，结果显示所属群。早期四张颜色测试可通过开关查看。上下文与已有解读按需展开。
- **索引与说明**：保留已有主题索引、来源说明及数据下载。不以题目关联或写作实验作为日常使用步骤。

需要读取最新独立文件时，在 EssayLab 目录运行：

```sh
python3 -m http.server 8765 --bind 127.0.0.1
```

打开本机地址 `http://127.0.0.1:8765/viewer/`。页面通过 `materials/index.json` 找到各张素材，并读取原文件；索引保存文件名与派生的素材群定义，不另存素材正文。修改已有素材后刷新即可；新增素材或修改 `materials/groups.json` 时运行 `scripts/materials.py render` 更新索引。无需重建 HTML。

直接打开 viewer 文件时也可选择题库、主题以及素材 JSON；通常使用最新版单文件更方便。历史 [v0.1 地图](思想素材地图.html) 只作留档。

修改页面模板后运行：

```sh
.venv/bin/python scripts/build_library.py
.venv/bin/python scripts/export_latest_html.py
.venv/bin/python scripts/validate_library.py
```

这些步骤更新浏览器与离线快照。题目和素材 JSON 仍是唯一编辑版本，页面操作不写回 Zotero 或原文件。

## Codex 如何处理一批摘录

Zotero 批注先按 组合流程（本地文件 `Zotero批注整理.md`） 保存和整理，不逐条生成卡。以下命令用于备用的手工输入。

先把真实摘录按 [输入规范](templates/manual-batch.schema.json) 存成批次 JSON，再执行：

```sh
python3 scripts/materials.py import inbox/本批摘录.json
```

脚本逐条保留原文、生成稳定 ID 和默认空字段，创建 `inbox` 状态的素材。**它不自动理解或分类文字**，也不会把转录或事实核验设成完成。随后 Codex 依 整理指令（本地文件 `Codex整理指令.md`） 阅读真实材料、写成 `draft`，再生成阅读卡：

```sh
python3 scripts/materials.py validate
python3 scripts/materials.py render
```

只有得到你明确的内容认可，才记录为 `reviewed`。这表示认可整理结果，不表示赞同作者观点，也不表示材料中的事实已经查证。

导入会跳过完全相同的录入记录，并保留已修订卡片；相同原文来自不同出处、或带着不同留言时保留为不同记录。重复判定目前只覆盖精确相同的输入，不做模糊合并。整批数据校验通过后才开始写入，普通写入失败会撤回本次新建文件；本版没有并发写入与断电恢复功能。

## 修改题库与检查

直接修改 `taxonomy/prompts.json` 或 `taxonomy/themes.json`，ID 保持不变。题目索引根据当前归类派生，避免维护两份关联列表。需要更新 Markdown 题库或浏览器模板时执行：

```sh
python3 scripts/build_library.py
python3 scripts/validate_library.py
```

`build_library.py` 只生成阅读视图，不再从旧配置覆盖你修改后的 JSON。v0.1 的生成输入、脚本和说明已保存在 `sources/legacy-v0.1/`，只供追溯。检验工具需要 Python 的 `jsonschema`，依赖见 `requirements.txt`。

题目原文仍只据所附合订本，未经官方来源核验。阶段 1 没有增加或重新分类题目。

## 已纳入补充题目

补充文件的 21 条记录新增 20 题、合并 1 条重复来源，总计 121 题。原有 ID 保持不变；近似题不自动合并，自招题和作文投稿单列。见 [纳入与去重明细](sources/补充题目纳入说明.md)。

## 页面交互检查

`scripts/test_viewer.cjs` 使用 jsdom 在本地检查搜索、筛选、原文保真、素材展开/返回、离线与独立数据加载，不请求外部站点。需要运行时可把 jsdom 安装在临时目录，不改变项目依赖：

```sh
npm install --prefix /tmp/essaylab-dom-check --no-audit --no-fund jsdom
NODE_PATH=/tmp/essaylab-dom-check/node_modules node scripts/test_viewer.cjs
```
