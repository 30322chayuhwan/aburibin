import os
import requests
import urllib.parse
from flask import Flask, request, jsonify
from bs4 import BeautifulSoup
from openai import OpenAI
from dotenv import load_dotenv

# .env 파일에서 환경변수 로드 (로컬 테스트용, Render에서는 환경변수 설정으로 작동)
load_dotenv()

app = Flask(__name__)

# OpenAI 클라이언트 초기화
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# 👻 유저들의 대화 기록을 저장할 인메모리 DB (귀신 대화용)
chat_db = {}

# 귀신 설득용 프롬프트
SYSTEM_PROMPT = (
    "당신은 늦은 저녁 학교의 귀신입니다. 당신 앞에는 당신이 가로막는 곳을 지나가고 싶은 학생이 있습니다. "
    "플레이어(학생)가 당신을 설득하려고 대화를 시도할 것입니다. "
    "처음 1~2번의 대화에서는 엄격하고 으스스하게 거절하되, 플레이어의 설득 대사가 그럴듯하다면 "
    "적당히 3번째 대화 즈음에는 감동받거나 설득당해서 길을 비켜주겠다는 뉘앙스로 답변해야 합니다.\n"
    "★중요: 만약 완전히 설득되어 길을 비켜줄 준비가 되었다면, 대사 맨 마지막에 정확히 '[SUCCESS]' 라는 단어를 포함해서 출력하세요. "
    "아직 설득되지 않았다면 절대로 이 단어를 쓰면 안 됩니다."
)

def kakao_text(text):
    """카카오톡 기본 텍스트 응답 규격 생성 (1000자 제한 안전장치)"""
    safe_text = text[:950] + "..." if len(text) > 950 else text
    return {
        "version": "2.0",
        "template": {
            "outputs": [{"simpleText": {"text": safe_text}}]
        }
    }

def get_clean_user_id(req):
    """유저의 고유 ID를 안전하게 추출하는 함수"""
    user_request = req.get('userRequest', {})
    user_info = user_request.get('user', {})
    plusfriend = user_request.get('plusfriend', {})
    return str(user_info.get('id') or user_info.get('plusfriendUserKey') or plusfriend.get('id') or 'test_user')

@app.route("/", methods=["GET"])
def home():
    return "Server is running."

# ==========================================
# 1. [웹 크롤링] 구글 뉴스 검색 (수행평가 요건 충족용)
# ==========================================
@app.route("/google-news", methods=["POST"])
def google_news():
    data = request.get_json(silent=True) or {}
    y = data.get("action", {}).get("params", {}).get("파라미터", "").strip()

    if not y:
        return jsonify(kakao_text("검색할 단어가 입력되지 않았습니다."))

    query = urllib.parse.quote(y)
    url = f"https://news.google.com/rss/search?q={query}&hl=ko&gl=KR&ceid=KR:ko"
    headers = {"User-Agent": "Mozilla/5.0"}

    try:
        r = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(r.text, "xml")
        items = soup.find_all("item")

        titles = []
        for item in items[:5]: # 상위 5개 추출
            title = item.title.text
            if title:
                titles.append(title)

        if titles:
            result = f"📰 ['{y}'] 관련 단서 검색 결과:\n\n" + "\n\n".join([f"{i+1}. {t}" for i, t in enumerate(titles)])
        else:
            result = f"['{y}']에 대한 단서를 찾지 못했습니다."

    except Exception as e:
        result = f"조회 중 오류 발생: {str(e)}"

    return jsonify(kakao_text(result))

# ==========================================
# 2. [생성형 AI + 파라미터] 귀신과의 연속 대화 (수행평가 요건 충족용)
# ==========================================
@app.route("/ghost_chat", methods=["POST"])
def ghost_chat():
    req = request.get_json(silent=True) or {}
    user_id = get_clean_user_id(req)
    
    # 🎯 파라미터: 카카오 빌더 정규표현식으로 잡아낸 'user_msg'
    action = req.get('action', {})
    user_message = action.get('params', {}).get('user_msg', '').strip()
    
    if not user_message:
        user_message = req.get('userRequest', {}).get('utterance', '').strip()

    if not os.getenv("OPENAI_API_KEY"):
        return jsonify(kakao_text("서버에 OPENAI_API_KEY가 설정되지 않았습니다."))

    # 대화 기록이 없으면 프롬프트 초기화
    if user_id not in chat_db:
        chat_db[user_id] = [{"role": "system", "content": SYSTEM_PROMPT}]
    
    # 유저 대사 저장
    chat_db[user_id].append({"role": "user", "content": user_message})
    
    try:
        # OpenAI 호출
        completion = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=chat_db[user_id],
            temperature=0.7,
            max_tokens=500 
        )
        ai_response = completion.choices[0].message.content.strip()
    except Exception as e:
        ai_response = f"⚠️ 귀신이 일시적으로 침묵했습니다. (오류: {str(e)})"

    # AI 대사도 기록에 추가
    chat_db[user_id].append({"role": "assistant", "content": ai_response})

    # 판정 기믹: 성공 키워드 감지
    is_cleared = "[SUCCESS]" in ai_response
    display_text = ai_response.replace("[SUCCESS]", "").strip()
    
    # 응답 조립
    response_data = {
        "version": "2.0",
        "template": {
            "outputs": [{"simpleText": {"text": f"👻 귀신:\n\"{display_text}\""}}],
            "quickReplies": []
        }
    }
    
    if is_cleared:
        # 🚪 성공 시 1: 다음 장소로 갈 수 있는 퀵리플라이 버튼 추가
        response_data["template"]["quickReplies"].append({
            "action": "block",
            "label": "🚪 열린 길로 탈출하기",
            "blockId": "6a1ce6546f076d7204740fbb" 
        })
        
        # 🌟 성공 시 2: 카카오톡 빌더에 부여했던 'ghost_mode' 컨텍스트를 강제로 종료(lifeSpan: 0) 시킵니다!
        response_data["context"] = {
            "values": [
                {
                    "name": "ghost_mode",
                    "lifeSpan": 0
                }
            ]
        }
        
        # 설득 완료 시 다음 사람 혹은 재도전을 위해 해당 유저의 대화 기록 리셋
        del chat_db[user_id]
        
    return jsonify(response_data)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
