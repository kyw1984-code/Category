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
# 1. 쿠팡 API 서명 생성 및 데이터 호출 함수
# ---------------------------------------------------------
def generate_hmac(method, url, secret_key, access_key):
    """
    쿠팡 파트너스 API 호출을 위한 HMAC 서명 생성
    """
    dateTime = time.strftime('%y%m%d') + 'T' + time.strftime('%H%M%S') + 'Z'
    message = method + url + dateTime + access_key
    
    signature = hmac.new(bytes(secret_key, 'utf-8'),
                         message.encode('utf-8'),
                         hashlib.sha256).hexdigest()
    
    return f"CEA algorithm=HmacSHA256, access-key={access_key}, signed-date={dateTime}, signature={signature}"

def get_best_products(access_key, secret_key, category_id, limit=20):
    """
    쿠팡 파트너스 API를 통해 카테고리별 베스트 상품 조회
    """
    DOMAIN = "https://api-gateway.coupang.com"
    URL = "/v2/providers/affiliate_sdp/pa/products/ranking"
    
    # API 요청 파라미터
    params = {
        "categoryId": category_id,
        "limit": limit
    }
    
    # URL 인코딩 및 전체 URL 생성
    query_string = urlencode(params)
    full_url = f"{URL}?{query_string}"
    
    # 헤더 생성
    authorization = generate_hmac("GET", full_url, secret_key, access_key)
    headers = {
        "Authorization": authorization,
        "Content-Type": "application/json"
    }
    
    try:
        response = requests.get(DOMAIN + full_url, headers=headers)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        return {"error": str(e)}

# ---------------------------------------------------------
# 2. 엑셀 다운로드 처리 함수
# ---------------------------------------------------------
def to_excel(df):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Sheet1')
        workbook = writer.book
        worksheet = writer.sheets['Sheet1']
        # 컬럼 너비 조정 (선택사항)
        worksheet.set_column('B:B', 40) # 상품명 컬럼 넓게
        worksheet.set_column('D:D', 50) # URL 컬럼 넓게
    
    processed_data = output.getvalue()
    return processed_data

# ---------------------------------------------------------
# 3. Streamlit UI 구성
# ---------------------------------------------------------
def main():
    st.set_page_config(page_title="쿠팡 베스트 상품 크롤러", layout="wide")

    st.title("🛍️ 쿠팡 카테고리별 베스트 상품 추출기")
    st.markdown("쿠팡 파트너스 API를 활용하여 판매량 순위가 높은 제품 리스트를 추출하고 엑셀로 저장합니다.")

    # 사이드바: 설정 영역
    st.sidebar.header("🔑 API 설정")
    
    # Streamlit Secrets에서 키를 우선 로드하고, 없으면 입력창 사용
    api_access_key = st.sidebar.text_input("Access Key", type="password")
    api_secret_key = st.sidebar.text_input("Secret Key", type="password")

    st.sidebar.markdown("---")
    st.sidebar.header("📂 검색 옵션")

    # 주요 카테고리 ID 매핑 (필요에 따라 추가/수정 가능)
    categories = {
        "여성패션": 1001,
        "남성패션": 1002,
        "뷰티": 1010,
        "출산/유아동": 1011,
        "식품": 1012,
        "주방용품": 1013,
        "생활용품": 1014,
        "홈인테리어": 1015,
        "가전디지털": 1016,
        "스포츠/레저": 1017,
        "자동차용품": 1018,
        "도서/음반/DVD": 1019,
        "완구/취미": 1020,
        "문구/오피스": 1021,
        "반려동물용품": 1022,
        "헬스/건강식품": 1023
    }

    selected_cat_name = st.sidebar.selectbox("카테고리 선택", list(categories.keys()))
    limit_count = st.sidebar.slider("추출 개수", min_value=10, max_value=50, value=20)

    # 메인 로직 실행
    if st.sidebar.button("데이터 가져오기"):
        if not api_access_key or not api_secret_key:
            st.warning("API Access Key와 Secret Key를 입력해주세요.")
            return

        with st.spinner(f"쿠팡에서 [{selected_cat_name}] 베스트 상품을 가져오는 중..."):
            cat_id = categories[selected_cat_name]
            result = get_best_products(api_access_key, api_secret_key, cat_id, limit_count)

            if result and 'data' in result:
                items = result['data']
                
                # 데이터 가공
                data_list = []
                for idx, item in enumerate(items):
                    data_list.append({
                        "순위": idx + 1,
                        "상품명": item.get('productName', ''),
                        "가격": item.get('productPrice', 0),
                        "로켓배송": "O" if item.get('isRocket', False) else "X",
                        "상품URL": item.get('productUrl', ''),
                        "이미지URL": item.get('productImage', '')
                        # *참고: API 버전에 따라 리뷰수는 제공되지 않을 수 있습니다.
                    })
                
                df = pd.DataFrame(data_list)

                # 1. 화면 출력 (이미지와 링크 포맷팅)
                st.subheader(f"📊 검색 결과: {len(df)}개")
                st.dataframe(
                    df,
                    column_config={
                        "이미지URL": st.column_config.ImageColumn("이미지"),
                        "상품URL": st.column_config.LinkColumn("링크"),
                        "가격": st.column_config.NumberColumn("가격", format="%d원")
                    },
                    use_container_width=True,
                    hide_index=True
                )

                # 2. 엑셀 다운로드 버튼
                excel_file = to_excel(df)
                file_name = f"쿠팡베스트_{selected_cat_name}_{time.strftime('%Y%m%d')}.xlsx"
                
                st.download_button(
                    label="📥 엑셀 다운로드",
                    data=excel_file,
                    file_name=file_name,
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )

            elif result and 'error' in result:
                st.error(f"API 오류 발생: {result['error']}")
            else:
                st.error("데이터를 가져올 수 없습니다. API 키를 확인하거나 잠시 후 다시 시도해주세요.")

if __name__ == "__main__":
    main()
