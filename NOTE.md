# NOTE — 如何让 AI 从 0 构建 IEEE 期刊 Metadata 采集需求

本文档面向 **AI 大模型**（Cursor Agent、Claude、GPT 等）。当用户提出类似下面的自然语言需求时，请按本文档理解目标、规划实现、编写脚本并产出标准交付物。

---

## 1. 典型用户请求（示例）

用户可能会这样说：

> 帮我查询、生成 **IEEE TAP 2020–2026 年**所有文章的 metadata，格式类似下面这一条：

```
J. Wang, Y. Li, J. Wang, L. Ge, M. Chen, Z. Zhang, and Z. Li, "A Low-Profile Vertically Polarized Magneto-Electric Monopole Antenna With a 60% Bandwidth for Millimeter-Wave Applications," in IEEE Transactions on Antennas and Propagation, vol. 69, no. 1, pp. 3-13, January 2021, doi: 10.1109/TAP.2020.3030907.  Abstract: A millimeter-wave (mmW) low-profile wideband magneto-electric (ME) monopole antenna with the vertically polarized endfire radiation is presented by combining a pair of the top-loaded electric monopoles with a thin open-ended substrate integrated waveguide (SIW) with the extended lower broad wall. The antenna has a profile of 0.19 wavelength at the center frequency of the operating band, a wide bandwidth of 60.7% (from 23.5 to 44 GHz) covering all the fifth-generation (5G) mmW bands in the Ka-band, a stable gain of around 7 dBi, and a tilted radiation pattern. Then a $1 \times 8$ ME-monopole array is designed to investigate the beam scanning properties and the effects of the metallic ground and the polycarbonate radome, which should be considered in practical applications. As a sample, a $1 \times 8$ array fed by an SIW feed network, assembled on a metallic ground plane, and covered by a polycarbonate radome is finally designed, fabricated, and measured. The prototype achieves promising radiation features with a gain up to 15.3 dBi. Owing to the compact low-profile structure with good performance, the proposed design would be valuable to the mmW applications.  keywords: {N/A},  URL: https://ieeexplore.ieee.org/stamp/stamp.jsp?tp=&arnumber=9234023
```

**AI 应从中解析出：**

| 维度 | 本例取值 |
|------|----------|
| 期刊 | IEEE Transactions on Antennas and Propagation（简称 TAP） |
| 年份范围 | 2020–2026（含首尾年） |
| 输出粒度 | 每篇论文一条完整 metadata 记录 |
| 目标格式 | IEEE Xplore「Cite This · Plain Text」风格（见 §2） |

同类请求还可能换成其他期刊（AWPL、TMTT、APM 等）或其他年份段；**实现逻辑相同，仅 ISSN、卷号、过滤条件不同**。

---

## 2. 单条记录的标准格式（Canonical Plain Text）

每条记录 **一行**（`.txt` 中多篇之间用 **空行** 分隔），结构固定为四段：

```
{CITATION}  Abstract: {ABSTRACT}  keywords: {KEYWORDS},  URL: {URL}
```

### 2.1 CITATION（引用行）

模板：

```
{Authors}, "{Title}," in {Journal}, vol. {V}, no. {N}, pp. {pages}, {Month} {Year}, doi: {DOI}.
```

规则：

- **Authors**：IEEE 风格缩写，`Given Initial. Family`，多人用逗号分隔，最后一人前加 `and`  
  例：`J. Wang, Y. Li, J. Wang, L. Ge, M. Chen, Z. Zhang, and Z. Li`
- **Title**：保留原标题，引号内，标题后加逗号：`"Title,"`
- **Journal**：使用 Crossref 的 `container-title`（IRE 时期可能是 `IRE Transactions on Antennas and Propagation`，不要擅自改名）
- **vol. / no. / pp.**：有则写，无则省略对应段
- **Month Year**：英文月份 + 年份，如 `January 2021`
- **doi**：小写或大写均可，保持 `10.1109/...` 形式

### 2.2 Abstract

- 有摘要：写完整摘要正文（可含 LaTeX 片段如 `$1 \times 8$`）
- 无摘要：写 **`N/A`**（不要编造、不要留空）

### 2.3 keywords

- 有主题词：`keywords: {词1; 词2; 词3}`（分号+空格分隔，花括号包裹）
- 无主题词：`keywords: {N/A}`

> **注意：** Crossref / OpenAlex 提供的是 **推断主题词**，不是 IEEE Xplore 页面上的 **IEEE Index Terms**。若用户明确要求「与 Cite This 完全一致的关键词」，需走浏览器采集（见 §6.3）。

### 2.4 URL

优先使用 IEEE Xplore stamp 链接：

```
https://ieeexplore.ieee.org/stamp/stamp.jsp?tp=&arnumber={arnumber}
```

若有 `isnumber`，可追加 `&isnumber={isnumber}`。`arnumber` 必须从 Crossref `link[].URL` 解析，**不要假设 DOI 后缀等于 arnumber**。

---

## 3. 必须交付的文件（每个数据集一组）

对用户请求的「期刊 + 年份段」，在工作区创建 **一个 metadata sets 文件夹**，内含 **三个文件**：

```
{Journal Name} metadata sets/
├── ieee-{code}-{yearStart}-{yearEnd}.json      # 结构化数据
├── ieee-{code}-{yearStart}-{yearEnd}.txt       # 纯文本目录（§2 格式）
└── ieee-{code}-{yearStart}-{yearEnd}-summary.md # 统计与数据来源说明
```

命名示例（TAP 2020–2026）：

```
IEEE TAP metadata sets/
├── ieee-tap-2020-2026.json
├── ieee-tap-2020-2026.txt
└── ieee-tap-2020-2026-summary.md
```

### 3.1 JSON 单条记录 Schema

```json
{
  "authors": "J. Wang, Y. Li, ...",
  "title": "A Low-Profile Vertically Polarized ...",
  "journal": "IEEE Transactions on Antennas and Propagation",
  "volume": "69",
  "issue": "1",
  "pages": "3-13",
  "month": "January",
  "year": 2021,
  "doi": "10.1109/TAP.2020.3030907",
  "abstract": "A millimeter-wave (mmW) ...",
  "keywords": null,
  "url": "https://ieeexplore.ieee.org/stamp/stamp.jsp?tp=&arnumber=9234023",
  "arnumber": "9234023",
  "isnumber": null,
  "sources": {
    "biblio": "crossref",
    "abstract": "semanticscholar",
    "keywords": "openalex"
  }
}
```

- `abstract` / `keywords` 缺失时用 `null`（生成 `.txt` 时转为 `N/A`）
- `sources` 记录各字段实际来源，便于审计

### 3.2 summary.md 应包含

- 期刊名、ISSN、IEEE Xplore punumber、日期范围、生成时间
- **Totals**：总篇数、有摘要/关键词/DOI/URL 的数量与百分比
- **Counts by year**、**Counts by volume/issue**（如适用）
- **Data sources**：用了哪些 API、如何过滤
- **Known gaps**：摘要/关键词缺口及原因（未编造）
- **Files**：三个输出文件的路径

---

## 4. 工作区目录约定

```
Literature_finder_helper/
├── NOTE.md                          # 本文件（需求说明书）
├── requirements.txt                 # Python 依赖
├── .mcp.json                        # Claude Code 项目级 MCP 配置（文献检索工具）
├── .venv/                           # 项目虚拟环境（CPU torch + 检索依赖）
├── scripts/                         # ★ AI 必须在此编写/维护采集脚本
│   ├── ieee_metadata_harvester.py   # 单条/小批量 DOI 采集
│   ├── enrich_catalog.py            # 已有 catalog 批量补全 keywords/abstract
│   ├── build_corpus.py              # 清洗：合并全部 catalog → index/corpus.jsonl
│   ├── litsearch.py                 # 检索核心：BM25 + 向量混合检索
│   ├── build_index.py               # 建索引（CPU 或 A100，增量）
│   ├── search.py                    # 命令行检索
│   ├── mcp_server.py                # Claude Code 检索工具（MCP）
│   └── pack_server_job.py           # 打包 A100 任务 → TEMPFILES/a100-embed-job.zip
├── server/                          # A100 服务器任务：README、check_env.py、run_embed.bat/.sh、requirements-gpu.txt
├── index/                           # 由脚本生成的检索索引，可随时重建
├── IEEE TAP metadata sets/          # 按期刊分文件夹（原始数据，检索流程只读不改）
├── IEEE AWPL metadata sets/
├── IEEE APM metadata sets/
└── TEMPFILES/                       # 备份、日志、浏览器采集 HTML 工具
    └── IEEE Literature Harvester.html
```

**规则：**

1. 所有 Python 实现代码放在 **`scripts/`**，不要散落在根目录。
2. 每个期刊/年份段的产出放在 **`{期刊名} metadata sets/`** 文件夹。
3. 大规模跑批前，先把已有数据备份到 **`TEMPFILES/`**。
4. 根目录维护 **`requirements.txt`**（至少 `requests`）。

---

## 5. AI 从 0 实现的推荐流程

### Step 0 — 澄清参数（可从用户句子里推断）

- 期刊全称与缩写（TAP / AWPL / …）
- Print ISSN（TAP: `0018-926X`；IRE 前身另需 `0096-1973`）
- 年份起止（ inclusive ）
- IEEE Xplore punumber（TAP = `8`）

### Step 1 — 创建 `scripts/` 与依赖

```bash
pip install -r requirements.txt
```

### Step 2 — 从 Crossref 拉取题录（主索引）

- API：`https://api.crossref.org/journals/{ISSN}/works`
- 过滤：`from-pub-date:YYYY-MM-DD,until-pub-date:YYYY-MM-DD`
- 分页：cursor + `rows=1000`
- **不要用 `select=` 丢掉 `link` 字段**（`link` 含真实 `arnumber`）
- 合并多个 ISSN 的结果，按 **DOI 去重**
- 作者转 IEEE 缩写格式

**排除非研究条目：** 目录页、封面、编者按、征稿、悼文、无作者条目、卷号/年份明显不符等。

### Step 3 — 补摘要

按优先级尝试（记录 `sources.abstract`）：

1. **Semantic Scholar**：`GET /graph/v1/paper/DOI:{doi}?fields=abstract` 或 batch API  
2. **OpenAlex**：`abstract_inverted_index` 解码  
3. 均无 → `null` / 文本 `N/A`

注意速率限制（429），加重试与 `delay`。

### Step 4 — 补 keywords

按优先级：

1. **OpenAlex**：`keywords[].display_name`，批量 `filter=doi:10.x|10.y|...`（每批约 40 个 DOI）  
2. 均无 → `null` / `{N/A}`

**不要用** Semantic Scholar 的 `fieldsOfStudy`（Engineering、Physics 等）冒充 keywords。

### Step 5 — 生成三个交付文件

1. 写 `.json`（数组，UTF-8，缩进 2）
2. 由 JSON 渲染 `.txt`（每篇一行 + 空行分隔）
3. 统计并写 `-summary.md`

### Step 6 — 验证

- 抽查用户给的示例 DOI，对比格式
- 统计：总篇数、摘要率、关键词率
- 确认无编造摘要/关键词

---

## 6. 数据源与限制（必读）

### 6.1 可用 API（脚本可直接调用）

| 来源 | 用途 | 备注 |
|------|------|------|
| **Crossref** | 题录、DOI、卷期页、arnumber | 主索引；IEEE 摘要通常不在 Crossref |
| **Semantic Scholar** | 摘要 | 近年覆盖好；老文献与版权摘要可能缺失 |
| **OpenAlex** | 摘要、主题 keywords | 适合批量；keywords 非 IEEE 官方词表 |

### 6.2 不可直接脚本爬 IEEE Xplore

- `ieeexplore.ieee.org` 对无头浏览器 / 裸 `requests` 返回 **418 / WAF**
- `/rest/document/{id}/metadata` 需浏览器同源 + 登录态

### 6.3 需要 IEEE 官方「Cite This」全文块时

使用 `TEMPFILES/IEEE Literature Harvester.html`：

1. 在已登录的 IEEE Xplore 检索结果页打开
2. 运行页面内嵌脚本（同源调用 `/rest/search`、`/xpl/downloadCitations`）
3. 导出与示例完全一致的 Plain Text / BibTeX

这是 **唯一可靠** 获取 IEEE Index Terms 的方式。

---

## 7. 本仓库已有脚本（可复用，勿重写）

| 脚本 | 作用 |
|------|------|
| `scripts/ieee_metadata_harvester.py` | 按 DOI / arnumber 采集单条，输出 §2 格式 |
| `scripts/enrich_catalog.py` | 对已有 `.json` 批量补 OpenAlex keywords + 摘要，并刷新 `.txt` / `summary.md` |

示例命令：

```powershell
# 单篇验证
python scripts/ieee_metadata_harvester.py --doi 10.1109/TAP.2020.3030907 --print

# 批量补全已有 catalog
python scripts/enrich_catalog.py "IEEE TAP metadata sets\ieee-tap-1960-1999.json" --delay 0.12
```

---

## 8. 常见期刊速查

| 缩写 | 期刊名 | Print ISSN | punumber |
|------|--------|------------|----------|
| TAP | IEEE Transactions on Antennas and Propagation | 0018-926X（IRE 前身 0096-1973） | 8 |
| AWPL | IEEE Antennas and Wireless Propagation Letters | 1536-1225 | 7737 |
| APM / MAP | IEEE Antennas and Propagation Magazine | 1045-9243 | 74 |

卷号与年份（TAP）：约 **volume ≈ year − 1952**（vol. 69 ≈ 2021）。

---

## 9. 质量红线（AI 必须遵守）

1. **不编造** 摘要或关键词；没有就写 `N/A` / `null`。
2. **不猜测** arnumber；必须从 Crossref `link` 或 IEEE 页面解析。
3. **不改写** IRE 时期的期刊名（Crossref 给什么写什么）。
4. 大批量任务使用 **checkpoint / 断点续跑**，避免中途失败丢数据。
5. 修改已有 metadata sets 前，先备份到 `TEMPFILES/`。

---

## 10. 给 AI 的一句话 Prompt 模板

用户可直接复制下面这段话发起任务：

```
请按工作区 NOTE.md 的规范，从 0 构建 IEEE TAP 2020–2026 年全部论文的 metadata 目录。
每条记录格式与 NOTE.md §2 示例一致。在 scripts/ 下编写 Python 采集脚本，
产出 ieee-tap-2020-2026.json、.txt、-summary.md 到 IEEE TAP metadata sets/ 文件夹。
题录走 Crossref，摘要优先 Semantic Scholar，keywords 用 OpenAlex；
缺失字段写 N/A，不要编造。跑批前备份已有数据到 TEMPFILES/。
```

---

## 11. 参考样例（本仓库已完成的数据集）

| 数据集 | 路径 |
|--------|------|
| TAP 1960–1999 | `IEEE TAP metadata sets/ieee-tap-1960-1999.*` |
| TAP 2000–2020 | `IEEE TAP metadata sets/ieee-tap-2000-2020.*` |
| TAP 2021–2026 | `IEEE TAP metadata sets/ieee-tap-2021-2026.*` |
| AWPL 2002–2026 | `IEEE AWPL metadata sets/ieee-awpl-2002-2026.*` |
| APM 1990–2026 | `IEEE APM metadata sets/ieee-map-1990-2026.*` |

新任务应 **对齐这些文件的格式与目录结构**，便于后续合并、检索与文献分析。

---

## 12. 检索系统（收集 → 清洗 → 小模型 → 定期更新）

目标：把期刊论文做成可查资料，设计时能查到相关做法。

| 阶段 | 状态 | 脚本 / 产物 |
|------|------|-------------|
| 收集摘要 | ✅ 96% 有摘要（2026-09-24 OpenAlex 补全） | `enrich_catalog.py`；剩余缺口见 `TEMPFILES/missing-abstract-arnumbers.txt` |
| 清洗 | ✅ | `build_corpus.py` → `index/corpus.jsonl` |
| 小模型 · 检索 | ✅ BM25 + Qwen3-Embedding-0.6B（2026-09-24 A100 编码；本机 CPU 查询约 110 ms，支持中文提问） | `build_index.py`、`search.py`、`mcp_server.py` |
| 小模型 · A100 | 待做 | 大模型抽取"做法"结构化字段；蒸馏小模型 |
| 定期更新 | 待做 | 需新写 Crossref 按期刊增量抓取脚本（原构建脚本不在仓库中） |

### 12.1 清洗规则（`build_corpus.py`）

- 原始 catalog **只读**；输出统一语料 `index/corpus.jsonl`。
- `doc_type`：`article` / `comment`（Comments on / Reply）/ `correction` / `editorial` / `news`。检索默认只返回 `article`。
- 剔除占位摘要（`International audience`、`See abstr. ...`），去掉 `Abstract—` 前缀与版权尾注；IEEE 通用摘要（`Presents corrections to ...`）不进入检索文本。
- LaTeX 转纯文本用于检索（`$1 \times 8$` → `1 × 8`），展示仍用原摘要。
- **OpenAlex keywords 不用于检索**：含 `Relevance (law)`、`CHAOS (operating system)` 等实体链接噪声。
- 同标题 + 同一作者的重复 article 只保留最完整的一条。

### 12.2 使用

```powershell
# 数据变化后重建（清洗秒级；BM25 秒级；向量增量，只编码新增/变更论文）
.venv\Scripts\python.exe scripts\build_corpus.py
.venv\Scripts\python.exe scripts\build_index.py

# 命令行检索
.venv\Scripts\python.exe scripts\search.py "wideband circularly polarized ME dipole array" -k 8
.venv\Scripts\python.exe scripts\search.py "metasurface RCS reduction" --journal TAP --from 2018
.venv\Scripts\python.exe scripts\search.py --similar 10.1109/TAP.2020.3030907
```

Claude Code：在本文件夹新开会话即读取 `.mcp.json`，首次提示批准 `ieee-literature` 后可直接用中文提设计问题。
要在别的项目文件夹里用：把本文件夹的 `.mcp.json` 复制到那个项目根目录（路径是绝对路径，无需修改）。
装有 `claude` 命令行时，也可一次注册为用户级（所有项目可用）：

```powershell
claude mcp add --scope user ieee-literature -e HF_HUB_OFFLINE=1 -- D:\AI_era\MicrowaveAntenna_github\Literature_finder_helper\.venv\Scripts\python.exe D:\AI_era\MicrowaveAntenna_github\Literature_finder_helper\scripts\mcp_server.py
```

### 12.3 换用 A100 编码的模型

本机打包（代码 + 语料；模型由服务器自己下载，huggingface.co 不通时自动换 hf-mirror.com）：

```powershell
.venv\Scripts\python.exe scripts\pack_server_job.py                # → TEMPFILES\a100-embed-job.zip（约 40 MB）
.venv\Scripts\python.exe scripts\pack_server_job.py --with-model   # 服务器不能联网时：连模型一起打包（约 1.2 GB）
```

拷到服务器解压后按包内 `README.md`（即 `server/README.md`）：在已激活的虚拟环境里先 `python check_env.py`（只检查不安装），通过后运行 `run_embed.bat`（Windows）或 `bash run_embed.sh`（Linux）。
把生成的 `index/emb.npy`、`index/emb-meta.json` 拷回本机 `index/` 即可；查询端按 `emb-meta.json` 里的模型名自动加载同一模型（Qwen3-Embedding-0.6B 在本机 CPU 单次查询约 60 ms，支持中文提问）。**前提：服务器与本机的 `index/corpus.jsonl` 必须是同一份**，否则向量索引会被判为过期而退回纯 BM25。
