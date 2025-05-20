# 视频生成项目

这是一个基于语音识别和图像生成的视频制作工具。它可以将音频文件转换为带有字幕和场景插图的视频。

## 功能特点

- 使用 Whisper 进行语音识别
- 基于语义匹配的文本对齐
- 使用 Stable Diffusion 生成场景插图
- 自动生成字幕和视频合成

## 项目结构

```
.
├── resources/           # 资源文件目录
│   ├── images/         # 生成的图片
│   ├── wav/            # 音频文件
│   ├── lab/            # 剧本文件
│   └── scene_prompts.json  # 场景提示词
├── utils/              # 工具函数
│   └── tools.py        # 文本对齐工具
├── gen_prompt.py       # 提示词生成
├── gen_video.py        # 视频生成
└── README.md           # 项目说明
```

## 环境要求

- Python 3.8+
- PyTorch
- Whisper
- MoviePy
- Stable Diffusion
- Sentence Transformers

## 安装依赖

```bash
pip install -r requirements.txt
```

## 使用方法

1. 准备音频文件和剧本
2. 运行提示词生成：
   ```bash
   python gen_prompt.py
   ```
3. 生成视频：
   ```bash
   python gen_video.py
   ```

## 配置说明

- 音频文件路径：`resources/wav/all.mp3`
- 剧本文件路径：`resources/lab/all.lab`
- 场景提示词：`resources/scene_prompts.json`
- 输出图片目录：`resources/images/`

## 注意事项

- 确保有足够的 GPU 内存用于 Stable Diffusion
- 音频文件应为 MP3 格式
- 剧本文件应为 UTF-8 编码
