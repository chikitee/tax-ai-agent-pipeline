import pandas as pd
import requests
import json
import time
import os

# ==========================================
# 0. 국세청 공공데이터 API 설정
# ==========================================
# 공공데이터포털에서 발급받은 Decoding 서비스 키
SERVICE_KEY = "YOUR_PUBLIC_DATA_API_SERVICE_KEY" 
API_URL = f"https://api.odcloud.kr/api/nts-businessman/v1/status?serviceKey={SERVICE_KEY}"

def check_nts_status_batch(biz_no_list):
    """
    국세청 진단 API를 10개씩 배치 호출하여 사업자 상태 및 과세유형 반환
    """
    cleaned_nos = [str(b).replace("-", "").strip() for b in biz_no_list]
    payload = {"b_no": cleaned_nos}
    headers = {'Content-Type': 'application/json'}
    
    try:
        response = requests.post(API_URL, data=json.dumps(payload), headers=headers, timeout=10)
        if response.status_code == 200:
            res_data = response.json()
            return res_data.get("data", [])
    except Exception as e:
        print(f"⚠️ 국세청 API 호출 중 오류 발생: {e}")
    return []

# ==========================================
# 1. DB 정제 & 폐업자 필터링 엔진
# ==========================================
def create_closed_free_db(input_excel="DB.xlsx", output_excel="DB_balanced.xlsx"):
    if not os.path.exists(input_excel):
        print(f"❌ '{input_excel}' 파일이 원본 폴더에 존재하지 않습니다.")
        return

    print("🔄 원본 DB.xlsx 로드 중...")
    df_raw = pd.read_excel(input_excel)
    
    if '사업자번호' not in df_raw.columns:
        print("❌ '사업자번호' 컬럼을 찾을 수 없습니다.")
        return

    df_raw['biz_clean'] = df_raw['사업자번호'].astype(str).str.replace("-", "").str.strip()
    biz_numbers = df_raw['biz_clean'].tolist()
    
    clean_records = []
    batch_size = 10
    total_len = len(biz_numbers)
    
    print(f"🔍 총 {total_len}건의 데이터에 대해 국세청 실시간 검증 시작 (폐업자 완전 제거 중)...")

    for i in range(0, total_len, batch_size):
        batch_keys = biz_numbers[i:i+batch_size]
        results = check_nts_status_batch(batch_keys)
        
        for idx, res in enumerate(results):
            row_idx = i + idx
            if row_idx < len(df_raw):
                row = df_raw.iloc[row_idx].to_dict()
                b_stt = res.get("b_stt", "")       # 계속사업자, 휴업자, 폐업자
                tax_type = res.get("tax_type", "") # 부가가치세 일반과세자, 간이과세자 등
                
                # 핵심 기준: 폐업자/휴업자 100% 제외 -> '계속사업자'만 수집
                if b_stt == "계속사업자":
                    row['국세청_상태'] = b_stt
                    row['국세청_과세유형'] = tax_type
                    
                    if "간이" in tax_type:
                        row['과세유형_구분'] = "간이과세자"
                    elif "일반" in tax_type:
                        row['과세유형_구분'] = "일반과세자"
                    else:
                        row['과세유형_구분'] = "기타과세자"
                        
                    clean_records.append(row)
                    
        print(f" 진행률: {min(i+batch_size, total_len)}/{total_len} 건 검증 완료")
        time.sleep(0.15)

    df_clean = pd.DataFrame(clean_records)
    
    print("\n" + "="*50)
    print(f"✅ 폐업자 필터링 완료! (살아있는 계속사업자: {len(df_clean)}건)")
    
    # 2. 과세유형 비율 확인 및 저장
    df_gani = df_clean[df_clean['과세유형_구분'] == '간이과세자']
    df_ilban = df_clean[df_clean['과세유형_구분'] == '일반과세자']
    
    print(f"📊 추출 결과 -> 간이과세자: {len(df_gani)}건 | 일반과세자: {len(df_ilban)}건")
    
    # 최종 엑셀 파일 저장
    df_clean.to_excel(output_excel, index=False)
    print(f"🎉 폐업자가 0건인 정제된 DB가 '{output_excel}' 로 새로 생성되었습니다!")
    print("="*50)

if __name__ == "__main__":
    create_closed_free_db("DB.xlsx", "DB_balanced.xlsx")