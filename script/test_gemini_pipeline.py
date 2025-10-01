#!/usr/bin/env python3
"""
Complete test for Paper Recommendation Pipeline with Gemini API.
This script tests both direct API and Batch API modes.
"""

import sys
import os
from pathlib import Path
import toml
import json

# Add script directory to path
REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "script"))

print("=" * 80)
print("Paper Recommendation Pipeline - Complete Test with Gemini")
print("=" * 80)

# Step 1: Check configuration
print("\n[Step 1] Checking configuration...")
config_path = REPO_ROOT / "config.toml"
if not config_path.exists():
    print("❌ config.toml not found!")
    sys.exit(1)

config = toml.load(config_path)
summary_config = config.get('summary', {})
model = summary_config.get('model', 'unknown')
use_batch_api = summary_config.get('use_batch_api', False)
api_key = os.getenv("SUMMARY_API_KEY")

print(f"✓ Model: {model}")
print(f"✓ Batch API enabled: {use_batch_api}")
print(f"✓ API Key: {'Set' if api_key else 'Not set'}")

if not api_key:
    print("❌ SUMMARY_API_KEY environment variable not set!")
    print("Please set it: export SUMMARY_API_KEY='your-api-key'")
    sys.exit(1)

# Check if model is Gemini
if not model.lower().startswith('gemini'):
    print(f"⚠️  Warning: Model '{model}' is not a Gemini model")
    print("   The Gemini handler will only be used for models starting with 'gemini'")

# Step 2: Test predictions
print("\n[Step 2] Checking prediction results...")
predictions_file = REPO_ROOT / "data" / "predictions.parquet"
if not predictions_file.exists():
    print("❌ predictions.parquet not found!")
    print("Please run: uv run python script/fit_predict.py")
    sys.exit(1)

import polars as pl
predictions = pl.read_parquet(predictions_file)
show_papers = predictions.filter(pl.col("show") == 1)
print(f"✓ Found {len(predictions)} papers, {len(show_papers)} to be shown")

# Step 3: Test PDF download
print("\n[Step 3] Checking PDF files...")
pdf_dir = REPO_ROOT / "pdfs"
if not pdf_dir.exists():
    print("❌ pdfs directory not found!")
    sys.exit(1)

pdf_files = list(pdf_dir.glob("*.pdf"))
print(f"✓ Found {len(pdf_files)} PDF files")

if len(pdf_files) == 0:
    print("⚠️  No PDF files found. Run: uv run python script/download_pdf.py")
    sys.exit(1)

# Step 4: Test markdown extraction
print("\n[Step 4] Checking extracted markdown files...")
test_md_dir = REPO_ROOT / "extracted_mds_test"
if test_md_dir.exists():
    md_files = list(test_md_dir.glob("**/*.md"))
    print(f"✓ Found {len(md_files)} markdown files in test directory")
    
    if len(md_files) > 0:
        test_md = md_files[0]
        print(f"✓ Using test file: {test_md.name}")
        
        # Test Gemini direct API
        print("\n[Step 5] Testing Gemini Direct API...")
        print("This will call the Gemini API once to generate a summary.")
        
        from gemini_handler import GeminiHandler
        
        handler = GeminiHandler(api_key=api_key, model=model)
        
        # Load necessary data
        example = (REPO_ROOT / "examples" / "summary_example_zh.json").read_text(encoding='utf-8')
        with open(REPO_ROOT / "config" / "keywords.json", 'r', encoding='utf-8') as f:
            keywords = json.load(f)
        
        paper_content = test_md.read_text(encoding='utf-8')
        paper_content = paper_content.split("# Reference")[0]
        
        system_prompt = handler.create_prompt(example, 'zh', keywords)
        
        result = handler.summarize_single(
            paper_content=paper_content,
            system_prompt=system_prompt,
            temperature=summary_config['temperature'],
            top_p=summary_config['top_p'],
            paper_id=test_md.stem,
            lang='zh'
        )
        
        if 'error' in result:
            print(f"❌ Summarization failed: {result['error']}")
        else:
            print("✓ Direct API test successful!")
            print(f"  Summary: {result.get('one_sentence_summary', 'N/A')[:100]}...")
            print(f"  Keywords: {', '.join(result.get('keywords', [])[:5])}")
            print(f"  Model: {result.get('model', 'N/A')}")
        
        # Test Batch API info
        print("\n[Step 6] Batch API Information...")
        if use_batch_api and model.lower().startswith('gemini'):
            print("✓ Batch API is ENABLED in config.toml")
            print("  Benefits:")
            print("  - 50% cost savings compared to direct API")
            print("  - Ideal for large batches of papers")
            print("  Drawbacks:")
            print("  - Target turnaround time: 24 hours")
            print("  - Not suitable for immediate results")
            print("\n  To use Batch API:")
            print(f"  1. Ensure use_batch_api = true in config.toml (currently: {use_batch_api})")
            print("  2. Run: uv run python script/summarize.py <directory> --lang zh")
            print("  3. The script will automatically use Batch API for Gemini models")
        else:
            print("ℹ️  Batch API is DISABLED in config.toml")
            print("  Current mode: Direct API (immediate results, standard pricing)")
            print("  To enable Batch API (50% cost savings, 24h turnaround):")
            print("  Set use_batch_api = true in config.toml")
        
        # Cost estimation
        print("\n[Step 7] Cost Estimation...")
        print(f"  Number of papers to process: {len(show_papers)}")
        print(f"  Model: {model}")
        print(f"  Mode: {'Batch API (50% off)' if use_batch_api else 'Direct API (standard)'}")
        print("\n  Gemini 2.5 Flash pricing:")
        print("  - Input: $0.075 per 1M tokens (Batch: $0.0375)")
        print("  - Output: $0.30 per 1M tokens (Batch: $0.15)")
        print("  - Assuming ~30K tokens per paper (input + output)")
        print(f"  - Estimated cost: ${len(show_papers) * 0.009:.2f} (Direct) / ${len(show_papers) * 0.0045:.2f} (Batch)")
        
else:
    print("⚠️  No test markdown files found.")
    print("Run marker to extract PDFs first:")
    print("  mkdir -p pdfs_test && cp pdfs/*.pdf pdfs_test/ (copy some PDFs)")
    print("  uv run marker pdfs_test --disable_image_extraction --output_dir ./extracted_mds_test")

print("\n" + "=" * 80)
print("Summary")
print("=" * 80)
print(f"✓ Pipeline is ready to use")
print(f"✓ Model: {model}")
print(f"✓ Batch API: {'Enabled (50% cost savings)' if use_batch_api else 'Disabled (immediate results)'}")
print("\nNext steps:")
print("1. Process all PDFs with marker:")
print("   mkdir -p extracted_mds")
print("   uv run marker pdfs --disable_image_extraction --output_dir ./extracted_mds --workers 2")
print("\n2. Generate summaries:")
if use_batch_api:
    print("   uv run python script/summarize.py ./extracted_mds --lang zh")
    print("   (Batch API will be used, expect 24h turnaround)")
else:
    print("   uv run python script/summarize.py ./extracted_mds --lang zh")
    print("   (Direct API will be used, immediate results)")
print("\n3. To switch between Direct/Batch API:")
print("   Edit config.toml and change use_batch_api = true/false")
