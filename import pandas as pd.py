import streamlit as st
import pandas as pd
import requests
import json
import random
import time
import os
from google import genai

# ==========================================
# 0. API KEY & 환경 설정 (보안 강화)
# ==========================================
# 공공데이터포털 국세청 사업자등록정보 진단 API Decoding 키
PUBLIC_DATA_SERVICE_KEY = os.getenv("PUBLIC_DATA_SERVICE_KEY", "YOUR_PUBLIC_DATA_API_SERVICE_KEY")

# Google Gemini API Key
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "YOUR_GEMINI_API_KEY")

# Gemini Client 초기화
client = None
if GEMINI_API_KEY and GEMINI_API_KEY != "YOUR_GEMINI_API_KEY":
    try:
        client = genai.Client(api_key=GEMINI_API_KEY)
    except Exception as e:
        st.warning(f"Gemini API 클라이언트 초기화 중 경고: {e}")

# Page Layout Config
st.set_page_config(
    page_title="삼일 AX 세무 AI Agent 파이프라인",
    page_icon="💼",
    layout="wide"
)

# ==========================================
# 1. 국세청 공공데이터 API 실시간 연동 Engine
# ==========================================
def check_nts_status(biz_no_list):
    """
    국세청 진단 API를 호출하여 실제 사업자 상태 및 과세유형을 실시간 반환
    """
    api_url = f"https://api.odcloud.kr/api/nts-businessman/v1/status?serviceKey={PUBLIC_DATA_SERVICE_KEY}"
    cleaned_nos = [str(b).replace("-", "").strip() for b in biz_no_list]
    payload = {"b_no": cleaned_nos}
    headers = {'Content-Type': 'application/json'}
    
    try:
        response = requests.post(api_url, data=json.dumps(payload), headers=headers, timeout=5)
        if response.status_code == 200:
            res_data = response.json()
            return res_data.get("data", [])
    except Exception as e:
        st.error(f"국세청 API 호출 중 오류 발생: {e}")
    return []

# ==========================================
# 2. Excel DB 불러오기 및 데이터 전처리
# ==========================================
@st.cache_data
def load_data():
    excel_file = "DB.xlsx"
    if not os.path.exists(excel_file):
        return pd.DataFrame()
    try:
        df = pd.read_excel(excel_file)
        # 전화번호 문자열 포맷팅
        if '전화번호' in df.columns:
            df['전화번호_clean'] = df['전화번호'].astype(str).str.replace("-", "").str.strip()
        # 사업자번호 정제
        if '사업자번호' in df.columns:
            df['biz_num_clean'] = df['사업자번호'].astype(str).str.replace("-", "").str.strip()
        return df
    except Exception as e:
        st.error(f"DB.xlsx 파일 로드 오류: {e}")
        return pd.DataFrame()

df_db = load_data()

# ==========================================
# 3. Gemini 2.0 Flash LLM 세무 응대 생성
# ==========================================
def generate_tax_response(user_name, company_name, tax_type, biz_status, query_msg):
    prompt = f"""
    당신은 대형 회계법인 및 세무법인의 전문 세무 CS AI Agent입니다.
    아래 고객 정보 및 국세청 실시간 과세유형 판별 결과를 바탕으로, 친절하고 명확한 1:1 맞춤형 세무 안내 문장을 작성해 주세요.

    [고객 및 사업장 정보]
    - 대표자명: {user_name}
    - 상호명: {company_name}
    - 국세청 실시간 상태: {biz_status}
    - 판별된 과세유형: {tax_type}
    - 고객 문의 내용: {query_msg}

    [응대 가이드라인]
    1. 간이과세자인 경우: 정기신고(1월) 시기 및 세금계산서 발급 가능 여부/부가가치세 확정신고 대상 여부를 명확히 안내하세요.
    2. 일반과세자인 경우: 부가가치세 신고 대상(1월/7월) 및 세금계산서 발행 의무를 안내하세요.
    3. 폐업자/휴업자인 경우: 폐업에 따른 부가가치세 수시신고 및 세무 처리 주의사항을 정중히 안내하세요.
    4. 비즈니스 톤앤매너: 전문적이고 신뢰감 있는 세무 컨설턴트의 어조를 유지하세요.
    """
    
    if client:
        try:
            response = client.models.generate_content(
                model="gemini-2.0-flash",
                contents=prompt
            )
            return response.text
        except Exception as e:
            return f"[Gemini API 응답 생성 오류]: {e}\n\n(기본 템플릿): 고객님({company_name})은 현재 국세청 기준 '{tax_type}' 상태입니다."
    else:
        return f"(API Key 미설정 기본 응대): 고객님({company_name})은 국세청 실시간 조회 결과 [{tax_type}] (상태: {biz_status})로 확인되었습니다. 이번 부가가치세 신고 대상 여부를 체크해 드립니다."

# ==========================================
# 4. Streamlit Main UI / 대시보드
# ==========================================
st.title("💼 삼일 AX 세무 AI Agent 파이프라인")
st.caption("Excel TA DB 실시간 매핑 → 국세청 공공데이터 API 과세유형 판별 → Gemini 2.0 Flash 맞춤 응대")
st.divider()

if df_db.empty:
    st.warning("⚠️ 'DB.xlsx' 파일을 찾을 수 없거나 데이터가 비어 있습니다. 폴더 위치를 확인해 주세요.")
else:
    if 'selected_row' not in st.session_state:
        st.session_state.selected_row = df_db.iloc[0]

    col1, col2 = st.columns([1, 1])

    # --------------------------------------
    # 왼쪽 컬럼: 고객 유입 & 시뮬레이션
    # --------------------------------------
    with col1:
        st.subheader("1. 고객 유입 시뮬레이션 (채널톡 UI)")
        
        if st.button("🎲 엑셀 DB에서 샘플 무작위 추출", use_container_width=True):
            random_idx = random.randint(0, len(df_db) - 1)
            st.session_state.selected_row = df_db.iloc[random_idx]

        curr_data = st.session_state.selected_row
        
        user_name = st.text_input("대표자명", value=str(curr_data.get('이름', '')))
        user_phone = st.text_input("전화번호 ('-' 제외)", value=str(curr_data.get('전화번호_clean', '')))
        biz_num_input = st.text_input("사업자등록번호", value=str(curr_data.get('사업자번호', '')))
        user_msg = st.text_area("고객 세무 문의 내용", value="이번 부가가치세 신고 대상에 해당하나요? 과세유형 확인 부탁드립니다.")

        btn_process = st.button("⚡ AI 자동화 파이프라인 실행", type="primary", use_container_width=True)

    # --------------------------------------
    # 오른쪽 컬럼: 파이프라인 실행 결과 (Agent Output)
    # --------------------------------------
    with col2:
        st.subheader("2. AI Agent 파이프라인 처리 결과")

        if btn_process:
            if not user_name or not user_phone:
                st.error("❌ [1차 검증 실패] 필수 고객 정보가 누락되었습니다.")
            else:
                with st.spinner("1️⃣ Excel DB 매핑 & 2️⃣ 국세청 실시간 API 조회 중..."):
                    time.sleep(0.3)
                    
                    # 1. DB 매핑
                    matched = df_db[
                        (df_db['전화번호_clean'] == user_phone) & 
                        (df_db['이름'] == user_name)
                    ]
                    
                    if matched.empty:
                        matched_info = {
                            '이름': user_name,
                            '상호': curr_data.get('상호', '미등록 사업장'),
                            '사업자번호': biz_num_input,
                            '개업일자': curr_data.get('개업일자', '-'),
                            '업종(업종코드)': curr_data.get('업종(업종코드)', '-')
                        }
                        st.info("ℹ️ DB 미등록 고객 - 입력된 사업자번호로 국세청 실시간 조회를 진행합니다.")
                    else:
                        matched_info = matched.iloc[0].to_dict()
                        st.success(f"✅ [TA DB 매핑 성공] {matched_info['이름']} 대표님 ({matched_info['상호']})")

                    # 2. 채널톡 '더보기 메모 카드' 자동 생성
                    st.markdown("### 📝 더보기 메모 카드 (자동 파싱)")
                    memo_content = f"""
                    • 대표자명: {matched_info.get('이름', '-')}
                    • 상호명: {matched_info.get('상호', '-')}
                    • 사업자번호: {matched_info.get('사업자번호', '-')}
                    • 개업일자: {matched_info.get('개업일자', '-')}
                    • 업종(코드): {matched_info.get('업종(업종코드)', '-')}
                    """
                    st.code(memo_content.strip(), language="markdown")

                    # 3. 국세청 공공데이터 API 실시간 호출
                    st.markdown("### 🔍 국세청 실시간 과세유형 진단")
                    raw_biz_no = str(matched_info.get('사업자번호', '')).replace("-", "").strip()
                    
                    nts_results = check_nts_status([raw_biz_no])
                    
                    if nts_results:
                        res = nts_results[0]
                        b_stt = res.get("b_stt", "조회불가") # 사업자상태 (계속사업자, 폐업자 등)
                        tax_type = res.get("tax_type", "정보없음") # 부가가치세 일반과세자, 간이과세자 등
                        
                        st.write(f"**[국세청 DB 상태]**: `{b_stt}` | **[과세유형]**: `{tax_type}`")
                    else:
                        b_stt = "조회 실패"
                        tax_type = "일반과세자(기본값)"
                        st.warning("⚠️ 국세청 API 응답 대기 초과로 기본 과세유형 로직을 적용합니다.")

                    # 4. Gemini 2.0 Flash 기반 실시간 세무 CS 응대 문장 생성
                    st.markdown("### 🤖 Gemini 2.0 Flash 맞춤 세무 응대")
                    with st.spinner("Gemini LLM이 맞춤형 세무 응대 메시지를 작성 중입니다..."):
                        llm_response = generate_tax_response(
                            user_name=matched_info.get('이름', user_name),
                            company_name=matched_info.get('상호', '사업장'),
                            tax_type=tax_type,
                            biz_status=b_stt,
                            query_msg=user_msg
                        )
                        
                        st.info(f"**[AI 자동 발송 메시지]**\n\n{llm_response}")

st.divider()
st.caption("Samil PwC AX Advisory Portfolio | End-to-End Tax Automation Pipeline Sandbox")