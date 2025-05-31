import imp
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
    os.makedirs(img_dir, exist_ok=True)
    scene_prompts_path = os.path.join(config["base"]["base_dir"], config["files"]["text"]["scene_prompts"])

    # 检查图片是否已存在
    def check_image_exists(scenes, img_dir):
        for scene in scenes:
            scene_num = scene["scene_number"]
            img_path = os.path.join(img_dir, f"scene_{scene_num:02d}.png")
            if os.path.exists(img_path):
                logging.info(f"场景 {scene_num} 的图片已存在，跳过生成")
            else:
                logging.info(f"场景 {scene_num} 的图片不存在, 重新生成")
                return False
        return True

    scenes = json.loads(open(scene_prompts_path, "r", encoding="utf-8").read())
    if check_image_exists(scenes, img_dir):
        logging.info("场景图片已存在，跳过生成")
        return
    
    logging.info("开始生成场景图片...")

    if not use_api:
        img_model = config["model"]["img"]["offline"]
        pipe = load_model(img_model)
        for scene in scenes:
            scene_num = scene["scene_number"]
            prompt = scene["prompt"]
            save_path = os.path.join(img_dir, f"scene_{scene_num:02d}.png")
            try:
                generate_image_by_offline(img_model, pipe, prompt, save_path)
                logging.info(f"场景 {scene_num} 图片生成成功")
            except Exception as e:
                logging.error(f"生成场景 {scene_num} 图片时出错: {str(e)}")
                break
    else:
        img_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        img_model = config["model"]["img"]["api"]
        for scene in scenes:
            scene_num = scene["scene_number"]
            prompt = scene["prompt"]
            save_path = os.path.join(img_dir, f"scene_{scene_num:02d}.png")
            try:
                generate_image_by_api(prompt, save_path, img_client, img_model)
                logging.info(f"场景 {scene_num} 图片生成成功")
            except Exception as e:
                logging.error(f"生成场景 {scene_num} 图片时出错: {str(e)}")
                break

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

def load_model(model):
    if model == "sd3.5":
        model_path_offline = "resources/models/img/stable-diffusion-3.5-medium"
        model_path_online = "stabilityai/stable-diffusion-3.5-medium"
        from diffusers.pipelines.stable_diffusion_3.pipeline_stable_diffusion_3 import StableDiffusion3Pipeline
        import gc

        pipe = StableDiffusion3Pipeline.from_pretrained(
            model_path_offline, 
            torch_dtype=torch.float16
        ).to("cuda")

        pipe.enable_model_cpu_offload()  # 不活跃模块转 CPU
        pipe.enable_attention_slicing() 
        # pipe.enable_sequential_cpu_offload()  # 更进一步：模块顺序加载（比前者更激进）

    elif model == "taiyi-sd":
        model_path = "resources/models/img/taiyi-sd"
    
    return pipe

def generate_image_by_offline(model, pipe, prompt, save_path):
    '''
    访问受限模型需要登陆
    huggingface-cli login
    '''

    if model == "taiyi-sd":
        pipe = StableDiffusionPipeline.from_pretrained(
            "IDEA-CCNL/Taiyi-Stable-Diffusion-1B-Chinese-v0.1",
            torch_dtype=torch.float16,
            use_safetensors = False
        ).to("cuda")

        prompt = prompt[:220]
        image = pipe(prompt).images[0] # type: ignore
        image.save(os.path.join(save_path))

    elif model == "sd3.5":

        import gc

        image = pipe(prompt, height=768, width=512, num_inference_steps=40, guidance_scale=4.5).images[0] # type: ignore
        image.save(os.path.join(save_path))

        del image
        torch.cuda.empty_cache()
        gc.collect()

    else:
        raise ValueError(f"不支持的模型: {model}")

if __name__ == "__main__":
    import yaml
    config = yaml.load(open("config/config.yaml", "r", encoding="utf-8"), Loader=yaml.FullLoader)
    generate_images(config)