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
# 1. 쿠팡 GET 요청 전용 서명 생성 (최종 교정)
# ---------------------------------------------------------
def generate_hmac(method, path, query, secret_key, access_key):
    """
    쿠팡 공식 문서의 GET 방식 서명 생성 규칙을 따릅니다.
    """
    # 시간 포맷: 240523T123456Z
    now_utc = datetime.now(timezone.utc)
    datetime_gmt = now_utc.strftime('%y%m%d') + 'T' + now_utc.strftime('%H%M%S') + 'Z'
    
    # [핵심] GET 방식은 path 뒤에 반드시 query 스트링이 붙어야 합니다.
    # 메시지 조합: {datetime}{method}{path}{query}
    message = datetime_gmt + method + path + query

    signature = hmac.new(bytes(secret_key, "utf-8"),
                         message.encode("utf-8"),
                         hashlib.sha256).hexdigest()

    return f"CEA algorithm=HmacSHA256, access-key={access_key}, signed-date={datetime_gmt}, signature={signature}"

# ---------------------------------------------------------
# 2. 데이터 호출 함수
# ---------------------------------------------------------
def get_best_products(access_key, secret_key, category_id, limit=20):
    DOMAIN = "https://api-gateway.coupang.com"
    PATH = "/v2/providers/affiliate_sdp/pa/products/ranking"
    
    # 쿼리 스트링 생성 (categoryId=1001&limit=20 형태)
    params = {"categoryId": category_id, "limit": limit}
    query_string = urlencode(params)
    
    # 서명 생성 시 파라미터 전달
    authorization = generate_hmac("GET", PATH, query_string, secret_key, access_key)
    
    headers = {
        "Authorization": authorization,
        "Content-Type": "application/json"
    }
    
    try:
        # 최종 URL 조립
        full_url = f"{DOMAIN}{PATH}?{query_string}"
        response = requests.get(full_url, headers=headers)
        
        if response.status_code == 200:
            return response.json()
        else:
            # 에러 발생 시 상세 내용을 반환하여 디버깅 용이하게 설정
            return {
                "error": True, 
                "status": response.status_code, 
                "msg": response.text
            }
    except Exception as e:
        return {"error": True, "msg": str(e)}

# ---------------------------------------------------------
# 3. Streamlit 앱 인터페이스
# ---------------------------------------------------------
def to_excel(df):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Sheet1')
    return output.getvalue()

def main():
    st.set_page_config(page_title="쿠팡 랭킹 추출기", layout="wide")
    st.title("🛍️ 쿠팡 파트너스 베스트 상품 추출")

    # [보안] Secrets에서 키 로드
    try:
        # .strip()을 통해 보이지 않는 공백 제거
        ACCESS_KEY = st.secrets["COUPANG_ACCESS_KEY"].strip()
        SECRET_KEY = st.secrets["COUPANG_SECRET_KEY"].strip()
    except Exception:
        st.error("🚨 Streamlit Secrets에서 API 키를 찾을 수 없습니다.")
        st.stop()

    categories = {
        "여성패션": 1001, "남성패션": 1002, "뷰티": 1010, "출산/유아동": 1011,
        "식품": 1012, "주방용품": 1013, "생활용품": 1014, "가전디지털": 1016,
        "스포츠/레저": 1017, "반려동물": 1022, "헬스/건강": 1023
    }

    selected_cat = st.sidebar.selectbox("카테고리 선택", list(categories.keys()))
    limit_count = st.sidebar.slider("추출 개수", 10, 50, 20)

    if st.sidebar.button("데이터 가져오기"):
        with st.spinner("데이터를 불러오는 중입니다..."):
            res = get_best_products(ACCESS_KEY, SECRET_KEY, categories[selected_cat], limit_count)

            if "data" in res:
                # 데이터 변환
                items = res['data']
                df = pd.DataFrame([{
                    "순위": i + 1,
                    "상품명": item.get('productName'),
                    "가격": item.get('productPrice'),
                    "로켓배송": "🚀" if item.get('isRocket') else "X",
                    "상품링크": item.get('productUrl')
                } for i, item in enumerate(items)])

                st.success(f"✅ {selected_cat} 베스트 상품 {len(df)}개를 가져왔습니다!")
                st.dataframe(df, use_container_width=True, hide_index=True)
                
                st.download_button(
                    "📥 엑셀 파일로 저장", 
                    to_excel(df), 
                    f"쿠팡_{selected_cat}_베스트.xlsx",
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
            else:
                # 에러 상세 정보 표시
                st.error("❌ API 호출에 실패했습니다.")
                st.json(res)
                st.info("💡 계속 UNKNOWN_ERROR가 발생한다면, API 키 발급 직후인지 확인하시고 약 1시간 뒤에 다시 시도해 보세요.")

if __name__ == "__main__":
    main()
