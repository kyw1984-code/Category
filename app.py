import streamlit as st
import hmac
import hashlib
import requests
import json
import time
from datetime import datetime, timezone
import pandas as pd
import io
from urllib.parse import urlencode

# ---------------------------------------------------------
# 1. 쿠팡 공식 가이드 기반 HMAC 서명 생성 함수 (수정됨)
# ---------------------------------------------------------
def generate_hmac(method, url, secret_key, access_key):
    """
    쿠팡 공식 문서 로직 적용:
    Message = datetimeGMT + method + path + (query if exists)
    """
    # URL에서 경로(path)와 쿼리(query) 분리
    parts = url.split("?")
    path = parts[0]
    query = parts[1] if len(parts) > 1 else ""

    # UTC 시간 생성 (공식 코드 포맷: YYMMDDThhmmssZ)
    now_utc = datetime.now(timezone.utc)
    datetimeGMT = now_utc.strftime('%y%m%d') + 'T' + now_utc.strftime('%H%M%S') + 'Z'

    # [핵심 변경] 공식 가이드 순서대로 조합
    message = datetimeGMT + method + path + query

    # 서명 생성
    signature = hmac.new(bytes(secret_key, "utf-8"),
                         message.encode("utf-8"),
                         hashlib.sha256).hexdigest()

    return f"CEA algorithm=HmacSHA256, access-key={access_key}, signed-date={datetimeGMT}, signature={signature}"

# ---------------------------------------------------------
# 2. 데이터 호출 함수
# ---------------------------------------------------------
def get_best_products(access_key, secret_key, category_id, limit=20):
    DOMAIN = "https://api-gateway.coupang.com"
    PATH = "/v2/providers/affiliate_sdp/pa/products/ranking"
    
    # 쿼리 스트링 수동 생성 (서명과 요청의 일치를 위해)
    params = {
        "categoryId": category_id,
        "limit": limit
    }
    query_string = urlencode(params)
    
    # 전체 URL 조립 (Path + Query)
    full_url = f"{PATH}?{query_string}"
    
    # 공식 로직으로 헤더 생성
    authorization = generate_hmac("GET", full_url, secret_key, access_key)
    
    headers = {
        "Authorization": authorization,
        "Content-Type": "application/json"
    }
    
    try:
        # requests 호출 시 전체 URL 사용
        response = requests.get(DOMAIN + full_url, headers=headers)
        
        if response.status_code == 200:
            return response.json()
        else:
            return {
                "error": True, 
                "status": response.status_code, 
                "msg": response.text
            }
    except Exception as e:
        return {"error": True, "msg": str(e)}

# ---------------------------------------------------------
# 3. 엑셀 변환 함수
# ---------------------------------------------------------
def to_excel(df):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Sheet1')
        worksheet = writer.sheets['Sheet1']
        worksheet.set_column('B:B', 40) # 상품명 넓게
        worksheet.set_column('E:E', 50) # URL 넓게
    return output.getvalue()

# ---------------------------------------------------------
# 4. 메인 UI
# ---------------------------------------------------------
def main():
    st.set_page_config(page_title="쿠팡 소싱 리스트", layout="wide")

    st.title("🛍️ 쿠팡 파트너스 베스트 상품 추출")
    
    # Secrets 로드
    try:
        ACCESS_KEY = st.secrets["COUPANG_ACCESS_KEY"].strip()
        SECRET_KEY = st.secrets["COUPANG_SECRET_KEY"].strip()
    except (FileNotFoundError, KeyError):
        st.error("🚨 API 키가 설정되지 않았습니다.")
        st.info("Streamlit Cloud의 'Secrets' 설정에 COUPANG_ACCESS_KEY와 COUPANG_SECRET_KEY를 등록해주세요.")
        st.stop()

    st.sidebar.header("📂 검색 옵션")
    
    categories = {
        "여성패션": 1001, "남성패션": 1002, "뷰티": 1010, 
        "출산/유아동": 1011, "식품": 1012, "주방용품": 1013, 
        "생활용품": 1014, "홈인테리어": 1015, "가전디지털": 1016, 
        "스포츠/레저": 1017, "자동차용품": 1018, "반려동물": 1022, 
        "헬스/건강": 1023
    }

    cat_name = st.sidebar.selectbox("카테고리", list(categories.keys()))
    limit = st.sidebar.slider("개수", 10, 50, 20)

    if st.sidebar.button("데이터 가져오기"):
        with st.spinner("데이터 요청 중..."):
            res = get_best_products(ACCESS_KEY, SECRET_KEY, categories[cat_name], limit)

            if "data" in res:
                items = res['data']
                rows = []
                for idx, item in enumerate(items):
                    rows.append({
                        "순위": idx + 1,
                        "상품명": item.get('productName'),
                        "가격": item.get('productPrice'),
                        "로켓": "🚀" if item.get('isRocket') else "",
                        "상품URL": item.get('productUrl'),
                        "이미지URL": item.get('productImage')
                    })
                
                df = pd.DataFrame(rows)
                st.success(f"✅ {len(df)}개 상품 로드 완료")
                
                st.dataframe(
                    df,
                    column_config={
                        "이미지URL": st.column_config.ImageColumn("이미지"),
                        "상품URL": st.column_config.LinkColumn("링크"),
                        "가격": st.column_config.NumberColumn("가격", format="%d원")
                    },
                    hide_index=True
                )
                
                st.download_button(
                    "📥 엑셀 다운로드",
                    to_excel(df),
                    f"쿠팡_{cat_name}.xlsx"
                )

            elif "error" in res:
                st.error("API 호출 실패")
                st.code(res['msg'], language='json')
                if "Provider id is not specified correctly" in str(res):
                     st.warning("⚠️ '쿠팡 윙' 키가 아닌 '파트너스' 키인지 다시 확인해주세요.")

if __name__ == "__main__":
    main()
