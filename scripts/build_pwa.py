#!/usr/bin/env python3
"""Build the deployable PWA from the existing template and canonical JSON."""
import argparse
import hashlib
import json
import shutil
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def digest(data):
    return hashlib.sha256(data).hexdigest()


def build(output):
    from build_library import main as build_library
    from export_latest_html import main as export_latest
    build_library()
    export_latest()
    payload = {}
    def include(path, target=None):
        payload[target or path] = (ROOT / path).read_bytes()
    for path in ['taxonomy/prompts.json', 'taxonomy/themes.json', 'materials/index.json', 'materials/groups.json']:
        include(path)
    index = json.loads(payload['materials/index.json'])
    for filename in index['material_files']:
        if Path(filename).name != filename or not filename.endswith('.json'):
            raise ValueError('Invalid material filename')
        include('materials/' + filename)
    extensions = {'.jpg', '.jpeg', '.png', '.svg', '.webp', '.avif', '.ico', '.woff', '.woff2', '.ttf', '.otf', '.css', '.js'}
    for path in sorted((ROOT / 'assets').rglob('*')):
        if path.is_file() and path.suffix.lower() in extensions:
            include(path.relative_to(ROOT).as_posix())
    for path in sorted((ROOT / 'pwa/icons').iterdir()):
        if path.is_file():
            include(path.relative_to(ROOT).as_posix(), 'icons/' + path.name)
    include('pwa/register.js', 'register.js')
    template = (ROOT / 'templates/preview.html').read_text(encoding='utf-8')
    worker = (ROOT / 'pwa/sw-template.js').read_text(encoding='utf-8')
    manifest_source = (ROOT / 'pwa/manifest.webmanifest').read_text(encoding='utf-8')
    offline = (ROOT / 'pwa/offline.html').read_bytes()
    inputs = {name: digest(data) for name, data in payload.items()}
    inputs.update(template=digest(template.encode()), worker=digest(worker.encode()),
                  manifest=digest(manifest_source.encode()), offline=digest(offline),
                  builder=digest(Path(__file__).read_bytes()))
    release = digest(json.dumps(inputs, sort_keys=True).encode())[:20]
    prefix = f'releases/{release}/'
    files = {prefix + name: data for name, data in payload.items()}
    html = template.replace('../', './' + prefix)
    head = f'''<meta name="essaylab-release" content="{release}">
<meta name="theme-color" content="#f6f4ee">
<meta name="mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-title" content="EssayLab">
<meta name="apple-mobile-web-app-status-bar-style" content="default">
<link rel="manifest" href="./manifest.webmanifest">
<link rel="icon" type="image/png" sizes="32x32" href="./{prefix}icons/icon-32.png">
<link rel="apple-touch-icon" sizes="180x180" href="./{prefix}icons/apple-touch-icon.png">
<script defer src="./{prefix}register.js"></script>
'''
    html = html.replace('</head>', head + '</head>')
    files['index.html'] = html.encode('utf-8')
    manifest = json.loads(manifest_source)
    for icon in manifest['icons']:
        icon['src'] = './' + prefix + icon['src']
    files['manifest.webmanifest'] = (json.dumps(manifest, ensure_ascii=False, indent=2) + '\n').encode()
    files['offline.html'] = offline
    inventory = [{'url': name, 'sha256': digest(data)} for name, data in sorted(files.items())]
    files['sw.js'] = worker.replace('__RELEASE__', json.dumps(release)).replace('__FILES__', json.dumps(inventory, ensure_ascii=False)).encode()
    files['release.json'] = (json.dumps({'release': release, 'files': inventory}, ensure_ascii=False, indent=2) + '\n').encode()
    # Supported by Netlify/Cloudflare Pages. Other hosts must set equivalent headers.
    files['_headers'] = b'/*\n  Cache-Control: no-cache\n/sw.js\n  Cache-Control: no-store\n/releases/*\n  Cache-Control: public, max-age=31536000, immutable\n'
    output = output.resolve()
    if output == ROOT or ROOT.is_relative_to(output) or output.exists() and not (output / 'release.json').is_file():
        raise ValueError('Output must be a new directory or an existing generated PWA directory')
    output.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix='.essaylab-pwa-', dir=output.parent))
    try:
        for name, data in files.items():
            destination = staging / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(data)
        if output.exists():
            shutil.rmtree(output)
        staging.rename(output)
    finally:
        if staging.exists():
            shutil.rmtree(staging)
    print(f'PWA {release}: {len(inventory)} cached files, {sum(len(data) for name, data in files.items()) / 1024 / 1024:.2f} MiB → {output}')
    return release


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT / 'dist')
    build(parser.parse_args().output)
