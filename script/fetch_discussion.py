#!/usr/bin/env python
import sys
import requests
import json
import os

def main(owner, repo, token, out_path="discussions.json"):
    """
    获取GitHub仓库讨论数据
    
    参数:
        owner: 仓库所有者
        repo: 仓库名称
        token: GitHub API令牌
        out_path: 输出文件路径
    """
    query = """
    query($repoOwner: String!, $repoName: String!) {
      repository(owner: $repoOwner, name: $repoName) {
        discussions(
          last: 150,
          orderBy: {field: UPDATED_AT, direction: DESC}
        ) {
          nodes {
            id
            title
            updatedAt
            url
            reactions(first: 100) {
              nodes {
                content
                user {
                  login
                }
              }
            }
          }
        }
      }
    }
    """
    variables = {"repoOwner": owner, "repoName": repo}
    headers = {"Authorization": f"Bearer {token}"}
    
    print(f"正在获取 {owner}/{repo} 仓库的讨论数据...")
    
    resp = requests.post(
        "https://api.github.com/graphql",
        json={"query": query, "variables": variables},
        headers=headers,
    )
    resp.raise_for_status()
    
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(resp.json(), f, indent=2)
        
    print(f"讨论数据已保存到 {out_path}")

if __name__ == "__main__":
    # 用法: python fetch_discussions.py owner repo token [out_path]
    if len(sys.argv) < 4:
        print("用法: python fetch_discussions.py <owner> <repo> <token> [out_path]")
        sys.exit(1)
    
    main(*sys.argv[1:])