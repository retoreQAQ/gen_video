import os
import json
import logging
import time
import whisper
from utils.tools import safe_extract_json
from utils.prompt import get_prompt


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

    system_prompt = get_prompt("align_subtitles")

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

def extract_subtitles(config, client):
    """
    提取字幕并进行对齐
    
    Args:
        audio_path: 音频文件路径
        script_path: 脚本文件路径
    """
    audio_path = os.path.join(config["base"]["base_dir"], config["files"]["audio"]["raw"])
    story_path = os.path.join(config["base"]["base_dir"], config["files"]["text"]["story"])
    subtitles_path = os.path.join(config["base"]["base_dir"], config["files"]["text"]["subtitles"])

    if os.path.exists(subtitles_path):
        with open(subtitles_path, "r", encoding="utf-8") as f:
            aligned_subtitles = json.load(f)
        logging.info(f"字幕文件已存在，跳过字幕提取")
        return aligned_subtitles
    
    logging.info("开始语音识别...")
    model = whisper.load_model("base")
    result = model.transcribe(audio_path, temperature=0.6, language="zh")
    segments = result["segments"]
    logging.info(f"语音识别完成，共识别出 {len(segments)} 个片段")
    aligned_subtitles = align_segments_with_script_batched(client, segments, story_path, batch_size=32)
    with open(subtitles_path, "w", encoding="utf-8") as f:
        json.dump(aligned_subtitles, f, ensure_ascii=False, indent=2)
    logging.info(f"字幕提取并对齐完成，输出到 {subtitles_path}")
    return aligned_subtitles