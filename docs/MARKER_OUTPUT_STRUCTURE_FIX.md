# Marker PDF 输出目录结构变化问题诊断报告

## 问题描述

GitHub Action 中 marker-pdf 处理看起来"卡住不动",实际上是**已经成功处理完成,但输出文件位置改变了**。

## 根本原因

**marker-pdf 1.10.1 的输出目录结构发生了变化:**

### 旧版本行为 (预期)
```
extracted_mds/
├── paper1.md
├── paper2.md
└── paper3.md
```

### 新版本行为 (实际)
```
extracted_mds/
├── paper1/
│   ├── paper1.md
│   └── paper1_meta.json
├── paper2/
│   ├── paper2.md
│   └── paper2_meta.json
└── paper3/
    ├── paper3.md
    └── paper3_meta.json
```

**每个 PDF 生成一个子目录,Markdown 文件在子目录中。**

## 测试结果

### 本地测试复现问题

```bash
$ cd /home/lyk/code/PaperDigest
$ uv run python script/test_marker_simple.py

# marker 成功处理了 4 个 PDF，耗时 402 秒
Processing PDFs: 100%|██████████| 4/4 [06:37<00:00, 99.35s/pdf]
Inferenced 83 pages in 397.51 seconds
命令执行完成，耗时: 402.30 秒，返回码: 0

# 但查找 *.md 文件时找不到（因为在子目录中）
成功提取了 0 个 Markdown 文件
```

### 实际输出结构

```bash
$ ls extracted_mds_test/
2201.06379/  2206.14263/  2506.05530/  2509.22566/

$ ls extracted_mds_test/2201.06379/
2201.06379.md  2201.06379_meta.json  # ← Markdown 在这里!
```

## 解决方案

### 方案1: 修改查找方式 (推荐)

更新 GitHub Action 脚本,递归查找 Markdown 文件:

```bash
# 旧的统计方式（找不到文件）
md_count=$(find ./extracted_mds -name "*.md" | wc -l)

# 新的统计方式（递归查找）
md_count=$(find ./extracted_mds -name "*.md" -type f | wc -l)

# 或者只在一级子目录中查找
md_count=$(find ./extracted_mds/*/ -name "*.md" -type f 2>/dev/null | wc -l)
```

### 方案2: 移动文件到父目录

在处理后将 Markdown 文件移到顶层:

```bash
# 处理完成后，移动所有 .md 文件到输出目录
for dir in ./extracted_mds/*/; do
    if [ -d "$dir" ]; then
        mv "$dir"/*.md ./extracted_mds/ 2>/dev/null || true
    fi
done

# 然后统计
md_count=$(find ./extracted_mds -maxdepth 1 -name "*.md" -type f | wc -l)
```

### 方案3: 使用 marker 的输出格式选项

检查是否有选项可以控制输出格式（需要查看文档）:

```bash
marker --help | grep -i output
# 可能有 --flat_output 或类似选项
```

## GitHub Action 修复建议

更新 `.github/workflows/xxx.yml`:

```yaml
- name: Extract PDFs to Markdown
  run: |
    # 创建输出目录
    mkdir -p extracted_mds
    
    # 获取当前批次
    BATCH_DIR="pdf_batches/batch_1"
    echo "处理批次目录: $BATCH_DIR"
    
    # 检查目录中的文件数量
    pdf_count=$(find "$BATCH_DIR" -name "*.pdf" | wc -l)
    echo "该批次包含 $pdf_count 个 PDF 文件"
    
    if [ $pdf_count -gt 0 ]; then
      # 使用 marker 处理整个目录
      uv run marker "$BATCH_DIR" \
        --disable_image_extraction \
        --output_dir ./extracted_mds \
        --workers 1
      
      # ⭐️ 新增: 将子目录中的 .md 文件移到顶层 ⭐️
      echo "移动 Markdown 文件到输出目录顶层..."
      for subdir in ./extracted_mds/*/; do
        if [ -d "$subdir" ]; then
          # 移动 .md 文件，保持原文件名
          find "$subdir" -maxdepth 1 -name "*.md" -type f -exec mv {} ./extracted_mds/ \;
        fi
      done
      
      # 清理空的子目录（可选）
      find ./extracted_mds -mindepth 1 -type d -empty -delete
      
      # 统计处理结果（现在应该能找到了）
      md_count=$(find ./extracted_mds -maxdepth 1 -name "*.md" -type f | wc -l)
      echo "成功提取了 $md_count 个 Markdown 文件"
      
      # 列出生成的文件
      echo "生成的 Markdown 文件:"
      ls -lh ./extracted_mds/*.md
    else
      echo "该批次没有 PDF 文件，跳过处理"
    fi
```

## 为什么 GitHub Action 看起来"卡住"?

1. **marker 实际上已经成功运行完成**
2. **但后续的统计脚本找不到 .md 文件** (因为在子目录中)
3. **工作流可能在等待文件出现或后续步骤失败**
4. **从日志看,模型下载和处理都完成了,只是文件组织方式变了**

## 验证修复

本地测试修复后的脚本:

```bash
# 1. 运行测试生成输出
cd /home/lyk/code/PaperDigest
uv run python script/test_marker_simple.py

# 2. 手动执行移动操作
for subdir in extracted_mds_test/*/; do
    if [ -d "$subdir" ]; then
        find "$subdir" -maxdepth 1 -name "*.md" -type f -exec mv {} extracted_mds_test/ \;
    fi
done

# 3. 验证文件
ls -lh extracted_mds_test/*.md
# 应该看到:
# extracted_mds_test/2201.06379.md
# extracted_mds_test/2206.14263.md
# extracted_mds_test/2506.05530.md
# extracted_mds_test/2509.22566.md
```

## 关键发现

✅ **marker 没有卡住,它正常完成了处理**  
✅ **问题在于输出目录结构变化**  
✅ **marker-pdf 1.10.1 现在为每个 PDF 创建子目录**  
⚠️ **需要更新 GitHub Action 脚本适应新的目录结构**

## 建议操作

1. **立即修复**: 在 GitHub Action 中添加文件移动步骤
2. **长期方案**: 考虑切换到我们的 latex2json + marker fallback 方案（更快、更可靠）
3. **监控**: 添加更详细的日志,显示实际生成的文件位置

## 性能数据

本地测试(4个PDF):
- 处理时间: 402秒 (~6.7分钟)
- 页数: 83页
- 吞吐量: 0.21 页/秒
- 每个PDF平均: 100秒

这个速度在预期范围内,并非性能问题。
