// Real-browser tests with an isolated profile and an in-memory static deployment.
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto'),http=require('node:http');
const {chromium}=require('playwright');
const root=path.resolve(__dirname,'..'),dist=path.join(root,'dist');
const expectedGroupCount=JSON.parse(fs.readFileSync(path.join(root,'materials','groups.json'),'utf8')).material_groups.length;
const original=JSON.parse(fs.readFileSync(path.join(dist,'release.json')));
const workerTemplate=fs.readFileSync(path.join(root,'pwa/sw-template.js'),'utf8');
const sha=bytes=>crypto.createHash('sha256').update(bytes).digest('hex');
function fixture(label){
  const id=sha(label).slice(0,20),files=new Map();
  for(const entry of original.files){
    let data=fs.readFileSync(path.join(dist,entry.url));
    if(/\.(html|webmanifest|js)$/.test(entry.url))data=Buffer.from(data.toString().replaceAll(original.release,id));
    if(entry.url==='index.html')data=Buffer.from(data.toString().replace('<html lang=',`<html data-build="${label}" lang=`));
    files.set(entry.url.replaceAll(original.release,id),data);
  }
  const inventory=[...files].map(([url,data])=>({url,sha256:sha(data)}));
  files.set('sw.js',Buffer.from(workerTemplate.replace('__RELEASE__',JSON.stringify(id)).replace('__FILES__',JSON.stringify(inventory))));
  return {id,files,inventory};
}
const versions=Object.fromEntries(['A','B','C','D','E'].map(label=>[label,fixture(label)]));
let current=versions.A,failure=null,browser;
const types={'.html':'text/html; charset=utf-8','.js':'text/javascript','.json':'application/json','.webmanifest':'application/manifest+json','.png':'image/png','.jpg':'image/jpeg','.svg':'image/svg+xml'};
const server=http.createServer((req,res)=>{
  const url=new URL(req.url,'http://localhost');
  const name=decodeURIComponent(url.pathname).replace(/^\/lab\//,'')||'index.html';
  res.setHeader('Cache-Control','no-store');
  if(failure&&name.endsWith(failure.suffix)){res.writeHead(failure.status,{'Content-Type':'image/jpeg'});res.end('broken release');return;}
  const bytes=current.files.get(name);
  res.writeHead(bytes?200:404,{'Content-Type':types[path.extname(name)]||'application/octet-stream'});res.end(bytes||'Not found');
});
(async()=>{
  await new Promise(r=>server.listen(0,'127.0.0.1',r));
  const base=`http://127.0.0.1:${server.address().port}/lab/`;
  browser=await chromium.launch({headless:true,...(process.env.PWA_CHROME_CHANNEL?{channel:process.env.PWA_CHROME_CHANNEL}:{})});
  const context=await browser.newContext(),page=await context.newPage(),errors=[];
  context.on('page',p=>p.on('pageerror',e=>errors.push(e.message)));page.on('pageerror',e=>errors.push(e.message));
  const ready=p=>p.waitForFunction(()=>document.documentElement.dataset.offlineReady==='true',null,{timeout:45000});
  const active=p=>p.evaluate(async()=>{
    const key=(await caches.keys()).find(key=>key.endsWith(':clients'));
    return key?(await(await caches.open(key)).match(new URL('__essaylab_active__',location.href)))?.text():null;
  });
  const names=p=>p.evaluate(()=>caches.keys());
  async function until(predicate,label){for(let n=0;n<200;n++){if(await predicate())return;await new Promise(r=>setTimeout(r,100));}throw Error('Timed out: '+label);}
  async function update(p){await p.evaluate(async()=>{
    const reg=await navigator.serviceWorker.getRegistration();await reg.update();
    if(reg.installing)await new Promise(resolve=>{const worker=reg.installing;worker.addEventListener('statechange',()=>{if(['activated','redundant'].includes(worker.state))resolve();});});
  });}
  const announce=p=>p.evaluate(()=>navigator.serviceWorker.controller.postMessage({type:'CLIENT_RELEASE',release:document.querySelector('meta[name="essaylab-release"]').content}));
  await page.goto(base);await ready(page);await page.waitForSelector('.group-card');
  assert.equal(await page.locator('.group-card').count(),expectedGroupCount);assert.equal(await active(page),versions.A.id);
  const cached=await page.evaluate(async()=>{const name=(await caches.keys()).find(name=>name.includes(':release:'));return(await(await caches.open(name)).keys()).map(r=>r.url);});
  for(const file of versions.A.inventory)assert.ok(cached.includes(new URL(file.url,base).href),file.url+' precached');
  const manifest=await(await fetch(base+'manifest.webmanifest')).json();
  assert.equal(manifest.display,'standalone');assert.equal(manifest.start_url,'./');assert.ok(manifest.icons.some(i=>i.purpose==='maskable'&&i.sizes==='512x512'));
  const cdp=await context.newCDPSession(page);assert.deepEqual((await cdp.send('Page.getAppManifest')).errors,[]);
  await page.evaluate(()=>{window.readingSentinel='untouched';return caches.open('unrelated-app-cache');});
  await context.setOffline(true);
  const offline=await context.newPage();await offline.goto(base+'?from=homescreen');await ready(offline);await offline.waitForSelector('.group-card');
  assert.equal(await offline.locator('.group-card').count(),expectedGroupCount);
  for(const img of await offline.locator('.group-art').all())await img.scrollIntoViewIfNeeded();
  await offline.waitForFunction(()=>[...document.querySelectorAll('.group-art')].every(i=>i.complete&&i.naturalWidth===1200));
  await offline.getByRole('button',{name:'现代的铁笼',exact:true}).click();assert.equal(await offline.locator('.directory-row').count(),4);
  await offline.locator('.directory-row .entry-title').first().click();await offline.locator('#material-detail').waitFor({state:'visible'});
  assert.ok((await offline.locator('#material-detail').innerText()).length>100);
  await offline.close();await context.setOffline(false);
  console.log('PASS full precache, manifest, offline cold launch, group images and reading');

  current=versions.B;await page.getByRole('button',{name:'现代的铁笼',exact:true}).click();
  await update(page);await until(async()=>await active(page)===versions.B.id,'B activates');
  assert.equal(await page.evaluate(()=>window.readingSentinel),'untouched');assert.equal(await page.locator('html').getAttribute('data-build'),'A');assert.equal(await page.locator('#material-group').isVisible(),true);
  await context.setOffline(true);
  const next=await context.newPage();await next.goto(base);await ready(next);assert.equal(await next.locator('html').getAttribute('data-build'),'B');
  const oldArt=versions.A.inventory.find(f=>f.url.endsWith('iron-cage-v1.jpg')).url;
  assert.equal(await page.evaluate(async url=>(await fetch(url)).status,new URL(oldArt,base).href),200);
  await page.close();await announce(next);await until(async()=>!(await names(next)).some(n=>n.endsWith(versions.A.id)),'A reclaimed');
  assert.ok((await names(next)).includes('unrelated-app-cache'));await context.setOffline(false);
  console.log('PASS update without reload, next offline launch on B, pinned old assets and scope-safe cleanup');

  for(const[label,status]of[['C',500],['D',200]]){
    current=versions[label];failure={suffix:'iron-cage-v1.jpg',status};await update(next);
    assert.equal(await active(next),versions.B.id);assert.ok(!(await names(next)).some(n=>n.endsWith(current.id)));
  }
  failure=null;current=versions.E;await update(next);await until(async()=>await active(next)===versions.E.id,'E activates');
  assert.equal(await next.locator('html').getAttribute('data-build'),'B');
  console.log('PASS HTTP 500/corrupt HTTP 200 rollback, then successful update recovery');

  const damaged=versions.E.inventory.find(f=>f.url.endsWith('values-v1.jpg')).url;
  await next.evaluate(async({id,url})=>{const n=(await caches.keys()).find(n=>n.endsWith(id));await(await caches.open(n)).delete(url);},{id:versions.E.id,url:new URL(damaged,base).href});
  failure={suffix:'values-v1.jpg',status:200};
  assert.equal(await next.evaluate(async url=>(await fetch(url)).status,new URL(damaged,base).href),503);
  failure=null;
  assert.equal(await next.evaluate(async url=>(await fetch(url)).status,new URL(damaged,base).href),200);
  console.log('PASS missing asset repair rejects corrupt bytes and retries successfully');

  await context.setOffline(true);
  const stop=await context.newCDPSession(next);await stop.send('ServiceWorker.enable');await stop.send('ServiceWorker.stopAllWorkers');
  const fresh=await context.newPage();await fresh.goto(base+'unknown/deep/link');await ready(fresh);
  assert.equal(new URL(fresh.url()).pathname,'/lab/');assert.equal(await fresh.locator('html').getAttribute('data-build'),'E');assert.equal(await fresh.locator('.group-card').count(),expectedGroupCount);
  assert.equal(await fresh.evaluate(async()=>(await fetch('./releases/missing/data.json')).status),503);
  await fresh.evaluate(async()=>{const n=(await caches.keys()).find(n=>n.endsWith(document.querySelector('meta[name="essaylab-release"]').content));await(await caches.open(n)).delete(new URL('index.html',location.href));});
  await fresh.reload();assert.ok((await fresh.locator('body').innerText()).includes('本地资料暂未准备完整'));
  await context.setOffline(false);await fresh.reload();await ready(fresh);assert.equal(await fresh.locator('.group-card').count(),expectedGroupCount);
  await next.close();assert.deepEqual(errors,[]);await context.close();
  console.log('PASS worker restart, deep-link/subpath fallback, non-HTML failures and cache repair');

  const first=await browser.newContext(),firstPage=await first.newPage();current=versions.C;failure={suffix:'iron-cage-v1.jpg',status:500};
  await firstPage.goto(base);
  await firstPage.evaluate(async()=>{
    try {
      const r=await navigator.serviceWorker.register('./sw.js');
      if(r.installing)await new Promise(resolve=>{const w=r.installing;w.addEventListener('statechange',()=>{if(w.state==='redundant')resolve();});});
    } catch {}
  });
  assert.equal(await firstPage.evaluate(async()=>!!(await navigator.serviceWorker.getRegistration())?.active),false);
  assert.ok(!(await names(firstPage)).some(n=>n.includes(':release:')));
  failure=null;await firstPage.evaluate(()=>window.dispatchEvent(new Event('online')));await ready(firstPage);assert.equal(await active(firstPage),versions.C.id);
  await first.close();console.log('PASS interrupted first install and online retry');
})().catch(e=>{console.error(e);process.exitCode=1;}).finally(async()=>{await browser?.close();server.closeAllConnections();await new Promise(r=>server.close(r));});
