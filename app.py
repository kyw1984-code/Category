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
# 1. 쿠팡 최적화 HMAC 서명 생성
# ---------------------------------------------------------
def generate_hmac(method, path, query, secret_key, access_key):
    # 쿠팡 서버가 요구하는 정확한 UTC 시간 포맷: YYMMDDTHHMMSSZ
    now_utc = datetime.now(timezone.utc)
    datetime_gmt = now_utc.strftime('%y%m%dT%H%M%SZ')
    
    # [중요] 메시지 조합: datetime + method + path + query
    message = f"{datetime_gmt}{method}{path}{query}"

    signature = hmac.new(
        secret_key.encode("utf-8"),
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
    
    params = {"categoryId": category_id, "limit": limit}
    query_string = urlencode(params)
    
    authorization = generate_hmac("GET", PATH, query_string, secret_key, access_key)
    
    headers = {
        "Authorization": authorization,
        "Content-Type": "application/json;charset=UTF-8",
        "x-requested-with": "openapi" 
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
# 3. 메인 UI 및 로직
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
        st.error("🚨 Streamlit Cloud 설정(Secrets)에 키를 등록해 주세요.")
        st.stop()

    # ⭐ [핵심 수정] 따옴표와 공백을 모두 강제로 제거합니다.
    # .strip() 은 양쪽 공백 제거 / .strip('"') 은 양쪽 큰따옴표 제거 / .strip("'") 은 양쪽 작은따옴표 제거
    ACCESS_KEY = st.secrets["COUPANG_ACCESS_KEY"].strip().strip('"').strip("'")
    SECRET_KEY = st.secrets["COUPANG_SECRET_KEY"].strip().strip('"').strip("'")

    categories = {
        "여성패션": 1001, "남성패션": 1002, "뷰티": 1010, "식품": 1012, 
        "주방용품": 1013, "생활용품": 1014, "가전디지털": 1016, "스포츠/레저": 1017,
        "완구/취미": 1018, "반려동물용품": 1019, "도서/음반/DVD": 1020
    }

    st.sidebar.header("추출 옵션")
    selected_cat = st.sidebar.selectbox("카테고리 선택", list(categories.keys()))
    limit_count = st.sidebar.slider("추출 개수", 10, 50, 20)

    if st.sidebar.button("데이터 가져오기"):
        with st.spinner("쿠팡 API 호출 중..."):
            res = get_best_products(ACCESS_KEY, SECRET_KEY, categories[selected_cat], limit_count)

            if isinstance(res, dict) and "data" in res:
                data_list = res['data']
                if not data_list:
                    st.warning("가져온 데이터가 없습니다.")
                    return

                df = pd.DataFrame([{
                    "순위": i + 1,
                    "상품명": item.get('productName'),
                    "가격": item.get('productPrice'),
                    "로켓배송": "🚀" if item.get('isRocket') else "일반",
                    "상품링크": item.get('productUrl')
                } for i, item in enumerate(data_list)])

                st.success(f"✅ {selected_cat} 데이터를 성공적으로 가져왔습니다!")
                st.dataframe(df, use_container_width=True)
                
                excel_data = to_excel(df)
                st.download_button(
                    label="📥 엑셀 파일 다운로드",
                    data=excel_data,
                    file_name=f"쿠팡_랭킹_{selected_cat}_{datetime.now().strftime('%Y%m%d')}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
            else:
                st.error("❌ 호출 실패")
                st.json(res) 
                st.info("💡 키를 수정한 직후에도 이 에러가 난다면, 쿠팡 시스템에 키가 등록될 때까지 시간이 더 필요할 수 있습니다.")

if __name__ == "__main__":
    main()
