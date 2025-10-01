import time
import requests
import toml
import polars as pl
from loguru import logger
from tqdm import tqdm
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

def get_shown_paper_id(df:pl.DataFrame) -> list[str]:
    """
    Get the show paper id from the dataframe.
    """
    return df.filter(pl.col("show") == 1).select("id").to_series().to_list()

def download_papers(paper_ids: list[str], output_dir: Path, delay: int = 3, max_retries: int = 3) -> tuple[int, int, int]:
    """
    Download papers from arXiv based on their IDs.
    
    Args:
        paper_ids: List of arXiv paper IDs.
        output_dir: Directory where PDFs will be saved.
        delay: Delay in seconds between downloads to respect arXiv's rate limits.
                Also used as base delay for retry attempts.
        max_retries: Maximum number of retry attempts if download fails.
    
    Returns:
        tuple: (successful_count, skipped_count, failed_count)
    """
    # Create output directory if it doesn't exist
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Download papers with progress bar
    skipped = 0
    failed = 0
    
    for paper_id in tqdm(paper_ids, desc="Downloading papers"):
        # Check if the file already exists
        pdf_path = output_dir / f"{paper_id}.pdf"
        if pdf_path.exists():
            logger.info(f"Paper {paper_id} already downloaded, skipping")
            skipped += 1
            continue
        
        # Retry loop
        success = False
        retry_count = 0
        
        while not success and retry_count <= max_retries:
            try:
                if retry_count > 0:
                    logger.warning(f"Retry attempt {retry_count}/{max_retries} for paper {paper_id}")
                    # Use delay as base for backoff, increasing with retry count
                    time.sleep(delay * retry_count)
                        
                # Using requests directly
                pdf_url = f"https://arxiv.org/pdf/{paper_id}.pdf"
                response = requests.get(pdf_url, timeout=(10, 30))  # Added timeout (connect, read)
                
                if response.status_code == 200:
                    with open(pdf_path, 'wb') as f:
                        f.write(response.content)
                    success = True
                else:
                    logger.warning(f"Failed to download {paper_id}: HTTP {response.status_code}")
                    retry_count += 1
                
            except requests.exceptions.RequestException as e:
                # Handle network-related exceptions
                logger.warning(f"Network error while downloading {paper_id}: {str(e)}")
                retry_count += 1
            except Exception as e:
                # Handle other exceptions
                logger.error(f"Error downloading paper {paper_id}: {str(e)}")
                retry_count += 1
        
        # Check if all retries failed
        if not success:
            logger.error(f"Failed to download {paper_id} after {max_retries} retries")
            failed += 1
        
        # Add delay between papers (not between retries of the same paper)
        if paper_id != paper_ids[-1]:  # Don't delay after the last paper
            time.sleep(delay)
    
    # Summary
    successful = len(paper_ids) - skipped - failed
    logger.info(f"Download complete. Downloaded {successful} new papers, skipped {skipped} existing papers, failed {failed} papers.")
    
    return successful, skipped, failed

if __name__ == "__main__":
    # Read the parquet file
    path = REPO_ROOT / "data" / "predictions.parquet"
    logger.info(f"Reading parquet file from {path}")
    df = pl.read_parquet(path)

    # Get the show paper id
    show_paper_id = get_shown_paper_id(df)

    logger.info(f"Number of papers to download: {len(show_paper_id)}")

    config = toml.load(REPO_ROOT / "config.toml")['download_pdf']
    output_dir = Path(config['output_dir'])
    delay = config['delay']
    max_retries = config['max_retry']
    logger.info(f"Output directory: {output_dir}")
    logger.info(f"Delay: {delay}")
    logger.info(f"Max retries: {max_retries}")
    # Download the papers
    successful, skipped, failed = download_papers(show_paper_id, output_dir, delay, max_retries)
    logger.info(f"Downloaded {successful} papers, skipped {skipped} papers, failed {failed} papers.")

