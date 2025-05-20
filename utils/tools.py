import json
import re
from sentence_transformers import SentenceTransformer, util
import torch

from difflib import SequenceMatcher

def align_by_substring_matching(segments, full_script_text):
    result = []
    cursor = 0  # 在剧本中推进的指针

    for seg in segments:
        whisper_text = seg["text"]
        search_text = full_script_text[cursor:]

        # 找到 whisper 识别的句子在剧本中的最佳匹配位置
        matcher = SequenceMatcher(None, search_text, whisper_text)
        match = matcher.find_longest_match(0, len(search_text), 0, len(whisper_text))

        if match.size > 5:
            # 在剧本中匹配到的位置
            start = cursor + match.a
            end = start + match.size
            aligned_text = full_script_text[start:end]
            cursor = end  # 向后推进，避免重复匹配
        else:
            aligned_text = whisper_text  # 匹配度太低，保留原内容

        seg["text"] = aligned_text
        result.append(seg)

    return result


def align_script_by_semantic(whisper_segments, manual_script):
    # Step 1: 准备模型
    model = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")

    # Step 2: 拆分剧本为句子列表
    sentences = re.split(r"[。！？\n]", manual_script)
    sentences = [s.strip() for s in sentences if s.strip()]

    # Step 3: 计算嵌入
    script_embeddings = model.encode(sentences, convert_to_tensor=True)
    whisper_texts = [seg["text"] for seg in whisper_segments]
    whisper_embeddings = model.encode(whisper_texts, convert_to_tensor=True)

    # 确保输入是 PyTorch Tensor
    whisper_embeddings = torch.tensor(whisper_embeddings)
    script_embeddings = torch.tensor(script_embeddings)

    # Step 4: 构建相似度矩阵并匹配
    sim_matrix = util.cos_sim(whisper_embeddings, script_embeddings)

    matched_indices = sim_matrix.argmax(dim=1)  # 每段whisper匹配最相似剧本句
    used = set()
    final_texts = []

    for idx in matched_indices:
        if idx.item() in used:
            # 避免重复使用剧本句，使用相邻的空闲句
            alt = next((i for i in range(len(sentences)) if i not in used), sentences[-1])
            final_texts.append(alt)
            used.add(alt)
        else:
            final_texts.append(sentences[idx])
            used.add(idx.item())

    # Step 5: 替换文本，保持原始结构
    for i in range(len(whisper_segments)):
        if i < len(final_texts):
            whisper_segments[i]["text"] = final_texts[i]
        else:
            whisper_segments[i]["text"] = sentences[-1]

    return whisper_segments

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
