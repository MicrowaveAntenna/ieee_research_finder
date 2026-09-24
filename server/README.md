# A100 任务：用 Qwen3-Embedding-0.6B 编码文献库

本包由本机 `scripts/pack_server_job.py` 生成：

```
a100-embed-job/
├── README.md               # 本文件
├── check_env.py            # 检查你的虚拟环境缺什么（只检查，不安装任何东西）
├── download_model.py       # 下载 Qwen3-Embedding-0.6B（约 1.2 GB）到 models/
├── run_embed.bat           # Windows：检查 → 下载模型（首次）→ GPU 编码
├── run_embed.sh            # Linux 服务器用（会自建 .venv 并装依赖）
├── requirements-gpu.txt
├── scripts/                # litsearch.py、build_index.py（与本机同一版本）
└── index/corpus.jsonl      # 清洗后的语料（必须与本机 index/ 里的是同一份）
```

模型由服务器自己下载：先试 huggingface.co，连不上自动换国内镜像 hf-mirror.com，断了重跑会续传。

用你**已有的虚拟环境**，不新建环境、不需要管理员权限：所有包都装在你自己目录下的虚拟环境里。

## 步骤（Windows 服务器）

1. **解压** `a100-embed-job.zip` 到你自己的目录。

2. **像平时一样激活你的虚拟环境**，然后进入解压出来的文件夹：

   ```bat
   cd 你的虚拟环境\Scripts
   .\activate
   cd /d 解压位置\a100-embed-job
   ```

3. **检查环境**（只读，不改任何东西）：

   ```bat
   python check_env.py
   ```

   全部 `[OK]` 并显示 `READY` 就直接做第 5 步。有 `[X]` 的话，它会打印出对应的修复命令。

4. **按需安装**（只在第 3 步报缺时做）：

   - 缺 numpy / sentence-transformers 等：**先预演**，看 pip 会升级或改动哪些包：

     ```bat
     python -m pip install --dry-run -r requirements-gpu.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
     ```

     确认不影响你这个环境里的其他项目后，去掉 `--dry-run` 再执行一次。

   - torch 看不到 GPU：Windows 上 `pip install torch` 默认装的是 **CPU 版**，需要按 `check_env.py`
     打印的命令装 CUDA 版（命令里的 `cu12x` 已按你的驱动版本选好）。这会替换该环境里的 torch；
     如果这个环境里有别的项目依赖特定 torch 版本，建议另建一个环境（在你自己目录下
     `python -m venv 新环境目录` 也不需要管理员权限）。

   装完再跑一次 `python check_env.py`，直到显示 `READY`。

5. **编码**：

   ```bat
   run_embed.bat
   ```

   PowerShell 里写成 `.\run_embed.bat`。首次运行会先下载模型到 `models\`，之后编码
   约 4.2 万篇，A100 上只需几分钟。
   GPU 与别人共用、显存紧张时先 `set BATCH=32` 再运行。中途中断直接重跑，会从断点续上。

6. **拷回本机**：把下面两个文件放进本机 `Literature_finder_helper\index\`（覆盖同名文件）：

   ```
   index\emb.npy
   index\emb-meta.json
   ```

   本机检索会按 `emb-meta.json` 自动改用 Qwen3-Embedding-0.6B（本机已缓存该模型，
   CPU 单次查询约 60 ms，可用中文提问）。

## 注意

- 服务器与本机的 `index\corpus.jsonl` 必须是同一份。本机重跑过 `build_corpus.py` 后，
  要么重新打包上传，要么直接在本机跑 `build_index.py --model Qwen/Qwen3-Embedding-0.6B`：
  它只编码新增或文本有变化的论文（每月新增几百篇，CPU 上一两分钟）。
- Linux 服务器：`bash run_embed.sh`（会在当前目录自建 `.venv` 并安装依赖）。
- 服务器两个下载源都连不上时，在本机用 `pack_server_job.py --with-model` 打一个自带模型的包。
