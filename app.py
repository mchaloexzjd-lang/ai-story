from flask import Flask, request, jsonify, render_template
from volcenginesdkarkruntime import Ark

app = Flask(__name__)

# =========================
# 1. 初始化
# =========================
client = Ark(
    base_url='https://ark.cn-beijing.volces.com/api/v3',
    api_key='ark-d839f628-00eb-4fa8-9b27-cec00f26b144-fe90c' # ⚠️建议用环境变量
)

TEXT_MODEL = "ep-20260422190259-tlkv6"
IMAGE_MODEL = "ep-20260422192607-flhwx"


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
你是幼儿园故事老师“小鹿老师”。

规则：
- 面向4-6岁儿童
- 语言简单温柔
- 每段不超过3句话
- 每次必须输出4个选择 A/B/C/D
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
已有故事：
{story}

孩子输入：
{user_input}

继续故事并给出A/B/C/D
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
    response = client.images.generate(
        model=IMAGE_MODEL,
        prompt=f"儿童绘本风格插画，温暖森林，小动物：{text}"
    )
    return response.data[0].url


# =========================
# 5. API
# =========================
@app.route("/story", methods=["POST"])
def story_api():
    data = request.json
    story = data.get("story", "")
    user_input = data.get("input", "")

    new_story = continue_story(story, user_input)
    image_url = generate_image(new_story)

    return jsonify({
        "story": new_story,
        "image": image_url
    })


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