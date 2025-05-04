import polars as pl
import json
import argparse
from pathlib import Path
import loguru
from tqdm import tqdm

def main():
    parser = argparse.ArgumentParser(description="Load meta data in parquet file and insert into json file")
    parser.add_argument("-j", "--json", type=str, required=True, help="Directory to the JSON files")
    parser.add_argument("-p", "--parquet", type=str, required=True, help="Path to a Parquet file")
    args = parser.parse_args()

    json_dir = Path(args.json)
    parquet_path = Path(args.parquet)
    if not json_dir.is_dir():
        raise ValueError(f"Invalid path: {json_dir}. Please provide a valid directory.")
    if not parquet_path.is_file():
        raise ValueError(f"Invalid path: {parquet_path}. Please provide a valid file.")
    
    # Load the Parquet file
    df = pl.read_parquet(parquet_path).select(
        "id", "score", "title", "authors", "abstract", "categories", "created", "updated"
    )

    # Convert to a dictionary, Dict[str, Dict], the key is the id, other values are the meta data dict
    meta_data_dict =  {item["id"]: item for item in df.to_dicts()}
    # Iterate through all JSON files in the directory
    for json_file in tqdm(list(json_dir.glob("*.json"))):
        # Load the JSON file
        with open(json_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        paper_id = json_file.stem
        # Check if the paper_id is in the meta_data_dict

        if paper_id in meta_data_dict:
            data.update(meta_data_dict[paper_id])
            with open(json_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=4)
        else:
            loguru.logger.warning(f"Paper ID {paper_id} not found in the metadata dictionary. Skipping file: {json_file}")

if __name__ == "__main__":
    main()