# 视频生成项目（ongoing）

这是一个基于语音识别和图像生成的视频制作工具。它可以将音频文件和故事文本转换为带有字幕和场景插图的视频。

## 开发进度

- v0.2 版本完成，可实现全流程自动化生成视频。

## 待更新
- 增加耗时记录（数据埋点）
- 根据效果决定要不要提前生成角色设定，避免不同对话中角色风格不一致
- 使用 img2prompt 进行使用参考图生成提示词
- 字幕优化：字幕背景需改为动态调整
- 对齐批处理太慢，考虑先用代码提取文本减少 token
- 封面的处理
- 添加背景音乐功能
- 尝试更多生图模型
- lora
- img2prompt
- output 内文件夹分类
- 自动发布抖音
- 增加功能：检测生图成本
- 增加log
- torch2.1.2 在 win 上报错，需要升级到 2.6 以上？
- webUI or GUI

- 增加分割故事前的检错
- 应对llm的出错：替换时某一两个字没换，导致后续硬对齐出错。（考虑是上下文太长的原因，尝试分批处理）
- 硬对齐时的检错
- 对比新旧环境，为何旧环境能生图，新的报错
- 硬对齐算法需要更多测试
- 语音合成调用优化

##Done
- 增加语音合成模块
- 升级moviepy到最新版本，升级代码
- 增加检测：story 为空
- whisper 的 large 表现比 base 好太多了，基本达到了直接用到程度。可以考虑添加是否进行文本对齐的选项(由于后续图片获取时间戳的流程，必须对齐)
- 对齐时是否考虑将字幕里的标点删除？
- 对生成提示词部分应用批处理
- 生成完后移动到 name 文件夹
- bug: 故事过短时，会有图片时长小于字幕时长，导致报错。

## 功能特点

- 使用 Whisper 进行语音识别
- 基于语义匹配的文本对齐
- 使用 Stable Diffusion 或 api 生成场景插图
- 自动生成字幕和视频合成

## 项目结构

```
.
├── config/                 # 配置文件目录
│   ├── config.yaml         # 主配置文件
│   └── key.zshrc           # API密钥配置
├── manual_img/             # 手动图片处理
│   ├── manual.py           # 图片下载脚本
│   └── urls.txt            # 图片URL列表
├── output/                 # 输出目录
│   ├── temp/               # 临时文件
│   └── story_name/         # 按故事名分类
│       │   ├── images/     # 生成的图片
│       ├── output_video.mp4     # 最终视频
│       └── ...             # 其他中间文件
├── upload/                 # 上传文件目录
│   ├── 新录音.m4a           # 音频文件
│   └── story.txt           # 剧本文件
├── utils/                  # 工具函数
│   ├── tools.py            # 通用工具
│   └── prompt.py           # 存放提示词
├── gen_image.py            # 图片生成
├── gen_prompt.py           # 提示词生成
├── gen_video.py            # 视频生成
├── main.py                 # 主程序入口
└── README.md               # 项目说明
```

## 环境要求

## 安装依赖

```bash
pip install -r requirements.txt
```

完全复原 conda 环境

```bash
conda env create -f environment_full.yml -n new_env_name
```

无法使用时手动构建环境, cuda版本为11.8或12.
```bash
conda create -n gen_video python=3.10
conda activate gen_video
apt install ffmpeg
pip install openai transformers==4.52.3 moviepy huggingface-hub==0.30.0 diffusers==0.33.1 python-dotenv==1.1.0 openai-whisper ipykernel accelerate
# cuda与torch版本参考 https://pytorch.org/get-started/previous-versions/
pip install torch==2.4.1 torchvision==0.19.1 torchaudio==2.4.1 --index-url https://download.pytorch.org/whl/cu121

# for FishSpeech TTS, it's not necessary if you don't need it
cd resources # 或者任意你想存储在的位置，参考config.yaml
git clone https://github.com/fishaudio/fish-speech.git
# (Ubuntu / Debian 用户) 安装 sox + ffmpeg
sudo apt install libsox-dev ffmpeg
# (Ubuntu / Debian 用户) 安装 pyaudio
sudo apt install build-essential \
    cmake \
    libasound-dev \
    portaudio19-dev \
    libportaudio2 \
    libportaudiocpp0
```

需要提前准备 deepseek 和 openai 等模型 api 的密钥，存放在 config/key.zshrc。
格式如下：

```python
OPENAI_API_KEY="sk-..."
DEEPSEEK_API_KEY="sk-..."
```

## 使用方法

1. 准备.ma4 音频文件和剧本(文本复制到 upload/story.txt)，放在 upload 文件夹。
2. 运行：
   ```bash
   python main.py story_name
   ```
   story_name 改为自定义的故事名
3. 生成的视频与中间文件存放在 output/story_name 下

- 当使用网页版生成图片时，挨个复制图片 url 到 manual_img/urls.txt，然后运行
  ```bash
  python manual_img/manual.py
  ```
- 再运行
  ```bash
  python gen_video.py
  ```

## 注意事项
在resources/models/tts/fish-speech/fish_speech/models/text2semantic/inference.py的最上面加：
```python
import pyrootutils
pyrootutils.setup_root(__file__, indicator=".project-root", pythonpath=True)
```
不然运行gen_audio.py报错

