import os
import sys
from gen_prompt import process_story_and_generate_prompts
from gen_image import generate_images
from gen_video import generate_video
from subtitle import extract_subtitles
from gen_audio import generate_audio
import yaml
from openai import OpenAI
from dotenv import load_dotenv
from utils.tools import prepare_data, move_files
import logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def main():
    config = yaml.load(open("config/config.yaml", "r"), Loader=yaml.FullLoader)

    # 路径定义
    output_dir = config["base"]["output_dir"]
    base_dir = config["base"]["base_dir"]
    use_tts = config["base"]["use_tts"]
    synthesized_audio_mp3 = os.path.join(base_dir, f"synthesized_{config['files']['audio']['mp3']}")

    os.makedirs(base_dir, exist_ok=True)

    if len(sys.argv) < 2:
        story_name = config["base"]["story_name"]
    else:
        story_name = sys.argv[1]

    output_dir = os.path.join(output_dir, story_name)

    load_dotenv(dotenv_path="config/key.zshrc", override=True)
    llm_client = OpenAI(api_key=os.getenv("DEEPSEEK_API_KEY"), base_url="https://api.deepseek.com")
    
    
    # 1. 数据准备
    prepare_data(config, story_name)

    if use_tts:
        generate_audio(config, synthesized_audio_mp3)

    # 2. 提取字幕
    extract_subtitles(config, llm_client)

    # 3. 生成提示词
    process_story_and_generate_prompts(config, llm_client)

    # 5. 文生图
    generate_images(config)

    # 6. 合成视频（调用 gen_video.py，传递参数）
    generate_video(config)

    # 7. 移动文件
    move_files(base_dir, output_dir)

if __name__ == "__main__":
    main()

