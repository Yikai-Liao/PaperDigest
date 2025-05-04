#!/usr/bin/env python
import sys
import os
import json
import polars as pl
from datetime import datetime
import glob

def update_raw_json_preferences(arxiv_id, preference_value):
    """
    更新raw目录下对应arxiv论文的JSON文件中的preference字段
    
    参数:
        arxiv_id: 论文ID (如 2501.12345)
        preference_value: 偏好值 ('like' 或 'dislike')
    
    返回:
        更新的文件路径列表
    """
    raw_dir = "raw"
    updated_files = []
    
    # 查找所有可能匹配的JSON文件
    json_pattern = os.path.join(raw_dir, f"*{arxiv_id}*.json")
    json_files = glob.glob(json_pattern)
    
    if not json_files:
        # 检查更一般的模式，仅匹配数字部分
        id_parts = arxiv_id.split('.')
        if len(id_parts) == 2:
            json_pattern = os.path.join(raw_dir, f"*{id_parts[0]}*{id_parts[1]}*.json")
            json_files = glob.glob(json_pattern)
    
    for json_file in json_files:
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # 更新preference字段
            data['preference'] = preference_value
            
            with open(json_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            
            updated_files.append(json_file)
        except Exception as e:
            print(f"更新 {json_file} 时出错: {str(e)}")
    
    return updated_files

def main(discussions_path, repo_owner, since_iso, yearmonth):
    """
    从讨论数据中提取反应并更新偏好文件
    
    参数:
        discussions_path: 讨论数据JSON文件路径
        repo_owner: 仓库所有者
        since_iso: ISO格式的日期，仅处理此日期之后更新的讨论
        yearmonth: 年月字符串 (YYYY-MM)，用于保存偏好文件
    """
    with open(discussions_path, "r") as f:
        data = json.load(f)
    
    # 提取讨论节点
    nodes = data.get("data", {}).get("repository", {}).get("discussions", {}).get("nodes", [])
    if not nodes:
        print("未找到讨论数据")
        return
    
    records = []
    updated_json_files = set()
    
    # 处理每个讨论
    for node in nodes:
        updated_at = node.get("updatedAt")
        if not updated_at or updated_at < since_iso:
            continue
            
        title = node.get("title", "")
        import re
        # 从标题中提取arxiv ID
        m = re.match(r"^paper_machine/papers/([0-9]+\.[0-9]+)/?", title)
        if not m:
            continue
            
        arxiv_id = m.group(1)
        
        # 处理反应
        for reaction in node.get("reactions", {}).get("nodes", []):
            if reaction.get("user", {}).get("login") == repo_owner and reaction.get("content") in ("THUMBS_UP", "THUMBS_DOWN"):
                pref = "like" if reaction["content"] == "THUMBS_UP" else "dislike"
                records.append((arxiv_id, pref))
                
                # 更新raw目录下的JSON文件
                updated_files = update_raw_json_preferences(arxiv_id, pref)
                updated_json_files.update(updated_files)
    
    if not records:
        print("没有找到需要更新的偏好")
        return
    
    # 更新preference目录下的CSV文件
    pref_dir = "preference"
    os.makedirs(pref_dir, exist_ok=True)
    pref_file = os.path.join(pref_dir, f"{yearmonth}.csv")
    
    # 读取现有偏好CSV或创建新的
    if os.path.exists(pref_file):
        df = pl.read_csv(pref_file)
    else:
        df = pl.DataFrame({"id": [], "preference": []})
    
    # 将新记录添加到DataFrame
    new_df = pl.DataFrame(records, schema=["id", "preference"])
    
    # 合并并确保每个ID只保留最新的偏好
    combined = pl.concat([df, new_df]).unique(subset=["id"], keep="last").sort("id")
    
    # 保存更新后的CSV
    combined.write_csv(pref_file)
    
    # 输出结果
    print(f"更新了CSV文件: {pref_file}")
    print(f"更新了 {len(updated_json_files)} 个JSON文件")
    
    print("<<<UPDATED_FILES_START>>>")
    print(pref_file)
    for json_file in updated_json_files:
        print(json_file)
    print("<<<UPDATED_FILES_END>>>")

if __name__ == "__main__":
    # 用法: python update_preference_from_discussion.py discussions.json repo_owner since_iso yearmonth
    if len(sys.argv) < 5:
        print("用法: python update_preference_from_discussion.py <discussions.json> <repo_owner> <since_iso> <yearmonth>")
        sys.exit(1)
    
    main(*sys.argv[1:5])