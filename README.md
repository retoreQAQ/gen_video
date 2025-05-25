# 视频生成项目（ongoing）

这是一个基于语音识别和图像生成的视频制作工具。它可以将音频文件和故事文本转换为带有字幕和场景插图的视频。

## 开发进度

- v0.1 版本完成，可实现全流程自动化生成视频。

## 待更新

- whisper 的 large 表现比 base 好太多了，基本达到了直接用到程度。可以考虑添加是否进行文本对齐的选项
  - 可以做成质量和速度模式
- 增加耗时记录（数据埋点）
- 对齐时是否考虑将字幕里的标点删除？
  - 暂不
- 对生成提示词部分应用批处理（done）
  - 根据效果决定要不要提前生成角色设定，避免不同对话中角色风格不一致
- 使用 img2prompt 进行使用参考图生成提示词
- 字幕优化：字幕背景需改为动态调整
- 对齐批处理太慢，考虑先用代码提取文本减少 token
- 封面的处理
- 添加背景音乐功能
- 尝试更多生图模型
- lora
- img2prompt
- 生成完后移动到 name 文件夹
- output 内文件夹分类
- 自动发布抖音

## 功能特点

- 使用 Whisper 进行语音识别
- 基于语义匹配的文本对齐
- 使用 Stable Diffusion 或 api 生成场景插图
- 自动生成字幕和视频合成

## 项目结构

```
.
├── config/             # 配置文件目录
│   ├── config.yaml    # 主配置文件
│   └── key.zshrc     # API密钥配置
├── manual_img/         # 手动图片处理
│   ├── manual.py     # 图片下载脚本
│   └── urls.txt      # 图片URL列表
├── output/             # 输出目录
│   ├── temp/      # 临时文件
│   └── story_name/    # 按故事名分类
│       │   ├── audio/     # 音频相关
│       │   ├── images/    # 生成的图片
│       │   └── text/      # 文本相关
│       └── video/     # 最终视频
├── upload/             # 上传文件目录
│   ├── audio/         # 音频文件
│   └── text/          # 剧本文件
├── utils/              # 工具函数
│   ├── tools.py       # 通用工具
│   └── prompt.py      # 存放提示词
├── gen_prompt.py       # 提示词生成
├── gen_video.py        # 视频生成
├── main.py            # 主程序入口
└── README.md          # 项目说明
```

## 环境要求

## 安装依赖

```bash
pip install -r requirements.txt
```

完全复原 conda 环境

```bash
conda env create -f environment.yml
```

需要提前准备 deepseek 和 openai 等模型 api 的密钥，存放在 config/key.zshrc。
格式如下：
OPENAI_API_KEY="sk-..."
DEEPSEEK_API_KEY="sk-..."

## 使用方法

1. 准备音频文件和剧本，放在 upload 文件夹。
2. 运行：
   ```bash
   python main.py story_name
   ```
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

- 确保有足够的 GPU 内存用于 Stable Diffusion
- 音频文件应为 MP3 格式
- 剧本文件应为 UTF-8 编码
