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
    raw_output_path = os.path.join(config["base"]["base_dir"], config["files"]["text"]["raw_scene_prompts"])
    output_path = os.path.join(config["base"]["base_dir"], config["files"]["text"]["scene_prompts"])
    story_path = os.path.join(config["base"]["base_dir"], config["files"]["text"]["story"])
    split_story_path = os.path.join(config["base"]["base_dir"], config["files"]["text"]["split_story"])

    generate_batch_size = config["model"]["llm"]["generate_batch_size"]

    # 读取故事
    with open(story_path, "r", encoding="utf-8") as f:
        story = f.read()
    if len(story) == 0:
        raise ValueError("故事文本为空")

    # 分割故事
    split_story = split_raw_story(client, story, split_story_path)

    # 生成提示词
    result = generate_scene_prompts(client, split_story, output_path, generate_batch_size)

    return result


def split_raw_story(client, story_text, split_story_path) -> str:
    if os.path.exists(split_story_path):
        logging.info(f"分割故事文件 {split_story_path} 已存在，跳过生成步骤")
        with open(split_story_path, "r", encoding="utf-8") as f:
            result = f.read()
        return result
    logging.info("开始分割故事...")
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
    
    json_data =[
            {
                "scene_number": i,
                "text": text.strip()
            }
            for i, text in enumerate(segments)
        ]
    
    result = json.dumps(json_data, ensure_ascii=False, indent=2)
    with open(split_story_path, "w", encoding="utf-8") as f:
        f.write(result)
    return result

def generate_scene_prompts(client, split_story, output_path, batch_size) -> str:
    if os.path.exists(output_path):
        logging.info(f"提示词文件 {output_path} 已存在，跳过生成步骤")
        with open(output_path, "r", encoding="utf-8") as f:
            result = f.read()
        return result
    logging.info("开始生成场景提示词...")
    prompt = get_prompt("generate_scene_prompts")

    # 将故事分成多个批次处理
    scenes = json.loads(split_story)
    results = []

    for i in range(0, len(scenes), batch_size):
        batch = scenes[i:i + batch_size]
        batch_story = json.dumps({"scenes": batch}, ensure_ascii=False, indent=2)

        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": batch_story}
            ],
            temperature=0.7,
            stream=False,
        )
        
        batch_result = response.choices[0].message.content
        if batch_result is None:
            raise ValueError(f"第 {i//batch_size + 1} 批次 LLM 返回的内容为空")
            
        # 清理并解析批次结果
        batch_result = batch_result.strip()
            
        try:

            batch_data = json.loads(batch_result)
            results.extend(batch_data)
        except json.JSONDecodeError as e:
            raise ValueError(f"第 {i//batch_size + 1} 批次返回的不是有效的JSON格式: {str(e)}")

    # 合并所有批次的结果
    final_result = json.dumps(results, ensure_ascii=False, indent=2)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(final_result)
    logging.info(f"成功生成 {len(final_result)} 个场景提示词,保存为 scene_prompts.json")
    return final_result