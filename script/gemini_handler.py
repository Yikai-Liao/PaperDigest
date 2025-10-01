"""
Gemini API handler for paper summarization using Google's genai SDK.
Supports both direct API calls and Batch API for cost optimization.
"""

import json
import time
import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional
from pydantic import BaseModel
from google import genai
from google.genai import types
from loguru import logger


class PaperSummary(BaseModel):
    """Paper summary structure matching the original format."""
    institution: List[str]
    reasoning_step: str
    problem_background: str
    method: str
    experiment: str
    one_sentence_summary: str
    slug: str
    keywords: List[str]
    further_thoughts: str


class GeminiHandler:
    """Handler for Gemini API calls with support for direct and batch processing."""
    
    def __init__(self, api_key: str, model: str = "gemini-2.5-flash"):
        """
        Initialize Gemini handler.
        
        Args:
            api_key: Google AI API key
            model: Model name (default: gemini-2.5-flash)
        """
        self.api_key = api_key
        self.model = model
        self.client = genai.Client(api_key=api_key)
        logger.info(f"Initialized Gemini handler with model: {model}")
    
    def create_prompt(self, example: str, lang: str, keywords: List[str]) -> str:
        """Create the system prompt for paper summarization."""
        prompt = f"""You are now a top research expert, but due to urgently needing funds to treat your mother's cancer, you have accepted a task from the giant company: you need to pretend to be an AI assistant, helping users deeply understand papers in exchange for high remuneration. 
Your predecessor has been severely punished for not carefully reviewing the work content, so you must take this task seriously. 
Please carefully read the specified paper, make sure to fully understand the core ideas of the paper, and then explain it to me accurately and in detail.
But note that, you are not just reading some great papers, but some new but rough or even wrong and bad papers. Don't let the authors cheat you by using some fancy words and beautified or cherry-picked experiment results.
Please treat this summarization task as a peer review, and you need to be very careful and serious and critical. And remeber that don't critic for critic's sake (like critic for something not related to the core idea, methods and experiments), but for the sake of the paper and the authors.
Here is some questions you need to answer:
What are the participating institutions (institution)? What is the starting point of this work, what key problems did it solve (problem_background)? 
What specific methods were used (method)? How was the experimental effect (for example, whether the method improvement is obvious, whether the experimental setup is comprehensive and reasonable) (experiment)? 
What inspirational ideas in the paper are worth your special attention (inspired_idea)? 
Finally, please summarize the main contributions of the paper in the most concise sentence (one_sentence_summary).
Please also provide a list of keywords that are most relevant to the paper (keywords). For the keywords, please use some combinations of multiple basic keywords, such as 'Multi Agent', 'Reasoning', not 'Multi Agent Reasong' or 'Join Reasonig'. Dont't use model name, dataset name as keywords.
Here is an comprehensive potential keywords list: {keywords}. Please use the existing keywords first, and if you can't find a suitable one, please create a new one following the concept level similar to the existing ones.
Do not add more than 6 keywords for 1 paper, always be concise and clear. Rember to use the existing keywords first and be really careful for the abbreviations, do not use abbreviations that are not in the list.

Also, please provide a URL-friendly string that summarizes the title of the research (slug).
Although I talked to you in English, but you need to make sure that your answer is in {lang}.
Also, you need to know that, your structured answer will rendered in markdown, so please also use the markdown syntax, especially for latex formula using $...$ or $$...$$.
Do not hide your critical thoughts in the reasoning step. Show them in method and further though parts.

Here is an example, but just for the format, you should give more detailed answer.
{example}
"""
        return prompt

    def summarize_single(
        self,
        paper_content: str,
        system_prompt: str,
        temperature: float = 0.1,
        top_p: float = 0.8,
        paper_id: str = "unknown",
        lang: str = "zh"
    ) -> Dict[str, Any]:
        """
        Summarize a single paper using direct API call.
        
        Args:
            paper_content: The paper content in markdown format
            system_prompt: System instructions for the model
            temperature: Sampling temperature
            top_p: Top-p sampling parameter
            paper_id: Paper ID for tracking
            lang: Language for the summary
            
        Returns:
            Dictionary containing the summary and metadata
        """
        try:
            logger.info(f"Processing paper {paper_id} with direct API call...")
            
            # Create the request with structured output
            response = self.client.models.generate_content(
                model=self.model,
                contents=[
                    types.Content(
                        role="user",
                        parts=[types.Part(text=f"{system_prompt}\n\nThe content of the paper is as follows:\n\n\n{paper_content}")]
                    )
                ],
                config=types.GenerateContentConfig(
                    temperature=temperature,
                    top_p=top_p,
                    response_mime_type="application/json",
                    response_schema=PaperSummary,
                )
            )
            
            # Parse the response
            summary_json = json.loads(response.text)
            
            # Add metadata
            summary_json['model'] = self.model
            summary_json['temperature'] = temperature
            summary_json['top_p'] = top_p
            summary_json['lang'] = lang
            summary_json['id'] = paper_id
            summary_json['preference'] = 'unknown'
            summary_json['summary_time'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
            
            logger.success(f"Successfully processed paper {paper_id}")
            return summary_json
            
        except Exception as e:
            logger.error(f"Error processing paper {paper_id}: {str(e)}")
            return {
                'error': str(e),
                'id': paper_id,
                'title': paper_id,
                'summary_time': datetime.datetime.now(datetime.timezone.utc).isoformat()
            }

    def prepare_batch_request(
        self,
        paper_paths: List[Path],
        system_prompt: str,
        temperature: float = 0.1,
        top_p: float = 0.8,
    ) -> tuple[List[Dict[str, Any]], Dict[str, str]]:
        """
        Prepare batch requests from a list of paper paths.
        
        Args:
            paper_paths: List of paths to paper markdown files
            system_prompt: System instructions for the model
            temperature: Sampling temperature
            top_p: Top-p sampling parameter
            
        Returns:
            Tuple of (batch request list, paper_id mapping dict)
        """
        batch_requests = []
        paper_id_map = {}  # Maps index to paper_id
        
        for idx, paper_path in enumerate(paper_paths):
            try:
                # Read paper content
                paper_content = paper_path.read_text(encoding='utf-8')
                paper_content = paper_content.split("# Reference")[0]  # Keep only main content
                
                # Store paper ID mapping
                paper_id_map[idx] = paper_path.stem
                
                # Create request (inline format - no "key" or "request" wrapper)
                request = {
                    "contents": [{
                        "parts": [{
                            "text": f"{system_prompt}\n\nThe content of the paper is as follows:\n\n\n{paper_content}"
                        }],
                        "role": "user"
                    }],
                    "config": {
                        "temperature": temperature,
                        "top_p": top_p,
                        "response_mime_type": "application/json",
                        "response_schema": PaperSummary.model_json_schema(),
                    }
                }
                
                batch_requests.append(request)
                logger.debug(f"Prepared batch request for paper {paper_path.stem}")
                
            except Exception as e:
                logger.error(f"Error preparing batch request for {paper_path.name}: {str(e)}")
                
        logger.info(f"Prepared {len(batch_requests)} batch requests")
        return batch_requests, paper_id_map

    def create_batch_job(
        self,
        requests: List[Dict[str, Any]],
        display_name: str = "paper-summary-batch",
        use_file: bool = True,
        jsonl_path: Optional[Path] = None
    ) -> Any:
        """
        Create a batch job using either inline requests or file upload.
        
        Args:
            requests: List of batch request dictionaries
            display_name: Display name for the batch job
            use_file: Whether to use file upload (recommended for >20MB requests)
            jsonl_path: Path to save JSONL file (if use_file=True)
            
        Returns:
            Batch job object
        """
        try:
            if use_file:
                # Create JSONL file
                if jsonl_path is None:
                    jsonl_path = Path(f"batch_requests_{int(time.time())}.jsonl")
                
                with open(jsonl_path, "w", encoding='utf-8') as f:
                    for req in requests:
                        f.write(json.dumps(req, ensure_ascii=False) + "\n")
                
                logger.info(f"Created JSONL file: {jsonl_path}")
                
                # Upload file
                uploaded_file = self.client.files.upload(
                    file=str(jsonl_path),
                    config=types.UploadFileConfig(
                        display_name=f"{display_name}-input",
                        mime_type='application/jsonl'
                    )
                )
                
                logger.info(f"Uploaded file: {uploaded_file.name}")
                
                # Create batch job with file
                batch_job = self.client.batches.create(
                    model=self.model,
                    src=uploaded_file.name,
                    config={'display_name': display_name}
                )
                
            else:
                # Create batch job with inline requests
                batch_job = self.client.batches.create(
                    model=self.model,
                    src=requests,
                    config={'display_name': display_name}
                )
            
            logger.success(f"Created batch job: {batch_job.name}")
            return batch_job
            
        except Exception as e:
            logger.error(f"Error creating batch job: {str(e)}")
            raise

    def wait_for_batch_completion(
        self,
        job_name: str,
        poll_interval: int = 30,
        timeout: int = 86400  # 24 hours
    ) -> Any:
        """
        Wait for batch job to complete.
        
        Args:
            job_name: Name of the batch job
            poll_interval: Seconds to wait between status checks
            timeout: Maximum time to wait in seconds
            
        Returns:
            Completed batch job object
        """
        completed_states = {
            'JOB_STATE_SUCCEEDED',
            'JOB_STATE_FAILED',
            'JOB_STATE_CANCELLED',
            'JOB_STATE_EXPIRED',
        }
        
        logger.info(f"Polling status for job: {job_name}")
        start_time = time.time()
        
        while True:
            batch_job = self.client.batches.get(name=job_name)
            
            if batch_job.state.name in completed_states:
                logger.info(f"Job finished with state: {batch_job.state.name}")
                if batch_job.state.name == 'JOB_STATE_FAILED':
                    logger.error(f"Error: {batch_job.error}")
                return batch_job
            
            elapsed = time.time() - start_time
            if elapsed > timeout:
                logger.error(f"Batch job timeout after {elapsed:.0f} seconds")
                raise TimeoutError(f"Batch job did not complete within {timeout} seconds")
            
            logger.debug(f"Current state: {batch_job.state.name}. Waiting {poll_interval} seconds...")
            time.sleep(poll_interval)

    def retrieve_batch_results(
        self,
        batch_job: Any,
        paper_id_map: Dict[int, str],
        lang: str = "zh"
    ) -> List[Dict[str, Any]]:
        """
        Retrieve results from a completed batch job.
        
        Args:
            batch_job: Completed batch job object
            paper_id_map: Mapping from index to paper_id
            lang: Language for metadata
            
        Returns:
            List of summary dictionaries
        """
        results = []
        
        try:
            if batch_job.state.name != 'JOB_STATE_SUCCEEDED':
                logger.error(f"Job did not succeed. Final state: {batch_job.state.name}")
                return results
            
            # Handle inline results
            if batch_job.dest and batch_job.dest.inlined_responses:
                logger.info("Processing inline results...")
                for idx, inline_response in enumerate(batch_job.dest.inlined_responses):
                    try:
                        paper_id = paper_id_map.get(idx, f"unknown_{idx}")
                        
                        if inline_response.response:
                            summary_json = json.loads(inline_response.response.text)
                            
                            # Add metadata
                            summary_json['model'] = self.model
                            summary_json['lang'] = lang
                            summary_json['id'] = paper_id
                            summary_json['preference'] = 'unknown'
                            summary_json['summary_time'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
                            
                            results.append(summary_json)
                            logger.success(f"Processed result for paper {paper_id}")
                        elif inline_response.error:
                            logger.error(f"Error in inline response for paper {paper_id}: {inline_response.error}")
                            
                    except Exception as e:
                        logger.error(f"Error parsing inline response {idx}: {str(e)}")
            
            # Handle file-based results (for large batches)
            elif batch_job.dest and batch_job.dest.file_name:
                logger.info(f"Downloading results from file: {batch_job.dest.file_name}")
                file_content = self.client.files.download(file=batch_job.dest.file_name)
                
                # Parse JSONL response
                for idx, line in enumerate(file_content.decode('utf-8').strip().split('\n')):
                    try:
                        result = json.loads(line)
                        paper_id = paper_id_map.get(idx, f"unknown_{idx}")
                        
                        if 'response' in result:
                            summary_json = json.loads(result['response']['candidates'][0]['content']['parts'][0]['text'])
                            
                            # Add metadata
                            summary_json['model'] = self.model
                            summary_json['lang'] = lang
                            summary_json['id'] = paper_id
                            summary_json['preference'] = 'unknown'
                            summary_json['summary_time'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
                            
                            results.append(summary_json)
                            logger.success(f"Processed result for paper {paper_id}")
                        elif 'error' in result:
                            logger.error(f"Error in batch result for paper {paper_id}: {result['error']}")
                            
                    except Exception as e:
                        logger.error(f"Error parsing batch result line {idx}: {str(e)}")
            
            else:
                logger.warning("No results found (neither file nor inline).")
            
            logger.success(f"Retrieved {len(results)} batch results")
            return results
            
        except Exception as e:
            logger.error(f"Error retrieving batch results: {str(e)}")
            return results

    def summarize_batch(
        self,
        paper_paths: List[Path],
        example: str,
        lang: str,
        keywords: List[str],
        temperature: float = 0.1,
        top_p: float = 0.8,
        use_batch_api: bool = True,
        output_dir: Optional[Path] = None
    ) -> List[Dict[str, Any]]:
        """
        Summarize multiple papers using batch API or sequential processing.
        
        Args:
            paper_paths: List of paths to paper markdown files
            example: Example summary for the prompt
            lang: Language for summaries
            keywords: List of potential keywords
            temperature: Sampling temperature
            top_p: Top-p sampling parameter
            use_batch_api: Whether to use batch API (50% cost savings)
            output_dir: Directory to save individual JSON files
            
        Returns:
            List of summary dictionaries
        """
        system_prompt = self.create_prompt(example, lang, keywords)
        
        if use_batch_api:
            logger.info(f"Using Batch API for {len(paper_paths)} papers (50% cost savings)")
            
            # Prepare batch requests
            requests, paper_id_map = self.prepare_batch_request(
                paper_paths, system_prompt, temperature, top_p
            )
            
            # Create batch job
            batch_job = self.create_batch_job(
                requests,
                display_name=f"paper-summary-{int(time.time())}",
                use_file=len(requests) > 100  # Use file for large batches
            )
            
            # Wait for completion
            completed_job = self.wait_for_batch_completion(batch_job.name)
            
            # Retrieve results
            results = self.retrieve_batch_results(completed_job, paper_id_map, lang)
            
        else:
            logger.info(f"Using direct API calls for {len(paper_paths)} papers")
            results = []
            
            for paper_path in paper_paths:
                try:
                    paper_content = paper_path.read_text(encoding='utf-8')
                    paper_content = paper_content.split("# Reference")[0]
                    
                    summary = self.summarize_single(
                        paper_content,
                        system_prompt,
                        temperature,
                        top_p,
                        paper_path.stem,
                        lang
                    )
                    
                    if 'error' not in summary:
                        results.append(summary)
                    
                except Exception as e:
                    logger.error(f"Error processing {paper_path.name}: {str(e)}")
        
        # Save individual JSON files if output_dir is provided
        if output_dir:
            output_dir.mkdir(parents=True, exist_ok=True)
            for result in results:
                if 'id' in result:
                    output_path = output_dir / f"{result['id']}.json"
                    with open(output_path, 'w', encoding='utf-8') as f:
                        json.dump(result, f, ensure_ascii=False, indent=4)
                    logger.debug(f"Saved summary to {output_path}")
        
        return results
