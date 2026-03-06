import streamlit as st
import hmac
import hashlib
from time import gmtime, strftime
import requests
from datetime import datetime
import pandas as pd
import io
import urllib.parse
import random
import time


# ---------------------------------------------------------
# 쿠팡 카테고리 구조 (대 > 중 > 소)
# ---------------------------------------------------------
CATEGORY_TREE = {
    "패션의류/잡화": {
        "여성패션": ["여성 니트", "여성 원피스", "여성 바지", "여성 재킷", "여성 코트", "여성 티셔츠"],
        "남성패션": ["남성 티셔츠", "남성 바지", "남성 자켓", "남성 코트", "남성 니트"],
        "스포츠웨어": ["레깅스", "트레이닝복", "스포츠 브라", "러닝화"],
        "가방/지갑": ["여성가방", "남성가방", "백팩", "크로스백", "지갑"],
        "신발": ["운동화", "구두", "샌들", "부츠", "슬리퍼"],
        "액세서리": ["목걸이", "귀걸이", "반지", "팔찌", "시계"],
    },
    "뷰티": {
        "스킨케어": ["토너", "세럼", "크림", "선크림", "에센스"],
        "메이크업": ["파운데이션", "립스틱", "아이섀도", "마스카라", "쿠션"],
        "헤어케어": ["샴푸", "트리트먼트", "헤어에센스", "헤어드라이어"],
        "바디케어": ["바디로션", "바디워시", "핸드크림", "향수"],
        "남성그루밍": ["남성 스킨", "면도기", "남성 샴푸"],
    },
    "식품": {
        "건강식품": ["홍삼", "비타민", "프로바이오틱스", "오메가3", "콜라겐"],
        "신선식품": ["과일", "채소", "계란", "육류", "수산물"],
        "가공식품": ["라면", "통조림", "즉석밥", "과자", "음료"],
        "커피/차": ["원두커피", "캡슐커피", "녹차", "허브티"],
        "유제품/아이스크림": ["우유", "요거트", "치즈", "아이스크림"],
    },
    "주방/생활/건강": {
        "주방용품": ["프라이팬", "냄비", "칼", "도마", "그릇"],
        "생활용품": ["휴지", "물티슈", "세제", "청소용품", "방향제"],
        "욕실용품": ["치약", "칫솔", "샤워기", "욕실청소"],
        "건강용품": ["혈압계", "체온계", "마사지기", "안마의자"],
        "반려동물": ["강아지사료", "고양이사료", "반려동물간식", "강아지패드"],
    },
    "가전/디지털": {
        "생활가전": ["에어프라이어", "전기밥솥", "청소기", "공기청정기", "가습기"],
        "영상/음향": ["TV", "블루투스스피커", "이어폰", "헤드폰"],
        "컴퓨터/주변기기": ["노트북", "마우스", "키보드", "모니터", "웹캠"],
        "스마트폰/태블릿": ["스마트폰케이스", "보조배터리", "충전기", "태블릿"],
        "카메라": ["디지털카메라", "카메라가방", "삼각대", "짐벌"],
    },
    "스포츠/레저": {
        "운동기구": ["덤벨", "요가매트", "폼롤러", "홈트레이닝", "줄넘기"],
        "아웃도어": ["등산화", "텐트", "등산스틱", "배낭", "침낭"],
        "구기스포츠": ["축구공", "농구공", "배드민턴", "탁구"],
        "수영/워터스포츠": ["수영복", "물안경", "서핑보드"],
        "자전거/킥보드": ["자전거", "전동킥보드", "헬멧", "자전거용품"],
    },
    "완구/육아": {
        "유아동완구": ["블록장난감", "인형", "보드게임", "레고"],
        "유아용품": ["기저귀", "분유", "유모차", "아기띠"],
        "아동의류": ["아동 티셔츠", "아동 바지", "아동 신발"],
        "임산부용품": ["임산부 의류", "임산부 영양제", "수유브라"],
    },
    "도서/취미": {
        "도서": ["자기계발", "소설", "경제경영", "육아도서", "요리책"],
        "음반/DVD": ["K팝 앨범", "영화 DVD"],
        "문구/오피스": ["볼펜", "노트", "다이어리", "포스트잇"],
        "DIY/원예": ["화분", "식물", "원예도구", "DIY키트"],
    },
}

# ---------------------------------------------------------
# 랜덤 User-Agent 목록 (시크릿 모드 효과)
# ---------------------------------------------------------
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/119.0.0.0 Safari/537.36",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 Mobile Safari/604.1",
]


# ---------------------------------------------------------
# HMAC 서명 생성
# ---------------------------------------------------------
def generate_hmac(method, url, secret_key, access_key):
    path, *query = url.split("?")
    datetime_gmt = strftime('%y%m%d', gmtime()) + 'T' + strftime('%H%M%S', gmtime()) + 'Z'
    message = datetime_gmt + method + path + (query[0] if query else "")
    signature = hmac.new(
        bytes(secret_key, "utf-8"),
        message.encode("utf-8"),
        hashlib.sha256
    ).hexdigest()
    return f"CEA algorithm=HmacSHA256, access-key={access_key}, signed-date={datetime_gmt}, signature={signature}"


# ---------------------------------------------------------
# 쿠팡 파트너스 상품 검색 (시크릿 모드 + 중복 제거)
# ---------------------------------------------------------
def search_products(access_key, secret_key, keyword, limit=10):
    DOMAIN = "https://api-gateway.coupang.com"
    encoded_keyword = urllib.parse.quote(keyword)

    # 캐시 방지: 타임스탬프를 파라미터로 추가
    timestamp = int(time.time() * 1000)
    URL = f"/v2/providers/affiliate_open_api/apis/openapi/products/search?keyword={encoded_keyword}&limit={limit}&_t={timestamp}"

    authorization = generate_hmac("GET", URL, secret_key, access_key)

    headers = {
        "Authorization": authorization,
        "Content-Type": "application/json;charset=UTF-8",
        # 랜덤 User-Agent로 시크릿 모드 효과
        "User-Agent": random.choice(USER_AGENTS),
        "Cache-Control": "no-cache, no-store, must-revalidate",
        "Pragma": "no-cache",
        "Expires": "0",
    }

    try:
        # requests.Session() 새로 생성 → 쿠키/세션 초기화 효과
        session = requests.Session()
        session.cookies.clear()
        response = session.get(f"{DOMAIN}{URL}", headers=headers, timeout=10)

        if response.status_code == 200:
            data = response.json()
            products = data.get("data", {}).get("productData", [])

            # ── 중복 제거: productId 기준 ──
            seen_ids = set()
            seen_names = set()
            unique_products = []
            for item in products:
                pid = str(item.get("productId", ""))
                pname = item.get("productName", "").strip()

                # ID 중복 또는 상품명 완전 동일한 경우 제거
                if pid and pid in seen_ids:
                    continue
                if pname and pname in seen_names:
                    continue

                seen_ids.add(pid)
                seen_names.add(pname)
                unique_products.append(item)

            return {"success": True, "products": unique_products}
        else:
            return {"success": False, "error": f"HTTP {response.status_code}", "msg": response.text}
    except Exception as e:
        return {"success": False, "error": str(e)}


# ---------------------------------------------------------
# 엑셀 변환
# ---------------------------------------------------------
def to_excel(df):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False)
    return output.getvalue()


# ---------------------------------------------------------
# 메인 앱
# ---------------------------------------------------------
def main():
    st.set_page_config(page_title="쿠팡 카테고리 순위", layout="wide")
    st.title("🏆 쿠팡 카테고리별 인기상품 순위")
    st.caption("🔒 시크릿 모드 적용 | 중복 상품 자동 제거")

    missing = []
    if "COUPANG_ACCESS_KEY" not in st.secrets: missing.append("COUPANG_ACCESS_KEY")
    if "COUPANG_SECRET_KEY" not in st.secrets: missing.append("COUPANG_SECRET_KEY")
    if missing:
        st.error(f"🚨 Streamlit Secrets에 다음 키를 등록해 주세요: {', '.join(missing)}")
        st.stop()

    ACCESS_KEY = st.secrets["COUPANG_ACCESS_KEY"].strip().strip('"').strip("'")
    SECRET_KEY = st.secrets["COUPANG_SECRET_KEY"].strip().strip('"').strip("'")

    # ── 사이드바: 카테고리 선택 ──
    st.sidebar.header("📂 카테고리 선택")

    big_cat = st.sidebar.selectbox("🔹 대카테고리", list(CATEGORY_TREE.keys()))
    mid_cats = list(CATEGORY_TREE[big_cat].keys())
    mid_cat = st.sidebar.selectbox("🔸 중카테고리", mid_cats)
    small_cats = CATEGORY_TREE[big_cat][mid_cat]
    selected_small = st.sidebar.selectbox("🔺 소카테고리", small_cats)
    limit_count = st.sidebar.slider("추출 상품 수", 1, 10, 10)

    st.sidebar.divider()
    st.sidebar.markdown("""
    **🔒 시크릿 모드란?**
    - 매 요청마다 새 세션 생성
    - 랜덤 브라우저로 위장
    - 캐시 완전 비활성화
    - 쿠키 초기화
    """)

    # 선택 경로 표시
    st.markdown(f"### 📌 `{big_cat}` > `{mid_cat}` > `{selected_small}`")
    st.divider()

    if st.sidebar.button("🏆 순위 조회", type="primary", use_container_width=True):
        with st.spinner(f"🔒 시크릿 모드로 '{selected_small}' 순위 조회 중..."):
            result = search_products(ACCESS_KEY, SECRET_KEY, selected_small, limit_count)

        if result["success"]:
            products = result["products"]

            if not products:
                st.warning("검색 결과가 없습니다. 다른 소카테고리를 선택해보세요.")
                return

            # 순위 오름차순 정렬
            products_sorted = sorted(
                products,
                key=lambda x: int(x.get("rank", 999)) if x.get("rank") else 999
            )

            total = len(products_sorted)
            st.success(f"✅ **{big_cat} > {mid_cat} > {selected_small}** 인기상품 {total}개 (중복 제거 완료)")

            # TOP3 카드
            if total >= 3:
                st.markdown("#### 🥇🥈🥉 TOP 3")
                col1, col2, col3 = st.columns(3)
                medals = ["🥇", "🥈", "🥉"]
                cols_ui = [col1, col2, col3]
                for i in range(min(3, total)):
                    item = products_sorted[i]
                    name = item.get("productName", "-")
                    price = item.get("productPrice", "-")
                    rocket = "🚀 로켓" if item.get("isRocket") else "일반배송"
                    link = item.get("productUrl", "")
                    with cols_ui[i]:
                        st.markdown(f"""
                        <div style='background:#f8f9fa;padding:14px;border-radius:10px;
                                    border:1px solid #dee2e6;min-height:130px'>
                            <div style='font-size:24px'>{medals[i]}</div>
                            <div style='font-size:13px;font-weight:600;margin:6px 0'>
                                {name[:45]}{'...' if len(name)>45 else ''}
                            </div>
                            <div style='color:#e63946;font-weight:700'>
                                {f"{int(price):,}원" if str(price).isdigit() else f"{price}원"}
                            </div>
                            <div style='font-size:12px;color:#888;margin-top:4px'>{rocket}</div>
                        </div>
                        """, unsafe_allow_html=True)
                        if link:
                            st.markdown(f"[🔗 상품 보기]({link})")
                st.divider()

            # 전체 순위표
            st.markdown("#### 📋 전체 순위표")
            df = pd.DataFrame([{
                "순위": idx + 1,
                "상품명": item.get("productName", "-"),
                "가격(원)": f"{int(item.get('productPrice', 0)):,}" if str(item.get("productPrice","")).isdigit() else "-",
                "로켓배송": "🚀" if item.get("isRocket") else "일반",
                "무료배송": "✅" if item.get("isFreeShipping") else "❌",
                "상품ID": str(item.get("productId", "-")),
                "상품링크": item.get("productUrl", ""),
            } for idx, item in enumerate(products_sorted)])

            st.dataframe(df, use_container_width=True, hide_index=True)

            # 엑셀 다운로드
            excel_data = to_excel(df)
            st.download_button(
                label="📥 순위표 엑셀 다운로드",
                data=excel_data,
                file_name=f"쿠팡_{big_cat}_{mid_cat}_{selected_small}_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

        else:
            st.error(f"❌ 조회 실패: {result.get('error')}")
            with st.expander("상세 오류 보기"):
                st.write(result.get("msg", ""))
            st.info("⚠️ 쿠팡 파트너스 API는 시간당 최대 10회 호출 가능합니다.")


main()
