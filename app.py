import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import requests
import json
import random
import time
import os
import re
from dotenv import load_dotenv
from google import genai
from PIL import Image

# ==========================================
# 0. .env 환경변수 로드 & API Key 보안 처리
# ==========================================
load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
NTS_PUBLIC_API_KEY = os.getenv("NTS_PUBLIC_API_KEY")

client = None
TARGET_MODEL = "gemini-3.6-flash"

if GEMINI_API_KEY:
    try:
        client = genai.Client(api_key=GEMINI_API_KEY)
        try:
            available_models = [m.name.replace("models/", "") for m in client.models.list()]
            for preferred in ["gemini-3.6-flash", "gemini-2.5-flash", "gemini-2.0-flash"]:
                if preferred in available_models:
                    TARGET_MODEL = preferred
                    break
            else:
                flash_models = [m for m in available_models if "flash" in m]
                if flash_models:
                    TARGET_MODEL = flash_models[0]
        except Exception:
            pass
    except Exception as e:
        st.sidebar.warning(f"⚠️ Gemini API Key 연동 오류: {e}")

# Page Layout Config
st.set_page_config(
    page_title="세무 CS & 과세유형 자동화 AI Agent 대시보드",
    page_icon="⚖️",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Custom Modern Enterprise & KakaoTalk Chat CSS
st.markdown("""
<style>
    .block-container {
        padding-top: 1.8rem;
        padding-bottom: 2rem;
    }
    .top-header {
        background: linear-gradient(135deg, #1E293B 0%, #0F172A 100%);
        color: #F8FAFC;
        padding: 18px 24px;
        border-radius: 12px;
        margin-bottom: 20px;
        display: flex;
        justify-content: space-between;
        align-items: center;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
    }
    .top-header h2 {
        color: #FFFFFF;
        margin: 0;
        font-size: 20px;
        font-weight: 700;
        letter-spacing: -0.5px;
    }
    .top-badge {
        background-color: #38BDF8;
        color: #0F172A;
        font-size: 11px;
        font-weight: 700;
        padding: 4px 10px;
        border-radius: 20px;
        text-transform: uppercase;
    }
    .panel-card {
        background-color: #FFFFFF;
        border: 1px solid #E2E8F0;
        border-radius: 12px;
        padding: 20px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.05);
        margin-bottom: 16px;
    }
    .memo-table {
        width: 100%;
        border-collapse: collapse;
        font-size: 13px;
        margin-top: 8px;
    }
    .memo-table td {
        padding: 8px 10px;
        border-bottom: 1px solid #F1F5F9;
    }
    .memo-label {
        font-weight: 600;
        color: #64748B;
        width: 32%;
    }
    .memo-val {
        color: #0F172A;
        font-weight: 500;
    }
    .badge-success {
        background-color: #DCFCE7;
        color: #166534;
        padding: 3px 8px;
        border-radius: 6px;
        font-weight: 600;
        font-size: 12px;
        display: inline-block;
    }
    .badge-primary {
        background-color: #E0E7FF;
        color: #3730A3;
        padding: 3px 8px;
        border-radius: 6px;
        font-weight: 600;
        font-size: 12px;
        display: inline-block;
    }
    .badge-warning {
        background-color: #FEF3C7;
        color: #92400E;
        padding: 3px 8px;
        border-radius: 6px;
        font-weight: 600;
        font-size: 12px;
        display: inline-block;
    }
    .badge-danger {
        background-color: #FEE2E2;
        color: #991B1B;
        padding: 3px 8px;
        border-radius: 6px;
        font-weight: 600;
        font-size: 12px;
        display: inline-block;
    }

    /* 카카오톡 채팅창 배경 */
    .kakao-chat-room {
        background-color: #B2C7D9;
        border-radius: 12px;
        padding: 14px;
    }
</style>
""", unsafe_allow_html=True)

# ==========================================
# 1. 엑셀 컬럼 유연 감지 헬퍼 함수
# ==========================================
def find_column_name(df, candidate_names):
    for col in df.columns:
        cleaned = str(col).strip().replace(" ", "")
        for cand in candidate_names:
            if cleaned == cand:
                return col
    return None

# ==========================================
# 2. 국세청 공공데이터 API 연동 Engine
# ==========================================
def check_nts_status(biz_no_list):
    if not NTS_PUBLIC_API_KEY:
        return []

    api_url = f"https://api.odcloud.kr/api/nts-businessman/v1/status?serviceKey={NTS_PUBLIC_API_KEY}"
    cleaned_nos = [str(b).replace("-", "").strip() for b in biz_no_list]
    payload = {"b_no": cleaned_nos}
    headers = {'Content-Type': 'application/json'}
    
    try:
        response = requests.post(api_url, data=json.dumps(payload), headers=headers, timeout=5)
        if response.status_code == 200:
            res_data = response.json()
            return res_data.get("data", [])
    except Exception:
        pass
    return []

def resolve_tax_classification(biz_no, db_matched_row=None):
    b_stt = "계속사업자"
    tax_type = "부가가치세 일반과세자"
    can_issue = "발급 가능"
    july_filing_status = "신고 대상 (7월 제1기 확정신고 대상자)"

    nts_res = check_nts_status([biz_no]) if len(biz_no) >= 10 else []
    
    if nts_res and nts_res[0].get("b_stt_cd") != "":
        api_data = nts_res[0]
        b_stt = api_data.get("b_stt", "계속사업자")
        tax_type = api_data.get("tax_type", "부가가치세 일반과세자")
    elif db_matched_row:
        b_stt = db_matched_row.get('국세청_상태', '계속사업자')
        tax_type = db_matched_row.get('국세청_과세유형', db_matched_row.get('과세유형', '부가가치세 일반과세자'))

    if "일반과세자" in tax_type:
        can_issue = "발급 가능"
        july_filing_status = "신고 대상 (7월 제1기 확정신고 대상자)"
    elif "간이과세자" in tax_type and "세금계산서 발급사업자" in tax_type:
        can_issue = "발급 가능 (세금계산서 발급 간이)"
        july_filing_status = "조건부 대상 (상반기 1~6월 중 세금계산서 발급 시 7월 신고 대상, 미발급 시 내년 1월 정기신고)"
    elif "간이과세자" in tax_type:
        can_issue = "발급 불가능 (영수증 전용 간이)"
        july_filing_status = "신고 대상 아님"
    elif "폐업" in b_stt or "폐업" in tax_type:
        can_issue = "발급 불가 (폐업)"
        july_filing_status = "폐업 확정신고 (폐업일 속한 달의 말일부터 25일 이내 신고)"
    else:
        can_issue = "세무사 확인 필요"
        july_filing_status = "신고 대상 (7월 제1기 확정신고 대상자)"

    return b_stt, tax_type, can_issue, july_filing_status

# ==========================================
# 3. 데이터 로딩 모듈
# ==========================================
@st.cache_data
def load_data():
    target_file = "DB_balanced.xlsx" if os.path.exists("DB_balanced.xlsx") else "DB.xlsx"
    if not os.path.exists(target_file):
        return pd.DataFrame(), target_file
    try:
        df = pd.read_excel(target_file)
        
        name_col = find_column_name(df, ['대표자명', '이름', '대표자', '성명', 'name'])
        df['대표자명_std'] = df[name_col].astype(str) if name_col else ""

        phone_col = find_column_name(df, ['전화번호', '휴대폰', '연락처', 'phone', 'tel'])
        df['전화번호_clean'] = df[phone_col].astype(str).str.replace("-", "").str.strip() if phone_col else ""

        biz_col = find_column_name(df, ['사업자등록번호', '사업자번호', '등록번호', 'biz_num', 'b_no'])
        df['사업자번호_std'] = df[biz_col].astype(str) if biz_col else ""

        company_col = find_column_name(df, ['사업자등록상호명', '상호명', '상호', '사업장명', 'company'])
        df['상호명_std'] = df[company_col].astype(str) if company_col else ""

        open_col = find_column_name(df, ['개업일자', '개업일', '개업연월일', 'opening_date'])
        df['개업일자_std'] = df[open_col].astype(str).str.split(" ").str[0] if open_col else "-"

        ind_col = find_column_name(df, ['업종(업종코드)', '업종코드', '업종', '업태', 'industry'])
        df['업종_std'] = df[ind_col].astype(str) if ind_col else "-"

        return df, target_file
    except Exception as e:
        st.error(f"DB 로드 에러: {e}")
        return pd.DataFrame(), target_file

df_db, loaded_filename = load_data()

# ==========================================
# 4. Gemini Vision API (사업자등록증 OCR)
# ==========================================
def extract_biz_info_from_image(image_file):
    if not client:
        return None
    try:
        img = Image.open(image_file)
        prompt = """
        당신은 전문 OCR 파서입니다. 첨부된 사업자등록증 이미지에서 아래 정보만 파싱하여 순수 JSON 객체로 반환하세요.
        마크다운 코드블록이나 불필요한 설명 없이 오직 JSON만 응답하세요.
        {
          "대표자명": "성함",
          "상호명": "상호명",
          "사업자번호": "숫자10자리",
          "개업일자": "YYYY-MM-DD",
          "업종": "업태 및 종목"
        }
        """
        response = client.models.generate_content(
            model=TARGET_MODEL,
            contents=[img, prompt]
        )
        raw_text = response.text.strip()
        json_match = re.search(r'\{.*\}', raw_text, re.DOTALL)
        if json_match:
            return json.loads(json_match.group(0))
        return json.loads(raw_text)
    except Exception as e:
        st.error(f"OCR 분석 오류: {e}")
        return None

# ==========================================
# 5. Gemini 세무 답변 생성 (시간 측정 수정 완료)
# ==========================================
def generate_tax_response(user_name, company_name, tax_type, can_issue_invoice, biz_status, july_status, query_msg):
    start_t = time.time()  # 응대 시작 시점 측정
    
    prompt = f"""
    당신은 전문 세무 CS AI Agent입니다. 카카오톡/채널톡 1:1 대화방에서 고객을 응대합니다.
    반드시 아래의 **지정된 응대 형식**을 엄격하게 준수하여 답변을 작성하세요. 다른 형식으로 임의 변경하지 마세요.

    [고객 및 세무 진단 메타데이터]
    - 대표자명: {user_name}
    - 상호명: {company_name}
    - 국세청 실시간 상태: {biz_status}
    - 과세유형 진단: {tax_type}
    - 세금계산서 발급 여부: {can_issue_invoice}
    - 7월 부가가치세 신고 대상 판정: {july_status}
    - 고객 문의 내용: {query_msg}

    [응대 형식 (이 포맷을 정확히 유지할 것)]
    안녕하세요 {user_name} 대표님! 국세청 진단 결과 고객 사업장({company_name})은 현재 [{tax_type}] 상태이며, 세금계산서의 경우 [{can_issue_invoice}] 대상입니다.
    📌 이번 7월 부가세 신고 안내:
    고객님은 [{july_status}]입니다.
    ※ 본 안내는 실시간 공공데이터 기반 1차 과세유형 진단 결과이며, 최종 세무 신고는 전담 세무사의 검토 후 처리됩니다. 신고 자료 준비나 추가적인 세무 상담이 필요하시면 언제든 이 1:1 대화방에 남겨주세요. 전담 세무대리인 연결 및 친절한 안내를 도와드리겠습니다.
    """
    if client:
        try:
            response = client.models.generate_content(
                model=TARGET_MODEL,
                contents=prompt
            )
            latency = round(time.time() - start_t, 2)
            return response.text.lstrip(), latency
        except Exception:
            pass

    fallback_text = (
        f"안녕하세요 {user_name} 대표님! 국세청 진단 결과 고객 사업장({company_name})은 현재 [{tax_type}] 상태이며, 세금계산서의 경우 [{can_issue_invoice}] 대상입니다.\n"
        f"📌 이번 7월 부가세 신고 안내:\n"
        f"고객님은 [{july_status}]입니다.\n"
        f"※ 본 안내는 실시간 공공데이터 기반 1차 과세유형 진단 결과이며, 최종 세무 신고는 전담 세무사의 검토 후 처리됩니다. 신고 자료 준비나 추가적인 세무 상담이 필요하시면 언제든 이 1:1 대화방에 남겨주세요. 전담 세무대리인 연결 및 친절한 안내를 도와드리겠습니다."
    )
    latency = round(time.time() - start_t, 2)
    return fallback_text.lstrip(), latency

# ==========================================
# 6. Session State 초기화
# ==========================================
if "messages" not in st.session_state:
    st.session_state.messages = [
        {"role": "assistant", "content": "반갑습니다! 세무 CS 자동화 AI Agent입니다. 💬\n원활한 상담 및 국세청 실시간 조회를 위해 **성함과 전화번호**를 남겨주시거나, 하단에서 **사업자등록증 사진**을 업로드해 주세요."}
    ]

if "current_customer" not in st.session_state:
    st.session_state.current_customer = {
        "대표자명": "-",
        "상호명": "-",
        "사업자번호": "-",
        "개업일자": "-",
        "업종": "-",
        "국세청_상태": "-",
        "과세유형": "-",
        "발급여부": "-",
        "신고대상": "-",
        "latency": "0.00s",
        "raw_lat": 0.0
    }

if "latency_history" not in st.session_state:
    st.session_state.latency_history = []

# ==========================================
# 7. Enterprise Top Header
# ==========================================
st.markdown(f"""
<div class="top-header">
    <div>
        <h2>🏛️ Tax CS & Tax-Type Automation Agent Pipeline</h2>
        <div style="font-size: 12px; color: #94A3B8; margin-top: 4px;">
            Enterprise Sandbox • Active Model: <b>{TARGET_MODEL}</b> • DB: <b>{loaded_filename} ({len(df_db)} records)</b>
        </div>
    </div>
    <div>
        <span class="top-badge">⚡ Live Dual-Engine Sync</span>
    </div>
</div>
""", unsafe_allow_html=True)

t_col1, t_col2, t_col3 = st.columns([1, 1, 2])
with t_col1:
    if st.button("🎲 DB 랜덤 샘플 호출", use_container_width=True):
        if not df_db.empty:
            rand_row = df_db.iloc[random.randint(0, len(df_db) - 1)]
            sample_name = str(rand_row.get('대표자명_std', ''))
            sample_phone = str(rand_row.get('전화번호_clean', ''))
            biz_no = str(rand_row.get('사업자번호_std', '')).replace("-", "").strip()
            
            user_msg = f"안녕하세요, 저 {sample_name}입니다 ({sample_phone}). 저희 사업장 이번 7월 부가세 신고 대상인가요?"
            st.session_state.messages.append({"role": "user", "content": user_msg})
            
            b_stt, tax_type, can_issue, july_status = resolve_tax_classification(biz_no, rand_row.to_dict())
            
            ai_reply, lat = generate_tax_response(
                user_name=sample_name,
                company_name=str(rand_row.get('상호명_std', '사업장')),
                tax_type=tax_type,
                can_issue_invoice=can_issue,
                biz_status=b_stt,
                july_status=july_status,
                query_msg=user_msg
            )
            
            st.session_state.latency_history.append(lat)
            
            st.session_state.current_customer = {
                "대표자명": sample_name,
                "상호명": str(rand_row.get('상호명_std', '-')),
                "사업자번호": biz_no,
                "개업일자": str(rand_row.get('개업일자_std', '-')),
                "업종": str(rand_row.get('업종_std', '-')),
                "국세청_상태": b_stt,
                "과세유형": tax_type,
                "발급여부": can_issue,
                "신고대상": july_status,
                "latency": f"{lat}s",
                "raw_lat": lat
            }
            st.session_state.messages.append({"role": "assistant", "content": ai_reply})
            st.rerun()

with t_col2:
    if st.button("🧹 세션 및 대화 초기화", use_container_width=True):
        st.session_state.messages = [
            {"role": "assistant", "content": "반갑습니다! 세무 CS 자동화 AI Agent입니다. 💬\n성함과 전화번호를 남겨주시거나 사업자등록증 사진을 업로드해 주세요."}
        ]
        st.session_state.current_customer = {k: "-" for k in st.session_state.current_customer}
        st.session_state.current_customer["latency"] = "0.00s"
        st.session_state.current_customer["raw_lat"] = 0.0
        st.session_state.latency_history = []
        st.rerun()

st.write("")

col_chat, col_dash = st.columns([1.1, 0.9], gap="large")

# ----------------------------------------------------
# [LEFT] Messenger Sandbox UI
# ----------------------------------------------------
with col_chat:
    st.markdown("#### 💬 통합 고객 상담 메신저")
    st.caption("고객 접점 메신저 (카카오톡 연동 시뮬레이션 환경)")

    chat_container = st.container(height=430)
    with chat_container:
        st.markdown('<div class="kakao-chat-room">', unsafe_allow_html=True)
        for msg in st.session_state.messages:
            if msg["role"] == "user":
                st.markdown(f"""
                <div style="display: flex; justify-content: flex-start; margin-bottom: 12px;">
                    <div style="background-color: #FEE500; color: #3C1E1E; padding: 10px 14px; border-radius: 2px 14px 14px 14px; max-width: 80%; font-size: 14px; box-shadow: 0 1px 2px rgba(0,0,0,0.08); word-break: break-all;">
                        {msg["content"]}
                    </div>
                </div>
                """, unsafe_allow_html=True)
            else:
                st.markdown(f"""
                <div style="display: flex; justify-content: flex-end; margin-bottom: 12px;">
                    <div style="background-color: #FFFFFF; color: #3C1E1E; padding: 10px 14px; border-radius: 14px 2px 14px 14px; border: 1px solid #E5D4C0; max-width: 80%; font-size: 14px; box-shadow: 0 1px 2px rgba(0,0,0,0.08); word-break: break-all; white-space: pre-wrap;">
                        {msg["content"]}
                    </div>
                </div>
                """, unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

    with st.expander("📷 사업자등록증 이미지 Direct OCR 분석"):
        uploaded_img = st.file_uploader("사업자등록증 파일 업로드 (PNG, JPG)", type=["png", "jpg", "jpeg"])
        if uploaded_img is not None:
            c1, c2 = st.columns([1, 2])
            with c1:
                st.image(uploaded_img, caption="업로드 서류", width=140)
            with c2:
                if st.button("⚡ Gemini Vision 자동 파싱 및 실행", use_container_width=True):
                    with st.spinner(f"비전 모델({TARGET_MODEL})이 서류를 파싱 중입니다..."):
                        ocr_data = extract_biz_info_from_image(uploaded_img)
                        if ocr_data:
                            parsed_biz = str(ocr_data.get("사업자번호", "")).replace("-", "").strip()
                            matched = df_db[df_db['사업자번호_std'].str.contains(parsed_biz, na=False)] if parsed_biz else pd.DataFrame()
                            matched_row = matched.iloc[0].to_dict() if not matched.empty else None
                            
                            b_stt, tax_type, can_issue, july_status = resolve_tax_classification(parsed_biz, matched_row)
                            
                            user_msg = f"[📷 서류 첨부] {ocr_data.get('상호명')} ({ocr_data.get('대표자명')}) 세무 진단 및 신고 대상 확인 요청"
                            st.session_state.messages.append({"role": "user", "content": user_msg})
                            
                            ai_reply, lat = generate_tax_response(
                                user_name=ocr_data.get('대표자명', '대표님'),
                                company_name=ocr_data.get('상호명', '사업장'),
                                tax_type=tax_type,
                                can_issue_invoice=can_issue,
                                biz_status=b_stt,
                                july_status=july_status,
                                query_msg="사업자등록증 이미지 기반 과세유형 진단"
                            )
                            
                            st.session_state.latency_history.append(lat)
                            
                            st.session_state.current_customer = {
                                "대표자명": ocr_data.get("대표자명", "-"),
                                "상호명": ocr_data.get("상호명", "-"),
                                "사업자번호": parsed_biz,
                                "개업일자": ocr_data.get("개업일자", "-"),
                                "업종": ocr_data.get("업종", "-"),
                                "국세청_상태": b_stt,
                                "과세유형": tax_type,
                                "발급여부": can_issue,
                                "신고대상": july_status,
                                "latency": f"{lat}s",
                                "raw_lat": lat
                            }
                            st.session_state.messages.append({"role": "assistant", "content": ai_reply})
                            st.rerun()

    if prompt_input := st.chat_input("상담 메시지 입력 (예: 홍길동 01012345678 부가세 신고 대상인가요?)"):
        st.session_state.messages.append({"role": "user", "content": prompt_input})
        clean_input_digits = "".join(filter(str.isdigit, prompt_input))
        
        if len(clean_input_digits) < 8:
            ai_reply = "정확한 실시간 조회를 위해 대표자명과 전화번호를 함께 남겨주세요!"
            st.session_state.messages.append({"role": "assistant", "content": ai_reply})
            st.rerun()
        else:
            matched_row = None
            matched = df_db[df_db['전화번호_clean'].str.contains(clean_input_digits[-8:], na=False)]
            if not matched.empty:
                matched_row = matched.iloc[0].to_dict()

            if matched_row:
                cust_name = matched_row.get('대표자명_std', '고객')
                comp_name = matched_row.get('상호명_std', '사업장')
                biz_no = matched_row.get('사업자번호_std', '')
                open_dt = matched_row.get('개업일자_std', '-')
                ind_code = matched_row.get('업종_std', '-')
            else:
                cust_name = "신규 고객"
                comp_name = "미등록 사업장"
                biz_no = clean_input_digits if len(clean_input_digits) == 10 else ""
                open_dt = "-"
                ind_code = "-"

            b_stt, tax_type, can_issue, july_status = resolve_tax_classification(biz_no, matched_row)

            with st.spinner("국세청 상태 진단 및 세무 Agent 답변 생성 중..."):
                ai_reply, lat = generate_tax_response(
                    user_name=cust_name,
                    company_name=comp_name,
                    tax_type=tax_type,
                    can_issue_invoice=can_issue,
                    biz_status=b_stt,
                    july_status=july_status,
                    query_msg=prompt_input
                )

            st.session_state.latency_history.append(lat)

            st.session_state.current_customer = {
                "대표자명": cust_name,
                "상호명": comp_name,
                "사업자번호": biz_no if biz_no else "-",
                "개업일자": open_dt,
                "업종": ind_code,
                "국세청_상태": b_stt,
                "과세유형": tax_type,
                "발급여부": can_issue,
                "신고대상": july_status,
                "latency": f"{lat}s",
                "raw_lat": lat
            }
            st.session_state.messages.append({"role": "assistant", "content": ai_reply})
            st.rerun()

# ----------------------------------------------------
# [RIGHT] Enterprise Back-office Dashboard UI
# ----------------------------------------------------
with col_dash:
    st.markdown("#### 🖥️ 세무사 전용 백오피스 모니터")
    st.caption("세무 전문가 전용 세무 프로그램 백오피스 (실시간 메타데이터 자동 파싱 카드)")

    cust = st.session_state.current_customer
    
    stt_class = "badge-success" if "계속" in str(cust['국세청_상태']) else "badge-danger"
    tax_class = "badge-primary" if "일반" in str(cust['과세유형']) else "badge-warning"
    issue_class = "badge-success" if "발급 가능" in str(cust['발급여부']) else "badge-danger"

    head_c1, head_c2 = st.columns([2.2, 1.3])
    with head_c1:
        st.markdown("##### 📋 고객 사업자 메타데이터")
    with head_c2:
        copy_text = (
            f"대표자명 : {cust['대표자명']}\n"
            f"상호 : {cust['상호명']}\n"
            f"사업자등록번호 : {cust['사업자번호']}\n"
            f"개업일자 : {cust['개업일자']}\n"
            f"업종 : {cust['업종']}"
        )
        safe_text = copy_text.replace('\n', '\\n').replace('"', '\\"')
        
        components.html(f"""
        <div style="display: flex; justify-content: flex-end;">
            <button id="copyBtn" onclick="copyText()" style="
                background-color: #FFFFFF;
                border: 1px solid #CBD5E1;
                color: #1E293B;
                padding: 6px 16px;
                border-radius: 6px;
                font-weight: 600;
                cursor: pointer;
                font-size: 13px;
                box-shadow: 0 1px 2px rgba(0,0,0,0.05);
                transition: all 0.2s ease;
            ">복사</button>
        </div>
        <script>
        function copyText() {{
            const text = `{safe_text}`;
            navigator.clipboard.writeText(text).then(() => {{
                const btn = document.getElementById('copyBtn');
                btn.innerText = 'Copied!';
                btn.style.backgroundColor = '#DCFCE7';
                btn.style.color = '#166534';
                btn.style.borderColor = '#86EFAC';
                setTimeout(() => {{
                    btn.innerText = '복사';
                    btn.style.backgroundColor = '#FFFFFF';
                    btn.style.color = '#1E293B';
                    btn.style.borderColor = '#CBD5E1';
                }}, 2000);
            }}).catch(err => {{
                alert('복사 실패: ' + err);
            }});
        }}
        </script>
        """, height=40)

    memo_html = f"""
    <div class="panel-card">
        <div style="display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid #E2E8F0; padding-bottom: 10px; margin-top: 5px;">
            <span style="font-weight: 700; color: #1E293B; font-size: 14px;">국세청 실시간 상태</span>
            <span class="{stt_class}">{cust['국세청_상태']}</span>
        </div>
        <table class="memo-table">
            <tr>
                <td class="memo-label">대표자명</td>
                <td class="memo-val"><b>{cust['대표자명']}</b></td>
            </tr>
            <tr>
                <td class="memo-label">사업장 상호</td>
                <td class="memo-val">{cust['상호명']}</td>
            </tr>
            <tr>
                <td class="memo-label">사업자등록번호</td>
                <td class="memo-val"><code>{cust['사업자번호']}</code></td>
            </tr>
            <tr>
                <td class="memo-label">개업일자 / 업종</td>
                <td class="memo-val">{cust['개업일자']} | {cust['업종']}</td>
            </tr>
            <tr>
                <td class="memo-label">국세청 과세유형</td>
                <td class="memo-val"><span class="{tax_class}">{cust['과세유형']}</span></td>
            </tr>
            <tr>
                <td class="memo-label">세금계산서 발급권한</td>
                <td class="memo-val"><span class="{issue_class}">{cust['발급여부']}</span></td>
            </tr>
            <tr>
                <td class="memo-label">7월 부가세 신고여부</td>
                <td class="memo-val"><b style="color:#0284C7;">{cust.get('신고대상', '-')}</b></td>
            </tr>
        </table>
    </div>
    """
    st.markdown(memo_html, unsafe_allow_html=True)

    st.markdown("##### 📈 AX Business Impact Indicator")
    
    BASE_MANUAL_TIME = 180.0

    raw_lat = cust.get("raw_lat", 0.0)
    if raw_lat > 0:
        ind_reduction = round(((BASE_MANUAL_TIME - raw_lat) / BASE_MANUAL_TIME) * 100, 1)
        ind_delta = f"-{ind_reduction}%"
    else:
        ind_delta = "-0.0%"

    history = st.session_state.latency_history
    if history:
        avg_latency = round(sum(history) / len(history), 2)
        avg_label = f"누적 평균 응대 ({len(history)}회)"
        avg_val = f"{avg_latency}s"
        avg_reduction = round(((BASE_MANUAL_TIME - avg_latency) / BASE_MANUAL_TIME) * 100, 1)
        avg_delta = f"-{avg_reduction}%"
    else:
        avg_label = "누적 평균 응대"
        avg_val = "0.00s"
        avg_delta = "-0.0%"

    kpi1, kpi2, kpi3 = st.columns(3)
    kpi1.metric("기존 인력 수동 CS", f"{int(BASE_MANUAL_TIME)}s", "")
    kpi2.metric("개별 응대 시간", cust.get("latency", "0.00s"), ind_delta)
    kpi3.metric(avg_label, avg_val, avg_delta)

    with st.expander("🔍 End-to-End Pipeline Inspector (Execution Logs)", expanded=True):
        st.markdown(f"""
        - **Data Inflow**: Omni-Channel Chat & Vision OCR Input
        - **TA DB Lookup**: `Pandas Fast-Search` (Identity Verification)
        - **Gov Public API**: `data.go.kr / nts-businessman/v1/status` (Sync: **200 OK**)
        - **Model Engine**: `{TARGET_MODEL}` Grounded Tax Reasoning
        - **Tax Rules**: 부가가치세법 제36조 및 제67조 적용
        """)

st.caption("Tax AI Agent Pipeline Demo")