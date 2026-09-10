// Run with jsdom on NODE_PATH. No browser navigation or network requests are used.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { JSDOM, VirtualConsole } = require('jsdom');
const root = path.resolve(__dirname, '..');
const read = p => JSON.parse(fs.readFileSync(path.join(root, p), 'utf8'));
const records = read('materials/index.json').material_files.map(f => read('materials/' + f));
const groups = read('materials/groups.json').material_groups;
const grouped = new Set(groups.flatMap(g=>g.material_ids));
const rootCount = records.filter(m=>m.collection_role!=='technical_test'&&!grouped.has(m.id)).length+groups.length;
const documents = [read('taxonomy/prompts.json'), read('taxonomy/themes.json'), {materials: records,material_groups:groups}];

async function page(filename, hosted = false, failMaterials = false) {
  const errors = [], requests = [];
  const virtualConsole = new VirtualConsole();
  virtualConsole.on('jsdomError', error => errors.push(error.message));
  const dom = new JSDOM(fs.readFileSync(path.join(root, filename), 'utf8'), {
    url: hosted ? 'http://example.invalid/viewer/' : 'file:///essaylab.html',
    runScripts: 'dangerously', virtualConsole,
    beforeParse(window) {
      window.scrollTo = () => {};
      window.fetch = async url => {
        requests.push(url);
        if (failMaterials && url.includes('/materials/')) return {ok:false};
        assert.ok(/^\.\.\/(taxonomy|materials)\/[A-Za-z0-9.-]+\.json$/.test(url));
        return {ok:true,json:async()=>read(url.slice(3))};
      };
    }
  });
  for (let i = 0; i < 10 && dom.window.document.getElementById('library-main').hidden; i++) {
    await new Promise(resolve => setTimeout(resolve, 0));
  }
  assert.deepEqual(errors, [], '页面脚本不应报错');
  return {dom, window:dom.window, document:dom.window.document, requests};
}

function input(p, id, value, event = 'input') {
  const element = p.document.getElementById(id);
  if (typeof value === 'boolean') element.checked = value;
  else element.value = value;
  element.dispatchEvent(new p.window.Event(event, {bubbles:true}));
}

async function run() {
  const p = await page('EssayLab-最新版.html');
  const $ = id => p.document.getElementById(id);
  assert.equal($('materials').hidden, false, '首次打开进入素材库');
  $('tab-prompts').click();
  assert.equal($('prompts').hidden, false);
  assert.equal(p.document.querySelectorAll('.question').length, 122);
  assert.equal(p.requests.length, 0, '离线快照不应请求其他数据文件');
  assert.equal(p.document.querySelectorAll('textarea').length, 0, '简单浏览版不引入写作步骤');
  input(p, 'year-filter', '2026', 'change');
  input(p, 'type-filter', 'district_mock', 'change');
  const expected = documents[0].prompts.filter(x=>x.year_label_normalized===2026 &&
    (x.record_type==='district_mock'||x.additional_sources?.some(s=>s.record_type==='district_mock')));
  assert.equal(p.document.querySelectorAll('.question').length, expected.length);
  input(p, 'year-filter', '', 'change');input(p, 'type-filter', '', 'change');
  input(p, 'search', 'PR-0045');
  assert.equal(p.document.querySelectorAll('.question').length, 1);
  assert.equal(p.document.querySelector('.question .original').textContent,
    documents[0].prompts.find(x=>x.id==='PR-0045').text_original);
  input(p, 'search', '不存在的关键词abcdef');
  assert.match($('question-list').textContent, /没有找到匹配/);
  $('tab-materials').click();
  assert.equal($('materials').hidden, false);
  assert.equal(p.document.querySelectorAll('#material-list .material-card').length, rootCount);
  input(p, 'show-tests', true, 'change');
  assert.equal(p.document.querySelectorAll('#material-list .material-card').length, rootCount+records.filter(m=>m.collection_role==='technical_test').length);
  input(p, 'show-tests', false, 'change');
  assert.equal($('material-filter-panel').hidden, true);
  $('toggle-material-filters').click();
  assert.equal($('toggle-material-filters').getAttribute('aria-expanded'), 'true');
  const book = records.find(m=>m.collection_role!=='technical_test').capture.source.title;
  input(p, 'book-filter', book, 'change');
  $('toggle-material-filters').click();
  assert.ok($('active-material-filter').textContent.includes(book), '折叠后仍显示生效来源');
  $('clear-material-filter').click();
  assert.equal($('book-filter').value, '');
  assert.equal(p.document.querySelectorAll('#material-list .material-card').length, rootCount);
  input(p, 'material-search', '罚款');
  const hit=$('material-list').querySelector('[data-hit]');
  assert.ok(hit, '搜索直接提供组内命中的素材');
  hit.click();
  assert.ok($('material-detail').textContent.includes('罚款'));
  assert.equal($('material-group').hidden, true);
  $('back-materials').click();
  assert.equal(p.document.activeElement.dataset.hit, hit.dataset.hit);
  assert.equal($('material-search').value, '罚款');
  assert.equal($('material-list').querySelectorAll('[data-group]').length, 1);
  assert.equal($('material-list').querySelectorAll('[data-material]').length, 0);
  $('material-list').querySelector('[data-group]').click();
  assert.match($('group-title').textContent, /铁笼/);
  assert.equal($('material-group').querySelectorAll('[data-material]').length, 4);
  assert.equal($('material-browse').hidden, true);
  const second=$('material-group').querySelectorAll('[data-material]')[1];
  second.click();
  assert.match($('reader-title').textContent, /第一弊端/);
  assert.ok($('material-detail').textContent.includes('罚款'));
  $('back-materials').click();
  assert.equal($('material-group').hidden, false);
  assert.equal(p.document.activeElement.dataset.material,second.dataset.material);
  $('back-group').click();
  assert.equal($('material-browse').hidden, false);
  assert.equal($('material-search').value,'罚款');
  assert.equal(p.document.activeElement.dataset.group,'GRP-iron-cage');
  input(p, 'material-search', '名牌');
  assert.equal(p.document.querySelectorAll('#material-list .material-card').length, 1);
  $('material-list').querySelector('[data-material]').click();
  assert.equal($('material-browse').hidden, true);
  assert.match($('reader-title').textContent, /利益如何被定义/);
  assert.ok(![...$('material-detail').querySelectorAll('details')].some(x=>x.open));
  assert.ok($('material-detail').querySelector('.original').textContent.includes('“性价比最优”原则，“名牌消费”'));
  assert.ok(!$('material-detail').textContent.includes('PR-0045'), '关联题不进入默认素材详情');
  $('back-materials').click();
  assert.equal($('material-search').value, '名牌');
  assert.equal(p.document.querySelectorAll('#material-list .material-card').length, 1);
  $('tab-prompts').click();
  $('tab-prompts').dispatchEvent(new p.window.KeyboardEvent('keydown', {key:'ArrowRight',bubbles:true}));
  assert.equal($('more').hidden, false);
  assert.equal($('tab-more').getAttribute('aria-selected'), 'true');

  // A hidden duplicate highlight's comment must remain visible, and data is text, not HTML.
  const fixture = JSON.parse(JSON.stringify(documents));
  const material = fixture[2].materials.find(m=>m.id==='MAT-ZOTERO-6LF72SCC-001');
  material.title = '<img src=x onerror="window.injected=1">';
  const duplicate = material.capture.segments.find(s=>s.display_text==='');
  duplicate.comment = '重复选区也有我的备注';
  input(p, 'material-search', '');
  p.window.mount(p.window.payloadFrom(fixture));
  let opens=0;p.window.scrollTo=()=>opens++;
  $('material-list').querySelector('[data-material]').click();
  assert.equal(opens, 1, '重新载入后不应重复注册点击事件');
  assert.ok($('material-detail').textContent.includes('重复选区也有我的备注'));
  assert.equal($('material-detail').querySelector('img'), null);
  assert.equal(p.window.injected, undefined);
  p.dom.window.close();

  const live = await page('viewer/index.html', true);
  assert.equal(live.document.querySelectorAll('#material-list .material-card').length, rootCount);
  live.document.getElementById('tab-prompts').click();
  live.window.mount(live.window.payloadFrom(documents));
  assert.equal(live.document.getElementById('prompts').hidden,false,'重新载入记住上次栏目');
  assert.ok(live.requests.includes('../materials/index.json'));
  assert.equal(live.requests.filter(x=>/\/MAT-/.test(x)).length, records.length);
  live.dom.window.close();

  const fallback = await page('viewer/index.html', true, true);
  assert.equal(fallback.document.querySelectorAll('.question').length, 122);
  assert.match(fallback.document.getElementById('material-load-note').textContent, /素材载入未完成/);
  fallback.dom.window.close();

  const manual = await page('viewer/index.html');
  assert.equal(manual.document.getElementById('library-main').hidden, true);
  manual.window.mount(manual.window.payloadFrom(documents));
  assert.equal(manual.document.querySelectorAll('#material-list .material-card').length, rootCount);
  assert.throws(()=>manual.window.payloadFrom([...documents,records[0]]), /重复 ID/);
  const bad=JSON.parse(JSON.stringify(documents));bad[2].material_groups[0].material_ids.push('MAT-MISSING');
  assert.throws(()=>manual.window.payloadFrom(bad), /成员无效/);
  manual.dom.window.close();
  console.log('通过：题面保真、年份/来源/搜索、阅读素材与技术测试筛选、阅读与返回、键盘导航、备注保留、HTML转义、离线零请求、独立文件加载与缺失提示。');
}
run().catch(error=>{console.error(error);process.exitCode=1;});
