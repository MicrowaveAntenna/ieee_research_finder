# IEEE Research Finder

Tools for finding IEEE antenna & electromagnetics literature: a browser-based search page, and a
local search engine over ~41k IEEE TAP / AWPL / APM papers that Claude Code can query while you design.

把期刊论文做成可查资料，设计时能查到相关做法。仓库包含两部分：

| 部分 | 内容 | 入口 |
|------|------|------|
| 网页工具 | 浏览器里直接调用 OpenAlex 检索 TAP、AWPL、OJAP、TVT、IEEE Access | [`index.html`](index.html) · 在线：<https://microwaveantenna.github.io/ieee_research_finder/> |
| 本地检索系统 | TAP 1960–2026、AWPL 2002–2026、APM 1990–2026 共约 4.16 万篇，BM25 + Qwen3-Embedding 混合检索，可作为 Claude Code 工具使用 | [`scripts/`](scripts/) · 规范见 [`NOTE.md`](NOTE.md) |

## 本地检索系统

流程：**收集摘要 → 清洗 → 小模型 → 定期更新**

| 阶段 | 状态 | 脚本 |
|------|------|------|
| 收集摘要 | ✅ 96.4% 有摘要（Crossref 题录 + OpenAlex / Semantic Scholar 摘要） | `enrich_catalog.py`、`ieee_metadata_harvester.py` |
| 清洗 | ✅ 文献类型分类、剔除占位摘要、LaTeX 转纯文本、去重 | `build_corpus.py` |
| 检索 | ✅ BM25 + Qwen3-Embedding-0.6B（A100 编码，CPU 查询约 110 ms，支持中文提问） | `litsearch.py`、`build_index.py`、`search.py`、`mcp_server.py` |
| 做法抽取 / 蒸馏小模型 | 计划中 | — |
| 定期更新 | 计划中 | — |

### 数据下载

数据集（`IEEE * metadata sets/*.json|*.txt`，含论文摘要）不放在仓库里，而是作为 Release 附件发布：
**[Dataset snapshot 2026-09-24](https://github.com/MicrowaveAntenna/ieee_research_finder/releases/tag/data-2026-09-24)**

| 压缩包 | 期刊 | 篇数 | 有摘要 |
|--------|------|------|--------|
| [`ieee-map-1990-2026.zip`](https://github.com/MicrowaveAntenna/ieee_research_finder/releases/download/data-2026-09-24/ieee-map-1990-2026.zip)（2 MB） | APM 1990–2026 | 2,719 | 94.3% |
| [`ieee-awpl-2002-2026.zip`](https://github.com/MicrowaveAntenna/ieee_research_finder/releases/download/data-2026-09-24/ieee-awpl-2002-2026.zip)（9 MB） | AWPL 2002–2026 | 11,392 | 98.0% |
| [`ieee-tap-1960-2026.zip`](https://github.com/MicrowaveAntenna/ieee_research_finder/releases/download/data-2026-09-24/ieee-tap-1960-2026.zip)（23 MB） | TAP 1960–2026（三段） | 27,515 | 95.9% |

分别解压到仓库根目录下同名的 `IEEE * metadata sets` 文件夹。各数据集的覆盖范围与统计见文件夹里的 `-summary.md`。
检索索引 `index/` 由脚本生成，不单独发布（见下方快速开始）。

### 快速开始（Windows）

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install torch --index-url https://download.pytorch.org/whl/cpu
.venv\Scripts\python.exe -m pip install -r requirements.txt

# 解压数据集后：几秒钟重建清洗语料和关键词索引
.venv\Scripts\python.exe scripts\build_corpus.py
.venv\Scripts\python.exe scripts\build_index.py --no-dense

# 检索
.venv\Scripts\python.exe scripts\search.py "wideband circularly polarized ME dipole array" -k 8
.venv\Scripts\python.exe scripts\search.py --similar 10.1109/TAP.2020.3030907
```

语义向量（`index/emb.npy`，支持中文提问、同义表述）需要 GPU 编码：用 `scripts/pack_server_job.py` 打包，
在 GPU 服务器上按 [`server/README.md`](server/README.md) 运行，再把结果拷回 `index/`。没有语义向量时自动退回关键词检索。

### 在 Claude Code 里使用

在仓库根目录新建 `.mcp.json`（把路径换成你的实际位置），在该文件夹打开 Claude Code 并批准 `ieee-literature` 工具：

```json
{
  "mcpServers": {
    "ieee-literature": {
      "command": "D:/path/to/ieee_research_finder/.venv/Scripts/python.exe",
      "args": ["D:/path/to/ieee_research_finder/scripts/mcp_server.py"],
      "env": { "HF_HUB_OFFLINE": "1", "PYTHONIOENCODING": "utf-8" }
    }
  }
}
```

之后直接提设计问题即可，例如"如何减小天线阵元之间的互耦"。

### 示范对话

- [为 wideband low-profile ME dipole 课题整理文献综述](https://microwaveantenna.github.io/ieee_research_finder/examples/me-dipole-literature-review.html)
  （[源文件](examples/me-dipole-literature-review.html)）：6 次工具调用，整理出降剖面技术对比表、带宽与剖面的取舍趋势、可改写的英文综述段落和 IEEE 格式参考文献。

## 目录

```
index.html              网页工具（GitHub Pages）
NOTE.md                 数据采集规范 + 检索系统说明（§12）
InfoGet.md              IEEE 文献信息获取方法与数据源对比
requirements.txt        本地检索依赖
scripts/                采集、补全、清洗、建索引、检索、MCP 服务器
server/                 GPU 服务器编码任务（check_env.py、run_embed.bat 等）
examples/               示范对话（HTML，可在 GitHub Pages 上直接打开）
IEEE * metadata sets/   各数据集统计说明（-summary.md）
```
