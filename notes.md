# 旅行攻略门户 — 项目备忘录

## 1. 目的

`projects/victor-travel` → `https://travel.victor42.work/`。

**红线：** `guides/*.md` 是行程事实的唯一源头；`data.json` 只附加 md 没有的门户字段，**无权覆盖** guide 里的正文事实。

## 2. 数据流转与冲突规则

```
guides/*.md       ──────────────┐
guides/en/*.md    ─────────────┼── generate_site.py → 静态页 + Word（中/英）
data.json         ─────────────┘
```

| 字段 | 来源 | 说明 |
|------|------|------|
| 中文标题 | **guide 文件名**（去 `.md`） | data.json 禁止写 `title.zh` |
| 中文行程正文 | **`guides/<中文名>.md`** | 中文源头 |
| 英文行程正文 | **`guides/en/<slug>.md`** | 与中文版同结构；按 slug 对齐 |
| 中文「几天几晚」 | **从中文 guide 正文解析** `（N天N晚）` | data.json 禁止写 `duration.zh` |
| `slug` / `emoji` / `order` | data.json | 门户路由与展示 |
| `title.en` / `duration.en` | data.json | 英译附加 |
| `summary.{zh,en}` | data.json | 卡片/SEO 文案（正文无此字段） |
| `album` / `blog` | data.json | 互链；**不写进** guide md |
| 博客卡片头图 | `covers-cache.json` | 单图；外链 `cdn.victor42.work` |
| 相册卡片缩略图 | `album-thumbs-cache.json` | 相册页前 5 张不重复 CDN 图，等宽 5 列 |

冲突时：**以 guide 为准**；生成脚本若发现 data.json 试图写入 `title.zh` / `duration.zh` 会直接报错退出。

## 3. Guide 正文约定

### 中文（`guides/*.md`）

- **版式**：`## 行程`、`**时间：**`、`### Dn`、任务列表等固定结构
- **脱敏**：具体酒店名、行程日可写为 `xx` / `xx日`（月保留）；星期不写，避免反推具体日期
- **禁止出现在 guide 内**：YAML frontmatter、游记/相册外链、内嵌图片
- **检查清单**：`行李清单可使用[Excel表格](https://my.feishu.cn/wiki/R7EAwcYX1ikNlukteCdcVhdinhb?from=from_copylink)管理。`

### 英文（`guides/en/<slug>.md`）

- 与中文版**同结构、同事实**；区块标题与字段标签用英文（见 `scripts/guide_i18n.py`）
- 常用英文标签：`## Itinerary`、`## Checklist`、`## Tips`、`## POI Shortlist`、`## References`；`**Dates:**`；`Intercity transport:` / `Local transport:` / `Transport:` / `Accommodation:`；`**Sights:**`；`**Lunch:**` / `**Dinner:**`
- 检查清单：`Manage your packing list with an [Excel spreadsheet](…).`
- 改中文后需同步更新对应 `guides/en/<slug>.md`，无自动同步机制

## 4. 详情页结构

每篇 `trip/{slug}/index.html` 自上而下：

1. 标题、摘要、天数标签
2. **互链卡片**（`data.json` 的 `blog` / `album`）：左图右文，含完整 URL
   - 博客游记：单张头图，高度随卡片拉伸
   - 旅行相册：前 5 张图等宽 5 列；外框与博客单图同为 108×(3:2)，不随文字拉伸
3. 结构化攻略正文（`guide_render.py`）；中/英各一份，`data-lang` 切换
4. **Word 下载**：`{slug}.docx`（中文）、`{slug}_en.docx`（英文）；按钮随当前语种
5. **关于旅行攻略**：引流至博客《手把手教你制作旅行攻略》（`post/3642/`）

## 5. 目录

```
victor-travel/
├── guides/*.md             # 中文攻略正文（发布源头）
├── guides/en/<slug>.md     # 英文攻略正文（与 slug 对齐）
├── data.json               # 附加元数据（人工维护）
├── covers-cache.json       # 博客头图外链缓存（生成时更新）
├── album-thumbs-cache.json # 相册五列缩略图外链缓存（生成时更新）
├── trip/{slug}/            # 详情页 + {slug}.docx + {slug}_en.docx（生成物）
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

`fetch_covers.py` 在生成时访问 `data.json` 中的 `blog` / `album` URL：博客取单张头图（优先 `og:image`，否则首张 `cdn.victor42.work` 图）；相册取前 5 张不重复 CDN 图。无图时卡片退回纯文字（标签 + URL）。

依赖：`python-docx`（Word 生成）、`markdown`（正文渲染）。

## 6. 维护

### 日常（改一篇或新增一篇）

1. 编辑或新增 `guides/<中文名>.md`；同步维护 `guides/en/<slug>.md`
2. 在 `data.json` 补/改对应条目（`file` 对上文件名；只写附加字段）
3. `python3 scripts/generate_site.py`
4. 本地预览：`python3 -m http.server 8765`

