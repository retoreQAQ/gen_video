import os
import json
import logging
import time
import whisper
from utils.tools import safe_extract_json
from utils.prompt import get_prompt

def extract_subtitles(config, client):
    """
    提取字幕并进行对齐
    
    Args:
        audio_path: 音频文件路径
        script_path: 脚本文件路径
    """
    audio_path = os.path.join(config["base"]["base_dir"], config["files"]["audio"]["mp3"])
    story_path = os.path.join(config["base"]["base_dir"], config["files"]["text"]["story"])
    subtitles_path = os.path.join(config["base"]["base_dir"], config["files"]["text"]["subtitles"])
    asr_result_path = os.path.join(config["base"]["base_dir"], config["files"]["text"]["asr_result"])

    model = config["model"]["asr"]["model"]
    if model == "whisper":
        model = config["model"]["asr"]["whisper"]
    else:
        raise ValueError("不支持的语音识别模型")
    align_batch_size = config["model"]["llm"]["align_batch_size"]

    if os.path.exists(subtitles_path):
        with open(subtitles_path, "r", encoding="utf-8") as f:
            aligned_subtitles = json.load(f)
        logging.info(f"字幕文件已存在，跳过字幕提取")
        return aligned_subtitles
    
    if os.path.exists(asr_result_path):
        with open(asr_result_path, "r", encoding="utf-8") as f:
            asr_result = json.load(f)
        logging.info(f"ASR结果文件已存在，跳过ASR,开始对齐")
    else:
        logging.info("开始语音识别...")
        model = whisper.load_model(model)
        result = model.transcribe(audio_path, temperature=0.6, language="zh")
        segments = result["segments"]
        logging.info(f"语音识别完成，共识别出 {len(segments)} 个片段")
        asr_result = [
            {
                "text": seg["text"], #type: ignore
                "start": round(seg["start"], 2), #type: ignore
                "end": round(seg["end"], 2), #type: ignore
                "duration": round(seg["end"] - seg["start"], 2) #type: ignore
            } for seg in segments
        ]
        with open(asr_result_path, "w", encoding="utf-8") as f:
            json.dump(asr_result, f, ensure_ascii=False, indent=2)
    aligned_subtitles = align_segments_with_script_batched(client, asr_result, story_path, asr_result_path, batch_size=align_batch_size)
    with open(subtitles_path, "w", encoding="utf-8") as f:
        json.dump(aligned_subtitles, f, ensure_ascii=False, indent=2)
    logging.info(f"字幕提取并对齐完成，输出到 {subtitles_path}")
    return aligned_subtitles

def align_segments_with_script_batched(client, asr_result, script_file, asr_result_path, batch_size = 8):
    """
    Whisper语音识别片段与剧本逐段匹配（batched处理，节省token）

    Args:
        asr_result: Whisper识别的语音片段列表
        script_file: 完整剧本路径
        batch_size: 每次发送给 LLM 的片段数量

    Returns:
        List[dict]: 对齐后的字幕数据
    """
    with open(script_file, "r", encoding="utf-8") as f:
        script = f.read()

    system_prompt = get_prompt("align_subtitles")

    aligned_results = []

    for i in range(0, len(asr_result), batch_size):
        batch = asr_result[i:i + batch_size]
        with open(asr_result_path, "w", encoding="utf-8") as f:
            json.dump(batch, f, ensure_ascii=False, indent=2)

        user_prompt = f"""剧本文本：
{script}

识别句子列表：
{json.dumps(batch, ensure_ascii=False, indent=2)}
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

