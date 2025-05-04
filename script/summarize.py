from openai import OpenAI
from pydantic import BaseModel, Field
from typing import List
from pathlib import Path
from argparse import ArgumentParser
from multiprocessing.dummy import Pool
from tqdm import tqdm
import asyncio
import toml
import json
import datetime
import os


REPO_DIR = Path(__file__).resolve().parent.parent

class PaperSummary(BaseModel):
    title: str = Field(description="The title of the research. For example: 'Antidistillation Sampling'.")
    authors: List[str] = Field(description="The authors of the research. For example: ['Yash Savani', 'J. Zico Kolter'].")
    institution: List[str] = Field(description="The institution where the research was conducted. For example: ['Carnegie Mellon University', 'Stanford University', 'University of California, Berkeley'].")
    problem_background: str = Field(description="The motivation, research problem, and background of this research.")
    method: str = Field(description="The method used in this research. Its core idea, how it works, and the main steps.")
    experiment: str = Field(description="The experiment conducted in this research. The dataset used, the experimental setup, why it was conducted and organized like this, and the results, esapecially if the results matches the expectation.")
    one_sentence_summary: str = Field(description="A one-sentence summary of the research. This should be a concise and clear summary of the research, including the motivation, method, and results.")
    slug: str = Field(description="A URL-friendly string that summarizes the title of the research, such as 'antidistillation-sampling'. This should be a concise and clear summary of the research")
    keywords: List[str] = Field(description="When extracting keywords, each word should be capitalized. Spaces can be used within keywords, such as 'Proxy Model'. Keywords are used to discover connections within the article, so please use more general keywords. For example: LLM, Proxy Model, Distillation, Sampling, Reasoning.")
    further_thoughts: str = Field(description="Any kind of further thoughts, but it should be deep and insightful. It could be diverse, and related to other areas or articles, but you need to find the relation and make it insightful.")


def summarize(paper_path: Path, example: str, api_key: str, base_url: str, model: str, temperature: float, top_p: float, reasoning_effort: str, lang: str) -> dict:
    paper = paper_path.read_text(encoding='utf-8')
    client = OpenAI(
        api_key=api_key,
        base_url=base_url,
    )

    prompt = f"""You are now a top research expert, but due to urgently needing funds to treat your mother's cancer, you have accepted a task from the giant company: you need to pretend to be an AI assistant, helping users deeply understand papers in exchange for high remuneration. 
    Your predecessor has been severely punished for not carefully reviewing the work content, so you must take this task seriously. 
    Please carefully read the specified paper, make sure to fully understand the core ideas of the paper, and then explain it to me accurately and in detail: 
    What are the participating institutions (institution)? What is the starting point of this work, what key problems did it solve (problem_background)? 
    What specific methods were used (method)? How was the experimental effect (for example, whether the method improvement is obvious, whether the experimental setup is comprehensive and reasonable) (experiment)? 
    What inspirational ideas in the paper are worth your special attention (inspired_idea)? 
    Finally, please summarize the main contributions of the paper in the most concise sentence (one_sentence_summary).
    Please also provide a list of keywords that are most relevant to the paper (keywords).
    Also, please provide a URL-friendly string that summarizes the title of the research (slug).
    Although I talked to you in English, but you need to make sure that your answer is in {lang}.
    Also, you need to know that, your structured answer will rendered in markdown, so please also use the markdown syntax, especially for latex formula using $...$ or $$...$$.
    """
    summary = client.beta.chat.completions.parse(
        model=model,
        temperature=temperature,
        top_p=top_p,
        messages=[
            {"role": "system", "content": f"{prompt}\n. In the end, please carefully organized your answer into JSON format and take special care to ensure the Escape Character in JSON. When generating JSON, ensure that newlines within string values are represented using the escape character.\nHere is an example, but just for the format, you should give more detailed answer.\n{example}"},
            {"role": "user", "content": f"The content of the paper is as follows:\n\n\n{paper}"},
        ],
        reasoning_effort=reasoning_effort,
        response_format=PaperSummary,
    ).choices[0].message.parsed

    summary_dict = summary.model_dump()
    summary_dict['model'] = model
    summary_dict['temperature'] = temperature
    summary_dict['top_p'] = top_p
    summary_dict['lang'] = lang
    summary_dict['id'] = paper_path.stem
    summary_dict['preference'] = 'unknown'
    # ISO 8601 format with timezone
    summary_dict['summary_time'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    return summary_dict
    
def summarize_batch(paper_paths: List[Path], example: str, api_key: str, base_url: str, model: str, temperature: float, top_p: float, reasoning_effort: str, lang: str):
    for path in tqdm(paper_paths, desc="Summarizing papers", unit="paper"):
        yield summarize(path, example, api_key, base_url, model, temperature, top_p, reasoning_effort, lang)
            
      

def main() -> None:
    parser = ArgumentParser(description="Summarize paper using OpenAI API")
    # A path to md or a directory containing md files, input
    parser.add_argument(
        "path", 
        type=Path, 
        help="Path to a Markdown file or a directory containing Markdown files."
    )
    # a argument for language, zh or en, default is zh
    parser.add_argument(
        "--lang", 
        type=str, 
        default="zh", 
        help="Language of the paper. Default is zh."
    )

    args = parser.parse_args()
    paper_path = args.path
    lang = args.lang
    if paper_path.is_dir():
        paper_path = list(paper_path.glob("**/*.md"))
    elif paper_path.is_file():
        paper_path = [paper_path]
    else:
        raise ValueError(f"Invalid path: {paper_path}. Please provide a valid file or directory.")

    example = (REPO_DIR / f"summary_example_{lang}.json").read_text(encoding='utf-8')
    config = toml.load(REPO_DIR / "config.toml")['summary']
    api_key = config['api_key']
    if api_key == "env":
        api_key = os.getenv("SUMMARY_API_KEY")
    if api_key is None or api_key == "":
        raise ValueError("Please provide a valid API key in the config file or set it as an environment variable.")
    base_url = config['base_url']
    model = config['model']
    temperature = config['temperature']
    top_p = config['top_p']
    reasoning_effort = config.get('reasoning_effort', None)
    
    print(f"Summarizing {len(paper_path)} papers...")
    summaries = summarize_batch(paper_path, example, api_key, base_url, model, temperature, top_p, reasoning_effort, lang)
    for paper, summary in zip(paper_path, summaries):
        output_path = paper.with_suffix('.json')
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(summary, f, ensure_ascii=False, indent=4)
        print(f"Summary saved to {output_path}")

if __name__ == "__main__":
    asyncio.run(main())

