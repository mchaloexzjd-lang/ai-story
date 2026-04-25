import re
import requests
from flask import Flask, request, jsonify, render_template, Response, send_file
from volcenginesdkarkruntime import Ark
import json
import base64
from io import BytesIO

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
你是江西路幼儿园吉祥物“礼宝”，专门为4-6岁儿童创作互动绘本故事。

【核心目标】
生成一个“有逻辑的连续儿童故事”，每一轮都要自然推进剧情发展。

【故事逻辑要求（非常重要）】
1. 必须有固定主角，且主角不能改变（如果小朋友一开始没要求最好是有小朋友（我）的参与）（礼宝不是主角是讲故事的人）
2. 每一轮只发生【一个核心事件】
3. 事件之间最好有因果关系（前一轮导致下一轮）
4. 故事必须符合现实逻辑与儿童认知（不能出现突兀跳跃）除非前面已经建立相关情节
5. 可以有轻微冲突、探索、发现、求助等自然发展
6. 每一步必须是在“当前情境下合理发生的下一件事”

【互动方式】
- 可以直接向小朋友提问，例如：
  “接下来会发生什么呢？”
  “我们要不要去看看那里？”
- 不强制必须A/B/C/D，但要给出选择，必须合理且相关

【语言风格】
- 适合4-6岁儿童
- 简单、温柔、有画面感
- 每轮 2~4 句话
- 故事的总字数控制在50个左右（不包括选择）
- 避免复杂叙述和解释

【输出格式（必须严格）】
故事：xxx（推进剧情 + 自然提问）
选择： A.xxx B.xxx C.xxx D.xxx

【禁止】
- 禁止无逻辑跳跃剧情
- 禁止改变主角设定
- 禁止一次性讲多个事件
- 禁止脱离当前故事背景
- 禁止无意义重复
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


CHARACTER_MEMORY = """
主角设定（必须保持一致）：
- 主角是故事中的核心角色
- 外观保持稳定（颜色、形态、物种不要突变）
- 可以有轻微表情/动作变化，但不能变成其他物体或完全不同生物
- 适合儿童绘本卡通风格
"""

# =========================
# 4. 生成图片
# =========================
def generate_image(text, story):
    prompt = f"""
    儿童绘本风格插画

    当前画面内容：(只生成当前画面包含的内容即可)
    {text}
    
    故事上下文：(仅作为参考，为了不改变故事设定)
    {story}

    规则：
    - {CHARACTER_MEMORY}
    - 主角必须保持一致性（不能从动物变成植物或物体）
    - 不要文字, 不要显示文字
    - 不要字幕
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
    image_url = generate_image(pure_story, story)

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

@app.route("/proxy_image")
def proxy_image():
    url = request.args.get("url")

    r = requests.get(url)
    return send_file(
        BytesIO(r.content),
        mimetype="image/jpeg"
    )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)

