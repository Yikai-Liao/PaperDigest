#!/usr/bin/env python3
"""
Dry run test for the paper recommendation pipeline.
Tests the full pipeline without uploading results.
"""

import sys
import os
from pathlib import Path
from loguru import logger

# Add script directory to path
REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "script"))

logger.info("=" * 80)
logger.info("Paper Recommendation Pipeline - DRY RUN")
logger.info("=" * 80)

# Step 1: Run prediction model
logger.info("\n[Step 1/3] Running prediction model (fit_predict.py)...")
try:
    import fit_predict
    logger.success("✓ fit_predict.py completed successfully")
except Exception as e:
    logger.error(f"✗ fit_predict.py failed: {str(e)}")
    sys.exit(1)

# Step 2: Download PDFs
logger.info("\n[Step 2/3] Downloading PDFs (download_pdf.py)...")
try:
    import download_pdf
    logger.success("✓ download_pdf.py completed successfully")
except Exception as e:
    logger.error(f"✗ download_pdf.py failed: {str(e)}")
    sys.exit(1)

# Step 3: Check if we have PDFs to process
pdf_dir = REPO_ROOT / "pdfs"
pdf_files = list(pdf_dir.glob("*.pdf")) if pdf_dir.exists() else []
logger.info(f"Found {len(pdf_files)} PDF files to process")

if len(pdf_files) == 0:
    logger.warning("No PDF files found. Skipping extraction and summarization.")
    logger.info("\n" + "=" * 80)
    logger.info("DRY RUN COMPLETED - No papers to process")
    logger.info("=" * 80)
    sys.exit(0)

# Step 3a: Extract text from PDFs (using marker-pdf)
logger.info("\n[Step 3/3] Extracting text from PDFs...")
logger.info("Note: This step requires marker-pdf to be installed.")
logger.info("Run: pip install marker-pdf")

# Check if marker is available
import shutil
if not shutil.which("marker"):
    logger.warning("marker-pdf is not installed. Skipping PDF extraction.")
    logger.info("To install: pip install marker-pdf")
else:
    # Run marker on a subset of PDFs for testing
    test_pdf_count = min(2, len(pdf_files))
    logger.info(f"Processing {test_pdf_count} PDFs as a test (out of {len(pdf_files)} total)")
    
    import subprocess
    extracted_dir = REPO_ROOT / "extracted_mds_test"
    extracted_dir.mkdir(exist_ok=True)
    
    for i, pdf_file in enumerate(pdf_files[:test_pdf_count]):
        logger.info(f"Processing {i+1}/{test_pdf_count}: {pdf_file.name}")
        try:
            result = subprocess.run(
                ["marker", str(pdf_file), "--disable_image_extraction", "--output_dir", str(extracted_dir)],
                capture_output=True,
                text=True,
                timeout=120
            )
            if result.returncode == 0:
                logger.success(f"✓ Extracted {pdf_file.name}")
            else:
                logger.error(f"✗ Failed to extract {pdf_file.name}: {result.stderr}")
        except subprocess.TimeoutExpired:
            logger.error(f"✗ Timeout extracting {pdf_file.name}")
        except Exception as e:
            logger.error(f"✗ Error extracting {pdf_file.name}: {str(e)}")
    
    # Check extracted markdown files
    md_files = list(extracted_dir.glob("**/*.md"))
    logger.info(f"Extracted {len(md_files)} markdown files")
    
    if len(md_files) > 0:
        # Step 3b: Test summarization with Gemini
        logger.info("\n[Step 3b/3] Testing summarization with Gemini...")
        logger.info("Note: This requires SUMMARY_API_KEY environment variable to be set")
        
        api_key = os.getenv("SUMMARY_API_KEY")
        if not api_key:
            logger.warning("SUMMARY_API_KEY not set. Skipping summarization test.")
            logger.info("To test summarization, set your Gemini API key:")
            logger.info("export SUMMARY_API_KEY='your-api-key-here'")
        else:
            # Test with the first markdown file
            test_md = md_files[0]
            logger.info(f"Testing summarization on: {test_md.name}")
            
            try:
                # Import after adding to path
                from summarize import summarize
                import toml
                import json
                
                config = toml.load(REPO_ROOT / "config.toml")['summary']
                example = (REPO_ROOT / "examples" / "summary_example_zh.json").read_text(encoding='utf-8')
                
                with open(REPO_ROOT / "config" / "keywords.json", 'r', encoding='utf-8') as f:
                    keywords = json.load(f)
                
                result = summarize(
                    paper_path=test_md,
                    example=example,
                    api_key=api_key,
                    base_url=config['base_url'],
                    model=config['model'],
                    temperature=config['temperature'],
                    top_p=config['top_p'],
                    reasoning_effort=config.get('reasoning_effort'),
                    lang='zh',
                    keywords=keywords
                )
                
                if 'error' in result:
                    logger.error(f"✗ Summarization failed: {result['error']}")
                else:
                    logger.success(f"✓ Summarization completed successfully")
                    logger.info(f"Summary preview: {result.get('one_sentence_summary', 'N/A')[:100]}...")
                    
                    # Save test result
                    test_output = extracted_dir / f"{test_md.stem}_summary.json"
                    with open(test_output, 'w', encoding='utf-8') as f:
                        json.dump(result, f, ensure_ascii=False, indent=4)
                    logger.info(f"Test summary saved to: {test_output}")
                    
            except Exception as e:
                logger.error(f"✗ Summarization test failed: {str(e)}")
                import traceback
                logger.debug(traceback.format_exc())

logger.info("\n" + "=" * 80)
logger.info("DRY RUN COMPLETED")
logger.info("=" * 80)
logger.info("\nNext steps:")
logger.info("1. Review the test results in ./extracted_mds_test/")
logger.info("2. If everything looks good, you can:")
logger.info("   - Set use_batch_api = true in config.toml for production (50% cost savings)")
logger.info("   - Run the full pipeline with all papers")
logger.info("3. For batch API, expect 24h turnaround time but significant cost savings")
logger.info("\nCost comparison:")
logger.info("- Direct API: Standard rate")
logger.info("- Batch API: 50% of standard rate")
logger.info(f"- Your current setting: use_batch_api = {config.get('use_batch_api', False)}")
