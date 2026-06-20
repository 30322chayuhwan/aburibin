from flask import Flask, request, jsonify
import os
from openai import OpenAI

app = Flask(__name__)

# 🔑 Render의 Environment Variables(환경 변수)에 설정한 OPENAI_API_KEY를 가져옵니다.
# Render 설정 메뉴에서 Key: OPENAI_API_KEY / Value: sk-xxxx... 형태로 넣으시면 됩니다.
client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

# 유저들과의 대화 기록 및 대화 횟수를 저장할 인메모리 DB
chat_db = {}

# 📜 AI에게 주입할 핵심 프롬프트 (기획하신 내용을 여기에 작성하시면 됩니다!)
SYSTEM_PROMPT = (
    "당신은 늦은 저녁 학교의 귀신입니다. 당신 앞에는 당신이 가로막는 곳을 지나가고 싶은 학생이 있습니다. "
    "플레이어(학생)가 당신을 설득하려고 대화를 시도할 것입니다. "
    "처음 1~2번의 대화에서는 엄격하고 으스스하게 거절하되, 플레이어의 설득 대사가 그럴듯하다면 "
    "적당히 3번째 대화 즈음에는 감동받거나 설득당해서 길을 비켜주겠다는 뉘앙스로 답변해야 합니다.\n"
    "★중요: 만약 완전히 설득되어 길을 비켜줄 준비가 되었다면, 대사 맨 마지막에 정확히 '[SUCCESS]' 라는 단어를 포함해서 출력하세요. "
    "아직 설득되지 않았다면 절대로 이 단어를 쓰면 안 됩니다."
)

def get_clean_user_id(req):
    user_request = req.get('userRequest', {})
    user_info = user_request.get('user', {})
    plusfriend = user_request.get('plusfriend', {})
    uid = user_info.get('id') or user_info.get('plusfriendUserKey') or plusfriend.get('id') or 'test_user'
    return str(uid)

@app.route('/ghost_chat', methods=['POST'])
def ghost_chat():
    """ 👻 생성형 AI + 파라미터 연동 대화 구간 """
    req = request.get_json()
    user_id = get_clean_user_id(req)
    
    # 🎯 [파라미터 요소]: 카카오 오픈빌더에서 유저가 타이핑한 대사(텍스트)를 파라미터로 받습니다.
    # 빌더에서 설정한 파라미터 이름을 'user_msg'라고 가정합니다.
    action = req.get('action', {})
    user_message = action.get('params', {}).get('user_msg', '').strip()
    
    if not user_message:
        # 혹시 파라미터가 비어있다면 유저가 보낸 날것의 발화문을 대사로 씁니다.
        user_message = req.get('userRequest', {}).get('utterance', '').strip()

    # 해당 유저의 대화 기록이 없으면 초기화
    if user_id not in chat_db:
        chat_db[user_id] = [
            {"role": "system", "content": SYSTEM_PROMPT}
        ]
    
    # 유저 대사 대화 기록에 추가
    chat_db[user_id].append({"role": "user", "content": user_message})
    
    try:
        # 🤖 [생성형 AI 요소]: OpenAI gpt-4o-mini 모델을 사용해 실시간 답변 생성
        completion = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=chat_db[user_id],
            temperature=0.7
        )
        ai_response = completion.choices[0].message.content.strip()
    except Exception as e:
        ai_response = f"⚠️ 귀신이 일시적으로 침묵했습니다. (API 오류: {str(e)})"

    # AI 답변도 기록에 추가 (맥락 유지용)
    chat_db[user_id].append({"role": "assistant", "content": ai_response})

    # 🔑 판정 기믹: AI가 대사에 '[SUCCESS]'를 포함했는지 검사합니다.
    is_cleared = "[SUCCESS]" in ai_response
    
    # 유저에게 보여줄 대사에서는 시스템 키워드인 [SUCCESS]를 깔끔하게 지워줍니다.
    display_text = ai_response.replace("[SUCCESS]", "").strip()
    
    # 카카오 챗봇 응답 조립
    response_data = {
        "version": "2.0",
        "template": {
            "outputs": [{"simpleText": {"text": f"👻 귀신:\n\"{display_text}\""}}],
            "quickReplies": []
        }
    }
    
    if is_cleared:
        # 2️⃣ [성공 시]: 설득 완료되었다면 다음 지역으로 가는 탈출 버튼을 띄워줍니다!
        response_data["template"]["quickReplies"].append({
            "action": "block",
            "label": "🚪 열린 길로 탈출하기",
            "blockId": "여기에_다음_지역_블록_ID_넣기"
        })
        # 대화 기록 리셋 (다음 플레이를 위해)
        del chat_db[user_id]
    else:
        # 3️⃣ [대화 진행 중]: 아직 설득이 안 됐다면 다시 귀신에게 말을 거는 퀵리플라이를 띄웁니다.
        response_data["template"]["quickReplies"].append({
            "action": "block",
            "label": "💬 다시 설득해보기",
            "blockId": req.get('userRequest', {}).get('block', {}).get('id') # 현재 블록 반복
        })

    return jsonify(response_data)
