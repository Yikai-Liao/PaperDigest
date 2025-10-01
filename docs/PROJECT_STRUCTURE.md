# PaperDigest 项目结构说明

## 📁 目录结构

```
PaperDigest/
├── .github/              # GitHub Actions 工作流配置
│   └── workflows/
│       ├── recommend.yaml    # 论文推荐工作流
│       └── build_page.yaml   # 网站构建工作流
│
├── config/               # 配置文件目录
│   ├── keywords.json     # 论文关键词列表
│   └── template.j2       # Jinja2 模板文件
│
├── data/                 # 数据文件目录
│   └── predictions.parquet   # 预测结果数据（被 .gitignore 忽略）
│
├── docs/                 # 项目文档
│   ├── BATCH_API_TEST_REPORT.md           # Batch API 测试报告
│   ├── GEMINI_GUIDE.md                    # Gemini 集成指南
│   ├── GEMINI_INTEGRATION_SUMMARY.md      # Gemini 集成总结
│   ├── IMPLEMENTATION_COMPLETE.md         # 实现完成报告
│   └── PROJECT_STRUCTURE.md               # 项目结构说明（本文件）
│
├── examples/             # 示例文件目录
│   ├── summary_example_en.json   # 英文摘要示例
│   └── summary_example_zh.json   # 中文摘要示例
│
├── notebook/             # Jupyter Notebook 文件
│   ├── melt.ipynb        # 数据处理笔记本
│   └── vectordb.ipynb    # 向量数据库笔记本
│
├── script/               # Python 脚本目录
│   ├── download_pdf.py            # PDF 下载脚本
│   ├── fetch_discussion.py        # 获取讨论脚本
│   ├── fit_predict.py             # 模型训练和预测
│   ├── gemini_handler.py          # Gemini API 处理器
│   ├── json2parquet.py            # JSON 转 Parquet
│   ├── render_md.py               # Markdown 渲染
│   ├── summarize.py               # 论文摘要生成（支持 OpenAI 和 Gemini）
│   ├── test_gemini_pipeline.py    # Gemini 管道测试
│   ├── test_pipeline_dry_run.py   # 完整管道空运行测试
│   ├── update_metadata.py         # 更新元数据
│   └── upload2hg.py               # 上传到 Hugging Face
│
├── content/              # 生成的网站内容（Markdown 文件）
├── pdfs/                 # 下载的 PDF 文件（被 .gitignore 忽略）
├── preference/           # 用户偏好数据
├── raw/                  # 原始论文 JSON 数据
├── website/              # 网站源代码
│
├── .gitignore            # Git 忽略规则
├── config.toml           # 主配置文件
├── LICENSE               # 许可证文件
├── pyproject.toml        # Python 项目配置（uv）
├── README.md             # 项目说明文档
├── requirements.txt      # Python 依赖列表
├── uv.lock               # uv 锁文件
└── vercel.json           # Vercel 部署配置
```

## 📝 目录说明

### 配置目录

- **config/**: 存放所有配置文件
  - `keywords.json`: 用于论文分类和匹配的关键词列表
  - `template.j2`: 生成 Markdown 内容的 Jinja2 模板

### 数据目录

- **data/**: 存放生成的数据文件
  - `predictions.parquet`: 模型预测结果，由 `fit_predict.py` 生成

### 文档目录

- **docs/**: 项目文档和技术报告
  - 包含 API 测试报告、集成指南、实现总结等

### 示例目录

- **examples/**: 示例文件
  - 包含中英文摘要示例，用于 AI 模型的 few-shot learning

### 脚本目录

- **script/**: 所有 Python 脚本
  - 数据处理、模型训练、API 调用、测试等

### Notebook 目录

- **notebook/**: Jupyter Notebook 文件
  - 用于数据探索、实验和分析

## 🔄 文件引用关系

### 配置文件引用

- `script/summarize.py` → `config/keywords.json`, `examples/summary_example_*.json`
- `script/render_md.py` → `config/template.j2`
- 所有脚本 → `config.toml`

### 数据文件引用

- `script/fit_predict.py` → 生成 `data/predictions.parquet`
- `script/download_pdf.py` → 读取 `data/predictions.parquet`
- `.github/workflows/recommend.yaml` → 上传/下载 `data/predictions.parquet` artifact

## 🔧 迁移说明

此次重构将文件从项目根目录迁移到了对应的子目录，主要改动：

1. **配置文件**: `keywords.json`, `template.j2` → `config/`
2. **示例文件**: `summary_example_*.json` → `examples/`
3. **文档文件**: `*_REPORT.md`, `*_SUMMARY.md` → `docs/`
4. **笔记本**: `melt.ipynb` → `notebook/`
5. **数据文件**: `predictions.parquet` → `data/`

所有脚本和工作流已更新以反映新的文件路径。

## 📌 注意事项

- `data/predictions.parquet` 在 `.gitignore` 中被忽略，不会被提交到 Git
- 项目使用 `uv` 作为包管理器（而非传统的 pip）
- GitHub Actions 工作流已更新为使用 `uv run` 运行所有 Python 脚本
