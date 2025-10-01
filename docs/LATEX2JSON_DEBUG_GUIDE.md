# LaTeX2JSON 本地调试指南

## 背景

latex2json 库经过重构，调用方式与之前不同。本指南展示如何在本地进行调试。

## 当前实现的调用方式

### 正确的调用流程

```python
from latex2json import TexReader

# 1. 初始化 TexReader
tex_reader = TexReader()

# 2. 处理 LaTeX 源码文件
# 支持：单文件、文件夹、压缩包 (.tar.gz, .gz, .zip)
result = tex_reader.process("path/to/file.tar.gz", cleanup=False)

# 3. 转换为 JSON 字符串
json_str = tex_reader.to_json(result, merge_inline_tokens=True)

# 4. 解析 JSON 并转换为 Markdown
import json
from script.json2md import json_to_markdown

structured_data = json.loads(json_str)
markdown = json_to_markdown(structured_data, ignore_reference=True)
```

### 实际集成代码

查看 `script/pdf_extractor.py` 中的实现：

```python
def _extract_from_latex(self, arxiv_id: str, save_intermediate: bool):
    """Extract content from LaTeX source."""
    
    # 下载 LaTeX 源码
    latex_tar_gz_file = self.latex_dir / f"{arxiv_id}.tar.gz"
    self._download_latex_source(arxiv_id, latex_tar_gz_file)
    
    # 处理 LaTeX
    result = self.tex_reader.process(str(latex_tar_gz_file), cleanup=False)
    json_output_str = self.tex_reader.to_json(result, merge_inline_tokens=True)
    
    # 转为 Markdown
    structured_data = json.loads(json_output_str)
    markdown = json_to_markdown(structured_data, ignore_reference=True)
    
    return markdown
```

## 本地调试步骤

### 1. 准备测试环境

```bash
# 安装依赖
cd /home/lyk/code/PaperDigest
uv sync

# 确认 latex2json 安装成功
uv run python -c "from latex2json import TexReader; print('✓ latex2json installed')"
```

### 2. 下载测试论文

```bash
# 下载一个测试论文的 LaTeX 源码
arxiv_id="2509.04027"
wget "https://arxiv.org/e-print/${arxiv_id}" -O "test_${arxiv_id}.tar.gz"
```

### 3. 创建调试脚本

创建 `test_latex_debug.py`：

```python
from latex2json import TexReader
from pathlib import Path
import json
import sys

def test_latex_processing(latex_file):
    """Test LaTeX processing with detailed logging."""
    
    print(f"Testing file: {latex_file}")
    print("-" * 80)
    
    # Step 1: Initialize
    print("Step 1: Initializing TexReader...")
    tex_reader = TexReader()
    print("  ✓ TexReader initialized")
    
    # Step 2: Process
    print("\nStep 2: Processing LaTeX file...")
    try:
        result = tex_reader.process(str(latex_file), cleanup=False)
        print(f"  ✓ Processing complete")
        print(f"  - Type: {type(result)}")
        if hasattr(result, 'tokens'):
            print(f"  - Token count: {len(result.tokens)}")
    except Exception as e:
        print(f"  ✗ Processing failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # Step 3: Convert to JSON
    print("\nStep 3: Converting to JSON...")
    try:
        json_str = tex_reader.to_json(result, merge_inline_tokens=True)
        print(f"  ✓ JSON conversion complete")
        print(f"  - JSON length: {len(json_str)} chars")
        
        # Parse to verify
        data = json.loads(json_str)
        print(f"  - JSON structure valid")
        print(f"  - Top-level keys: {list(data.keys())}")
    except Exception as e:
        print(f"  ✗ JSON conversion failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # Step 4: Convert to Markdown (optional)
    print("\nStep 4: Converting to Markdown...")
    try:
        from json2md import json_to_markdown
        markdown = json_to_markdown(data, ignore_reference=True)
        print(f"  ✓ Markdown conversion complete")
        print(f"  - Markdown length: {len(markdown)} chars")
        print(f"  - First 200 chars:\n{markdown[:200]}")
    except Exception as e:
        print(f"  ✗ Markdown conversion failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    print("\n" + "=" * 80)
    print("✓ All steps completed successfully!")
    return True

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python test_latex_debug.py <path_to_latex_file>")
        sys.exit(1)
    
    latex_file = Path(sys.argv[1])
    if not latex_file.exists():
        print(f"Error: File not found: {latex_file}")
        sys.exit(1)
    
    success = test_latex_processing(latex_file)
    sys.exit(0 if success else 1)
```

### 4. 运行调试

```bash
# 测试下载的论文
uv run python test_latex_debug.py test_2509.04027.tar.gz

# 或使用 pdf_extractor 的测试
uv run python script/pdf_extractor.py 2509.04027
```

## 常见问题

### Q1: 如何查看 latex2json 的详细日志？

```python
import logging

# 启用 latex2json 的详细日志
logging.getLogger('latex2json').setLevel(logging.DEBUG)
logging.getLogger('latex2json.tex_reader').setLevel(logging.DEBUG)
```

### Q2: 如何处理超时？

```python
import signal

def timeout_handler(signum, frame):
    raise TimeoutError("Processing timeout")

# 设置 30 秒超时
signal.signal(signal.SIGALRM, timeout_handler)
signal.alarm(30)

try:
    result = tex_reader.process(file)
finally:
    signal.alarm(0)  # 取消超时
```

### Q3: 如何查看中间结果？

```python
# 查看 ProcessingResult
result = tex_reader.process(file)
print(f"Tokens: {len(result.tokens)}")
print(f"Colors: {result.color_map}")
print(f"Main tex: {result.main_tex_path}")

# 查看 JSON 结构
json_str = tex_reader.to_json(result)
data = json.loads(json_str)

# 美化输出
import json
print(json.dumps(data, indent=2)[:1000])  # 前 1000 字符
```

### Q4: latex2json 失败时如何调试？

1. **检查错误类型**：
   ```python
   try:
       result = tex_reader.process(file)
   except Exception as e:
       print(f"Error type: {type(e).__name__}")
       print(f"Error message: {str(e)}")
       import traceback
       traceback.print_exc()
   ```

2. **保存中间文件**：
   ```python
   # 保存 JSON 用于后续调试
   with open('debug_output.json', 'w') as f:
       f.write(json_str)
   ```

3. **尝试单独的 .tex 文件**：
   ```python
   # 如果 .tar.gz 失败，尝试提取后单独处理
   import tarfile
   with tarfile.open(latex_file) as tar:
       tar.extractall('temp_latex')
   
   # 找到主文件
   main_tex = Path('temp_latex/main.tex')
   result = tex_reader.process(main_tex)
   ```

## 已知的 latex2json Bug

### Bug 1: 正则表达式错误

**错误信息**：
```
re.error: bad escape \l at position 4
```

**原因**：某些 LaTeX 文件定义了特殊的命令名（如 `\l`），在编译正则表达式时失败。

**解决方案**：这是 latex2json 库的 bug，需要在上游修复。暂时使用 PDF fallback。

**受影响论文示例**：
- 2509.20138

### Bug 2: 复杂宏定义解析失败

**症状**：某些使用高级宏定义的论文无法解析。

**临时解决方案**：
1. 使用 PDF fallback
2. 或尝试简化 LaTeX 文件后再处理

## 性能优化建议

### 1. 批量处理

```python
# 好：批量处理多个文件
results = {}
for arxiv_id in arxiv_ids:
    result = tex_reader.process(file)
    results[arxiv_id] = result

# 差：每次重新初始化
for arxiv_id in arxiv_ids:
    tex_reader = TexReader()  # 重复初始化开销大
    result = tex_reader.process(file)
```

### 2. 禁用详细日志

```python
# 生产环境禁用详细日志以提升性能
import logging
logging.getLogger('latex2json').setLevel(logging.ERROR)
logging.getLogger('chardet').setLevel(logging.ERROR)
```

### 3. 合理设置超时

```python
# 根据论文复杂度调整超时
# 简单论文: 5-10 秒
# 复杂论文: 20-30 秒
# 极复杂论文: 60 秒

signal.alarm(30)  # 30 秒超时通常足够
```

## 参考资源

- [latex2json GitHub](https://github.com/mrlooi/latex2json)
- [latex2json 文档](https://github.com/mrlooi/latex2json/blob/main/README.md)
- [PaperDigestAction 参考实现](../reference/PaperDigestAction/src/summarize.py)
- [pdf_extractor.py 实现](../script/pdf_extractor.py)

## 贡献修复

如果你发现 latex2json 的 bug 并修复了它，请考虑：

1. **提交 Issue**：在 latex2json 仓库报告问题
2. **提交 PR**：贡献修复代码
3. **本地 Fork**：临时使用修复版本
   ```toml
   [project]
   dependencies = [
       "latex2json @ git+https://github.com/your-fork/latex2json.git@fix-branch",
   ]
   ```

## 总结

latex2json 是一个功能强大但仍在发展中的库。通过：
- ✅ 正确的调用方式
- ✅ 完善的错误处理
- ✅ PDF fallback 机制
- ✅ 详细的日志记录

我们可以在生产环境中稳定使用它，同时处理各种边缘情况。

---

**更新日期**: 2025-10-01  
**测试版本**: latex2json 0.5.0  
**Python 版本**: 3.12+
