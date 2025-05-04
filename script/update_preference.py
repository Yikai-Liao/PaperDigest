#!/usr/bin/env python
import sys
import os
import json
import polars as pl
from datetime import datetime
import glob
from pathlib import Path
import re
from collections import defaultdict
import argparse

def build_json_index(json_root: Path):
    return {json_file.stem: json_file for json_file in json_root.glob("**/*.json")}

reaction2int = defaultdict(lambda: 3, {
    "THUMBS_UP": 0,
    "THUMBS_DOWN": 1,
    "EYES": 2,
    "HEART": 0,
})
int2pref = ["like", "dislike", "neutral", "unknown"]



def main(discussions_path, repo_owner):
    """
    从讨论数据中提取反应并更新偏好文件
    
    参数:
        discussions_path: 讨论数据JSON文件路径
        repo_owner: 仓库所有者
    """
    json_idx = build_json_index(Path("raw"))
    print(json_idx)

    with open(discussions_path, "r") as f:
        data = json.load(f)
    
    # 提取讨论节点
    nodes = data.get("data", {}).get("repository", {}).get("discussions", {}).get("nodes", [])
    if not nodes:
        print("未找到讨论数据")
        return
    
    
    ids = []
    prefs = []
    
    # 处理每个讨论
    for node in nodes:
        title = node.get("title", "")
        title = title.strip()
        title = title if title[-1] != "/" else title[:-1]
        stem = title.split("/")[-1].strip()
        if not stem:
            print(f"标题 '{title}' 无法提取stem，跳过")
            continue
        # 正常情况下, stem 应该是arxiv ID，使用正则检测是否合法
        m = re.match(r"^\d{4}\.\d{4,5}v?\d*$", stem)
        if not m:
            print(f"标题 '{title}' 的stem '{stem}' 不符合arxiv ID格式，跳过")
            continue

        if stem not in json_idx:
            print(f"标题 '{title}' 的stem '{stem}' 不在raw目录下的JSON文件中，跳过")
            continue

        reactions = [
            reaction2int[reaction['content']]
            for reaction in node.get("reactions", {}).get("nodes", [])
            if reaction.get("user", {}).get("login", "") == repo_owner and reaction.get("content", "") !=  ""
        ]
        
        if not reactions:
            print(f"标题 '{title}' 没有找到用户 '{repo_owner}' 的反应，跳过")
            continue
        
        pref = int2pref[min(reactions)]
        
        # 更新raw目录下的JSON文件
        with open(json_idx[stem].resolve(), "r", encoding="utf-8") as f:
            json_data = json.load(f)
        json_data["preference"] = pref
        # Write back to the JSON file
        with open(json_idx[stem].resolve(), "w", encoding="utf-8") as f:
            json.dump(json_data, f, indent=4, ensure_ascii=False)

        ids.append(stem)
        prefs.append(pref)

    patch = pl.DataFrame({"id": ids, "preference": prefs}, schema={"id": pl.Utf8, "preference": pl.Utf8})

    # YYYY-MM.csv from now
    csv_path = Path("preference") / f"{datetime.now().strftime('%Y-%m')}.csv"
    if not csv_path.exists():
        print(f"文件 {csv_path} 不存在，创建新文件")
        patch.write_csv(csv_path, include_header=True)
        print(f"文件 {csv_path} 已创建，包含 {len(patch)} 行数据")
    else:
        # 读取，并覆盖可能重复的行，然后新增
        existing_data = pl.read_csv(csv_path, schema={"id": pl.Utf8, "preference": pl.Utf8})
        print(f"文件 {csv_path} 已存在，读取现有数据 {len(existing_data)} 行")
        combined_data = pl.concat([existing_data, patch]).unique(subset=["id"], keep="last").sort("id")
        combined_data.write_csv(csv_path, include_header=True)
        print(f"文件 {csv_path} 已更新，包含 {len(combined_data)} 行数据")

if __name__ == "__main__":
    # 用法: python update_preference_from_discussion.py discussions.json repo_owner since_iso yearmonth
    # if len(sys.argv) == 3:
    #     print("用法: python update_preference_from_discussion.py <discussions.json> <repo_owner>")
    #     sys.exit(1)
    # main(*sys.argv[1:3])

    parser = argparse.ArgumentParser(description="从讨论数据中提取反应并更新偏好文件")
    parser.add_argument("discussions_path", type=str, help="讨论数据JSON文件路径")
    parser.add_argument("repo_owner", type=str, help="仓库所有者")

    args = parser.parse_args()
    discussions_path = args.discussions_path
    repo_owner = args.repo_owner
    main(Path(discussions_path), repo_owner)