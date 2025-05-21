import json
import os
import logging
import base64
from openai import OpenAI
import torch
from diffusers.pipelines.stable_diffusion.pipeline_stable_diffusion import StableDiffusionPipeline
from transformers import logging as hf_logging

hf_logging.set_verbosity_error()
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def generate_images(config):
    use_api = config["model"]["img"]["use_api"]
    img_dir = os.path.join(config["base"]["base_dir"], config["files"]["media"]["image_dir"])
    scene_prompts_path = os.path.join(config["base"]["base_dir"], config["files"]["text"]["scene_prompts"])
    logging.info("开始生成场景图片...")
    os.makedirs(img_dir, exist_ok=True)
    
    scenes = json.loads(open(scene_prompts_path, "r", encoding="utf-8").read())
    for i, scene in enumerate(scenes):
        scene_num = scene["scene_number"]
        prompt = scene["prompt"]
        logging.info(f"正在生成场景 {scene_num} 的图片...")
        try:
            save_path = os.path.join(img_dir, f"scene_{scene_num:02d}.png")
            if use_api:
                img_model = config["model"]["img"]["api"]
                img_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
                generate_image_by_api(prompt, save_path, img_client, img_model)
            else:
                img_model = config["model"]["img"]["offline"]
                generate_image_by_offline(prompt, save_path, img_model)
            logging.info(f"场景 {scene_num} 图片生成成功")
        except Exception as e:
            logging.error(f"生成场景 {scene_num} 图片时出错: {str(e)}")
            continue

def generate_image_by_api(prompt, save_path, img_client, model="gpt-image-1"):
    """
    https://platform.openai.com/docs/api-reference/images/createVariation
    使用OpenAI的DALL·E 3 API根据提示词生成图片并保存到本地。
    
    """
    if model == "gpt-image-1":
        result = img_client.images.generate(
            model="gpt-image-1",
            prompt=prompt,
            n=1,
            size="1024x1536",
            quality="low"
        )
    elif model == "dall-e-3":
        result = img_client.images.generate(
            model="dall-e-3",
            prompt=prompt,
            n=1,
            size="1024x1792"
        )
    elif model == "dall-e-2":
        result = img_client.images.generate(
            model="dall-e-2",
            prompt=prompt,
            n=1,
            size="1024x1024"
        )
    image_base64 = result.data[0].b64_json
    image_bytes = base64.b64decode(image_base64)

    # Save the image to a file
    with open(save_path, "wb") as f:
        f.write(image_bytes)

def generate_image_by_offline(prompt, save_path, model):
    if model == "taiyi-sd":
        pipe = StableDiffusionPipeline.from_pretrained(
            "IDEA-CCNL/Taiyi-Stable-Diffusion-1B-Chinese-v0.1",
            torch_dtype=torch.float16,
            safety_checker=None,
            requires_safety_checker=False
        ).to("cuda")
    else:
        raise ValueError(f"不支持的模型: {model}")
    prompt = prompt[:220]
    image = pipe(prompt).images[0]
    image.save(os.path.join(save_path))

if __name__ == "__main__":
    generate_image_by_offline("一个美丽的女孩在海边散步", "test.png", "taiyi-sd")