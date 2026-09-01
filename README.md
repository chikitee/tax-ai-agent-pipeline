# 🏛️ Tax CS & Tax-Type Automation Agent Pipeline
> **세무 CS 인바운드 자동화 및 국세청 API 기반 실시간 과세유형 판별 AI Agent 파이프라인**  
> *AX Advisory & AI Product Portfolio for Big 4 Accounting Firms*

[![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Streamlit](https://img.shields.io/badge/Streamlit-App-FF4B4B?logo=streamlit&logoColor=white)](https://streamlit.io/)
[![Google GenAI](https://img.shields.io/badge/Gemini_2.0_Flash-Multimodal_LLM-4285F4?logo=google&logoColor=white)](https://ai.google.dev/)
[![Public Data API](https://img.shields.io/badge/NTS_API-data.go.kr-008080)](https://www.data.go.kr/)

---

## 📌 1. Project Background & Pain Points (프로젝트 배경 및 문제 정의)

세무법인 및 회계법인의 부가가치세 신고 기간마다 반복되는 **단순 조회성 인바운드 CS 및 과세유형 확인 작업의 병목(Bottleneck)**을 해결하기 위한 End-to-End AX(AI Transformation) 프로덕트입니다.

### 🔴 As-Is (기존 수동 프로세스의 한계)
* **심각한 공수 낭비**: 고객의 "이번 부가세 신고 대상인가요?" 문의 1건당 [고객 식별 → 세무 ERP(TA) 검색 → 홈택스 사업자 과세유형 수동 조회 → 세금계산서 발급 여부 확인 → 메신저 응대문 타이핑]까지 **건당 평균 3분(180초)** 소요.
* **복합 세법 분기 시 인적 오류 위험**: 간이과세자 중 세금계산서 발급 간이과세자(직전 연도 공급대가 4,800만 원 이상 ~ 1억 400만 원 미만)와 영수증 전용 간이과세자의 7월 확정신고 의무 차이로 인한 안내 혼선 발생.
* **백오피스 전표 입력 지연**: 유입된 사업자 메타데이터(상호, 사업자번호, 개업일자, 업종코드)를 세무 프로그램에 일일이 재입력하는 비효율성.

### 🟢 To-Be (AX AI Agent 도입 후 개선)
* **End-to-End 원스톱 파이프라인**: 텍스트 및 서류 이미지 유입 즉시 **[TA DB 매핑 + 국세청 공공데이터 API 실시간 동기화 + Gemini Multimodal/LLM 세법 추론 + 전문가 백오피스 카드 렌더링]**을 1.5초 내 자동 완결.
* **업무 리드타임 99.2% 단축**: 180초 → 1.5초로 단축하여 실무진의 단순 반복 업무를 제거하고 고부가가치 세무 자문 업무 집중 환경 조성.

---

## ⚙️ 2. System Architecture & Data Flow (시스템 구조)

```text
┌────────────────────────────────────────────────────────────────────────┐
│                        [Omni-Channel Inflow]                           │
│   - Chat Input: Representative Name & Phone Number                     │
│   - Multimodal Input: Business Registration Certificate Image (OCR)    │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│                   [Data Extraction & Preprocessing]                    │
│   - Gemini 2.0 Flash Vision API: Zero-shot JSON Document Parsing       │
│   - Pandas Fast-Lookup Engine: TA Database Matching & Validation       │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│                  [Real-Time Tax Sync & Rule Engine]                    │
│   - NTS Public Data API (data.go.kr / nts-businessman/v1/status)       │
│   - Tax Rule Grounding: 부가가치세법 제36조 & 제67조 적용              │
│     * 일반과세자: 7월 제1기 확정신고 대상 / 세금계산서 발급            │
│     * 세금계산서 발급 간이: 조건부 대상 (상반기 발급 시 7월 신고)     │
│     * 영수증 전용 간이: 7월 신고 대상 제외 (내년 1월 정기신고)        │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│               [Dual-Delivery AI Sandbox Dashboard]                     │
│                                                                        │
│   [Left] Client Messenger UI            [Right] Back-office Dashboard  │
│   - KakaoTalk Style Chatbot             - Real-time Metadata Card      │
│   - Gemini Grounded Tax Response        - 1-Click Clipboard Copy       │
│   - Live Response Latency Meter         - AX Business Impact KPIs      │
└────────────────────────────────────────────────────────────────────────┘
