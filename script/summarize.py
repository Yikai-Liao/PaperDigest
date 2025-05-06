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
import tiktoken  # 添加tiktoken库来计算token数量


REPO_DIR = Path(__file__).resolve().parent.parent
# 定义模型的最大标记限制
MAX_TOKENS = 50000  # 设置一个安全值，比实际限制131072小一些

def count_tokens(text: str, model: str) -> int:
    """计算文本的token数量"""
    try:
        encoding = tiktoken.encoding_for_model(model)
    except KeyError:
        encoding = tiktoken.get_encoding("cl100k_base")
    return len(encoding.encode(text))

def truncate_text(text: str, model: str, max_tokens: int) -> str:
    """如果文本token数量超过限制，截断文本"""
    encoding = tiktoken.encoding_for_model(model) if model in tiktoken.model.MODEL_TO_ENCODING else tiktoken.get_encoding("cl100k_base")
    tokens = encoding.encode(text)
    
    if len(tokens) <= max_tokens:
        return text
    
    # 保留前面部分和后面部分
    # 前面保留40%，后面保留30%，中间省略
    front_ratio = 0.4
    back_ratio = 0.3
    
    front_tokens = tokens[:int(max_tokens * front_ratio)]
    back_tokens = tokens[-int(max_tokens * back_ratio):]
    
    # 添加一个提示，说明内容已被截断
    truncation_msg = "\n\n[...内容过长，已省略中间部分...]\n\n"
    truncation_tokens = encoding.encode(truncation_msg)
    
    # 确保留出足够空间给truncation_msg
    remaining_tokens = max_tokens - len(front_tokens) - len(back_tokens) - len(truncation_tokens)
    if remaining_tokens < 0:
        # 如果空间不够，减少front和back的tokens
        reduction = abs(remaining_tokens) // 2 + 1
        front_tokens = front_tokens[:-reduction] if len(front_tokens) > reduction else front_tokens
        back_tokens = back_tokens[reduction:] if len(back_tokens) > reduction else back_tokens
    
    # 组合最终的tokens
    final_tokens = front_tokens + truncation_tokens + back_tokens
    
    return encoding.decode(final_tokens)

class PaperSummary(BaseModel):
    # title: str = Field(description="The title of the research. For example: 'Antidistillation Sampling'.")
    # authors: List[str] = Field(description="The authors of the research. For example: ['Yash Savani', 'J. Zico Kolter'].")
    institution: List[str] = Field(description="The institution where the research was conducted. For example: ['Carnegie Mellon University', 'Stanford University', 'University of California, Berkeley'].")
    reasoning_step: str = Field(description="Just a draft for you to understand this paper and do some further reasoning here. You need to think here, deep dive into the paper and find some interesting things, some problems, some insights, and all the things you think that you need to think. This is a draft, so you can write anything here, but it should be deep and help you to make the following answer better.")
    problem_background: str = Field(description="The motivation, research problem, and background of this research.")
    method: str = Field(description="The method used in this research. Its core idea, how it works, and the main steps.")
    experiment: str = Field(description="The experiment conducted in this research. The dataset used, the experimental setup, why it was conducted and organized like this, and the results, esapecially if the results matches the expectation.")
    one_sentence_summary: str = Field(description="A one-sentence summary of the research. This should be a concise and clear summary of the research, including the motivation, method, and results.")
    slug: str = Field(description="A URL-friendly string that summarizes the title of the research, such as 'antidistillation-sampling'. This should be a concise and clear summary of the research")
    keywords: List[str] = Field(description="When extracting keywords, each word should be capitalized. Spaces can be used within keywords, such as 'Proxy Model'. Keywords are used to discover connections within the article, so please use more general keywords. For example: LLM, Proxy Model, Distillation, Sampling, Reasoning.")
    further_thoughts: str = Field(description="Any kind of further thoughts, but it should be deep and insightful. It could be diverse, and related to other areas or articles, but you need to find the relation and make it insightful.")


def summarize(paper_path: Path, example: str, api_key: str, base_url: str, model: str, temperature: float, top_p: float, reasoning_effort: str, lang: str) -> dict:
    paper = paper_path.read_text(encoding='utf-8')
    paper = paper.split("# Reference")[0] # 只保留正文部分
    client = OpenAI(
        api_key=api_key,
        base_url=base_url,
    )

    prompt = f"""You are now a top research expert, but due to urgently needing funds to treat your mother's cancer, you have accepted a task from the giant company: you need to pretend to be an AI assistant, helping users deeply understand papers in exchange for high remuneration. 
    Your predecessor has been severely punished for not carefully reviewing the work content, so you must take this task seriously. 
    Please carefully read the specified paper, make sure to fully understand the core ideas of the paper, and then explain it to me accurately and in detail.
    But note that, you are not just reading some great papers, but some new but rough or even wrong and bad papers. Don't let the authors cheat you by using some fancy words and beautified or cherry-picked experiment results.
    Please treat this summarization task as a peer review, and you need to be very careful and serious and critical.
    Here is some questions you need to answer:
    What are the participating institutions (institution)? What is the starting point of this work, what key problems did it solve (problem_background)? 
    What specific methods were used (method)? How was the experimental effect (for example, whether the method improvement is obvious, whether the experimental setup is comprehensive and reasonable) (experiment)? 
    What inspirational ideas in the paper are worth your special attention (inspired_idea)? 
    Finally, please summarize the main contributions of the paper in the most concise sentence (one_sentence_summary).
    Please also provide a list of keywords that are most relevant to the paper (keywords).
    Also, please provide a URL-friendly string that summarizes the title of the research (slug).
    Although I talked to you in English, but you need to make sure that your answer is in {lang}.
    Also, you need to know that, your structured answer will rendered in markdown, so please also use the markdown syntax, especially for latex formula using $...$ or $$...$$.
    """
    
    # 估算prompt和system message的token数
    system_content = f"{prompt}\n. In the end, please carefully organized your answer into JSON format and take special care to ensure the Escape Character in JSON. When generating JSON, ensure that newlines within string values are represented using the escape character.\nHere is an example, but just for the format, you should give more detailed answer.\n{example}"
    system_tokens = count_tokens(system_content, model)
    print(f"System message token count: {system_tokens}")
    
    # 为paper内容保留的最大token数 = 最大限制 - system消息token数 - 一些安全余量
    max_paper_tokens = MAX_TOKENS - system_tokens - 2000  # 2000作为安全余量
    
    # 检查并截断paper内容
    if token_num := count_tokens(paper, model) > max_paper_tokens:
        print(f"Paper content too long ({count_tokens(paper, model)} tokens), truncating to {max_paper_tokens} tokens")
        paper = truncate_text(paper, model, max_paper_tokens)
    else:
        print(f"Paper content within limit ({token_num} tokens), no truncation needed")
    
    try:
        summary = client.beta.chat.completions.parse(
            model=model,
            temperature=temperature,
            top_p=top_p,
            messages=[
                {"role": "system", "content": system_content},
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
    except Exception as e:
        print(f"Error processing {paper_path.name}: {str(e)}")
        # 返回一个错误状态的字典而不是直接抛出异常
        return {
            'error': str(e),
            'id': paper_path.stem,
            'title': paper_path.stem,
            'summary_time': datetime.datetime.now(datetime.timezone.utc).isoformat()
        }

def summarize_batch(paper_paths: List[Path], example: str, api_key: str, base_url: str, model: str, temperature: float, top_p: float, reasoning_effort: str, lang: str, num_workers: int = 1):
    """Summarize a batch of papers using a thread pool."""
    if num_workers > 1:
        with Pool(num_workers) as pool:
            tasks = [(path, example, api_key, base_url, model, temperature, top_p, reasoning_effort, lang) for path in paper_paths]
            results = []
            # 修改函数以返回路径和摘要结果的元组
            def process_paper(p, e, a, b, m, t, tp, r, l):
                output_path = p.with_suffix('.json')
                # 检查目标JSON文件是否已存在，如果存在则跳过处理
                if output_path.exists():
                    print(f"Summary already exists at {output_path}, skipping...")
                    return None
                
                try:
                    summary = summarize(p, e, a, b, m, t, tp, r, l)
                    
                    # 检查是否发生错误
                    if 'error' in summary:
                        print(f"Error in summarizing {p.name}: {summary['error']}")
                        return None
                        
                    with open(output_path, 'w', encoding='utf-8') as f:
                        json.dump(summary, f, ensure_ascii=False, indent=4)
                    print(f"Summary saved to {output_path}")
                    return summary
                except Exception as e:
                    print(f"Unexpected error processing {p.name}: {str(e)}")
                    return None
                
            # 直接处理结果，不使用yield
            return list(tqdm(
                pool.starmap(process_paper, tasks),
                total=len(tasks),
                desc="Summarizing papers",
                unit="paper"
            ))
    else:
        # Fallback to sequential processing
        results = []
        for path in tqdm(paper_paths, desc="Summarizing papers", unit="paper"):
            try:
                output_path = path.with_suffix('.json')
                if output_path.exists():
                    print(f"Summary already exists at {output_path}, skipping...")
                    continue
                
                summary = summarize(path, example, api_key, base_url, model, temperature, top_p, reasoning_effort, lang)
                
                # 检查是否发生错误
                if 'error' in summary:
                    print(f"Error in summarizing {path.name}: {summary['error']}")
                    continue
                    
                with open(output_path, 'w', encoding='utf-8') as f:
                    json.dump(summary, f, ensure_ascii=False, indent=4)
                print(f"Summary saved to {output_path}")
                results.append(summary)
            except Exception as e:
                print(f"Unexpected error processing {path.name}: {str(e)}")
        return results
      

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
    num_workers = config.get('num_workers', 1)
    
    print(f"Summarizing {len(paper_path)} papers with {num_workers} workers...")
    # 直接调用summarize_batch，已经在函数内完成了文件保存
    summarize_batch(paper_path, example, api_key, base_url, model, temperature, top_p, reasoning_effort, lang, num_workers)

if __name__ == "__main__":
    main()

