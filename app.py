import streamlit as st
import hmac
import hashlib
import requests
import json
import time
import pandas as pd
import io
from urllib.parse import urlencode

# ---------------------------------------------------------
# 1. 쿠팡 API 설정 및 HMAC 서명 생성 함수
# ---------------------------------------------------------
def generate_hmac_signature(method, url, secret_key, access_key):
    # 쿠팡 API 요구사항에 맞춘 서명 생성
    date_gmt = time.strftime('%y%m%d')
    time_gmt = time.strftime('%H%M%S')
    
    message = method + url + date_gmt + 'T' + time_gmt + 'Z' + access_key
    signature = hmac.new(bytes(secret_key, 'utf-8'),
                         message.encode('utf-8'),
                         hashlib.sha256).hexdigest()
    
    return f"CEA algorithm=HmacSHA256, access-key={access_key}, signed-date={date_gmt}T{time_gmt}Z, signature={signature}"

def get_coupang_best_products(access_key, secret_key, category_id, limit=20):
    # 쿠팡 파트너스 API: 골드박스/베스트 상품 조회 엔드포인트 예시
    # (실제 사용하는 API 엔드포인트에 따라 URL을 수정해야 할 수 있습니다. 여기선 예시로 구성합니다)
    DOMAIN = "https://api-gateway.coupang.com"
    URL = f"/v2/providers/affiliate_sdp/pa/products/ranking" # 랭킹 API 경로
    
    # 쿼리 파라미터 (카테고리 ID 및 개수)
    params = {
        "categoryId": category_id,
        "limit": limit
    }
    query_string = urlencode(params)
    FULL_URL = f"{URL}?{query_string}"
    
    authorization = generate_hmac_signature("GET", FULL_URL, secret_key, access_key)
    
    headers = {
        "Authorization": authorization,
        "Content-Type": "application/json"
    }
    
    try:
        response = requests.get(DOMAIN + FULL_URL, headers=headers)
        response.raise_for_status() # 에러 발생 시 예외 처리
        return response.json()
    except requests.exceptions.RequestException as e:
        st.error(f"API 호출 중 오류 발생: {e}")
        return None

# ---------------------------------------------------------
# 2. 엑셀 다운로드 처리 함수
# ---------------------------------------------------------
def to_excel(df):
    output = io.BytesIO()
    # 엑셀 writer 생성 (xlsxwriter 엔진 사용)
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Sheet1')
    processed_data = output.getvalue()
    return processed_data

# ---------------------------------------------------------
# 3. Streamlit UI 구성
# ---------------------------------------------------------
st.set_page_config(page_title="쿠팡 소싱 리스트 추출기", layout="wide")

st.title("🛍️ 쿠팡 베스트 상품 리스트 추출기")
st.markdown("카테고리를 선택하면 판매 랭킹순으로 상품 정보를 가져옵니다.")

# 사이드바: API 키 입력 (보안을 위해 입력받거나 st.secrets 사용 권장)
st.sidebar.header("API 설정")
access_key = st.sidebar.text_input("Access Key", type="password")
secret_key = st.sidebar.text_input("Secret Key", type="password")

st.sidebar.info("※ 쿠팡 파트너스 API Key가 필요합니다.")

# 메인: 카테고리 선택
# (주요 카테고리 ID 예시 - 실제 필요한 ID를 추가하세요)
categories = {
    "여성패션": 1001,
    "남성패션": 1002,
    "가전디지털": 1010,
    "출산/유아동": 1013,
    "식품": 1018,
    "주방용품": 1019,
    "생활용품": 1015,
    "뷰티": 1016
}

selected_category_name = st.selectbox("카테고리 선택", list(categories.keys()))
selected_category_id = categories[selected_category_name]
limit_count = st.slider("가져올 상품 수", 10, 50, 20)

# 실행 버튼
if st.button("상품 리스트 가져오기"):
    if not access_key or not secret_key:
        st.warning("사이드바에 API Key를 먼저 입력해주세요.")
    else:
        with st.spinner("쿠팡에서 데이터를 가져오는 중입니다..."):
            data = get_coupang_best_products(access_key, secret_key, selected_category_id, limit_count)
            
            if data and 'data' in data:
                # 데이터 프레임 변환
                product_list = []
                for item in data['data']:
                    product_list.append({
                        "순위": item.get('rank', 'N/A'), # API 응답에 따라 키값 조정 필요
                        "상품명": item.get('productName', ''),
                        "가격": item.get('productPrice', 0),
                        "상품URL": item.get('productUrl', ''),
                        "이미지": item.get('productImage', ''), # 대표 이미지 URL
                        "로켓배송": "🚀" if item.get('isRocket', False) else ""
                    })
                
                df = pd.DataFrame(product_list)
                
                # 화면 출력용 데이터프레임 (이미지 컬럼 설정)
                st.subheader(f"📊 {selected_category_name} 베스트 상품 ({len(df)}개)")
                
                st.dataframe(
                    df,
                    column_config={
                        "이미지": st.column_config.ImageColumn(
                            "상품 이미지", help="상품 대표 이미지"
                        ),
                        "상품URL": st.column_config.LinkColumn(
                            "링크", help="클릭 시 쿠팡 이동"
                        ),
                        "가격": st.column_config.NumberColumn(
                            "판매가", format="%d원"
                        )
                    },
                    use_container_width=True,
                    hide_index=True
                )
                
                # 엑셀 다운로드 버튼
                excel_data = to_excel(df)
                st.download_button(
                    label="📥 엑셀 파일로 다운로드",
                    data=excel_data,
                    file_name=f"쿠팡_{selected_category_name}_베스트_{time.strftime('%Y%m%d')}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
                
            else:
                st.error("데이터를 가져오지 못했습니다. API 키나 호출 횟수 제한을 확인해주세요.")