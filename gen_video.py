import os
from moviepy.editor import AudioFileClip, ImageClip, CompositeVideoClip, concatenate_videoclips
import logging
from difflib import SequenceMatcher
from PIL import Image, ImageDraw, ImageFont # type: ignore
import numpy as np
from moviepy.editor import ImageClip
import json
import subtitle

def generate_video(config, use_text_match=False):
    """
    根据字幕和场景数据生成视频（图片和字幕分离，字幕严格按subtitles.json时间戳显示）
    Args:
        config: 配置文件
        use_text_match: 是否使用文本相似度匹配（保留但不影响本流程）
    """
    logging.info("开始合成视频...")
    audio_path = os.path.join(config["base"]["base_dir"], config["files"]["audio"]["mp3"])
    split_story_path = os.path.join(config["base"]["base_dir"], config["files"]["text"]["split_story"])
    subtitles_path = os.path.join(config["base"]["base_dir"], config["files"]["text"]["subtitles"])
    image_dir = os.path.join(config["base"]["base_dir"], config["files"]["media"]["image_dir"])
    output_video = os.path.join(config["base"]["base_dir"], config["files"]["media"]["output_video"])

    with open(subtitles_path, "r", encoding="utf-8") as f:
        subtitles = json.load(f)
    with open(split_story_path, "r", encoding="utf-8") as f:
        split_story = json.load(f)
        
    audio_duration = AudioFileClip(audio_path).duration
    scene_timestamps = get_scene_timestamps(split_story, subtitles, audio_duration)
    # 计算场景总时长
    total_duration = sum(scene["duration"] for scene in scene_timestamps)
    logging.info(f"总时长: {total_duration:.2f}秒")
    for idx, ts in enumerate(scene_timestamps):
        logging.info(f"场景{idx}: start={ts['start']}, end={ts['end']}, duration={ts['duration']}")

    audio_clip = AudioFileClip(audio_path)

    # 1. 生成图片片段序列
    img_clips = []
    for i, ts in enumerate(scene_timestamps):
        img_path = os.path.join(image_dir, f"scene_{i:02d}.png")
        if not os.path.exists(img_path) or ts["duration"] <= 0:
            logging.warning(f"图片文件不存在或时长无效: {img_path}")
            continue
        img_clip = ImageClip(img_path).set_duration(ts["duration"]).resize(height=720)
        img_clips.append(img_clip)
    if not img_clips:
        logging.error("没有可用的图片片段，无法生成视频")
        raise ValueError("没有可用的图片片段")
    img_video = concatenate_videoclips(img_clips)

    # 2. 生成字幕片段序列
    subtitle_clips = []
    for sub in subtitles:
        text = sub["text"]
        start = sub["start"]
        end = sub["end"]
        duration = round(end - start, 2)
        subtitle_clip = create_subtitle_clip(text, duration, img_video.size)
        subtitle_clip = subtitle_clip.set_start(start)
        subtitle_clips.append(subtitle_clip)
    if subtitle_clips:
        all_subtitles = CompositeVideoClip(subtitle_clips, size=img_video.size)
        # 3. 合成最终视频
        final_video = CompositeVideoClip([img_video, all_subtitles]).set_audio(audio_clip)
    else:
        logging.info("没有字幕片段，只保留图片")
        final_video = img_video.set_audio(audio_clip)
    final_video.write_videofile(output_video, fps=24)
    logging.info("视频生成完成！")

def get_img_duration(split_story, subtitles):
    """
    根据原文和字幕数据计算每个场景的时长
    
    Args:
        split_story: 分段后的原文列表
        subtitles: 带时间戳的字幕数据列表
    
    Returns:
        scene_durations: 每个场景的开始时间、结束时间和持续时间
    """
    scene_durations = []
    subtitle_idx = 0
    
    for story_text in split_story["scenes"]:
        start_time = None
        end_time = None
        
        # 遍历字幕找到匹配的片段
        while subtitle_idx < len(subtitles):
            subtitle = subtitles[subtitle_idx]
            subtitle_text = subtitle["text"]
            
            # 如果字幕文本在当前故事片段中
            if subtitle_text in story_text:
                if start_time is None:
                    start_time = subtitle["start"]
                end_time = subtitle["end"]
                subtitle_idx += 1
            else:
                # 如果已经找到了开始时间但字幕不匹配,说明当前片段结束
                if start_time is not None:
                    break
                subtitle_idx += 1
                
        if start_time is not None and end_time is not None:
            duration = end_time - start_time
            scene_durations.append({
                "start": start_time,
                "end": end_time,
                "duration": duration
            })
            
    return scene_durations

# 添加场景匹配函数
def find_best_matching_scene(text, scenes):
    """根据文本内容找到最匹配的场景"""
    best_match = None
    best_score = 0
    
    for scene_num, desc, scene_detail, prompt in scenes:
        # 计算文本与场景描述的相似度
        score = max(
            SequenceMatcher(None, text, desc).ratio(),
            SequenceMatcher(None, text, scene_detail).ratio()
        )
        if score > best_score:
            best_score = score
            best_match = scene_num
    
    return best_match if best_score > 0.3 else None  # 设置相似度阈值

def get_scene_timestamps(split_story, subtitles, audio_duration=None):
    """
    返回每个场景的时间戳（start, end, duration），自动补齐开头、结尾和中间gap
    """
    scene_timestamps = []
    subtitle_idx = 0
    for scene in split_story:
        scene_text = scene["text"]
        scene_start = None
        scene_end = None
        # 收集属于该场景的所有字幕
        while subtitle_idx < len(subtitles):
            subtitle = subtitles[subtitle_idx]
            if subtitle["text"] in scene_text:
                if scene_start is None:
                    scene_start = subtitle["start"]
                scene_end = subtitle["end"]
                subtitle_idx += 1
            else:
                # 如果已经开始匹配但遇到不属于该场景的字幕，说明该场景结束
                if scene_start is not None:
                    break
                subtitle_idx += 1
        if scene_start is not None and scene_end is not None:
            scene_timestamps.append({
                "start": scene_start,
                "end": scene_end,
                "duration": round(scene_end - scene_start, 2)
            })
        else:
            # 没有匹配到字幕，填None或0
            scene_timestamps.append({
                "start": None,
                "end": None,
                "duration": 0
            })
    # 修正开头
    if scene_timestamps and scene_timestamps[0]["start"] is not None and scene_timestamps[0]["start"] > 0:
        scene_timestamps[0]["start"] = 0
        scene_timestamps[0]["duration"] = round(scene_timestamps[0]["end"] - 0, 2)
    # 修正中间gap
    for i in range(1, len(scene_timestamps)):
        prev = scene_timestamps[i-1]
        curr = scene_timestamps[i]
        if prev["end"] is not None and curr["start"] is not None and curr["start"] > prev["end"]:
            # 比较duration，补短的
            prev_duration = prev["end"] - prev["start"] if prev["start"] is not None else 0
            curr_duration = curr["end"] - curr["start"] if curr["start"] is not None else 0
            if prev_duration < curr_duration:
                prev["end"] = curr["start"]
                prev["duration"] = round(prev["end"] - prev["start"], 2)
            else:
                curr["start"] = prev["end"]
                curr["duration"] = round(curr["end"] - curr["start"], 2)
    # 修正结尾
    if audio_duration is not None and scene_timestamps and scene_timestamps[-1]["end"] is not None and scene_timestamps[-1]["end"] < audio_duration:
        scene_timestamps[-1]["end"] = audio_duration
        scene_timestamps[-1]["duration"] = round(audio_duration - scene_timestamps[-1]["start"], 2)
    return scene_timestamps

def create_subtitle_clip(text, duration, img_size):
    """使用Pillow绘制自动换行、垂直居中的字幕"""
    width, height = img_size
    font_size = 30
    font_path = "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"
    font = ImageFont.truetype(font_path, font_size)

    # 自动换行
    max_text_width = int(width * 0.9)  # 限制文本最大宽度为画面宽度的90%
    draw_dummy = ImageDraw.Draw(Image.new("RGB", (1, 1)))

    def wrap_text(text, font, max_width):
        lines = []
        line = ""
        for char in text:
            if draw_dummy.textlength(line + char, font=font) <= max_width:
                line += char
            else:
                lines.append(line)
                line = char
        lines.append(line)
        return lines

    lines = wrap_text(text, font, max_text_width)
    line_height = font_size + 10
    total_text_height = len(lines) * line_height

    padding = 20
    canvas_height = total_text_height + 2 * padding
    canvas = Image.new("RGBA", (width, canvas_height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(canvas)

    # 背景矩形
    bg_top = 0
    bg_bottom = canvas_height
    draw.rectangle(
        [(0, bg_top), (width, bg_bottom)],
        fill=(0, 0, 0, 150)
    )

    # 绘制多行文字
    y = padding
    for line in lines:
        line_width = draw.textlength(line, font=font)
        x = (width - line_width) // 2
        draw.text((x, y), line, font=font, fill="white")
        y += line_height

    # 转换为ImageClip
    np_img = np.array(canvas)
    subtitle_clip = ImageClip(np_img).set_duration(duration)
    subtitle_clip = subtitle_clip.set_position(("center", "bottom"))
    subtitle_clip = subtitle_clip.crossfadein(0.3).crossfadeout(0.3)

    return subtitle_clip

if __name__ == "__main__":
    import yaml
    config = yaml.load(open("config/config.yaml", "r", encoding="utf-8"), Loader=yaml.FullLoader)
    generate_video(config, use_text_match=False)