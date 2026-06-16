import os
import random
import requests
import urllib.parse
from flask import Flask, request, jsonify
from bs4 import BeautifulSoup
from anthropic import Anthropic

app = Flask(__name__)

# 클로드(Anthropic) 클라이언트 초기화
# Render 환경변수에 ANTHROPIC_API_KEY를 등록하면 자동으로 불러옵니다.
client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

def kakao_text(text):
    """카카오톡 텍스트 응답 규격 생성 (1000자 제한 안전장치)"""
    safe_text = text[:950] + "..." if len(text) > 950 else text
    return {
        "version": "2.0",
        "template": {
            "outputs": [{
                "simpleText": {
                    "text": safe_text
                }
            }]
        }
    }

@app.route("/", methods=["GET"])
def home():
    return "Server is running."

# ==========================================
# 스킬 1: 클로드 암호 해독기
# ==========================================
@app.route("/claude-decrypt", methods=["POST"])
def claude_decrypt():
    data = request.get_json(silent=True) or {}
    
    # 카카오톡 파라미터에서 사용자 입력값 추출
    user_input = data.get("action", {}).get("params", {}).get("파라미터", "").strip()

    if not user_input:
        return jsonify(kakao_text("해독할 암호문이 없습니다. 다시 입력해 주세요."))

    if not os.getenv("ANTHROPIC_API_KEY"):
        return jsonify(kakao_text("서버에 API 키가 설정되지 않았습니다."))

    try:
        response = client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=600,
            system="당신은 천재 암호 해독가입니다. 사용자의 암호를 분석하고, 해독 결과와 풀이 과정을 카카오톡에서 읽기 편하게 간결히 설명해 주세요.",
            messages=[
                {"role": "user", "content": user_input}
            ]
        )
        result_text = response.content[0].text.strip()
    except Exception as e:
        result_text = f"해독 중 오류 발생: {str(e)}"

    return jsonify(kakao_text(result_text))

# ==========================================
# 스킬 2: 구글 뉴스 검색 (학교 예시 코드 재활용)
# ==========================================
@app.route("/google-news", methods=["POST"])
def google_news():
    data = request.get_json(silent=True) or {}
    y = data.get("action", {}).get("params", {}).get("파라미터", "").strip()

    if not y:
        return jsonify(kakao_text("검색어가 없습니다."))

    query = urllib.parse.quote(y)
    url = f"https://news.google.com/rss/search?q={query}&hl=ko&gl=KR&ceid=KR:ko"
    headers = {"User-Agent": "Mozilla/5.0"}

    try:
        r = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(r.text, "xml")
        items = soup.find_all("item")

        titles = [item.title.text for item in items[:5] if item.title.text]

        if titles:
            result = f"['{y}'] 최신 뉴스:\n\n" + "\n\n".join([f"{i+1}. {t}" for i, t in enumerate(titles)])
        else:
            result = f"['{y}']에 대한 뉴스를 찾지 못했습니다."
    except Exception as e:
        result = f"뉴스 조회 중 오류 발생: {str(e)}"

    return jsonify(kakao_text(result))

# ==========================================
# 스킬 3: 랜덤 암호 퀴즈 출제
# ==========================================
@app.route("/random-quiz", methods=["POST"])
def random_quiz():
    quizzes = [
        {"type": "시저 암호 (3칸 밀기)", "cipher": "KHOOR", "answer": "HELLO"},
        {"type": "시저 암호 (3칸 밀기)", "cipher": "DSSOH", "answer": "APPLE"},
        {"type": "이진수 암호", "cipher": "01001111 01001011", "answer": "OK"}
    ]
    
    selected = random.choice(quizzes)
    
    response_text = (
        f"🕵️‍♂️ 훈련을 시작하지!\n\n"
        f"유형: {selected['type']}\n"
        f"암호문: {selected['cipher']}\n\n"
        f"이 암호가 뜻하는 원래 단어는 무엇일까?"
    )
    
    return jsonify(kakao_text(response_text))

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
