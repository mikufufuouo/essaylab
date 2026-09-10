# EssayLab PWA

PWA 是当前页面的另一种生成产物，不是另一套 UI。唯一页面模板仍是 `templates/preview.html`，题目和素材仍来自现有 JSON。`viewer/` 保留直接读取本地编辑数据的行为；`EssayLab-最新版.html` 保留单文件离线导出。只有发布到站点的 `dist/` 注册 Service Worker，避免本地编辑时被发布缓存干扰。

## 构建与本地预览

在 EssayLab 目录执行：

```sh
.venv/bin/python scripts/build_pwa.py
python3 -m http.server 8767 --bind 127.0.0.1 --directory dist
```

打开 `http://127.0.0.1:8767/`。默认生成 `dist/`，也可传 `--output` 指定新的生成目录。命令会先运行现有 `build_library.py` 与 `export_latest_html.py`，然后构建 PWA。相同输入产生相同版本，不需要人工递增版本号。

首次联网访问自动下载完整站点；首次缓存结束后即可离线重开。下载耗时取决于网络速度，不能在首个页面刚出现时立即断网就保证安装已完成。为了保留 UI，没有弹窗、安装按钮或刷新提示。调试时可在控制台查看 `document.documentElement.dataset.offlineReady === 'true'`；页面也会发出 `essaylab:offline-ready` 事件。

## 安装

- macOS / Windows：Chrome、Edge 使用地址栏安装入口；macOS Sonoma 14 或更新系统也可用 Safari 的“文件 → 添加到程序坞”。
- iPhone / iPad：Safari 的分享菜单 → 添加到主屏幕；系统提供“作为网页 App 打开”选项时保持开启。
- Android：Chrome 菜单或地址栏提供“安装应用 / 添加到主屏幕”。

安装菜单由浏览器控制，页面不会要求安装。首次访问必须使用 HTTPS（开发时 localhost / 127.0.0.1 例外）；`file://` 不能注册 Service Worker。手机访问局域网普通 HTTP 不等同于本机 localhost，正式设备测试请使用 HTTPS。

图标是与现有纸色、深绿相匹配的 E 字形：源文件 `icons/icon.svg`，附 32/192/512 PNG、180 Apple touch icon 和 512 maskable icon。主图形位于 maskable 安全区域内；所有版本均为本地文件。

## 缓存与更新

| 对象 | 策略 |
| --- | --- |
| 首页 HTML（含现有 CSS、JS） | 本地立即响应，同时后台检查新版；整版 stale-while-revalidate |
| 题库、主题、素材索引、全部素材 JSON、素材群配图 | 构建为 `releases/<内容版本>/…` 的不可变 URL，首次访问全部预缓存，之后直接读缓存 |
| manifest、离线 fallback | 和同版首页一起缓存、更新 |
| 注册脚本、图标、未来 assets 内的字体/CSS/JS | 与数据一样进入版本目录和全量缓存清单 |
| 字体 | 当前使用操作系统字体，没有需要联网加载的第三方字体 |
| Service Worker / 更新检查 | `updateViaCache: none`，网络检查，不使用应用内容缓存 |
| 外部链接及非清单资源 | 不缓存，不把外部网站和原始工作文件纳入应用 |

**更新以整版为单位。** 构建按文件内容生成版本号和每个文件的 SHA-256；新版安装时最多六路并发下载，每个请求 30 秒超时。全部文件校验成功才标记完整并 `skipWaiting()` / `clients.claim()`。任何 404/500、重定向、错误内容或下载中断都会使安装失败，删除此次临时缓存，旧版保持可用；下次联网检查会重试。

这里的 stale-while-revalidate 检查的是整套发布版本，不是把各个 JSON 请求的网络结果分别写入当前缓存。因此不会发生新索引引用尚未下载的新素材，也不会把发布到一半的 HTML 写进好缓存。

**正在打开的页面不刷新。** 没有 `location.reload()` 或 controllerchange 自动刷新；页面数据仍在内存中，依赖 URL 固定到原版。新版完整启用后，新开窗口、下次启动或用户主动刷新就使用新版，即使别的旧阅读窗口仍开着。恢复之前未关闭的窗口会继续保留原阅读内容。

客户端在启动、重新联网、回到前台以及可见期间每 30 分钟主动检查；一分钟内去重，失败后允许重试。导航请求也触发后台检查，因此不会仅依赖浏览器默认更新周期。静态内容每次修改后必须重新构建发布；直接修改服务器版本目录中的文件不属于受支持的发布方式。

## 旧缓存与失败恢复

- 缓存前缀包含站点子路径。同一域名下其他应用的缓存不会被删除。
- 客户端通过消息报告自己正在阅读的版本，记录保存在 Cache Storage，Service Worker 休眠 / 重启后仍能恢复。
- 保留当前版本及仍有打开页面使用的版本；页面关闭后，下次客户端报告 / 激活清理时删除无人使用的旧版及对应客户端记录。
- 尚未报告版本的现有窗口会暂缓淘汰，确保不误删正在阅读页面的惰性加载配图。
- 不清除另一份正在安装的缓存；失败安装主动删除自身缓存，异常终止遗留的 staging 超过 24 小时后在后续清理中回收。
- 某个当前版缓存项缺失时尝试按原始 SHA-256 修复。主页无法恢复且离线时展示轻量 fallback；不存在的 JSON/图片离线返回 503，不伪装成 HTML 或缓存错误响应。
- 未定义的站内页面导航回到应用根路径，根目录与子目录部署均能离线启动。

浏览器和系统仍可在存储不足、用户清除网站数据等情况下移除本地数据；PWA 无法保证永久存储。清除后需要再联网完成缓存。不会主动删除用户的 localStorage 栏目偏好。

## 发布

**仅发布 `dist/` 内容**，不要公开工作目录中的 PDF、inbox、批注来源或临时文件。发布产物包含应用可阅读的所有素材（含可选测试素材），上线前按正常内容流程维护这些 JSON。

根域名或 `/EssayLab/` 等子路径均可，无需写死域名。必须保持 manifest ID、scope 和入口路径稳定，以便已安装应用持续更新。

优先使用支持整份静态产物原子部署的 HTTPS 平台。若逐文件上传，先上传 `releases/<版本>/`，再发布 manifest / 首页 / fallback，最后发布 `sw.js`；保留上一版不可变目录覆盖部署期间的在途请求。校验失败不会污染旧缓存，但原子部署能减少重试。回滚需恢复整份历史产物。

响应头建议：

```text
/sw.js               Cache-Control: no-store
/index.html          Cache-Control: no-cache
/manifest.webmanifest Cache-Control: no-cache
/releases/*          Cache-Control: public, max-age=31536000, immutable
```

根目录 `/` 也应按首页设置 revalidation。`dist/_headers` 提供 Netlify / Cloudflare Pages 配置示例；其他静态主机需配置等价规则。确保 sw.js 是 JavaScript MIME，manifest 是 `application/manifest+json` 或 JSON，不把缺失文件统一重写成首页。使用自带 CDN 的主机，检查 sw.js 不被长期边缘缓存。

已提供 `.github/workflows/pages.yml`：以 EssayLab 为仓库根目录，GitHub Pages Source 选择 GitHub Actions 后，推送 main 会构建、校验、运行真实浏览器测试，再自动发布 `dist/`；也可手动运行。当前未连接仓库或执行线上部署。若 EssayLab 放在父仓库子目录，需要调整 workflow 位置和 working-directory。

## 验证

```sh
npm ci
npx playwright install chromium
.venv/bin/python scripts/build_pwa.py
npm test
npm run test:pwa
```

本机也可用已安装的 Chrome：`PWA_CHROME_CHANNEL=chrome npm run test:pwa`。测试使用独立临时浏览器身份和内存静态服务器，不接管日常浏览器，不修改真实素材或发布产物。

真实浏览器测试覆盖完整预缓存、manifest、断网冷启动与阅读、后台升级不刷新、旧页面配图保留、无人使用的缓存清理、HTTP 500 与错误内容回滚、后续升级恢复、Worker 重启、子路径部署、离线 fallback 和首次安装失败后的重试。各平台真实安装入口仍应在正式 HTTPS 地址上做设备验收。

参考：[Service Worker 生命周期](https://web.dev/articles/service-worker-lifecycle)、[PWA 更新](https://web.dev/learn/pwa/update)、[manifest](https://web.dev/learn/pwa/web-app-manifest)、[Safari Mac 网页 App](https://support.apple.com/en-us/104996)。
