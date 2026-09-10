# 素材群视觉扉页

六张主题图由用户提供，2026-09-10 从桌面同名 PNG 接入。网页使用 1200 × 800、质量 84 的 JPEG 副本，六张合计约 1 MB；原始 PNG 保留在桌面。

| 素材群 | 网页图片 |
| --- | --- |
| 现代的两种转向 | modern-turns-v1.jpg |
| 祛魅 | disenchantment-v1.jpg |
| 事实、价值与诸神之争 | values-v1.jpg |
| 工具理性 | rationality-v1.jpg |
| 现代的铁笼 | iron-cage-v1.jpg |
| 反思现代 | reflection-v1.jpg |

图片承担素材群的长期视觉识别：统一哑光纸面、柔和光线与低饱和色调，通过材料轮廓与空间关系区分主题。生成方向见 prompts.json。

首页使用两列视觉扉页，窄屏改为单列。标题、简介和部分数量是叠在图片留白上的真实文字；不截断简介，搜索命中在扉页后自然展开。长标题使用均衡换行，避免末行只剩一个字。进入素材群后仍是文字目录，阅读页不增加配图。

图片路径映射保存在 templates/preview.html。build_library.py 同步在线浏览页；export_latest_html.py 将六张图嵌入 EssayLab-最新版.html，单个 HTML 即可离线浏览。未来更换配图应保留左侧约六成的低细节留白，并检查手机排版。
