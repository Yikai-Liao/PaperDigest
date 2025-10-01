#!/bin/bash
# 修复 marker-pdf 1.10.1 输出目录结构

OUTPUT_DIR="${1:-./extracted_mds}"

echo "修复 marker 输出目录结构: $OUTPUT_DIR"

# 移动 .md 文件到顶层
for subdir in "$OUTPUT_DIR"/*/; do
    if [ -d "$subdir" ]; then
        for md in "$subdir"*.md; do
            [ -f "$md" ] && mv "$md" "$OUTPUT_DIR/" && echo "  移动: $(basename "$md")"
        done
    fi
done

# 清理空子目录
find "$OUTPUT_DIR" -mindepth 1 -type d -empty -delete 2>/dev/null

#统计结果
md_count=$(find "$OUTPUT_DIR" -maxdepth 1 -name "*.md" -type f | wc -l)
echo "完成! 顶层目录有 $md_count 个 Markdown 文件"
