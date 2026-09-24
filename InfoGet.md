# InfoGet — IEEE 期刊文献信息获取方法

本文档说明如何用 **Python** 获取 IEEE 期刊文献信息，包括：

- 指定期刊 → 批量获取所有文章的 **标题 + 链接**
- 单篇论文 → 获取完整 **metadata**（引用格式、摘要、keywords、URL）
- 各数据源的适用场景、限流情况与注意事项

---

## 1. 目标输出格式（完整 metadata 示例）

每条记录的标准 plain text 格式：

```
{Authors}, "{Title}," in {Journal}, vol. {V}, no. {N}, pp. {pages}, {Month} {Year}, doi: {DOI}.  Abstract: {abstract}  keywords: {keywords},  URL: {url}
```

示例：

```
J. Wang, Y. Li, J. Wang, L. Ge, M. Chen, Z. Zhang, and Z. Li, "A Low-Profile Vertically Polarized Magneto-Electric Monopole Antenna With a 60% Bandwidth for Millimeter-Wave Applications," in IEEE Transactions on Antennas and Propagation, vol. 69, no. 1, pp. 3-13, January 2021, doi: 10.1109/TAP.2020.3030907.  Abstract: A millimeter-wave (mmW) low-profile wideband magneto-electric (ME) monopole antenna ...  keywords: {Dipole antennas; Gain; Bandwidth; ...},  URL: https://ieeexplore.ieee.org/stamp/stamp.jsp?tp=&arnumber=9234023
```

缺失字段写 `N/A`，不要编造。

---

## 2. 任务一：指定期刊，获取所有文章标题 + 链接

### 2.1 推荐方法：CrossRef API

**适用：** 批量拉取某期刊某年份范围内全部论文的标题、DOI、IEEE 链接。  
**优点：** 免费、稳定、**不限流**（比 Semantic Scholar 宽松得多）。  
**缺点：** 不含 IEEE 官方 Index Terms；摘要覆盖因年代而异。

#### 基本思路

1. 查期刊 **Print ISSN**
2. 用 CrossRef `journals/{ISSN}/works` 接口，按发表日期过滤
3. cursor 分页（每页最多 1000 条）直到取完
4. 从 `link[]` 字段提取 IEEE Xplore URL；没有则退回 `https://doi.org/{DOI}`

#### 常用期刊 ISSN

| 缩写 | 期刊名 | Print ISSN | 备注 |
|------|--------|------------|------|
| TAP | IEEE Transactions on Antennas and Propagation | 0018-926X | IRE 前身另需 0096-1973 |
| AWPL | IEEE Antennas and Wireless Propagation Letters | 1536-1225 | |
| APM | IEEE Antennas and Propagation Magazine | 1045-9243 | |

TAP 卷号与年份近似关系：**volume ≈ year − 1952**（vol. 69 ≈ 2021）。

#### Python 示例：批量获取标题 + 链接

```python
import csv
import re
import requests

ISSN = "0018-926X"          # 期刊 Print ISSN
YEAR_FROM, YEAR_TO = 2020, 2026
OUTPUT = "tap-2020-2026-titles.csv"

def ieee_url(item: dict) -> str:
    for link in item.get("link", []):
        url = link.get("URL", "")
        if "ieee" in url.lower():
            ar = re.search(r"arnumber=(\d+)", url, re.I)
            if ar:
                return f"https://ieeexplore.ieee.org/stamp/stamp.jsp?tp=&arnumber={ar.group(1)}"
            doc = re.search(r"/document/(\d+)", url, re.I)
            if doc:
                return f"https://ieeexplore.ieee.org/document/{doc.group(1)}/"
            return url
    doi = item.get("DOI")
    return f"https://doi.org/{doi}" if doi else ""

rows = []
cursor = "*"
while cursor:
    resp = requests.get(
        f"https://api.crossref.org/journals/{ISSN}/works",
        params={
            "filter": f"from-pub-date:{YEAR_FROM}-01-01,until-pub-date:{YEAR_TO}-12-31",
            "rows": 1000,
            "cursor": cursor,
        },
        headers={"User-Agent": "InfoGet/1.0 (mailto:your@email.com)"},
        timeout=60,
    )
    resp.raise_for_status()
    msg = resp.json()["message"]
    for item in msg["items"]:
        title = (item.get("title") or [""])[0]
        doi = item.get("DOI", "")
        rows.append({"title": title, "url": ieee_url(item), "doi": doi})
    cursor = msg.get("next", {}).get("cursor")

with open(OUTPUT, "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=["title", "url", "doi"])
    w.writeheader()
    w.writerows(rows)

print(f"Wrote {len(rows)} rows -> {OUTPUT}")
```

#### IRE 老刊（TAP 1960–1987 部分条目）

Crossref 中 IRE TAP 条目可能在 ISSN `0096-1973` 下。需对两个 ISSN 分别拉取，**按 DOI 去重合并**。

#### 过滤非论文条目

Crossref 会混入目录页、封面、征稿等，建议排除：

- 标题含 `Table of contents`、`Front cover`、`Information for authors` 等
- 无作者
- 卷号/年份明显不符

---

## 3. 任务二：单篇论文，获取完整 metadata

### 3.1 Python + 外部 API（无需 IEEE 登录）

**脚本：** `scripts/ieee_metadata_harvester.py`

```powershell
# 按 DOI
python scripts/ieee_metadata_harvester.py --doi 10.1109/TAP.2020.3030907 --print

# 按 IEEE arnumber
python scripts/ieee_metadata_harvester.py --arnumber 9234023 --print
```

| 字段 | 来源 |
|------|------|
| 题录（作者/期刊/卷期页/DOI） | CrossRef |
| 摘要 | Semantic Scholar → OpenAlex 兜底 |
| keywords | OpenAlex 主题词（**非** IEEE Index Terms） |
| URL / arnumber | CrossRef `link` 或 OpenAlex landing page |

**限制：** Semantic Scholar / OpenAlex 有速率限制（HTTP 429）；IEEE 直连会被 WAF 拦截（HTTP 418）。

### 3.2 Python + IEEE 会话（单链接、不限第三方 API 限流）

若要从 **IEEE Xplore 页面** 拿与「Cite This」一致的内容（含 IEEE Index Terms），Python 需携带**已登录浏览器的 Cookie**，或使用 Playwright/Selenium 打开真实浏览器。

IEEE 同源接口（须在 `ieeexplore.ieee.org` 域下、带登录态）：

```
GET  /rest/document/{arnumber}/metadata
POST /xpl/downloadCitations   (citations-format=citation-abstract)
```

页面内嵌数据：

```javascript
window.xplGlobal.document.metadata
```

**裸 `requests.get("https://ieeexplore.ieee.org/...")` 会被 WAF 拒绝**，这不是 Python 做不到，而是 IEEE 反爬策略。解决办法：

1. 浏览器登录 IEEE → 导出 Cookie → Python `requests.Session` 带 Cookie 请求
2. Playwright 使用本机 Chrome 用户数据目录（保留登录态）
3. 在 IEEE 文章页 Console 运行脚本（见 §3.3）

从 URL 解析 arnumber：

```python
import re

def arnumber_from_url(url: str) -> str | None:
    m = re.search(r"/document/(\d+)", url) or re.search(r"arnumber=(\d+)", url, re.I)
    return m.group(1) if m else None
```

### 3.3 浏览器脚本（推荐拿 IEEE 官方 keywords）

**工具：** `TEMPFILES/IEEE Literature Harvester.html`

1. 在已登录的 `ieeexplore.ieee.org` 打开检索结果页或文章页
2. 从 Harvester 页面复制脚本到 Console 运行
3. 调用同源接口 `/rest/search`、`/xpl/downloadCitations`
4. 导出与 Cite This · Plain Text 一致的 `.txt` / `.bib` / `.json`

**特点：** 不受 CrossRef / OpenAlex / Semantic Scholar 限流影响；可拿 IEEE 官方摘要和 Index Terms。

---

## 4. 任务三：批量补全已有 catalog 的摘要和 keywords

**脚本：** `scripts/enrich_catalog.py`

对已生成的 `.json` catalog 批量补充 OpenAlex keywords 和摘要，并刷新 `.txt` 与 `-summary.md`：

```powershell
python scripts/enrich_catalog.py "IEEE TAP metadata sets\ieee-tap-1960-1999.json" --delay 0.12
```

内部用 OpenAlex **DOI 批量查询**（每批约 40 个 DOI，`filter=doi:10.x|10.y|...`），比逐条请求快得多。

---

## 5. 数据源对比总表

| 数据源 | 标题 | 链接 | 题录 | 摘要 | IEEE keywords | 限流 | Python 直连 |
|--------|------|------|------|------|---------------|------|-------------|
| **CrossRef** | ✅ | ✅ | ✅ | 极少 | ❌ | 宽松 | ✅ |
| **OpenAlex** | ✅ | ✅ | 部分 | 部分 | 近似主题词 | 中等 | ✅ |
| **Semantic Scholar** | ✅ | ✅ | 部分 | 部分 | ❌ | 容易 429 | ✅ |
| **IEEE Xplore API** | ✅ | ✅ | ✅ | ✅ | ✅ | 无第三方限流 | ❌ 需 Cookie/浏览器 |

---

## 6. 推荐工作流

```
指定期刊 + 年份
       │
       ▼
  CrossRef 批量拉标题+链接+DOI+arnumber     ← 不限流，Python 首选
       │
       ▼
  过滤非论文条目，生成初始 .json
       │
       ├── 只需标题+链接 → 导出 CSV/TXT，结束
       │
       └── 需要摘要+keywords
                │
                ▼
           enrich_catalog.py（OpenAlex 批量）   ← 快，但 keywords 非 IEEE 官方
                │
                ▼
           仍缺或要 IEEE Index Terms？
                │
                ▼
           IEEE Literature Harvester（浏览器）  ← 登录后不限流，格式与 Cite This 一致
```

---

## 7. 本仓库相关文件

| 文件 | 用途 |
|------|------|
| `InfoGet.md` | 本文档 |
| `NOTE.md` | AI 从 0 构建 metadata catalog 的完整规范 |
| `scripts/ieee_metadata_harvester.py` | 单篇 / 小批量 DOI 采集 |
| `scripts/enrich_catalog.py` | 已有 JSON 批量补摘要和 keywords |
| `requirements.txt` | Python 依赖（`requests`） |
| `TEMPFILES/IEEE Literature Harvester.html` | 浏览器端 IEEE 官方采集 |
| `IEEE TAP metadata sets/` 等 | 已生成的 catalog 示例（.json / .txt / -summary.md） |

---

## 8. 质量原则

1. **不编造**摘要或关键词；没有就写 `N/A`。
2. **不假设** DOI 后缀等于 IEEE arnumber；从 Crossref `link` 解析。
3. IRE 时期期刊名用 Crossref 原文（`IRE Transactions on Antennas and Propagation`），不擅自改名。
4. 大规模任务使用 **checkpoint 断点续跑**；修改已有数据前先备份到 `TEMPFILES/`。
