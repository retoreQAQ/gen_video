import os
import requests
import logging
from openai import OpenAI
import base64

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

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
    # image_url = result.data[0].url
    # img_data = requests.get(image_url).content
    # headers = {
    #     "Authorization": f"Bearer {img_client.api_key}",
    #     "Content-Type": "application/json"
    # }
    # data = {
    #     "model": "dall-e-2",
    #     "prompt": prompt,
    #     "n": 1,
    #     "size": "1024x1792"  # 竖屏9:16，DALL·E 3支持的最大竖屏尺寸
    # }
    # response = requests.post(url, headers=headers, json=data)
    # response.raise_for_status()
    # image_url = response.json()["data"][0]["url"]

    # # 下载图片
    # img_data = requests.get(image_url).content
    # with open(save_path, "wb") as f:
    #     f.write(img_data)
    return save_path

def generate_images(scene_data, image_dir, img_client):
    logging.info("开始生成场景图片...")
    os.makedirs(image_dir, exist_ok=True)
    for i, (scene_num, desc, scene, prompt) in enumerate(scene_data):
        logging.info(f"正在生成场景 {scene_num} 的图片...")
        try:
            save_path = os.path.join(image_dir, f"scene_{i:02d}.png")
            generate_image_by_api(prompt, save_path, img_client)
            logging.info(f"场景 {scene_num} 图片生成成功")
        except Exception as e:
            logging.error(f"生成场景 {scene_num} 图片时出错: {str(e)}")
            continue