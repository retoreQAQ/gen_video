import os
import requests
from pathlib import Path

# 创建保存图片的目录
output_dir = Path("output/temp/images")
output_dir.mkdir(parents=True, exist_ok=True)

# 读取url文件
with open("manual_img/urls.txt", "r") as f:
    urls = f.read().splitlines()

# 假设 urls 是已经读取好的 URL 列表
urls = [url.strip() for url in urls]  # 清理空格

# 检查是否有重复
from collections import defaultdict

duplicate_urls = defaultdict(list)
for idx, url in enumerate(urls):
    duplicate_urls[url].append(idx + 1)  # 使用行号（从1开始）

# 过滤出实际重复的URL
duplicates = {url: lines for url, lines in duplicate_urls.items() if len(lines) > 1}

# 如果存在重复
if duplicates:
    print("\n发现重复的URL:")
    for url, lines in duplicates.items():
        # print(f"URL: {url}")
        print(f"出现在以下行: {lines}")

    choice = input("\n发现重复URL，是否退出程序? (y/n): ")
    if choice.lower() == 'y':
        print("检测到重复URL，程序退出")
        exit()
    else:
        print("忽略重复URL，继续执行程序...")

for i, url in enumerate(urls):
    try:
        # 下载图片
        response = requests.get(url)
        response.raise_for_status()
        
        # 构建保存路径
        scene_num = str(i).zfill(2)
        save_path = output_dir / f"scene_{scene_num}.png"
        
        # 保存图片
        with open(save_path, "wb") as f:
            f.write(response.content)
            
        print(f"已下载并保存: scene_{scene_num}.png")
            
    except Exception as e:
        print(f"下载第{i}张图片时出错: {str(e)}")

print("所有图片下载完成!")


