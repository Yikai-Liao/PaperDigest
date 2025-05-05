import polars as pl
import glob
import os
from pathlib import Path
from argparse import ArgumentParser

def json2parquet(json_dir, parquet_path):

    # 获取所有JSON文件的路径
    json_files = Path(json_dir).glob("**/*.json")

    # 初始化一个空列表来存储所有的DataFrame
    dfs = []

    # 读取所有JSON文件
    for file_path in json_files:
        try:
            # 读取单个JSON文件
            df = pl.read_json(file_path)
            # 可以添加源文件名作为新列
            df = df.with_columns(pl.lit(os.path.basename(file_path)).alias("source_file"))
            dfs.append(df)
        except Exception as e:
            print(f"处理文件 {file_path} 时出错: {e}")

    # 合并所有DataFrame
    if dfs:
        combined_df = pl.concat(dfs)

        # 保存为Parquet文件
        combined_df.write_parquet(parquet_path)
        print(f"成功合并 {len(dfs)} 个文件，并保存为 {parquet_path}")
    else:
        print("没有成功处理任何文件")

if __name__ == "__main__":
    parser = ArgumentParser(description="Convert JSON files to Parquet format.")
    parser.add_argument("json_dir", type=str, help="Directory containing JSON files.")
    parser.add_argument("parquet_path", type=str, help="Output path for the Parquet file.")
    args = parser.parse_args()

    json2parquet(args.json_dir, args.parquet_path)
