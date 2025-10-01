"""
PDF/LaTeX to Markdown Extractor
Priority: LaTeX source (via latex2json) -> PDF (via marker-pdf)
"""
import json
import logging
import os
import subprocess
import requests
from pathlib import Path
from typing import Optional, Tuple
from loguru import logger

# Import latex2json components
try:
    from latex2json import TexReader
    LATEX2JSON_AVAILABLE = True
except ImportError:
    LATEX2JSON_AVAILABLE = False
    logger.warning("latex2json not available, will only use marker-pdf")

# Import json2md converter
from json2md import json_to_markdown


class PaperExtractor:
    """Extract paper content to Markdown, trying LaTeX first, then PDF."""
    
    def __init__(
        self, 
        latex_dir: Optional[Path] = None,
        json_dir: Optional[Path] = None,
        markdown_dir: Optional[Path] = None,
        pdf_dir: Optional[Path] = None,
        latex_timeout: int = 30,
        marker_timeout: int = 120,
    ):
        """
        Initialize the extractor.
        
        Args:
            latex_dir: Directory to store downloaded LaTeX source files (.tar.gz)
            json_dir: Directory to store intermediate JSON files
            markdown_dir: Directory to store extracted Markdown files
            pdf_dir: Directory containing PDF files (for fallback)
            latex_timeout: Timeout for LaTeX processing in seconds
            marker_timeout: Timeout for marker-pdf processing in seconds
        """
        self.latex_dir = latex_dir or Path("arxiv/latex")
        self.json_dir = json_dir or Path("arxiv/json")
        self.markdown_dir = markdown_dir or Path("arxiv/markdown")
        self.pdf_dir = pdf_dir or Path("pdfs")
        
        self.latex_timeout = latex_timeout
        self.marker_timeout = marker_timeout
        
        # Create directories
        for d in [self.latex_dir, self.json_dir, self.markdown_dir]:
            d.mkdir(parents=True, exist_ok=True)
        
        # Initialize TexReader if available
        if LATEX2JSON_AVAILABLE:
            self._setup_latex2json_logging()
            self.tex_reader = TexReader()
        else:
            self.tex_reader = None
    
    def _setup_latex2json_logging(self):
        """Suppress verbose logging from latex2json."""
        loggers_to_silence = [
            'latex2json',
            'latex2json.tex_reader', 
            'latex2json.parser',
            'tex_reader',
            'chardet',
            'chardet.charsetgroupprober',
            'chardet.universaldetector',
            'charset_normalizer'
        ]
        
        for logger_name in loggers_to_silence:
            logging.getLogger(logger_name).setLevel(logging.ERROR)
    
    def extract_paper(
        self, 
        arxiv_id: str,
        force_pdf: bool = False,
        save_intermediate: bool = True
    ) -> Tuple[Optional[str], str]:
        """
        Extract paper content to Markdown.
        
        Args:
            arxiv_id: ArXiv paper ID (e.g., "2412.10133")
            force_pdf: If True, skip LaTeX and use PDF directly
            save_intermediate: If True, save intermediate JSON and Markdown files
        
        Returns:
            Tuple of (markdown_content, method_used)
            method_used can be: "latex", "pdf", or "failed"
        """
        markdown_file = self.markdown_dir / f"{arxiv_id}.md"
        
        # Check if markdown already exists
        if markdown_file.exists():
            logger.info(f"Markdown for {arxiv_id} already exists, loading from file")
            try:
                return markdown_file.read_text(encoding='utf-8'), "cached"
            except Exception as e:
                logger.warning(f"Failed to read existing markdown for {arxiv_id}: {e}")
        
        # Try LaTeX extraction first (unless forced to use PDF)
        if not force_pdf and LATEX2JSON_AVAILABLE and self.tex_reader:
            markdown, success = self._extract_from_latex(arxiv_id, save_intermediate)
            if success:
                return markdown, "latex"
            else:
                logger.info(f"LaTeX extraction failed for {arxiv_id}, falling back to PDF")
        
        # Fall back to PDF extraction
        markdown, success = self._extract_from_pdf(arxiv_id, save_intermediate)
        if success:
            return markdown, "pdf"
        
        logger.error(f"All extraction methods failed for {arxiv_id}")
        return None, "failed"
    
    def _extract_from_latex(
        self, 
        arxiv_id: str,
        save_intermediate: bool
    ) -> Tuple[Optional[str], bool]:
        """
        Extract content from LaTeX source.
        
        Returns:
            Tuple of (markdown_content, success)
        """
        logger.info(f"Attempting LaTeX extraction for {arxiv_id}")
        
        latex_tar_gz_file = self.latex_dir / f"{arxiv_id}.tar.gz"
        json_file = self.json_dir / f"{arxiv_id}.json"
        markdown_file = self.markdown_dir / f"{arxiv_id}.md"
        
        # Step 1: Download LaTeX source if not exists
        if not latex_tar_gz_file.exists():
            if not self._download_latex_source(arxiv_id, latex_tar_gz_file):
                return None, False
        
        # Step 2: Convert LaTeX to JSON if not exists
        structured_data = None
        if not json_file.exists():
            try:
                logger.info(f"Processing LaTeX with TexReader: {latex_tar_gz_file}")
                
                # Process with timeout
                import signal
                
                def timeout_handler(signum, frame):
                    raise TimeoutError("LaTeX processing timeout")
                
                # Set timeout
                signal.signal(signal.SIGALRM, timeout_handler)
                signal.alarm(self.latex_timeout)
                
                try:
                    # Process the LaTeX file
                    result = self.tex_reader.process(str(latex_tar_gz_file), cleanup=False)
                    json_output_str = self.tex_reader.to_json(result, merge_inline_tokens=True)
                    
                    # Cancel timeout
                    signal.alarm(0)
                    
                    if save_intermediate:
                        with open(json_file, 'w', encoding='utf-8') as f:
                            f.write(json_output_str)
                        logger.info(f"Saved JSON file: {json_file}")
                    
                    structured_data = json.loads(json_output_str)
                    
                except TimeoutError:
                    signal.alarm(0)
                    logger.warning(f"LaTeX processing timeout for {arxiv_id}")
                    return None, False
                    
            except Exception as e:
                logger.warning(f"Failed to process LaTeX for {arxiv_id}: {e}")
                # Clean up partial JSON file
                if json_file.exists():
                    try:
                        json_file.unlink()
                    except:
                        pass
                return None, False
        else:
            # Load existing JSON
            logger.info(f"Loading existing JSON: {json_file}")
            try:
                with open(json_file, 'r', encoding='utf-8') as f:
                    structured_data = json.load(f)
            except Exception as e:
                logger.warning(f"Failed to load JSON file {json_file}: {e}")
                return None, False
        
        # Step 3: Convert JSON to Markdown
        if structured_data:
            try:
                markdown_content = json_to_markdown(
                    structured_data, 
                    ignore_reference=True,
                    clean_equations=False
                )
                
                if save_intermediate:
                    with open(markdown_file, 'w', encoding='utf-8') as f:
                        f.write(markdown_content)
                    logger.info(f"Saved Markdown file: {markdown_file}")
                
                logger.success(f"Successfully extracted {arxiv_id} from LaTeX")
                return markdown_content, True
                
            except Exception as e:
                logger.warning(f"Failed to convert JSON to Markdown for {arxiv_id}: {e}")
                return None, False
        
        return None, False
    
    def _download_latex_source(self, arxiv_id: str, output_path: Path) -> bool:
        """
        Download LaTeX source from arXiv.
        
        Returns:
            True if successful, False otherwise
        """
        try:
            source_url = f"https://arxiv.org/e-print/{arxiv_id}"
            logger.info(f"Downloading LaTeX source from {source_url}")
            
            response = requests.get(source_url, timeout=30)
            response.raise_for_status()
            
            with open(output_path, 'wb') as f:
                f.write(response.content)
            
            logger.info(f"Downloaded LaTeX source: {output_path}")
            return True
            
        except requests.exceptions.RequestException as e:
            logger.warning(f"Failed to download LaTeX source for {arxiv_id}: {e}")
            return False
        except Exception as e:
            logger.warning(f"Unexpected error downloading LaTeX for {arxiv_id}: {e}")
            return False
    
    def _extract_from_pdf(
        self, 
        arxiv_id: str,
        save_intermediate: bool
    ) -> Tuple[Optional[str], bool]:
        """
        Extract content from PDF using marker-pdf.
        
        Returns:
            Tuple of (markdown_content, success)
        """
        logger.info(f"Attempting PDF extraction for {arxiv_id}")
        
        pdf_path = self.pdf_dir / f"{arxiv_id}.pdf"
        markdown_file = self.markdown_dir / f"{arxiv_id}.md"
        
        # Check if PDF exists
        if not pdf_path.exists():
            logger.warning(f"PDF not found: {pdf_path}")
            return None, False
        
        # Check if marker is available
        import shutil
        if not shutil.which("marker"):
            logger.error("marker-pdf not installed. Install with: uv sync --extra marker")
            return None, False
        
        try:
            # Create temporary directory for PDF
            temp_pdf_dir = self.markdown_dir / f"temp_pdf_{arxiv_id}"
            temp_pdf_dir.mkdir(exist_ok=True)
            
            # Copy PDF to temp directory (marker expects directory input)
            import shutil
            temp_pdf_path = temp_pdf_dir / f"{arxiv_id}.pdf"
            shutil.copy(pdf_path, temp_pdf_path)
            
            # Create temporary output directory
            temp_output_dir = self.markdown_dir / f"temp_output_{arxiv_id}"
            temp_output_dir.mkdir(exist_ok=True)
            
            # Run marker on directory
            logger.info(f"Running marker on {temp_pdf_dir}")
            result = subprocess.run(
                [
                    "marker",
                    str(temp_pdf_dir),
                    "--disable_image_extraction",
                    "--output_dir",
                    str(temp_output_dir)
                ],
                capture_output=True,
                text=True,
                timeout=self.marker_timeout
            )
            
            if result.returncode == 0:
                # Find the generated markdown file
                # marker creates a directory with the pdf name
                marker_output_dir = temp_output_dir / arxiv_id
                marker_md_file = marker_output_dir / f"{arxiv_id}.md"
                
                if marker_md_file.exists():
                    markdown_content = marker_md_file.read_text(encoding='utf-8')
                    
                    if save_intermediate:
                        # Move to final location
                        markdown_file.write_text(markdown_content, encoding='utf-8')
                        logger.info(f"Saved Markdown file: {markdown_file}")
                    
                    # Clean up temp directories
                    import shutil
                    shutil.rmtree(temp_output_dir, ignore_errors=True)
                    shutil.rmtree(temp_pdf_dir, ignore_errors=True)
                    
                    logger.success(f"Successfully extracted {arxiv_id} from PDF")
                    return markdown_content, True
                else:
                    logger.warning(f"Marker output not found at {marker_md_file}")
                    import shutil
                    shutil.rmtree(temp_output_dir, ignore_errors=True)
                    shutil.rmtree(temp_pdf_dir, ignore_errors=True)
                    return None, False
            else:
                logger.warning(f"Marker failed for {arxiv_id}: {result.stderr}")
                import shutil
                shutil.rmtree(temp_output_dir, ignore_errors=True)
                shutil.rmtree(temp_pdf_dir, ignore_errors=True)
                return None, False
                
        except subprocess.TimeoutExpired:
            logger.warning(f"Marker timeout for {arxiv_id}")
            return None, False
        except Exception as e:
            logger.warning(f"Unexpected error during PDF extraction for {arxiv_id}: {e}")
            return None, False
    
    def extract_batch(
        self, 
        arxiv_ids: list[str],
        force_pdf: bool = False,
        save_intermediate: bool = True
    ) -> dict[str, str]:
        """
        Extract multiple papers.
        
        Args:
            arxiv_ids: List of arXiv paper IDs
            force_pdf: If True, skip LaTeX and use PDF directly
            save_intermediate: If True, save intermediate files
        
        Returns:
            Dictionary mapping arxiv_id to markdown content
        """
        results = {}
        stats = {"latex": 0, "pdf": 0, "cached": 0, "failed": 0}
        
        for arxiv_id in arxiv_ids:
            markdown, method = self.extract_paper(
                arxiv_id, 
                force_pdf=force_pdf,
                save_intermediate=save_intermediate
            )
            
            if markdown:
                results[arxiv_id] = markdown
                stats[method] = stats.get(method, 0) + 1
            else:
                stats["failed"] += 1
        
        # Log statistics
        logger.info(f"Extraction complete: {stats}")
        logger.info(f"LaTeX: {stats['latex']}, PDF: {stats['pdf']}, "
                   f"Cached: {stats['cached']}, Failed: {stats['failed']}")
        
        return results


def main():
    """Test the extractor."""
    import sys
    from argparse import ArgumentParser
    
    parser = ArgumentParser(description="Extract papers to Markdown")
    parser.add_argument("arxiv_ids", nargs="+", help="ArXiv paper IDs")
    parser.add_argument("--force-pdf", action="store_true", 
                       help="Force PDF extraction")
    parser.add_argument("--latex-dir", type=Path, default=Path("arxiv/latex"))
    parser.add_argument("--json-dir", type=Path, default=Path("arxiv/json"))
    parser.add_argument("--markdown-dir", type=Path, default=Path("arxiv/markdown"))
    parser.add_argument("--pdf-dir", type=Path, default=Path("pdfs"))
    
    args = parser.parse_args()
    
    extractor = PaperExtractor(
        latex_dir=args.latex_dir,
        json_dir=args.json_dir,
        markdown_dir=args.markdown_dir,
        pdf_dir=args.pdf_dir
    )
    
    results = extractor.extract_batch(
        args.arxiv_ids,
        force_pdf=args.force_pdf
    )
    
    print(f"\nSuccessfully extracted {len(results)}/{len(args.arxiv_ids)} papers")
    for arxiv_id in args.arxiv_ids:
        if arxiv_id in results:
            print(f"  ✓ {arxiv_id}")
        else:
            print(f"  ✗ {arxiv_id}")


if __name__ == "__main__":
    main()
