import streamlit as st
import hmac
import hashlib
import requests
import json
import time
from datetime import datetime, timezone
import pandas as pd
import io
from urllib.parse import quote

# ---------------------------------------------------------
# 1. 쿠팡 API 서명 생성 함수
# ---------------------------------------------------------
def generate_hmac(method, url, secret_key, access_key):
    # UTC 시간 생성 (쿠팡 서버 기준)
    now_utc = datetime.now(timezone.utc)
    date_gmt = now_utc.strftime('%y%m%d')
    time_gmt = now_utc.strftime('%H%M%S')
    dateTime = date_gmt + 'T' + time_gmt + 'Z'
    
    # 서명 메시지 생성
    message = method + url + dateTime + access_key
    
    signature = hmac.new(bytes(secret_key, 'utf-8'),
                         message.encode('utf-8'),
                         hashlib.sha256).hexdigest()
    
    return f"CEA algorithm=HmacSHA256, access-key={access_key}, signed-date={dateTime}, signature={signature}"

# ---------------------------------------------------------
# 2. 데이터 호출 함수
# ---------------------------------------------------------
def get_best_products(access_key, secret_key, category_id, limit=20):
    DOMAIN = "https://api-gateway.coupang.com"
    # URL 경로와 쿼리 파라미터를 정확히 조립
    PATH = "/v2/providers/affiliate_sdp/pa/products/ranking"
    QUERY = f"?categoryId={category_id}&limit={limit}"
    FULL_URL = PATH + QUERY
    
    # 공백 제거
    ak = access_key.strip()
    sk = secret_key.strip()
    
    authorization = generate_hmac("GET", FULL_URL, sk, ak)
    
    headers = {
        "Authorization": authorization,
        "Content-Type": "application/json"
    }
    
    try:
        response = requests.get(DOMAIN + FULL_URL, headers=headers)
        
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
        worksheet.set_column('B:B', 40) # 상품명
        worksheet.set_column('E:E', 50) # URL
    return output.getvalue()

# ---------------------------------------------------------
# 4. 메인 UI
# ---------------------------------------------------------
def main():
    st.set_page_config(page_title="쿠팡 소싱 리스트", layout="wide")

    st.title("🛍️ 쿠팡 파트너스 베스트 상품 추출")
    st.info("반드시 '쿠팡 윙(판매자)' 키가 아닌 **'쿠팡 파트너스' API 키**를 사용해야 합니다.")

    # 사이드바 설정
    st.sidebar.header("🔑 파트너스 API 키")
    
    # Secrets 우선 로드
    ak = st.secrets.get("COUPANG_ACCESS_KEY", "")
    sk = st.secrets.get("COUPANG_SECRET_KEY", "")

    if not ak:
        ak = st.sidebar.text_input("Access Key", type="password")
    if not sk:
        sk = st.sidebar.text_input("Secret Key", type="password")

    st.sidebar.markdown("---")
    
    # 카테고리 목록
    categories = {
        "여성패션": 1001, "남성패션": 1002, "뷰티": 1010, 
        "출산/유아동": 1011, "식품": 1012, "주방용품": 1013, 
        "생활용품": 1014, "홈인테리어": 1015, "가전디지털": 1016, 
        "스포츠/레저": 1017, "자동차용품": 1018, "반려동물": 1022, 
        "헬스/건강": 1023
    }

    cat_name = st.sidebar.selectbox("카테고리", list(categories.keys()))
    limit = st.sidebar.slider("개수", 10, 50, 20)

    if st.sidebar.button("가져오기"):
        if not ak or not sk:
            st.warning("API 키를 입력해주세요.")
            return

        with st.spinner("데이터 요청 중..."):
            res = get_best_products(ak, sk, categories[cat_name], limit)

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
                
                st.success(f"{len(df)}개 상품을 찾았습니다!")
                
                # 테이블 출력
                st.dataframe(
                    df,
                    column_config={
                        "이미지URL": st.column_config.ImageColumn("이미지"),
                        "상품URL": st.column_config.LinkColumn("링크"),
                        "가격": st.column_config.NumberColumn("가격", format="%d원")
                    },
                    hide_index=True
                )
                
                # 엑셀 다운로드
                st.download_button(
                    "📥 엑셀 다운로드",
                    to_excel(df),
                    f"쿠팡_{cat_name}.xlsx"
                )

            elif "error" in res:
                st.error("API 호출 실패")
                st.json(res)
                if "Provider id is not specified correctly" in str(res):
                    st.error("🚨 **원인 발견:** '쿠팡 파트너스' 키가 아닌 다른 키(예: 윙 판매자 키)를 넣으신 것 같습니다. 파트너스 홈페이지에서 키를 다시 확인해주세요.")

if __name__ == "__main__":
    main()
