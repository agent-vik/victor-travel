# Victor Travel — 项目备忘录

`https://travel.victor42.work/`

## 1. 硬约束（违反前必读）

1. **`guides/*.md` 是行程事实的唯一源头**。`data.json` 只附加 md 里没有的门户字段（slug/emoji/英译/summary/互链/排序），**无权覆盖**正文事实。生成脚本检测到 data.json 写入 `title.zh` / `duration.zh` 会直接报错退出。
2. **脱敏规则不可松动**：具体酒店名、行程日写为 `xx` / `xx日`（月保留）；星期不写（避免反推具体日期）。
3. **guide 内禁止出现**：YAML frontmatter、游记/相册外链、内嵌图片。互链只放在 data.json，由页面渲染成卡片。
4. **中文标题取自文件名**（去 `.md`），中文「几天几晚」从正文解析 `（N天N晚）`——这两个字段 data.json 写了就是违规。
5. 改中文稿后必须同步更新对应 `guides/en/<slug>.md`，无自动同步机制。

## 2. 日常维护（最高频操作）

### 改一篇 / 新增一篇

1. 编辑或新增 `guides/<中文名>.md`；同步维护 `guides/en/<slug>.md`
2. 在 `data.json` 补/改对应条目（`file` 对上文件名；只写附加字段）
3. `python3 scripts/generate_site.py`
4. 本地预览：`python3 -m http.server 8765`

### Guide 正文版式

- **中文**（`guides/*.md`）：`## 行程`、`**时间：**`、`### Dn`、任务列表等固定结构
- **检查清单**：`行李清单可使用[Excel表格](https://my.feishu.cn/wiki/R7EAwcYX1ikNlukteCdcVhdinhb?from=from_copylink)管理。`
- **英文**（`guides/en/<slug>.md`）：与中文版同结构、同事实，标签英文化（见 `scripts/guide_i18n.py`）
  - 常用标签：`## Itinerary`、`## Checklist`、`## Tips`、`## POI Shortlist`、`## References`；`**Dates:**`；`Intercity transport:` / `Local transport:` / `Transport:` / `Accommodation:`；`**Sights:**`；`**Lunch:**` / `**Dinner:**`
  - 检查清单：`Manage your packing list with an [Excel spreadsheet](…).`

## 3. 构建与依赖

```bash
python3 scripts/generate_site.py   # 站点生成（必跑）
python3 -m http.server 8765        # 本地预览
```

依赖：`python-docx`（Word 生成）、`markdown`（正文渲染）。

生成产物：`index.html`、`sitemap.xml`、`trip/{slug}/`（详情页 + `{slug}.docx` / `{slug}_en.docx`）。详情页自上而下：标题摘要天数 → 互链卡片（博客单张头图 / 相册前 5 张等宽 5 列，均外链 `cdn.victor42.work`）→ 结构化正文（中英 `data-lang` 切换）→ Word 下载 → 引流至博客《手把手教你制作旅行攻略》（`post/3642/`）。

## 4. 架构参考（低频）

### 数据流与字段归属

```
guides/*.md       ──────────────┐
guides/en/*.md    ─────────────┼── generate_site.py → 静态页 + Word（中/英）
data/data.json    ─────────────┘
```

| 字段 | 来源 |
|------|------|
| 中文标题 / 天数 | guide 文件名 / 正文解析（data.json 禁写） |
| 中/英文正文 | `guides/<中文名>.md` / `guides/en/<slug>.md` |
| `slug` / `emoji` / `order` / `title.en` / `duration.en` / `summary.{zh,en}` / `album` / `blog` | data.json |
| 博客头图 / 相册缩略图 | `data/covers-cache.json` / `data/album-thumbs-cache.json`（生成时由 `fetch_covers.py` 更新） |

### 目录

```
victor-travel/
├── guides/*.md             # 中文攻略正文（发布源头）
├── guides/en/<slug>.md     # 英文攻略正文（与 slug 对齐）
├── data/
│   ├── data.json               # 附加元数据（人工维护）
│   ├── covers-cache.json       # 博客头图外链缓存（生成时更新）
│   └── album-thumbs-cache.json # 相册五列缩略图外链缓存（生成时更新）
├── trip/{slug}/            # 详情页 + Word（生成物）
├── index.html, sitemap.xml # 首页与站点地图（生成物）
├── assets/                 # 样式与脚本
├── scripts/
│   ├── generate_site.py    # 站点生成（必跑）
│   ├── guide_i18n.py       # 中英区块名与 UI 标签
│   ├── guide_render.py     # 结构化行程 HTML 渲染
│   ├── guide_docx.py       # 结构化行程 Word 渲染
│   └── fetch_covers.py     # 解析 blog/album 外链图
└── notes.md
```

`fetch_covers.py` 在生成时访问 data.json 中的 `blog` / `album` URL：博客取单张头图（优先 `og:image`，否则首张 `cdn.victor42.work` 图）；相册取前 5 张不重复 CDN 图。无图时卡片退回纯文字（标签 + URL）。
