#!/usr/bin/env python3
"""Finish a local editing batch: render, build PWA, validate, verify its data."""
import json

from materials import ROOT, render_all
from build_pwa import build
from validate_library import main as validate_library


def main():
    render_all(ROOT)
    release = build(ROOT / 'dist')
    validate_library()
    output = ROOT / 'dist' / 'releases' / release
    index = json.loads((ROOT / 'materials/index.json').read_text())
    files = ['materials/index.json', 'materials/groups.json', 'taxonomy/prompts.json',
             'taxonomy/themes.json', *['materials/' + f for f in index['material_files']]]
    for filename in files:
        if (ROOT / filename).read_bytes() != (output / filename).read_bytes():
            raise ValueError(f'PWA data differs from source: {filename}')
    groups = json.loads((ROOT / 'materials/groups.json').read_text())['material_groups']
    print(f'本地更新完成：{len(index["material_files"])} 张素材，{len(groups)} 个素材群；PWA 版本 {release}。')
    print(f'单文件：{ROOT / "EssayLab-最新版.html"}')
    print(f'PWA：{ROOT / "dist"}；数据已逐文件核对。线上状态须另查 GitHub Actions 与正式网址。')


if __name__ == '__main__':
    main()
