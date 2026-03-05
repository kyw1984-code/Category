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
# 1. 쿠팡 API 서명 생성 및 데이터 호출 함수
# ---------------------------------------------------------
def generate_hmac(method, url, secret_key, access_key):
    """
    쿠팡 파트너스 API 호출을 위한 HMAC 서명 생성 (UTC 시간 적용)
    """
    # [수정됨] 한국 시간이 아닌 UTC(표준시) 기준으로 서명 생성해야 400/401 에러가 안 납니다.
    now_utc = datetime.now(timezone.utc)
    date_gmt = now_utc.strftime('%y%m%d')
    time_gmt = now_utc.strftime('%H%M%S')
    
    dateTime = date_gmt + 'T' + time_gmt + 'Z'
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
    
    # URL 인코딩
    query_string = urlencode(params)
    full_url = f"{URL}?{query_string}"
    
    # 헤더 생성 (키 앞뒤 공백 제거 적용)
    authorization = generate_hmac("GET", full_url, secret_key.strip(), access_key.strip())
    headers = {
        "Authorization": authorization,
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3"
    }
    
    try:
        response = requests.get(DOMAIN + full_url, headers=headers)
        
        # [수정됨] 400 에러 발생 시 구체적인 이유를 알기 위해 예외 처리 강화
        if response.status_code != 200:
            return {"error": f"상태 코드: {response.status_code}", "detail": response.text}
            
        return response.json()
    except Exception as e:
        return {"error": "통신 오류", "detail": str(e)}

# ---------------------------------------------------------
# 2. 엑셀 다운로드 처리 함수
# ---------------------------------------------------------
def to_excel(df):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Sheet1')
        workbook = writer.book
        worksheet = writer.sheets['Sheet1']
        worksheet.set_column('B:B', 40) # 상품명
        worksheet.set_column('E:E', 50) # 링크
    
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
    
    # Secrets에서 키 로드 시도
    api_access_key = st.secrets.get("COUPANG_ACCESS_KEY", "")
    api_secret_key = st.secrets.get("COUPANG_SECRET_KEY", "")

    # Secrets에 없으면 입력창 표시
    if not api_access_key:
        api_access_key = st.sidebar.text_input("Access Key", type="password")
    if not api_secret_key:
        api_secret_key = st.sidebar.text_input("Secret Key", type="password")

    st.sidebar.markdown("---")
    st.sidebar.header("📂 검색 옵션")

    # 주요 카테고리 ID 매핑
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
                
                data_list = []
                for idx, item in enumerate(items):
                    data_list.append({
                        "순위": idx + 1,
                        "상품명": item.get('productName', ''),
                        "가격": item.get('productPrice', 0),
                        "로켓배송": "O" if item.get('isRocket', False) else "X",
                        "상품URL": item.get('productUrl', ''),
                        "이미지URL": item.get('productImage', '')
                    })
                
                df = pd.DataFrame(data_list)

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

                excel_file = to_excel(df)
                file_name = f"쿠팡베스트_{selected_cat_name}_{time.strftime('%Y%m%d')}.xlsx"
                
                st.download_button(
                    label="📥 엑셀 다운로드",
                    data=excel_file,
                    file_name=file_name,
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )

            elif result and 'error' in result:
                # [수정됨] 에러 상세 메시지 출력
                st.error(f"⚠️ API 호출 실패: {result['error']}")
                st.code(result.get('detail'), language="json")
                st.info("💡 팁: 'code': 'BAD_REQUEST'가 나오면 카테고리 ID가 잘못되었거나, 키 값 앞뒤에 공백이 없는지 확인하세요.")
            
            else:
                st.error("데이터를 가져올 수 없습니다. API 키를 확인해주세요.")

if __name__ == "__main__":
    main()
