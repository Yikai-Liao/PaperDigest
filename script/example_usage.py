"""
示例：在摘要生成流程中使用 pdf_extractor

这个脚本展示了如何将 pdf_extractor 集成到现有的摘要生成流程中
"""
from pathlib import Path
from loguru import logger
import polars as pl

# 假设我们有推荐的论文数据
def create_sample_data():
    """创建示例数据模拟推荐结果"""
    return pl.DataFrame({
        'id': ['2509.04027', '2509.18405', '2509.20138'],
        'title': [
            'CoT-Space: A Theoretical Framework',
            'Another Paper Title',
            'Third Paper Title'
        ],
        'show': [1, 1, 1]
    })


def main():
    """主流程：从 PDF/LaTeX 提取到摘要生成"""
    
    # 步骤 1: 获取推荐的论文
    logger.info("Step 1: Load recommended papers")
    recommended_df = create_sample_data()
    logger.info(f"  Found {len(recommended_df)} papers to process")
    
    # 步骤 2: 提取论文内容（优先 LaTeX，失败时用 PDF）
    logger.info("\nStep 2: Extract paper content")
    logger.info("  Using LaTeX extraction (fast) with PDF fallback (slow)")
    
    from pdf_extractor import PaperExtractor
    
    extractor = PaperExtractor(
        latex_dir=Path("arxiv/latex"),
        json_dir=Path("arxiv/json"),
        markdown_dir=Path("arxiv/markdown"),
        pdf_dir=Path("pdfs")
    )
    
    arxiv_ids = recommended_df['id'].to_list()
    markdowns = extractor.extract_batch(arxiv_ids)
    
    logger.success(f"  ✓ Successfully extracted {len(markdowns)}/{len(arxiv_ids)} papers")
    
    # 步骤 3: 生成摘要（这里只是示例，不实际调用 API）
    logger.info("\nStep 3: Generate summaries")
    logger.info("  (Skipped in this demo - would call OpenAI/Gemini API)")
    
    summaries = []
    for arxiv_id, markdown_content in markdowns.items():
        logger.info(f"  - {arxiv_id}: {len(markdown_content)} chars")
        
        # 实际使用时，这里会调用摘要 API
        # summary = summarize_with_api(markdown_content, ...)
        # summaries.append(summary)
    
    # 步骤 4: 保存结果
    logger.info("\nStep 4: Save results")
    logger.info("  (Skipped in this demo - would save to JSON/database)")
    
    # 步骤 5: 总结统计
    logger.info("\n" + "=" * 80)
    logger.info("Processing Summary")
    logger.info("=" * 80)
    
    total_requested = len(arxiv_ids)
    total_extracted = len(markdowns)
    extraction_rate = (total_extracted / total_requested) * 100
    
    logger.info(f"Requested papers: {total_requested}")
    logger.info(f"Successfully extracted: {total_extracted}")
    logger.info(f"Extraction rate: {extraction_rate:.1f}%")
    
    if total_extracted < total_requested:
        failed_ids = set(arxiv_ids) - set(markdowns.keys())
        logger.warning(f"Failed papers: {failed_ids}")
        logger.info("Tip: Check network connection and PDF availability")
    
    logger.info("\n💡 Performance Tips:")
    logger.info("  1. LaTeX extraction is 100x faster than PDF")
    logger.info("  2. Enable caching to avoid reprocessing")
    logger.info("  3. Use batch processing for multiple papers")
    logger.info("  4. Consider running PDF fallback in parallel if needed")


if __name__ == "__main__":
    main()
