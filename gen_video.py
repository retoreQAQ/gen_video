import os
from moviepy.editor import AudioFileClip, ImageClip, CompositeVideoClip, concatenate_videoclips
import logging
from PIL import Image, ImageDraw, ImageFont # type: ignore
import numpy as np
import json
from utils.tools import clean_zh_text

def generate_video(config):
    """
    根据字幕和场景数据生成视频（图片和字幕分离，字幕严格按subtitles.json时间戳显示）
    Args:
        config: 配置文件
    """

    logging.info("开始合成视频...")
    audio_path = os.path.join(config["base"]["base_dir"], config["files"]["audio"]["mp3"])
    split_story_path = os.path.join(config["base"]["base_dir"], config["files"]["text"]["split_story"])
    subtitles_path = os.path.join(config["base"]["base_dir"], config["files"]["text"]["subtitles"])
    image_dir = os.path.join(config["base"]["base_dir"], config["files"]["media"]["image_dir"])
    output_video = os.path.join(config["base"]["base_dir"], config["files"]["media"]["output_video"])
    subtitles_matched_scenes_path = os.path.join(config["base"]["base_dir"], config["files"]["text"]["subtitles_matched_scenes"])
    split_story_matched_subs_path = os.path.join(config["base"]["base_dir"], config["files"]["text"]["split_story_matched_subs"])
    font_path = os.path.join(config["base"]["base_dir"], "resources", "font", config["files"]["resources"]["font"])

    with open(subtitles_path, "r", encoding="utf-8") as f:
        subtitles = json.load(f)
    with open(split_story_path, "r", encoding="utf-8") as f:
        split_story = json.load(f)
        
    # audio_duration = AudioFileClip(audio_path).duration
    subtitles, split_story = add_time_to_split_story(subtitles, split_story, subtitles_matched_scenes_path, split_story_matched_subs_path, 30)
    scene_timestamps = get_scene_timestamps(split_story)

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
        subtitle_clip = create_subtitle_clip(text, duration, img_video.size, font_path)
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

def add_time_to_split_story(subtitles, split_story, subtitles_matched_scenes_path, split_story_matched_subs_path, audio_duration=None):
    """
    给split_story.json每条场景加上start, end, duration字段，值为该场景对应的字幕的start, end, duration列表
    """

    for scene in split_story:
        scene["consumed"] = False
        scene["start"] = None
        scene["end"] = None
        scene["duration"] = 0.0
        scene["matched_subs"] = []

    for i, sub in enumerate(subtitles):
        sub_text = clean_zh_text(sub["text"])
        sub["matched_scenes"] = []

        for scene in split_story:

            if scene["consumed"]:
                continue

            scene_text = clean_zh_text(scene["text"])

            if len(sub_text) < len(scene_text):
                # 字幕较短，判断字幕是否被场景包含
                if sub_text in scene_text:
                    sub["matched_scenes"].append(scene["scene_number"])
                    scene["matched_subs"].append(i)
                    break
                else:
                    scene["consumed"] = True
                    continue
            else:
                # 字幕较长，判断场景是否被字幕包含
                if scene_text in sub_text:
                    sub["matched_scenes"].append(scene["scene_number"])
                    scene["matched_subs"].append(i)
                    scene["consumed"] = True
                    # 均分的话，需要遍历完这个字幕才能知道包含多少图片，才能知道均分后每张图片的开始结束和时长，怎么处理
                else:
                    break

    # Step 0: 若未指定 audio_duration，从字幕中推断
    if audio_duration is None:
        audio_duration = max((sub["end"] for sub in subtitles if "end" in sub), default=0.0)

    # Step 1: 分配每个 scene 的初步时间
    for scene in split_story:
        matched_subs = scene.get("matched_subs", [])
        if not matched_subs:
            continue

        subs = [subtitles[i] for i in matched_subs]

        # 场景只被一个字幕匹配（常规情况）
        if all(len(sub.get("matched_scenes", [])) == 1 for sub in subs):
            start = min(sub["start"] for sub in subs)
            end = max(sub["end"] for sub in subs)
            scene["start"] = round(start, 2)
            scene["end"] = round(end, 2)
            scene["duration"] = round(end - start, 2)

        else:
            # 场景被多个字幕共享（如一个字幕中包含多张图片的描述）
            for sub in subs:
                matched = sub.get("matched_scenes", [])
                if len(matched) <= 1:
                    continue
                total_duration = sub["end"] - sub["start"]
                per_duration = total_duration / len(matched)
                for j, scn_num in enumerate(matched):
                    scn = next((s for s in split_story if s["scene_number"] == scn_num), None)
                    if scn:
                        scn_start = sub["start"] + j * per_duration
                        scn_end = sub["start"] + (j + 1) * per_duration if j < len(matched) - 1 else sub["end"]
                        scn["start"] = round(scn_start, 2)
                        scn["end"] = round(scn_end, 2)
                        scn["duration"] = round(scn["end"] - scn["start"], 2)

    # Step 2: 修正开头
    if split_story and split_story[0].get("start") is not None and split_story[0]["start"] > 0:
        split_story[0]["start"] = 0.0
        split_story[0]["duration"] = round(split_story[0]["end"] - 0.0, 2)

    # Step 3: 修正中间 gap
    for i in range(1, len(split_story)):
        prev = split_story[i - 1]
        curr = split_story[i]
        if prev.get("end") is not None and curr.get("start") is not None and curr["start"] > prev["end"]:
            prev_duration = prev["end"] - prev.get("start", 0)
            curr_duration = curr["end"] - curr.get("start", 0)
            if prev_duration < curr_duration:
                prev["end"] = curr["start"]
                prev["duration"] = round(prev["end"] - prev["start"], 2)
            else:
                curr["start"] = prev["end"]
                curr["duration"] = round(curr["end"] - curr["start"], 2)

    # Step 4: 修正结尾
    if split_story and split_story[-1].get("end") is not None and split_story[-1]["end"] < audio_duration:
        split_story[-1]["end"] = round(audio_duration, 2)
        split_story[-1]["duration"] = round(audio_duration - split_story[-1]["start"], 2)

    # Step 5: 保存结果
    with open(subtitles_matched_scenes_path, "w", encoding="utf-8") as f:
        json.dump(subtitles, f, ensure_ascii=False, indent=2)
    with open(split_story_matched_subs_path, "w", encoding="utf-8") as f:
        json.dump(split_story, f, ensure_ascii=False, indent=2)
    return subtitles, split_story

def get_scene_timestamps(split_story):
    """
    返回每个场景的时间戳（start, end, duration）
    """
    scene_timestamps = []
    for scene in split_story:
        scene_timestamps.append({
            "scene_number": scene["scene_number"],
            "start": scene["start"],
            "end": scene["end"],
            "duration": scene["duration"]
        })
        # 计算场景总时长
    total_duration = sum(scene["duration"] for scene in scene_timestamps)
    logging.info(f"总时长: {total_duration:.2f}秒")
    for idx, ts in enumerate(scene_timestamps):
        logging.info(f"场景{idx}: start={ts['start']}, end={ts['end']}, duration={ts['duration']}")
    return scene_timestamps

def create_subtitle_clip(text, duration, img_size, font_path):
    """使用Pillow绘制自动换行、垂直居中的字幕"""
    width, height = img_size
    font_size = 30
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
    generate_video(config)