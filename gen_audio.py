# from fish-speech/inference.ipynb
import locale
import pwd
import subprocess
locale.setlocale(locale.LC_ALL, 'en_US.UTF-8')

import os
import yaml
import logging
import sys
from pathlib import Path
def generate_audio(config, output_path):
    speaker_name = 'huang'
    root_path = os.path.dirname(os.path.abspath(__file__))
    model_dir_name = config["model"]["tts"]["model_dir_name"]
    tts_path = config["model"]["tts"]["path"]
    use_reference_speaker = config["model"]["tts"]["use_reference_speaker"]
    use_compile = config["model"]["tts"]["use_compile"]
    codes = config["model"]["tts"]["codes"]
    num_samples = config["model"]["tts"]["num_samples"]
    story_path = os.path.join(config["base"]["base_dir"], config["files"]["text"]["story"])
    with open(story_path, "r") as f:
        story = f.read()

    logging.info(f"开始下载模型 {model_dir_name}...")
    
    if model_dir_name == "fish-speech":
        project_path = os.path.join(root_path, tts_path, model_dir_name)
        model_path = os.path.join(root_path, tts_path, model_dir_name,"checkpoints/fish-speech-1.5/")
        

        

        # 假设你 gen_audio.py 是在 gen_video/ 目录下
        # fish_speech 的路径为：gen_video/resources/models/tts/fish-speech/fish_speech
        # fish_speech_root = Path(__file__).resolve().parent / f"{os.path.join(root_path, project_path, '')}"
        # sys.path.append(str(fish_speech_root))

        # print("[DEBUG] sys.path:", sys.path)
        # print("[DEBUG] files in fish_speech_root:", os.listdir(str(fish_speech_root)))


        subprocess.run([
            "huggingface-cli",
            "download",
            "fishaudio/fish-speech-1.5",
            "--local-dir", f"{model_path}"
        ], check=True)
        logging.info(f"模型 {model_dir_name} 下载完成")

        if use_reference_speaker:

            reference_speaker_path = os.path.join(root_path, config["files"]["reference"]["speaker_path"], speaker_name)
            if not os.path.exists(reference_speaker_path):
                os.makedirs(reference_speaker_path, exist_ok=True)
            reference_speaker_audio_path = os.path.join(root_path, reference_speaker_path, "reference_audio.mp3")
            reference_speaker_text_path = os.path.join(root_path, reference_speaker_path, "prompt_text.txt")
            if not os.path.exists(reference_speaker_audio_path):
                raise FileNotFoundError(f"reference_speaker_audio 不存在: {reference_speaker_audio_path}")
            with open(reference_speaker_text_path, "r") as f:
                prompt_text = f.read()
                if not prompt_text:
                    raise FileNotFoundError(f"prompt_text 为空: {reference_speaker_text_path}")
                
            # 执行推理脚本
            step1_cmd = [
                "python", "fish_speech/models/vqgan/inference.py",
                "-i", reference_speaker_audio_path,
                "--checkpoint-path", f"{project_path}/checkpoints/fish-speech-1.5/firefly-gan-vq-fsq-8x1024-21hz-generator.pth",
                "--output-path", f"{reference_speaker_path}/fake.wav"
            ]
            subprocess.run(step1_cmd, check=True, cwd=project_path)
        else:
            prompt_text = None
            prompt_tokens_path = None
        prompt_tokens_path = f"{reference_speaker_path}/fake.npy"

        step2_cmd = [
            "python", f"{project_path}/fish_speech/models/text2semantic/inference.py",
            "--text", story,
            "--prompt-text", prompt_text,
            "--prompt-tokens", prompt_tokens_path,
            "--checkpoint-path", f"{project_path}/checkpoints/fish-speech-1.5",
            "--num-samples", f"{num_samples}",
            "--chunk-length", "100",
            "--output-dir", f"{reference_speaker_path}"
        ]
        if use_compile:
            step2_cmd.append("--compile")
        subprocess.run(step2_cmd, check=True, cwd=project_path)

        for i in range(num_samples):
            step3_cmd = [
                "python", f"{project_path}/fish_speech/models/vqgan/inference.py",
                "-i", f"{reference_speaker_path}/codes_{i}.npy",
                "--checkpoint-path", f"{project_path}/checkpoints/fish-speech-1.5/firefly-gan-vq-fsq-8x1024-21hz-generator.pth",
                "--output-path", output_path
            ]
            subprocess.run(step3_cmd, check=True, cwd=project_path)



if __name__ == "__main__":
    config = yaml.safe_load(open("config/config.yaml", "r"))
    base_dir = config["base"]["base_dir"]
    audio_mp3 = os.path.join(base_dir, f"synthesized_{config['files']['audio']['mp3']}")
    generate_audio(config, audio_mp3)