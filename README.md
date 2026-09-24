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

### 数据不在仓库里

数据集（`IEEE * metadata sets/*.json|*.txt`，含论文摘要）和检索索引（`index/`）体积大，未放入仓库；
各数据集的覆盖范围与统计见对应文件夹下的 `-summary.md`。

- 数据集与索引下载：**网盘链接待补充**
- 下载后放到仓库根目录，结构为 `IEEE TAP metadata sets/…`、`index/…`

### 快速开始（Windows）

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install torch --index-url https://download.pytorch.org/whl/cpu
.venv\Scripts\python.exe -m pip install -r requirements.txt

# 有数据集、没有 index/ 时：几秒钟重建清洗语料和关键词索引
.venv\Scripts\python.exe scripts\build_corpus.py
.venv\Scripts\python.exe scripts\build_index.py --no-dense

# 检索
.venv\Scripts\python.exe scripts\search.py "wideband circularly polarized ME dipole array" -k 8
.venv\Scripts\python.exe scripts\search.py --similar 10.1109/TAP.2020.3030907
```

语义向量（`index/emb.npy`）需要 GPU 编码：用 `scripts/pack_server_job.py` 打包，在 GPU 服务器上按
[`server/README.md`](server/README.md) 运行，再把结果拷回 `index/`；或直接下载网盘里的 `index/`。

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

## 目录

```
index.html              网页工具（GitHub Pages）
NOTE.md                 数据采集规范 + 检索系统说明（§12）
InfoGet.md              IEEE 文献信息获取方法与数据源对比
requirements.txt        本地检索依赖
scripts/                采集、补全、清洗、建索引、检索、MCP 服务器
server/                 GPU 服务器编码任务（check_env.py、run_embed.bat 等）
IEEE * metadata sets/   各数据集统计说明（-summary.md）
```
