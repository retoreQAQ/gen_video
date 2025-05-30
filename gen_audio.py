import os
import json
import logging
import requests
from typing import Optional

def generate_audio_by_fishspeech(text: str, output_path: str, server_url: str = "http://localhost:7860") -> Optional[str]:
    """
    使用本地部署的FishSpeech服务生成音频
    
    Args:
        text: 需要转换的文本
        output_path: 音频输出路径
        server_url: FishSpeech服务地址,默认为本地7860端口
        
    Returns:
        成功则返回输出音频路径,失败返回None
    """
    try:
        # 准备请求参数
        payload = {
            "text": text,
            "speaker_name": "派蒙",  # 可以根据需要修改说话人
            "sdp_ratio": 0.2,
            "noise_scale": 0.6,
            "noise_scale_w": 0.8,
            "length_scale": 1.0,
            "language": "zh"
        }
        
        # 发送POST请求到FishSpeech服务
        response = requests.post(f"{server_url}/run/tts", json=payload)
        
        if response.status_code == 200:
            # 保存音频文件
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            with open(output_path, "wb") as f:
                f.write(response.content)
            logging.info(f"音频生成成功,已保存至: {output_path}")
            return output_path
        else:
            logging.error(f"调用FishSpeech服务失败: {response.status_code}")
            return None
            
    except Exception as e:
        logging.error(f"生成音频时发生错误: {str(e)}")
        return None
