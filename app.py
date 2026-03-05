import streamlit as st
import hmac
import hashlib
import requests
import json
from datetime import datetime, timezone
import pandas as pd
import io
from urllib.parse import urlencode

# ---------------------------------------------------------
# 1. 쿠팡 최적화 HMAC 서명 생성 (정석 버전)
# ---------------------------------------------------------
def generate_hmac(method, path, query, secret_key, access_key):
    # 쿠팡 서버가 요구하는 UTC 시간 포맷
    now_utc = datetime.now(timezone.utc)
    datetime_gmt = now_utc.strftime('%y%m%d') + 'T' + now_utc.strftime('%H%M%S') + 'Z'
    
    # [중요] 메시지 조합 순서: datetime + method + path + query
    # 앞뒤 공백이나 줄바꿈이 절대 들어가면 안 됩니다.
    message = f"{datetime_gmt}{method}{path}{query}"

    signature = hmac.new(
        bytes(secret_key, "utf-8"),
        message.encode("utf-8"),
        hashlib.sha256
    ).hexdigest()

    return f"CEA algorithm=HmacSHA256, access-key={access_key}, signed-date={datetime_gmt}, signature={signature}"

# ---------------------------------------------------------
# 2. 데이터 호출 함수
# ---------------------------------------------------------
def get_best_products(access_key, secret_key, category_id, limit=20):
    DOMAIN = "https://api-gateway.coupang.com"
    PATH = "/v2/providers/affiliate_sdp/pa/products/ranking"
    
    # 쿼리 스트링 생성
    params = {"categoryId": category_id, "limit": limit}
    query_string = urlencode(params)
    
    # 헤더 생성
    authorization = generate_hmac("GET", PATH, query_string, secret_key, access_key)
    
    headers = {
        "Authorization": authorization,
        "Content-Type": "application/json;charset=UTF-8"
    }
    
    try:
        full_url = f"{DOMAIN}{PATH}?{query_string}"
        response = requests.get(full_url, headers=headers, timeout=10)
        
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
# 3. 메인 UI (보안 설정 포함)
# ---------------------------------------------------------
def to_excel(df):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False)
    return output.getvalue()

def main():
    st.set_page_config(page_title="쿠팡 랭킹 추출", layout="wide")
    st.title("🛍️ 쿠팡 파트너스 베스트 상품 추출")

    # [보안 점검] Secrets 로드
    if "COUPANG_ACCESS_KEY" not in st.secrets or "COUPANG_SECRET_KEY" not in st.secrets:
        st.error("🚨 Streamlit Cloud 설정(Secrets)에 키가 등록되지 않았습니다.")
        st.stop()

    # 키에서 혹시 모를 공백이나 특수문자 제거
    ACCESS_KEY = st.secrets["COUPANG_ACCESS_KEY"].strip().replace('"', '').replace("'", "")
    SECRET_KEY = st.secrets["COUPANG_SECRET_KEY"].strip().replace('"', '').replace("'", "")

    categories = {
        "여성패션": 1001, "남성패션": 1002, "뷰티": 1010, "식품": 1012, 
        "주방용품": 1013, "생활용품": 1014, "가전디지털": 1016, "스포츠/레저": 1017
    }

    selected_cat = st.sidebar.selectbox("카테고리", list(categories.keys()))
    limit_count = st.sidebar.slider("추출 개수", 10, 50, 20)

    if st.sidebar.button("데이터 가져오기"):
        with st.spinner("쿠팡 데이터를 확인 중..."):
            res = get_best_products(ACCESS_KEY, SECRET_KEY, categories[selected_cat], limit_count)

            if "data" in res:
                df = pd.DataFrame([{
                    "순위": i + 1,
                    "상품명": item.get('productName'),
                    "가격": item.get('productPrice'),
                    "로켓": "🚀" if item.get('isRocket') else "",
                    "링크": item.get('productUrl')
                } for i, item in enumerate(res['data'])])

                st.success("✅ 데이터를 성공적으로 가져왔습니다!")
                st.dataframe(df, use_container_width=True)
                st.download_button("📥 엑셀 다운로드", to_excel(df), f"쿠팡_{selected_cat}.xlsx")
            else:
                st.error("❌ 호출 실패")
                st.json(res)
                st.info("💡 만약 키가 확실하다면, 쿠팡 파트너스 API 페이지에서 'Access Key'를 새로 발급(재발급)받아 교체해 보시는 것을 권장합니다.")

if __name__ == "__main__":
    main()
