# victor-travel

Victor42 旅行攻略门户 — `https://travel.victor42.work/`

## 数据

| 层 | 职责 |
|----|------|
| `guides/*.md` | 中文行程正文（中文文件名） |
| `guides/en/<slug>.md` | 英文行程正文（与 slug 对齐；同结构） |
| `data.json` | 门户附加字段：`slug`、`emoji`、英译、`summary`、`album`/`blog`、`order` |

`data.json` **不覆盖** guide 里的标题、天数、交通、住宿等事实。

## 生成与预览

```bash
python3 scripts/generate_site.py
python3 -m http.server 8765
```

详情页：`/trip/<slug>/`；可下载 `trip/<slug>/<slug>.docx`（中文）与 `<slug>_en.docx`（英文），随页面语种切换。维护细节见 [`notes.md`](notes.md)。


Created by [Victor42](https://victor42.work/) & [Agent Vik](https://github.com/agent-vik/about-me). MIT licensed.
