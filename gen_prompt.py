import json
import os
import time
from openai import OpenAI
import logging
from utils.prompt import get_prompt
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def generate_scene_prompts(config, client, story_text: str) -> str:
    if config["base"]["manual_clip_story"]:
        pass
    else:
        prompt = get_prompt("sence")
    response = client.chat.completions.create(
        model="deepseek-chat",
        messages=[
            {"role": "system", "content": prompt},
            {"role": "user", "content": story_text}
        ],
        temperature=0.7,
        stream=False,
    )
    result = response.choices[0].message.content
    if result is None:
        raise ValueError("LLM 返回的内容为空")
    return result

def process_story_and_generate_prompts(config, client, story_path: str, output_path: str) -> None:
    """
    处理故事文本并生成场景提示词
    
    Args:
        story_path: 故事文本文件路径
        output_path: 输出JSON文件路径
    """
    # 如果输出文件已存在，直接返回
    if os.path.exists(output_path):
        logging.info(f"提示词文件 {output_path} 已存在，跳过生成步骤")
        return
    # 读取故事
    with open(story_path, "r", encoding="utf-8") as f:
        story = f.read()

    # 生成提示词
    result = generate_scene_prompts(config, client, story)
    
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
        print(f"生成的内容不是有效的JSON格式: {str(e)}")
        raise
        
    # 保存结果
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(result)
    print("✅ LLM 已生成分段与提示词，保存为 scene_prompts.json")

def parse_prompts(path):
    logging.info("开始解析提示词文件...")
    try:
        with open(path, "r", encoding="utf-8") as f:
            raw = f.read()
        
        # 解析 JSON
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as e:
            logging.error(f"JSON 解析错误: {str(e)}")
            logging.error(f"原始文本: {raw[:200]}...")  # 打印前200个字符用于调试
            raise
        
        scenes = data.get("scenes", [])
        
        if not scenes:
            raise ValueError("未找到任何场景数据")
        
        scene_data = [(scene["scene_number"], scene["description"], scene["scene_detail"], scene["prompt"]) 
                for scene in scenes]
        # 返回场景数据
        logging.info(f"成功解析 {len(scene_data)} 个场景")
        return scene_data
    except Exception as e:
        logging.error(f"解析提示词文件时出错: {str(e)}")
        raise



# def align_segments_with_script(segments: list, script_file: str) -> str:
#     """
#     将语音识别结果与原始脚本对齐并替换
    
#     Args:
#         segments: Whisper识别的语音片段列表
#         script: 原始脚本文本
    
#     Returns:
#         list: 对齐后的JSON格式文本
#     """
#     with open(script_file, "r", encoding="utf-8") as f:
#         script = f.read()
#     full_text = script.replace("\n", "").replace(" ", "")  # 去空格回车，提高匹配度

#     prompt = f"""
#     你是一个智能字幕匹配助手。
#     给你两个数据，一个是语音识别出的包含时间戳的中文句子组json数据列表，一个是剧本文本全文。
#     文本数据格式为字符串。
#     json数据列表格式为：
#     [
#         {{
#             "text": "句子原文",
#             "start": 开始时间戳,
#             "end": 结束时间戳,
#             "duration": 持续时间
#         }},
#         ...
#     ]
#     由于识别结果多有错漏，而时间戳信息需要保留，你的任务是：
#     1. 将语音识别出的中文句子组，与剧本文本进行逐句匹配，找到最匹配的那一句。
#     2. 将识别结果中的文本用匹配到的句子原文替换，其他任何地方都不动，返回给用户。
#     3. 返回的格式为与json数据列表格式相同的列表。
#     """
#     segments_json = []
#     for seg in segments:
#         segment_dict = {
#             "text": seg["text"],
#             "start": seg["start"],
#             "end": seg["end"],
#             "duration": seg["end"] - seg["start"]
#         }
#         segments_json.append(segment_dict)

#     usr_prompt = f"""
#     剧本文本：
#     {script}

#     语音识别出的中文句子组：
#     {segments_json}
#     """
    
#     response = client.chat.completions.create(
#         model="deepseek-chat",
#         messages=[
#             {"role": "system", "content": prompt},
#             {"role": "user", "content": usr_prompt}
#         ],
#     )

#     result = response.choices[0].message.content
#     print(result)
#     if result is None:
#         raise ValueError("LLM 返回的内容为空")
#     return result