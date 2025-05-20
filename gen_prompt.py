import json
import os
import time
from openai import OpenAI
import logging
from utils.prompt import get_prompt
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def process_story_and_generate_prompts(config, client):
    """
    处理故事文本并生成场景提示词
    
    Args:
        story_path: 故事文本文件路径
        output_path: 输出JSON文件路径
    """
    output_path = os.path.join(config["base"]["base_dir"], config["files"]["text"]["scene_prompts"])
    story_path = os.path.join(config["base"]["base_dir"], config["files"]["text"]["story"])
    split_story_path = os.path.join(config["base"]["base_dir"], config["files"]["text"]["split_story"])
    # 如果输出文件已存在，直接返回
    if os.path.exists(output_path):
        logging.info(f"提示词文件 {output_path} 已存在，跳过生成步骤")
        return
    # 读取故事
    with open(story_path, "r", encoding="utf-8") as f:
        story = f.read()

    # 分割故事
    split_story = split_raw_story(client, story, split_story_path)

    # 生成提示词
    result = generate_scene_prompts(config, client, split_story)

    # 清理文本
    clean_prompts(result, output_path)

    # 解析提示词
    scene_datas = parse_prompts(output_path)

    return scene_datas


def split_raw_story(client, story_text, split_story_path) -> str:
    prompt = get_prompt("split_raw_story")
    response = client.chat.completions.create(
        model="deepseek-chat",
        messages=[
            {"role": "system", "content": prompt},
            {"role": "user", "content": story_text}
        ],
        temperature=0.3,
        stream=False,
    )
    result = response.choices[0].message.content
    if result is None:
        raise ValueError("LLM 返回的内容为空")   
    
    # 将分割后的文本转换为JSON格式
    segments = result.split("|")
    segments = [seg.strip() for seg in segments if seg.strip()]
    
    json_data = {
        "scenes": [
            {
                "scene_number": i,
                "text": text
            }
            for i, text in enumerate(segments)
        ]
    }
    
    result = json.dumps(json_data, ensure_ascii=False, indent=2)
    with open(split_story_path, "w", encoding="utf-8") as f:
        f.write(result)
    return result

def generate_scene_prompts(config, client, split_story) -> str:
    if config["base"]["manual_clip_story"]:
        pass
    else:
        prompt = get_prompt("generate_scene_prompts")
    response = client.chat.completions.create(
        model="deepseek-chat",
        messages=[
            {"role": "system", "content": prompt},
            {"role": "user", "content": split_story}
        ],
        temperature=0.7,
        stream=False,
    )
    result = response.choices[0].message.content
    if result is None:
        raise ValueError("LLM 返回的内容为空")
    return result

def clean_prompts(result, output_path):
    # 清理文本
    result = result.strip()
    if result.startswith("```json"):
        result = result[7:]
    if result.endswith("```"):
        result = result[:-3]
    result = result.strip()
    
    # 验证JSON
    try:
        json.loads(result)
    except json.JSONDecodeError as e:
        logging.error(f"生成的内容不是有效的JSON格式: {str(e)}")
        logging.error(f"原始文本: {result[:200]}...")  # 打印前200个字符用于调试
        raise
        
    # 保存结果
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(result)
    print("✅ LLM 已生成提示词，保存为 scene_prompts.json")

def parse_prompts(path):
    logging.info("开始解析提示词文件...")
    try:
        with open(path, "r", encoding="utf-8") as f:
            raw = f.read()
        data = json.loads(raw)
        scenes = data.get("scenes", [])
        if not scenes:
            raise ValueError("未找到任何场景数据")
        scene_datas = [(scene["scene_number"], scene["scene_detail"], scene["prompt"]) for scene in scenes]
        # 返回场景数据
        logging.info(f"成功解析 {len(scene_datas)} 个场景")
        return scene_datas
    except Exception as e:
        logging.error(f"解析提示词文件时出错: {str(e)}")
        raise