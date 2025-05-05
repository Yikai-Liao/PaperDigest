import polars as pl
import huggingface_hub as hfh
import os
from pathlib import Path
from argparse import ArgumentParser


if __name__ == "__main__":
    # Merge the local version and remote huggingface version of a single parquet 
    # And upload to huggingface hub

    parser = ArgumentParser(description="Upload parquet files to Hugging Face Hub.")
    parser.add_argument("local_parquet_path", type=str, help="Path to the local parquet file.")
    parser.add_argument("remote_parquet_path", type=str, help="Path to the remote parquet file.")

    parser.add_argument("repo_id", type=str, help="Hugging Face Hub repo ID.")

    # Get HF Token from environment variable
    parser.add_argument("--hf_token", type=str, default=os.getenv("HUGGINGFACE_TOKEN"), help="Hugging Face Hub token.")


    args = parser.parse_args()
    local_parquet_path = args.local_parquet_path
    remote_parquet_path = args.remote_parquet_path
    repo_id = args.repo_id
    hf_token = args.hf_token
    print("HF Token:", hf_token)
    # Check if the local parquet file exists
    if not os.path.exists(local_parquet_path):
        raise FileNotFoundError(f"Local parquet file {local_parquet_path} does not exist.")
    
    # Download the remote file to a temporary location
    try:
        print(f"Downloading {remote_parquet_path} from {repo_id}...")
        remote_file_path = hfh.hf_hub_download(repo_id=repo_id, filename=remote_parquet_path, repo_type="dataset", token=hf_token)
        print(f"Downloaded to {remote_file_path}")
    except Exception as e:
        print(f"Warning: Could not download remote file: {str(e)}")
        print("Creating a new file on Hugging Face Hub instead.")
        remote_df = pl.DataFrame()
        exit(1)
    else:
        # Read the remote parquet file
        remote_df = pl.read_parquet(remote_file_path)
        
    # Read the local parquet file
    print(f"Reading local parquet file from {local_parquet_path}...")
    local_df = pl.read_parquet(local_parquet_path)
    
    print(f"Local dataframe shape: {local_df.shape}")
    print(f"Remote dataframe shape: {remote_df.shape}")
    
    # Merge the two dataframes
    if 'id' not in local_df.columns:
        raise ValueError("Local dataframe must have an 'id' column")
    
    if not remote_df.is_empty() and 'id' in remote_df.columns:
        # 使用纯polars实现combine_first的效果
        # 1. 首先执行外连接（保留所有id）
        # 2. 对于冲突的列，优先使用local_df的值
        
        # 获取两个数据框的所有列名（不包括id）
        local_cols = set(local_df.columns) - {'id'}
        remote_cols = set(remote_df.columns) - {'id'}
        
        # 找出共有的列和独有的列
        common_cols = local_cols.intersection(remote_cols)
        local_only_cols = local_cols - common_cols
        remote_only_cols = remote_cols - common_cols
        
        print(f"Common columns: {common_cols}")
        print(f"Local-only columns: {local_only_cols}")
        print(f"Remote-only columns: {remote_only_cols}")
        
        # 外连接，保留所有id
        merged_df = local_df.join(
            remote_df,
            on="id",
            how="full",
            suffix="_remote"
        )
        
        # 处理共有列，优先使用local_df的值
        select_exprs = [pl.col("id")]
        
        # 对于共有列，使用local_df的值，如果为空则使用remote_df的值
        for col in common_cols:
            select_exprs.append(
                pl.coalesce(pl.col(col), pl.col(f"{col}_remote")).alias(col)
            )
        
        # 添加local_df独有的列
        for col in local_only_cols:
            select_exprs.append(pl.col(col))
        
        # 添加remote_df独有的列
        for col in remote_only_cols:
            select_exprs.append(pl.col(f"{col}_remote").alias(col))
        
        # 应用选择表达式
        merged_df = merged_df.select(select_exprs)
        
        print(f"Merged dataframe shape: {merged_df.shape}")
    else:
        # If remote is empty, just use local
        merged_df = local_df
        print("Using local dataframe as the remote dataframe is empty.")
    
    # Save the merged dataframe to a temporary file
    temp_output_path = "merged_temp.parquet"
    print(f"Saving merged dataframe to {temp_output_path}...")
    merged_df.write_parquet(temp_output_path)
    
    # Upload the merged dataframe to huggingface hub
    print(f"Uploading to {repo_id}/{remote_parquet_path}...")
    hfh.upload_file(
        path_or_fileobj=temp_output_path,
        path_in_repo=remote_parquet_path,
        repo_id=repo_id,
        token=hf_token,
        repo_type="dataset"
    )
    
    # Clean up temporary file
    os.remove(temp_output_path)
    print(f"Successfully uploaded merged data to {repo_id}/{remote_parquet_path}")
    print(f"Original shapes - Local: {local_df.shape}, Remote: {remote_df.shape}, Merged: {merged_df.shape}")

