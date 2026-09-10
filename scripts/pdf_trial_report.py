#!/usr/bin/env python3
"""Build an optional, self-contained snapshot of the Liu Qing four-color trial.
Canonical cards remain in materials; importing more highlights does not run this.
"""
import base64
import html
import json
from pathlib import Path

from materials import ROOT, encoded, read

LABELS = {"yellow": "黄色 · 观点", "blue": "蓝色 · 案例", "green": "绿色 · 概念", "red": "红色 · 表达"}
ORDER = ["yellow", "blue", "green", "red"]


def esc(value):
    return html.escape(str(value))


def main():
    folder = ROOT / "试运行/刘擎四色测试"
    manifest = read(folder / "本次检查.json")
    cards = [read(ROOT / "materials" / f"{mid}.json") for mid in manifest['material_ids']]
    cards.sort(key=lambda m: ORDER.index(m['capture']['highlight']['color_normalized']))
    themes = {t['id']: t['name'] for t in read(ROOT / 'taxonomy/themes.json')['themes']}
    prompts = {p['id']: p for p in read(ROOT / 'taxonomy/prompts.json')['prompts']}
    sections = []
    for m in cards:
        capture, analysis = m['capture'], m['analysis']
        color = capture['highlight']['color_normalized']
        raw = read(ROOT / 'inbox/captures' / (m['parent_capture_id']+'.json'))
        tags = [themes[t] for t in [analysis['primary_theme'], *analysis['secondary_themes']] if t]
        uses = ''.join(f"<div class='use'><b>{esc(u['claim'])}</b><p>{esc(u['reasoning'])}</p><p class='small'>成立条件：{esc('；'.join(u['conditions']))}</p><p class='small'>不能推出：{esc('；'.join(u['limits']))}</p></div>" for u in analysis['argument_uses'])
        links = ''.join(f"<li><b>{esc(prompts[p['id']]['title'])}</b> · {esc(p['id'])}<br>{esc(p['reason'])}</li>" for p in analysis['related_prompts'])
        download = 'data:application/json;base64,' + base64.b64encode(encoded(m).encode()).decode()
        sections.append(f"""<article class='card {color}'>
<div class='label'>{LABELS[color]} <span>{esc(capture['highlight']['color_raw'])}</span></div>
<h2>{'暂不归类 · 保留阅读定位' if not tags else esc(' / '.join(tags))}</h2>
<p class='meta'>PDF 第 9 页 · {esc(raw['annotation']['info']['id'])} · 草稿，待你确认</p>
<h3>你实际划下的文字</h3><blockquote>{esc(capture['text_original'])}</blockquote>
<p class='small'>按原选区保留结尾与换行；颜色只记录本次测试输入。</p>
<details><summary>查看相邻原文，检查是否读反或断章取义</summary>
<h4>高亮之前（未选中）</h4><pre>{esc(capture['context_before'] or '')}</pre>
<h4>高亮之后（未选中）</h4><pre>{esc(capture['context_after'] or '')}</pre></details>
<h3>Codex 的理解</h3><p>{esc(analysis['paraphrase'])}</p><p class='small'>{esc(analysis['classification_reason'])}</p>
<h3>可能的论证用法</h3>{uses or '<p>当前没有足够完整的观点，不强行生成论证或关联题。</p>'}
{('<h3>关联作文题</h3><ul>'+links+'</ul>') if links else ''}
<details><summary>待讨论的问题与出处记录</summary><ul>{''.join('<li>'+esc(q)+'</li>' for q in analysis['open_questions'])}</ul>
<p class='small'>素材 ID：{esc(m['id'])}<br>原文核对：matched（Codex 对照本页图像与文字层）<br>事实核验：未完成，不把作者的概述当作已验证事实。<br>人工认可：未确认。</p></details>
<a class='download' download='{esc(m['id'])}.json' href='{download}'>下载这张素材卡 JSON</a></article>""")
    image_data = base64.b64encode((folder / '高亮原页.png').read_bytes()).decode()
    page = """<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>刘擎 · 四色标注实测</title>
<style>
*{box-sizing:border-box}body{margin:0;background:#f5f3ed;color:#243d35;font:16px/1.8 -apple-system,BlinkMacSystemFont,'PingFang SC',sans-serif}main,header,footer{max-width:920px;margin:auto;padding:26px}header{padding-top:42px}.eyebrow{font-size:12px;letter-spacing:.12em;color:#48715d}h1{font-family:'Songti SC',serif;font-size:36px;line-height:1.4;margin:12px 0}h2{font-size:23px;margin:12px 0}h3{font-size:16px;margin:24px 0 8px}h4{font-size:14px}p{margin:10px 0}.summary{background:#e4eee5;border-radius:12px;padding:20px}.stats{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin:25px 0}.stat{border-top:2px solid #b4c8b9;padding-top:10px}.stat b{display:block;font-size:29px;font-weight:500}.stat span{font-size:12px;color:#64736c}.card{background:#fffefa;border:1px solid #d9dfd4;border-top:5px solid var(--color);padding:24px;border-radius:12px;margin-bottom:22px}.yellow{--color:#ffd400}.blue{--color:#2ea8e5}.green{--color:#5fb236}.red{--color:#ff6666}.label{font-size:13px;font-weight:700}.label span{color:#6a786f;font-weight:400;margin-left:12px}.meta,.small{font-size:13px;color:#68746d}blockquote{margin:12px 0;padding:16px;background:#f3f3ed;border-left:3px solid var(--color);white-space:pre-wrap;font-family:'Songti SC',serif;font-size:19px}details{border-top:1px solid #e1e5dc;margin-top:18px;padding-top:12px}summary{cursor:pointer;font-size:14px;color:#315e4b}pre{white-space:pre-wrap;overflow-wrap:anywhere;font:14px/1.8 inherit;background:#f3f3ed;padding:12px}.use{padding:15px;border:1px solid #e1e5dc;border-radius:8px}.download{display:inline-block;margin-top:15px;font-size:13px;color:#315e4b}li{margin:10px 0}ul,ol{padding-left:21px}img{width:100%;height:auto;background:white}footer{font-size:12px;color:#6a786f;border-top:1px solid #d9dfd4}.steps{padding:20px;background:#fffefa;border:1px solid #d9dfd4;border-radius:12px}.code{font-size:12px;overflow-wrap:anywhere}a{color:#315e4b}@media(max-width:600px){header,main,footer{padding:20px}h1{font-size:29px}.card{padding:18px}.stat b{font-size:25px}.stat span{font-size:11px}blockquote{font-size:17px}}
</style></head><body><header><div class="eyebrow">ESSAYLAB / 真实 PDF 批注测试 · 2026-09-08</div>
<h1>四种颜色，已经变成<br>能回找原文的摘录。</h1><p>《刘擎西方现代思想讲义》中的四条 Zotero 高亮，已从 PDF 批注直接提取，并形成独立素材草稿。</p>
<div class="stats"><div class="stat"><b>4 / 4</b><span>批注已提取</span></div><div class="stat"><b>3</b><span>跨行高亮</span></div><div class="stat"><b>9</b><span>所在 PDF 页</span></div><div class="stat"><b>0</b><span>已获人工认可</span></div></div>
<div class="summary"><b>这次验证了采集链路，也暴露了上下文问题。</b><p>四条文字均按实际高亮保留，未使用 OCR。由于本次只是颜色测试，多个选区停在半句；其中蓝色的关键否定“不再抱有”在高亮之外。下方将原选区、相邻原文与 AI 理解分别列出。</p></div></header><main>
""" + ''.join(sections) + f"""<section class='steps'><h2>这次实际完成了什么</h2><ul>
<li>扫描 PDF 共 284 页，发现 4 条 Highlight；四色各 1 条，均在 PDF 第 9 页。批注中没有评论。</li>
<li>按每行 QuadPoints 提取字符，避免外包矩形混入未选文字。保留批注 ID、原始 RGB、坐标、字符与上下文。</li>
<li>提取没有改写原 PDF。全部草稿仍是独立 JSON，Markdown 是阅读副本。</li>
<li>黄色暂不归类；另外三条提出依赖上下文的用法。没有把四色测试当成四条成熟写作素材。</li>
<li>已通过 10 项导入与回归测试，以及本文件的重复导入、原文一致性、交叉引用和原文件哈希核对。</li></ul>
<details><summary>查看这一页的原始高亮图像</summary><img alt='PDF第9页，黄蓝绿红四种实际高亮；与每张卡的原选区对应' src='data:image/png;base64,{image_data}'></details>
<h3>以后怎样给 Codex</h3><p>Zotero 阅读后导出“包含批注的 PDF”，放进工作区即可。本次已验证这一导出路线；尚未连接 Zotero 数据库、账号或自动同步。</p>
<p class='small'>Zotero 的原生批注默认存于其数据库；直接复制附件文件不一定包含它们。参见 <a href='https://www.zotero.org/support/kb/annotations_in_database'>Zotero 官方的批注存储与导出说明</a>。</p>
<p>下一次可以用几条完整观点或案例继续试，尤其把否定词、转折和必要的对象一起划入。再判断分类和论证是否对你有帮助。</p>
<p class='code'>原始 PDF SHA-256：{esc(manifest['source_sha256'])}</p></section></main>
<footer>本页是此次测试的单文件快照，可离线查看。正式数据保存在 materials 与 inbox/captures，后续添加素材不依赖重建此报告。书名与作者依据用户说明及文件名，版次与印刷页码未知。</footer></body></html>"""
    (folder / '四色测试报告.html').write_text(page, encoding='utf-8')
    print('已生成独立测试报告快照：', folder / '四色测试报告.html')


if __name__ == '__main__':
    main()
