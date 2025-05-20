import os
from moviepy.editor import AudioFileClip, ImageClip, CompositeVideoClip, concatenate_videoclips
import logging
from difflib import SequenceMatcher
from PIL import Image, ImageDraw, ImageFont # type: ignore
import numpy as np
from moviepy.editor import ImageClip
import json
import subtitle

def generate_video(config, scene_datas):
    """
    根据字幕和场景数据生成视频
    
    Args:
        audio_path: 音频文件路径
        subtitles: 字幕片段
        scene_data: 场景数据
        image_dir: 图片目录
        output_video: 输出视频路径
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

    clips = []
    audio_clip = AudioFileClip(audio_path)
    current_scene = None
    scene_duration = 0
    min_scene_duration = 3  # 最小场景持续时间（秒）

    for i, subtitle in enumerate(subtitles):
        try:
            start = float(subtitle["start"])
            end = float(subtitle["end"])
            duration = end - start
            text = subtitle["text"]
            
            # 根据文本内容找到最匹配的场景
            matching_scene = find_best_matching_scene(text, scene_datas)
            
            # 如果找到匹配的场景且当前场景持续时间足够长，则切换场景
            if matching_scene is not None and (current_scene is None or scene_duration >= min_scene_duration):
                current_scene = matching_scene
                scene_duration = 0
            
            # 如果没有找到匹配的场景，使用当前场景或默认场景
            if current_scene is None:
                current_scene = 0
            
            scene_duration += duration
            img_path = f"{image_dir}/scene_{current_scene:02d}.png"
            
            # 检查图片文件是否存在
            if not os.path.exists(img_path):
                logging.error(f"图片文件不存在: {img_path}")
                continue

            # 创建图片剪辑
            img_clip = ImageClip(img_path).set_duration(duration).resize(height=720)
            
            # 创建字幕剪辑
            subtitle_clip = create_subtitle_clip(text, duration, img_clip.size)
            
            # 合成视频片段
            clip = CompositeVideoClip([img_clip, subtitle_clip])
            clips.append(clip)
            logging.info(f"已处理第 {i+1} 个片段，使用场景 {current_scene}")
        except Exception as e:
            logging.error(f"处理第 {i+1} 个片段时出错: {str(e)}")
            continue

    # 检查是否有可用的片段
    if not clips:
        logging.error("没有可用的视频片段，无法生成视频")
        raise ValueError("没有可用的视频片段")

    logging.info("正在生成最终视频...")
    final_video = concatenate_videoclips(clips).set_audio(audio_clip)
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



def create_subtitle_clip(text, duration, img_size):
    """完全基于Pillow绘制字幕，避免ImageMagick依赖"""
    width, height = img_size
    font_size = 40

    # 加载字体（改为你的系统字体）
    font_path = "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"
    font = ImageFont.truetype(font_path, font_size)

    # 创建画布
    padding = 20
    canvas_height = font_size + 2 * padding
    canvas = Image.new("RGBA", (width, canvas_height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(canvas)

    # 渲染文字区域大小
    text_bbox = draw.textbbox((0, 0), text, font=font)
    text_width = text_bbox[2] - text_bbox[0]
    text_height = text_bbox[3] - text_bbox[1]

    # 计算位置居中
    x = (width - text_width) // 2
    y = (canvas_height - text_height) // 2

    # 背景矩形（半透明）
    draw.rectangle(
        [(x - 10, y - 10), (x + text_width + 10, y + text_height + 10)],
        fill=(0, 0, 0, 150)
    )

    # 绘制文字
    draw.text((x, y), text, font=font, fill="white")

    # 转换为ImageClip
    np_img = np.array(canvas)
    subtitle_clip = ImageClip(np_img).set_duration(duration)
    subtitle_clip = subtitle_clip.set_position(("center", "bottom"))
    subtitle_clip = subtitle_clip.crossfadein(0.3).crossfadeout(0.3)

    return subtitle_clip