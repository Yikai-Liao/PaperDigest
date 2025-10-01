# Marker PDF 输出目录结构修复 - 快速指南

## 🎯 问题

GitHub Action 中 marker-pdf 看起来"卡住",实际是 **marker-pdf 1.10.1 改变了输出目录结构**,导致找不到生成的 Markdown 文件。

## ⚡ 快速修复

在你的 GitHub Action workflow 中,**marker 命令后添加一行**:

```yaml
# 运行 marker
uv run marker "$BATCH_DIR" --disable_image_extraction --output_dir ./extracted_mds --workers 1

# 🔧 添加这一行修复输出结构
bash script/fix_marker_output.sh ./extracted_mds

# 统计结果
md_count=$(find ./extracted_mds -maxdepth 1 -name "*.md" -type f | wc -l)
echo "✅ 成功提取了 $md_count 个 Markdown 文件"
```

就这么简单!

## 📝 完整修改示例

**修改前** (找不到文件):
```yaml
- name: Extract PDFs
  run: |
    uv run marker pdf_batches/batch_1 \
      --disable_image_extraction \
      --output_dir ./extracted_mds \
      --workers 1
    
    md_count=$(find ./extracted_mds -name "*.md" | wc -l)  # ← 返回 0
    echo "成功提取了 $md_count 个 Markdown 文件"
```

**修改后** (正常工作):
```yaml
- name: Extract PDFs
  run: |
    uv run marker pdf_batches/batch_1 \
      --disable_image_extraction \
      --output_dir ./extracted_mds \
      --workers 1
    
    # 🔧 修复输出结构
    bash script/fix_marker_output.sh ./extracted_mds
    
    md_count=$(find ./extracted_mds -maxdepth 1 -name "*.md" -type f | wc -l)
    echo "✅ 成功提取了 $md_count 个 Markdown 文件"
```

## ✅ 验证

本地测试已完全验证:

```bash
$ bash script/fix_marker_output.sh extracted_mds_test_final
修复 marker 输出目录结构: extracted_mds_test_final
  移动: 2201.06379.md
  移动: 2206.14263.md
  移动: 2506.05530.md
  移动: 2509.22566.md
完成! 顶层目录有 4 个 Markdown 文件
```

## 📂 生成的文件

| 文件 | 说明 |
|------|------|
| `script/fix_marker_output.sh` | ⭐ 修复脚本 (在 GitHub Action 中使用) |
| `script/test_marker_simple.py` | 测试脚本 (复现问题) |
| `script/test_marker_quick_fix.py` | 验证脚本 (验证修复) |
| `docs/MARKER_FIX_FINAL_SOLUTION.md` | ⭐ 最终解决方案 (详细说明) |
| `docs/MARKER_OUTPUT_STRUCTURE_FIX.md` | 详细分析 |
| `docs/GITHUB_ACTION_MARKER_FIX_COMPLETE_REPORT.md` | 完整诊断报告 |

## 🚀 下一步

1. **更新 GitHub Action workflow 文件**  
   在 marker 命令后添加: `bash script/fix_marker_output.sh ./extracted_mds`

2. **提交并推送**
   ```bash
   git add script/fix_marker_output.sh .github/workflows/*.yml
   git commit -m "fix: 修复 marker-pdf 1.10.1 输出目录结构问题"
   git push
   ```

3. **触发 Action 并验证**  
   检查日志,应该能看到 "✅ 成功提取了 N 个 Markdown 文件"

## 📖 更多信息

查看 [MARKER_FIX_FINAL_SOLUTION.md](./MARKER_FIX_FINAL_SOLUTION.md) 获取完整说明。

---

**问题已解决!** 🎉
