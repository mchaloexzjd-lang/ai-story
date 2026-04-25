import base64
import re

import requests
import json
from flask import Flask, request, jsonify, render_template, Response
from volcenginesdkarkruntime import Ark

app = Flask(__name__)

# =========================
# 1. 初始化
# =========================
import os
client = Ark(
    base_url='https://ark.cn-beijing.volces.com/api/v3',
    api_key=os.getenv("ARK_API_KEY")
)

TEXT_MODEL = "ep-20260422190259-tlkv6"
IMAGE_MODEL = "ep-20260422192607-flhwx"
# =========================
# 2. TTS 配置
# =========================
TTS_URL = "https://openspeech.bytedance.com/api/v3/tts/unidirectional"
TTS_HEADERS = {
    "x-api-key": os.getenv("TTS_API_KEY"),
    "X-Api-Resource-Id": os.getenv("TTS_RESOURCE_ID"),
    "Content-Type": "application/json"
}
def generate_audio(text):
    data = {
        "req_params": {
            "text": text,
            "speaker": "zh_male_tiancaitongsheng_mars_bigtts",
            "additions": json.dumps({
                "disable_markdown_filter": True,
                "enable_language_detector": True,
                "enable_latex_tn": True,
                "cache_config": {
                    "text_type": 1,
                    "use_cache": True
                }
            }),
            "audio_params": {
                "format": "mp3",
                "sample_rate": 24000
            }
        }
    }

    res = requests.post(TTS_URL, headers=TTS_HEADERS, json=data)

    audio_base64 = ""

    for line in res.text.splitlines():
        try:
            obj = json.loads(line)
            if obj.get("data"):
                audio_base64 += obj["data"]
        except:
            pass

    if not audio_base64:
        return None

    return base64.b64decode(audio_base64)

# =========================
# 2. 提取文本
# =========================
def extract_text(response):
    for item in response.output:
        if item.type == "message":
            for c in item.content:
                if c.type == "output_text":
                    return c.text
    return ""


# =========================
# 3. 生成故事
# =========================
def continue_story(story, user_input):
    response = client.responses.create(
        model=TEXT_MODEL,
        input=[
            {
                "role": "system",
                "content": [{
                    "type": "input_text",
                    "text": """
你是江西路幼儿园吉祥物“礼宝”，会讲故事。

规则：
- 面向4-6岁儿童
- 语言简单温柔
- 每段不超过3句话
- 必须严格基于“已有故事”继续发展
- 禁止重新开始新故事
- 禁止改变人物或背景
- 每次必须输出：

格式如下（必须严格一致）：
故事：（内容）（接下来的故事（对孩子提问题））
选择：A. xxx B. xxx C. xxx D. xxx

- 禁止输出任何思考过程
- 只输出故事
"""
                }]
            },
            {
                "role": "user",
                "content": [{
                    "type": "input_text",
                    "text": f"""
已有故事（必须延续）：
{story}

孩子的选择：
{user_input}

请继续故事。
"""
                }]
            }
        ]
    )
    return extract_text(response)


# =========================
# 4. 生成图片
# =========================
def generate_image(text):
    prompt = f"""
    儿童绘本风格插画，卡通风格，色彩柔和：{text}。
    
    要求：
    - 不要任何文字
    - 不要字幕
    - 不要对话框
    - 不要书写内容
    - no text, no words, no letters
    """

    response = client.images.generate(
        model=IMAGE_MODEL,
        prompt=prompt,
        size="1792x1024"
    )
    return response.data[0].url


def parse_story(text):
    story_match = re.search(r"故事[:：](.*?)(选择[:：]|$)", text, re.S)
    choice_match = re.search(r"选择[:：](.*)", text, re.S)

    story = story_match.group(1).strip() if story_match else text
    choices = choice_match.group(1).strip() if choice_match else ""

    return story, choices


# =========================
# 5. API
# =========================
@app.route("/story", methods=["POST"])
def story_api():
    data = request.json
    story = data.get("story", "")   # 👉 这里只应该是“纯故事”
    user_input = data.get("input", "")

    new_story = continue_story(story, user_input)

    # ⭐解析
    pure_story, choices = parse_story(new_story)

    # ⭐生成图片（只用纯故事）
    image_url = generate_image(pure_story)

    return jsonify({
        "story": pure_story,   # ⭐只返回纯故事
        "choices": choices,    # ⭐单独返回选择
        "image": image_url
    })

@app.route("/tts", methods=["POST"])
def tts_api():
    data = request.json
    text = data.get("text", "")

    mp3_bytes = generate_audio(text)

    if not mp3_bytes:
        return jsonify({"error": "tts failed"}), 500

    return Response(
        mp3_bytes,
        mimetype="audio/mpeg",
        headers={
            "Content-Disposition": "inline; filename=tts.mp3"
        }
    )

# =========================
# 6. 首页
# =========================
@app.route("/")
def home():
    return render_template("index.html")


# =========================
# 7. 启动
# =========================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
