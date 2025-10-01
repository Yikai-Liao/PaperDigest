# PDF/LaTeX 提取器使用指南

## 概述

新的 `pdf_extractor.py` 模块实现了智能的论文内容提取，优先使用 LaTeX 源码（通过 latex2json），失败时自动回退到 PDF 提取（通过 marker-pdf）。

## 性能对比

| 方法 | 速度 | 成功率 | 质量 |
|------|------|--------|------|
| **LaTeX (latex2json)** | ⚡ 非常快 (~1 秒) | 🟢 高 (~90%) | ⭐⭐⭐⭐⭐ 优秀 |
| **PDF (marker-pdf)** | 🐌 很慢 (~120 秒) | 🟡 中等 | ⭐⭐⭐ 良好 |

## 安装依赖

```bash
# 安装基础依赖（包括 latex2json）
uv sync

# 如果需要 PDF fallback，安装 marker-pdf（可选）
uv sync --extra marker
```

## 快速开始

### 1. 基础用法

```python
from pathlib import Path
from script.pdf_extractor import PaperExtractor

# 初始化提取器
extractor = PaperExtractor(
    latex_dir=Path("arxiv/latex"),
    json_dir=Path("arxiv/json"),
    markdown_dir=Path("arxiv/markdown"),
    pdf_dir=Path("pdfs")
)

# 提取单篇论文
arxiv_id = "2509.04027"
markdown_content, method = extractor.extract_paper(arxiv_id)

if markdown_content:
    print(f"✓ 成功使用 {method} 方法提取")
    print(f"  Markdown 长度: {len(markdown_content)} 字符")
else:
    print("✗ 提取失败")
```

### 2. 批量提取

```python
# 提取多篇论文
arxiv_ids = ["2509.04027", "2509.18405", "2509.20138"]
results = extractor.extract_batch(arxiv_ids)

print(f"成功提取 {len(results)}/{len(arxiv_ids)} 篇论文")
```

### 3. 强制使用 PDF 提取

```python
# 某些情况下可能需要强制使用 PDF
markdown, method = extractor.extract_paper(
    arxiv_id="2509.04027",
    force_pdf=True  # 跳过 LaTeX，直接使用 PDF
)
```

### 4. 命令行使用

```bash
# 提取单篇论文
uv run python script/pdf_extractor.py 2509.04027

# 提取多篇论文
uv run python script/pdf_extractor.py 2509.04027 2509.18405 2509.20138

# 强制使用 PDF
uv run python script/pdf_extractor.py 2509.04027 --force-pdf

# 指定目录
uv run python script/pdf_extractor.py 2509.04027 \
    --latex-dir custom/latex \
    --json-dir custom/json \
    --markdown-dir custom/markdown \
    --pdf-dir custom/pdfs
```

## 工作流程

```
开始
  │
  ├─ 检查 Markdown 是否已存在
  │   └─ 是 → 返回缓存的内容 ✓
  │
  ├─ 尝试 LaTeX 提取
  │   ├─ 下载 LaTeX 源码 (.tar.gz)
  │   ├─ 使用 latex2json 解析
  │   ├─ 转换为 JSON
  │   ├─ 转换为 Markdown
  │   └─ 成功 → 返回 Markdown ✓
  │
  └─ LaTeX 失败 → 尝试 PDF 提取
      ├─ 检查 PDF 文件是否存在
      ├─ 使用 marker-pdf 提取
      └─ 成功 → 返回 Markdown ✓
          失败 → 返回 None ✗
```

## 优势

### LaTeX 提取的优势

1. **速度快**：平均 1 秒完成
2. **质量高**：保留了原始 LaTeX 的结构和公式
3. **可靠性高**：大多数 arXiv 论文都有 LaTeX 源码
4. **资源占用少**：不需要下载大型 ML 模型

### 智能 Fallback

- 自动处理 LaTeX 解析失败的情况
- 无缝切换到 PDF 提取
- 确保最大的成功率

## 常见问题

### Q: LaTeX 提取失败怎么办？

A: 系统会自动尝试 PDF 提取。如果两者都失败，检查：
- 论文 ID 是否正确
- 网络连接是否正常
- PDF 文件是否存在于指定目录

### Q: 为什么不直接使用 PDF？

A: LaTeX 提取有以下优势：
- 速度快 100+ 倍
- 质量更高（保留原始结构）
- 公式和表格处理更准确

### Q: 可以禁用 PDF fallback 吗？

A: 可以，不安装 marker-pdf 即可：
```bash
uv sync  # 不加 --extra marker
```

### Q: 如何调整超时时间？

A: 在初始化时指定：
```python
extractor = PaperExtractor(
    latex_timeout=60,   # LaTeX 处理超时（秒）
    marker_timeout=300  # marker-pdf 超时（秒）
)
```

## 测试

运行测试脚本验证功能：

```bash
uv run python script/test_pdf_extractor.py
```

测试包括：
- ✓ LaTeX 提取
- ✓ 缓存机制
- ✓ 批量处理
- ⚠ PDF fallback（跳过以节省时间）

## 性能建议

1. **优先使用 LaTeX 提取**：快速且质量高
2. **启用缓存**：避免重复处理
3. **批量处理**：使用 `extract_batch()` 而不是循环调用
4. **合理设置超时**：LaTeX 30秒足够，PDF 可能需要 120+ 秒

## 与现有代码集成

### 在 summarize.py 中使用

```python
from script.pdf_extractor import PaperExtractor

# 初始化
extractor = PaperExtractor()

# 在摘要生成前提取 Markdown
arxiv_ids = recommended_df['id'].to_list()
markdowns = extractor.extract_batch(arxiv_ids)

# 后续使用 markdowns 字典进行摘要生成
for arxiv_id, markdown in markdowns.items():
    summary = summarize(markdown, ...)
```

## 目录结构

```
arxiv/
├── latex/          # LaTeX 源码 (.tar.gz)
├── json/           # 中间 JSON 文件
└── markdown/       # 最终 Markdown 文件
```

## 注意事项

1. **latex2json 库的限制**：
   - 某些复杂的 LaTeX 包可能不支持
   - 遇到错误时会自动回退到 PDF

2. **marker-pdf 的限制**：
   - 需要下载大型 ML 模型（首次使用）
   - 处理速度慢
   - 可能无法完美处理复杂布局

3. **网络依赖**：
   - LaTeX 源码需要从 arXiv 下载
   - 首次使用确保网络连接正常

## 相关文件

- `script/pdf_extractor.py` - 主要提取器模块
- `script/json2md.py` - JSON 到 Markdown 转换器
- `script/test_pdf_extractor.py` - 测试脚本
- `pyproject.toml` - 依赖配置

## 参考项目

- [latex2json](https://github.com/mrlooi/latex2json) - LaTeX 解析库
- [marker-pdf](https://github.com/VikParuchuri/marker) - PDF 提取库
- [PaperDigestAction](../reference/PaperDigestAction) - 参考实现
