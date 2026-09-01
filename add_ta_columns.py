import pandas as pd
import random
import os

# 1. DB_balanced.xlsx 로드
target_file = "DB_balanced.xlsx" if os.path.exists("DB_balanced.xlsx") else "DB.xlsx"
df = pd.read_excel(target_file)

# 2. TA 표준 업종 샘플 데이터
industries = [
    "소프트웨어 개발 및 공급업 (722000)",
    "한식 음식점업 (552001)",
    "전자상거래 소매업 (525101)",
    "커피 전문점 (552009)",
    "의류 소매업 (523111)",
    "경영 컨설팅업 (741400)",
    "통신판매업 (525102)",
    "기타 도소매업 (519099)"
]

def generate_random_date():
    year = random.randint(2018, 2024)
    month = random.randint(1, 12)
    day = random.randint(1, 28)
    return f"{year}-{month:02d}-{day:02d}"

# 3. 개업일자 및 업종(업종코드) 컬럼 자동 보완
if '개업일자' not in df.columns:
    df['개업일자'] = [generate_random_date() for _ in range(len(df))]

if '업종(업종코드)' not in df.columns:
    df['업종(업종코드)'] = [random.choice(industries) for _ in range(len(df))]

# 4. DB_balanced.xlsx 저장
df.to_excel("DB_balanced.xlsx", index=False)
print("🎉 DB_balanced.xlsx 에 개업일자 및 업종(업종코드) 컬럼 추가 완료!")