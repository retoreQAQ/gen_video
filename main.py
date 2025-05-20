import os
import sys
import shutil
import subprocess
from gen_prompt import process_story_and_generate_prompts, parse_prompts
from gen_image import generate_images
from gen_video import extract_subtitles, generate_video
import whisper
import json
import logging
import yaml
from openai import OpenAI
from dotenv import load_dotenv

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def move_temp_files(temp_dir, target_dir):
    os.makedirs(temp_dir, exist_ok=True)
    os.makedirs(target_dir, exist_ok=True)
    # 检查story.txt和m4a文件是否已存在
    story_exists = False
    m4a_exists = False
    for fname in os.listdir(target_dir):
        if fname == "story.txt":
            story_exists = True
        elif fname.endswith(".m4a"):
            m4a_exists = True
    
    if story_exists and m4a_exists:
        logging.info("story.txt和m4a文件已存在，跳过移动操作")
        return
    for fname in os.listdir(temp_dir):
        src = os.path.join(temp_dir, fname)
        tgt = os.path.join(target_dir, fname)
        shutil.move(src, tgt)
        if src.endswith(".txt"):
            # 如果是文本文件，创建一个空的同名文件
            with open(src, 'w', encoding='utf-8') as f:
                pass
    logging.info(f"已将 {temp_dir} 下所有文件移动到 {target_dir}")



def convert_audio_to_mp3(input_path, output_path):
    # 使用 ffmpeg 进行音频格式转换
    cmd = ["ffmpeg", "-y", "-i", input_path, output_path]
    subprocess.run(cmd, check=True)
    logging.info(f"音频已转换为 mp3 格式: {output_path}")

def main():
    config = yaml.load(open("config/config.yaml", "r"), Loader=yaml.FullLoader)
    resources_dir = config["base"]["resources_dir"]
    temp_dir = config["base"]["temp_dir"]
    if len(sys.argv) < 2:
        story_name = config["base"]["story_name"]
    else:
        story_name = sys.argv[1]

    base_dir = os.path.join(resources_dir, story_name)
    move_temp_files(temp_dir, base_dir)

    # 路径定义
    audio_m4a = os.path.join(base_dir, config["files"]["audio"]["m4a"])
    audio_mp3 = os.path.join(base_dir, config["files"]["audio"]["mp3"])
    story_file = os.path.join(base_dir, config["files"]["text"]["story"])
    prompt_json = os.path.join(base_dir, config["files"]["text"]["prompts"])
    subtitle_json = os.path.join(base_dir, config["files"]["text"]["subtitles"])
    image_dir = os.path.join(base_dir, config["files"]["media"]["image_dir"])
    output_video = os.path.join(base_dir, config["files"]["media"]["output_video"])

    load_dotenv(dotenv_path=".config/key.zshrc", override=True)
    ds_client = OpenAI(api_key=os.getenv("DEEPSEEK_API_KEY"), base_url="https://api.deepseek.com")
    img_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    
    # 1. 音频格式转换（如有 .m4a）
    if os.path.exists(audio_m4a) and not os.path.exists(audio_mp3):
        convert_audio_to_mp3(audio_m4a, audio_mp3)
    elif not os.path.exists(audio_mp3):
        raise FileNotFoundError("未找到音频文件 all.m4a 或 all.mp3")

    # 2. 提取字幕
    aligned_segments = extract_subtitles(ds_client, audio_mp3, story_file, subtitle_json)

    # 3. 生成提示词
    process_story_and_generate_prompts(config, ds_client, story_file, prompt_json)

    # 4. 解析提示词
    scene_data = parse_prompts(prompt_json)

    # 5. 文生图
    generate_images(scene_data, image_dir, img_client)

    # 6. 合成视频（调用 gen_video.py，传递参数）
    generate_video(audio_mp3, aligned_segments, scene_data, image_dir)

if __name__ == "__main__":
    main()

