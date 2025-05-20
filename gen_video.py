import os
import whisper
from moviepy.editor import VideoFileClip, AudioFileClip, ImageClip, CompositeVideoClip, concatenate_videoclips, ColorClip, TextClip
from diffusers.pipelines.stable_diffusion.pipeline_stable_diffusion import StableDiffusionPipeline
import torch
import json
import logging
from difflib import SequenceMatcher
from PIL import Image, ImageDraw, ImageFont # type: ignore
import numpy as np
from moviepy.editor import ImageClip
from utils.tools import safe_extract_json
import time

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def align_segments_with_script_batched(client, segments, script_file, batch_size = 8):
    """
    Whisper语音识别片段与剧本逐段匹配（batched处理，节省token）

    Args:
        segments: Whisper识别的语音片段列表
        script_file: 完整剧本路径
        batch_size: 每次发送给 LLM 的片段数量

    Returns:
        List[dict]: 对齐后的字幕数据
    """
    with open(script_file, "r", encoding="utf-8") as f:
        script = f.read().replace("\n", "").replace(" ", "")  # 清理格式

    system_prompt = """
你是一个字幕智能助手。任务是：
1. 接收一段剧本文本 + 若干语音识别句子（含时间戳）。
2. 将每个识别句子的 text 替换为在剧本文本中最接近的一句。
3. 保留时间戳字段 start / end / duration，不得改动。
4. 返回结构与输入一致的 JSON 列表，仅替换 text 字段。
    """

    aligned_results = []

    for i in range(0, len(segments), batch_size):
        batch = segments[i:i + batch_size]
        formatted_batch = [
            {
                "text": seg["text"],
                "start": round(seg["start"], 2),
                "end": round(seg["end"], 2),
                "duration": round(seg["end"] - seg["start"], 2)
            } for seg in batch
        ]

        user_prompt = f"""剧本文本：
{script}

识别句子列表：
{json.dumps(formatted_batch, ensure_ascii=False, indent=2)}
"""

        try:
            response = client.chat.completions.create(
                model="deepseek-chat",
                messages=[
                    {"role": "system", "content": system_prompt.strip()},
                    {"role": "user", "content": user_prompt.strip()}
                ],
                temperature=0.2,
            )
            result = response.choices[0].message.content
            if result is None:
                raise ValueError("LLM 返回的内容为空")
            batch_result = safe_extract_json(result)
            aligned_results.extend(batch_result)
            time.sleep(1.2)  # 防止触发速率限制
        except Exception as e:
            print(f"⚠️ 批次处理失败（第 {i//batch_size+1} 批）: {e}")
            continue

    return aligned_results

def extract_subtitles(client, audio_path, script_path, output_path):
    """
    提取字幕并进行对齐
    
    Args:
        audio_path: 音频文件路径
        script_path: 脚本文件路径
    """
    if os.path.exists(output_path):
        with open(output_path, "r", encoding="utf-8") as f:
            aligned_segments = json.load(f)
        logging.info(f"已从 {output_path} 读取 {len(aligned_segments)} 条字幕")
        return aligned_segments
    logging.info("开始语音识别...")
    model = whisper.load_model("base")
    result = model.transcribe(audio_path, temperature=0.6, language="zh")
    segments = result["segments"]
    logging.info(f"语音识别完成，共识别出 {len(segments)} 个片段")
    # 可选：对齐字幕

    aligned_segments = align_segments_with_script_batched(client, segments, script_path, batch_size=32)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(aligned_segments, f, ensure_ascii=False, indent=2)
    logging.info(f"字幕提取并对齐完成，输出到 {output_path}")
    return aligned_segments

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


def generate_video(audio_path, segments, scene_data, image_dir):
    """
    根据字幕和场景数据生成视频
    
    Args:
        audio_path: 音频文件路径
        segments: 字幕片段
        scene_data: 场景数据
        image_dir: 图片目录
    """
    logging.info("开始合成视频...")
    clips = []
    audio_clip = AudioFileClip(audio_path)
    current_scene = None
    scene_duration = 0
    min_scene_duration = 3  # 最小场景持续时间（秒）

    for i, seg in enumerate(segments):
        try:
            start = float(seg["start"])
            end = float(seg["end"])
            duration = end - start
            text = seg["text"]
            
            # 根据文本内容找到最匹配的场景
            matching_scene = find_best_matching_scene(text, scene_data)
            
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
    final_video.write_videofile("output_video.mp4", fps=24)
    logging.info("视频生成完成！")