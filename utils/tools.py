import os
import shutil
import json
import re
import subprocess
import logging
import string
import sys
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def prepare_data(config, story_name):
    # 路径定义
    output_dir = config["base"]["output_dir"]
    base_dir = config["base"]["base_dir"]
    upload_dir = config["base"]["upload_dir"]
    raw_audio = os.path.join(base_dir, config["files"]["audio"]["raw"])
    audio_mp3 = os.path.join(base_dir, config["files"]["audio"]["mp3"])
    use_tts = config["base"]["use_tts"]

    os.makedirs(base_dir, exist_ok=True)

    output_dir = os.path.join(output_dir, story_name)

    move_upload_files(upload_dir, base_dir, use_tts)
    if os.path.exists(raw_audio) and not os.path.exists(audio_mp3):
        convert_audio_to_mp3(raw_audio, audio_mp3)

def convert_audio_to_mp3(input_path, output_path):
    if not input_path.endswith(".mp3"):
        # 使用 ffmpeg 进行音频格式转换
        cmd = ["ffmpeg", "-y", "-i", input_path, output_path]
        subprocess.run(cmd, check=True)
        logging.info(f"音频已转换为 mp3 格式: {output_path}")

def move_upload_files(upload_dir, target_dir, use_tts):
    os.makedirs(upload_dir, exist_ok=True)
    os.makedirs(target_dir, exist_ok=True)
    # 检查story.txt和m4a文件是否已存在
    story_exists = False
    audio_exists = False
    for fname in os.listdir(target_dir):
        if fname == "story.txt":
            story_exists = True
            with open(os.path.join(target_dir, fname), 'r', encoding='utf-8') as f:
                content = f.read().strip()
                if not content:
                    logging.warning("story.txt 文件内容为空, 是否继续？ y/n")
                    if input() != "y":
                        exit()
        elif fname.endswith(".m4a") or fname.endswith(".mp3"):
            audio_exists = True

    if story_exists and audio_exists:
        logging.info("story.txt和audio文件已存在，跳过移动操作")
        return
    
    for fname in os.listdir(upload_dir):
        src = os.path.join(upload_dir, fname)
        tgt = os.path.join(target_dir, fname)
        if use_tts and not src.endswith(".txt"):
            logging.info(f"使用TTS，跳过非txt文件: {src}")
            continue
        shutil.move(src, tgt)
    with open(os.path.join(upload_dir, 'story.txt'), 'w', encoding='utf-8') as f:
        pass
    logging.info(f"已将 {upload_dir} 下所有文件移动到 {target_dir}")

def move_files(source_dir, target_dir):
    os.makedirs(target_dir, exist_ok=True)
    for fname in os.listdir(source_dir):
        src = os.path.join(source_dir, fname)
        tgt = os.path.join(target_dir, fname)
        shutil.move(src, tgt)

def safe_extract_json(content: str) -> list:
    """
    尝试从字符串中提取合法 JSON 列表，若失败则抛出异常
    """
    # 1. 先尝试直接解析
    try:
        data = json.loads(content)
        if isinstance(data, list):
            return data
    except json.JSONDecodeError:
        pass

    # 2. 正则提取以 [ 开头、以 ] 结尾的部分
    match = re.search(r"\[\s*\{.*?\}\s*\]", content, re.DOTALL)
    if match:
        try:
            data = json.loads(match.group(0))
            if isinstance(data, list):
                return data
        except json.JSONDecodeError:
            pass

    # 3. 提取失败
    raise ValueError("未能从模型输出中提取出合法的 JSON 列表")

def clean_zh_text(text: str) -> str:
    """
    清洗中文文本：去除标点、空格、换行等干扰字符
    """
    # 去除中文和英文标点
    text = re.sub(r"[！？｡。，“”‘’；：《》〈〉、·—…（）【】]", "", text)
    text = re.sub(r"[!?,.:;\"'()\[\]{}<>/~`@#$%^&*_+=\\|-]", "", text)

    # 去除所有空白符
    text = re.sub(r"\s+", "", text)

    return text.strip()

def clean_en_text(text: str) -> str:
    """
    清洗英文文本：小写化，去除标点和多余空白
    """

    # 小写化
    text = text.lower()

    # 去除英文标点
    text = text.translate(str.maketrans('', '', string.punctuation))

    # 去除多余空白
    text = re.sub(r"\s+", "", text)

    return text.strip()
