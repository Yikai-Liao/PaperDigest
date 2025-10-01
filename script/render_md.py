import jinja2
import os
import json
import toml
import shutil  # 添加shutil库导入

from pathlib import Path
import polars as pl
import huggingface_hub as hfh

REPO_DIR = Path(__file__).resolve().parent.parent
OUTPUT_DIR = REPO_DIR / "content"
TEMPLATE_PATH = REPO_DIR / "config" / "template.j2"

if __name__ == "__main__":
    config = toml.load(REPO_DIR / "config.toml")
    content_repo = config["content_repo"]
    data_link = f"hf://datasets/{content_repo}/main.parquet"
    raw_content = pl.read_parquet(data_link).to_dicts()
    # 清空输出目录
    if OUTPUT_DIR.exists():
        shutil.rmtree(OUTPUT_DIR)  # 递归删除目录及其所有内容
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)  # 重新创建目录
    # create .gitkeep
    (OUTPUT_DIR / ".gitkeep").touch(exist_ok=True)

    # Load the template
    with open(TEMPLATE_PATH, 'r', encoding='utf-8') as f_template: # Specify encoding
        template = jinja2.Template(f_template.read())

    for content in raw_content:
        content['draft'] = 'true' if content.get('preference') == 'dislike' else 'false'
        # Get the output path by replacing the raw directory with the output directory
        arxiv_id = content["id"]
        output_path = OUTPUT_DIR / f"{arxiv_id}.md"
        # Create the output directory if it doesn't exist
        # Use os.makedirs for potentially nested directories
        output_path.parent.mkdir(parents=True, exist_ok=True) # Use pathlib's mkdir
        try:
            rendered = template.render(content)
        except jinja2.exceptions.TemplateError as e:
            print(f"Error rendering template for {arxiv_id}: {e}")
            continue
        except Exception as e:
            print(f"Unexpected error rendering template for {arxiv_id}: {e}")
            continue

        with open(output_path, "w", encoding='utf-8') as f_out: # Specify encoding
            f_out.write(rendered)