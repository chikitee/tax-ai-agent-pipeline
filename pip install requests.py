import streamlit as st
import pandas as pd
import random
import os
import time
import requests
from dotenv import load_dotenv
from google import genai

# 0. 환경 변수(.env) 로드
load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
NTS_API_KEY = os.getenv("NTS_API_KEY")

# Gemini Client 초기화
client = None
if GEMINI_API_KEY:
    try:
        client = genai.Client(api_key=GEMINI_API_KEY)
    except Exception as e:
        st.error(f"Gemini Client 초기화 실패: {e}")

# Page Layout Config
st.set_page_config(
    page_title="세무 CS & 과세유형 자동화 AI Agent 대시보드",
    page_icon="📑",
    layout="wide"
)

# 국세청 사업자등록정보 진단 API 호출 함수
def check_nts_tax_type(biz_num):
    clean_biz_num = str(biz_num).replace("-", "").strip()
    
    if not NTS_API_KEY:
        return "API Key 미설정 (테스트 모드)", "NTS_API_KEY가 .env 파일에 설정되지 않았습니다."
    
    url = f"https://api.odcloud.kr/api/nts-businessman/v1/status?serviceKey={NTS_API_KEY}"
    headers = {"Content-Type": "json", "Accept": "application/json"}
    payload = {"b_no": [clean_biz_num]}
    
    try:
        response = requests.post(url, json=payload, headers=headers, timeout=5)
        if response.status_code == 200:
            res_data = response.json()
            if res_data.get("data") and len(res_data["data"]) > 0:
                item = res_data["data"][0]
                b_stt = item.get("b_stt", "")  # 사업자 상태 (계속사업자, 휴업자, 폐업자 등)
                tax_type = item.get("tax_type", "과세유형 정보 없음") # 부가가치세 일반과세자, 간이과세자 등
                
                if b_stt:
                    result_summary = f"{tax_type} ({b_stt})"
                else:
                    result_summary = tax_type
                return result_summary, res_data
        return "조회 실패 (사업자번호 확인 필요)", response.text
    except Exception as e:
        return "국세청 API 통신 오류", str(e)

# 1. Excel DB 불러오기
@st.cache_data
def load_data():
    excel_file = "DB.xlsx"
    if not os.path.exists(excel_file):
        st.error(f"❌ '{excel_file}' 파일을 찾을 수 없습니다. 파일이 '세무 자동화' 폴더에 존재하는지 확인해 주세요.")
        return pd.DataFrame()
    
    try:
        df = pd.read_excel(excel_file)
        # 전화번호 문자열 포맷팅 (앞자리 0 유지 및 하이픈 제거)
        df['전화번호_clean'] = df['전화번호'].astype(str).str.replace("-", "").str.zfill(11)
        return df
    except Exception as e:
        st.error(f"❌ 엑셀 파일을 읽는 중 오류가 발생했습니다: {e}")
        st.info("💡 팁: 컴퓨터에서 DB.xlsx 파일이 열려있다면 완전히 닫고 다시 실행해 주세요.")
        return pd.DataFrame()

df_db = load_data()

# Header Section
st.title("📑 세무 CS & 과세유형 자동화 AI Agent 대시보드")
st.caption("Excel DB 실시간 매핑 → 더보기 메모 파싱 → 국세청 API 과세유형 실시간 검증 → Gemini 2.0 Flash 맞춤 상담")
st.divider()

if not df_db.empty:
    st.success(f"🎉 엑셀 DB 연결 성공! (총 {len(df_db)}건의 대표자 데이터 로드 완료)")
    
    if 'selected_row' not in st.session_state:
        st.session_state.selected_row = df_db.iloc[0]

    col1, col2 = st.columns([1, 1])

    with col1:
        st.subheader("1. 고객 문의 유입 (시뮬레이터)")
        
        if st.button("🎲 엑셀 DB에서 랜덤 샘플 추출", use_container_width=True):
            random_idx = random.randint(0, len(df_db) - 1)
            st.session_state.selected_row = df_db.iloc[random_idx]

        curr_data = st.session_state.selected_row

        user_name = st.text_input("고객 이름", value=str(curr_data['이름']))
        user_phone = st.text_input("전화번호 ('-' 제외)", value=str(curr_data['전화번호_clean']))
        user_msg = st.text_area("고객 문의 내용", value="안녕하세요, 이번 부가가치세 확정신고 대상인지 그리고 세금계산서 발행 관련 안내 부탁드립니다.", height=80)

        btn_process = st.button("🚀 자동화 파이프라인 실행", type="primary", use_container_width=True)

    with col2:
        st.subheader("2. 파이프라인 처리 및 AI Agent 응대 결과")

        if btn_process:
            if not user_name or not user_phone:
                st.error("❌ [1차 검증 실패] 필수 정보(이름, 전화번호)가 누락되었습니다.")
            else:
                with st.spinner("TA/Excel DB 매핑 및 파이프라인 연동 중..."):
                    time.sleep(0.3)
                    matched = df_db[(df_db['전화번호_clean'] == user_phone) & (df_db['이름'] == user_name)]

                if matched.empty:
                    st.warning("⚠️ [TA 조회 실패] 엑셀 DB에 등록된 정보가 없습니다.")
                    st.info("🤖 [자동 챗봇 발송]: '등록된 사업자 정보가 없습니다. 담당자 연결을 도와드릴까요?'")
                else:
                    matched_info = matched.iloc[0]
                    biz_num = matched_info['사업자번호']
                    
                    st.success(f"✅ [TA 매핑 성공] {matched_info['이름']} 대표님 사업자 정보 매핑 완료")

                    # Scenario 1: 'More Info' Memo Card UI
                    st.markdown("### 📋 채널톡 '더보기 메모' 규격화 데이터")
                    memo_content = f"""[TA 연동 상세 정보]
• 대표자명: {matched_info['이름']}
• 상호명: {matched_info['상호']}
• 사업자번호: {biz_num}
• 개업일자: {matched_info['개업일자']}
• 업종(코드): {matched_info['업종(업종코드)']}"""
                    st.code(memo_content, language="markdown")

                    # Scenario 2: Real NTS Public API Call
                    st.markdown("### 🏛️ 국세청 공공데이터 API 실시간 과세유형 검증")
                    with st.spinner("국세청 DB 실시간 사업자 상태 및 과세유형 조회 중..."):
                        tax_type_result, raw_api_res = check_nts_tax_type(biz_num)
                    
                    st.info(f"**[국세청 API 조회 결과]**: `{tax_type_result}`")

                    # Scenario 3: Gemini 2.0 Flash LLM Response Generation
                    st.markdown("### 🤖 Gemini 2.0 Flash 실시간 맞춤 세무 상담 생성")
                    
                    if client:
                        with st.spinner("Gemini AI Agent가 맞춤형 상담 응대문을 작성 중입니다..."):
                            prompt = f"""너는 세무사사무소 전문 세무 상담 AI Agent야.
아래 세무 회계 DB 정보, 국세청 API 과세유형 조회 결과, 그리고 고객의 문의사항을 바탕으로 고객에게 발송할 친절하고 정확한 1:1 맞춤 세무 응대 메시지를 작성해줘.

[사업자 정보]
- 대표자명: {matched_info['이름']}
- 상호명: {matched_info['상호']}
- 사업자번호: {biz_num}
- 업종: {matched_info['업종(업종코드)']}

[국세청 API 과세유형 조회 결과]
- {tax_type_result}

[고객 문의 내용]
- "{user_msg}"

[작성 가이드라인]
1. 인사말과 함께 고객의 상호명 및 과세유형(간이/일반 등)을 명확히 언급할 것.
2. 간이과세자인지 일반과세자인지에 따라 이번 부가가치세 신고 대상 여부와 세금계산서 발급 시 유의사항을 세무 관점에서 정확하게 안내할 것.
3. 3~4문장 내외로 신뢰감 있고 친절한 어조로 작성할 것."""

                            try:
                                response = client.models.generate_content(
                                    model='gemini-2.0-flash',
                                    contents=prompt,
                                )
                                st.chat_message("assistant").write(response.text)
                            except Exception as e:
                                st.error(f"Gemini LLM 생성 중 오류 발생: {e}")
                    else:
                        st.warning("⚠️ GEMINI_API_KEY가 설정되지 않아 LLM 응대문 작성을 스킵합니다.")

st.divider()
st.caption("AI Product Portfolio | Full-stack Tax AI Agent Sandbox Dashboard")
