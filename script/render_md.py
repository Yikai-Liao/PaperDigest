import jinja2
import os
import json # <--- 1. 导入 json 库
from pathlib import Path

REPO_DIR = Path(__file__).resolve().parent.parent
RAW_DIR = REPO_DIR / "raw"
OUTPUT_DIR = REPO_DIR / "content"
TEMPLATE_PATH = REPO_DIR / "template.j2"

if __name__ == "__main__":
    # Ensure the template path is correct relative to the script location if needed
    # If template.j2 is in the same directory as the script:
    # SCRIPT_DIR = Path(__file__).resolve().parent
    # TEMPLATE_PATH = SCRIPT_DIR / "template.j2"
    # Or ensure REPO_DIR is correctly defined based on your project structure

    # Loop through all json files in the raw directory
    for json_file in RAW_DIR.glob("**/*.json"):
        # Get the relative path to the json file
        relative_path = json_file.relative_to(RAW_DIR)
        # Get the output path by replacing the raw directory with the output directory
        output_path = OUTPUT_DIR / relative_path.with_suffix(".md")
        # Create the output directory if it doesn't exist
        # Use os.makedirs for potentially nested directories
        output_path.parent.mkdir(parents=True, exist_ok=True) # Use pathlib's mkdir

        # Load the template
        try:
            with open(TEMPLATE_PATH, 'r', encoding='utf-8') as f_template: # Specify encoding
                template = jinja2.Template(f_template.read())
        except FileNotFoundError:
            print(f"Error: Template file not found at {TEMPLATE_PATH}")
            continue # Skip this file if template is missing
        except Exception as e:
            print(f"Error loading template {TEMPLATE_PATH}: {e}")
            continue

        # Load and parse the JSON data
        try:
            with open(json_file, 'r', encoding='utf-8') as f_json: # Specify encoding
                # --- 2. 解析 JSON 文件 ---
                data = json.load(f_json) # json.load() reads from a file object
        except json.JSONDecodeError:
            print(f"Error: Could not decode JSON from file {json_file}")
            continue # Skip corrupted JSON files
        except FileNotFoundError:
            print(f"Error: JSON file not found at {json_file}")
            continue # Should not happen with glob, but good practice
        except Exception as e:
            print(f"Error reading JSON file {json_file}: {e}")
            continue

        # --- 3. 将解析后的字典传递给 render ---
        # Jinja2 render can directly take a dictionary as context.
        # Keys in the dictionary become variables in the template.
        try:
            rendered = template.render(data)
            # Alternatively, you could unpack the dictionary:
            # rendered = template.render(**data)
        except Exception as e:
            print(f"Error rendering template for {json_file}: {e}")
            continue

        # Write the rendered template to the output file
        try:
            with open(output_path, "w", encoding='utf-8') as f_out: # Specify encoding
                f_out.write(rendered)
            print(f"Rendered {json_file.name} to {output_path}") # Use .name for cleaner log
        except Exception as e:
            print(f"Error writing output file {output_path}: {e}")