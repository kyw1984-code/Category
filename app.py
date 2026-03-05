import streamlit as st
import hmac
import hashlib
import requests
import json
from datetime import datetime, timezone
import pandas as pd
import io
from urllib.parse import urlencode
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# =========================================================
# 0) 공통: 세션(재시도) 구성
# =========================================================
def build_session():
    session = requests.Session()
    retry = Retry(
        total=3,
        backoff_factor=0.6,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET"],
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session

SESSION = build_session()

# =========================================================
# 1) 쿠팡 파트너스 HMAC 서명 생성
#    - signed-date: YYMMDDTHHMMSSZ (UTC)
#    - message: signed-date + method + path + query
# =========================================================
def build_signed_date():
    return datetime.now(timezone.utc).strftime("%y%m%dT%H%M%SZ")

def generate_authorization(method: str, path: str, query: str, secret_key: str, access_key: str):
    signed_date = build_signed_date()
    message = f"{signed_date}{method}{path}{query}"  # 매우 중요: query는 '?' 없이 순수 'a=b&c=d'

    signature = hmac.new(
        secret_key.encode("utf-8"),
        message.encode("utf-8"),
        hashlib.sha256
    ).hexdigest()

    authorization = (
        f"CEA algorithm=HmacSHA256, access-key={access_key}, "
        f"signed-date={signed_date}, signature={signature}"
    )
    return authorization, signed_date, message

# =========================================================
# 2) 안전한 Query String 생성
#    - 쿠팡은 query를 서명에 포함하므로 "항상 동일한 방식"으로 만들어야 함
#    - 정렬된 dict -> urlencode (doseq=False)
# =========================================================
def make_query(params: dict) -> str:
    # key 정렬(일관성)
    sorted_items = sorted(params.items(), key=lambda x: x[0])
    return urlencode(sorted_items)

# =========================================================
# 3) API 호출
# =========================================================
def coupang_get_ranking(access_key: str, secret_key: str, category_id: int, limit: int, debug: bool = False):
    DOMAIN = "https://api-gateway.coupang.com"
    PATH = "/v2/providers/affiliate_sdp/pa/products/ranking"

    params = {"categoryId": category_id, "limit": limit}
    query = make_query(params)

    authorization, signed_date, message = generate_authorization(
        method="GET",
        path=PATH,
        query=query,
        secret_key=secret_key,
        access_key=access_key
    )

    url = f"{DOMAIN}{PATH}?{query}"
    headers = {
        "Authorization": authorization,
        "Content-Type": "application/json;charset=UTF-8",
        "x-requested-with": "openapi",
    }

    if debug:
        st.subheader("🔧 Debug")
        st.write("URL:", url)
        st.write("signed-date:", signed_date)
        st.write("message length:", len(message))
        st.write("access key length:", len(access_key))
        st.write("secret key length:", len(secret_key))
        # Authorization 전체 노출은 위험 → 앞/뒤만
        st.write("Authorization (masked):", authorization[:45] + "..." + authorization[-12:])

    try:
        resp = SESSION.get(url, headers=headers, timeout=15)

        # JSON 파싱 시도
        try:
            payload = resp.json()
        except Exception:
            payload = {"raw_text": resp.text}

        if resp.status_code == 200:
            return {"ok": True, "status": resp.status_code, "payload": payload}

        # 실패 시 원문과 함께 반환
        return {
            "ok": False,
            "status": resp.status_code,
            "payload": payload,
            "raw_text": resp.text,
        }

    except requests.exceptions.Timeout:
        return {"ok": False, "status": None, "payload": {"message": "Timeout"}}
    except Exception as e:
        return {"ok": False, "status": None, "payload": {"message": str(e)}}

# =========================================================
# 4) 엑셀 변환
# =========================================================
def to_excel_bytes(df: pd.DataFrame) -> bytes:
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        df.to_excel(writer, index=False, sheet_name="ranking")
    return output.getvalue()

# =========================================================
# 5) Streamlit UI
# =========================================================
def main():
    st.set_page_config(page_title="쿠팡 파트너스 랭킹 추출", layout="wide")
    st.title("🛍️ 쿠팡 파트너스 베스트(랭킹) 상품 추출 - 안정 버전")

    # Secrets 확인
    if "COUPANG_ACCESS_KEY" not in st.secrets or "COUPANG_SECRET_KEY" not in st.secrets:
        st.error("🚨 Streamlit Secrets에 COUPANG_ACCESS_KEY / COUPANG_SECRET_KEY 를 등록해 주세요.")
        st.stop()

    ACCESS_KEY = st.secrets["COUPANG_ACCESS_KEY"].strip()
    SECRET_KEY = st.secrets["COUPANG_SECRET_KEY"].strip()

    categories = {
        "여성패션": 1001, "남성패션": 1002, "뷰티": 1010, "식품": 1012,
        "주방용품": 1013, "생활용품": 1014, "가전디지털": 1016, "스포츠/레저": 1017,
        "완구/취미": 1018, "반려동물용품": 1019, "도서/음반/DVD": 1020
    }

    st.sidebar.header("옵션")
    selected_cat = st.sidebar.selectbox("카테고리", list(categories.keys()))
    limit_count = st.sidebar.slider("추출 개수", 10, 50, 20)
    debug = st.sidebar.checkbox("디버그 표시(권장)", value=True)

    st.sidebar.markdown("---")
    st.sidebar.caption("⚠️ Provider id 오류가 계속이면: (1) OpenAPI 승인/활성화 상태 (2) 키 발급 후 24시간 (3) Streamlit Cloud IP 이슈를 먼저 확인하세요.")

    if st.sidebar.button("데이터 가져오기"):
        with st.spinner("쿠팡 API 호출 중..."):
            result = coupang_get_ranking(
                access_key=ACCESS_KEY,
                secret_key=SECRET_KEY,
                category_id=categories[selected_cat],
                limit=limit_count,
                debug=debug
            )

        if result["ok"]:
            payload = result["payload"]
            # 응답 구조: {"data": [...]} 형태 기대
            data_list = payload.get("data", [])
            if not data_list:
                st.warning("가져온 데이터가 없습니다. (data가 비어있음)")
                st.json(payload)
                return

            df = pd.DataFrame([{
                "순위": i + 1,
                "상품명": item.get("productName"),
                "가격": item.get("productPrice"),
                "로켓배송": "🚀" if item.get("isRocket") else "일반",
                "상품링크": item.get("productUrl"),
            } for i, item in enumerate(data_list)])

            st.success(f"✅ {selected_cat} 랭킹 {len(df)}개 가져오기 성공")
            st.dataframe(df, use_container_width=True)

            excel_bytes = to_excel_bytes(df)
            st.download_button(
                label="📥 엑셀 다운로드",
                data=excel_bytes,
                file_name=f"coupang_ranking_{selected_cat}_{datetime.now().strftime('%Y%m%d')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

        else:
            st.error("❌ 호출 실패")
            st.write("HTTP Status:", result["status"])
            st.subheader("응답(JSON 파싱 결과)")
            st.json(result["payload"])
            st.subheader("원문(raw)")
            st.code(result.get("raw_text", ""), language="json")

            # 특히 Provider id 에러 가이드
            payload = result["payload"] if isinstance(result["payload"], dict) else {}
            msg = ""
            if isinstance(payload, dict):
                msg = payload.get("message") or payload.get("error") or ""

            if "Provider id" in (msg or "") or "Provider id" in (result.get("raw_text") or ""):
                st.info(
                    "💡 Provider id 오류 체크리스트\n"
                    "- 쿠팡 파트너스 OpenAPI가 '승인/활성화' 상태인지\n"
                    "- 키 발급 후 24시간이 지났는지\n"
                    "- 발급한 키가 '파트너스' 키가 맞는지(셀러 API 키 아님)\n"
                    "- Streamlit Cloud 환경(IP가 자주 바뀜)에서 간헐적으로 차단/오탐이 날 수 있음"
                )

if __name__ == "__main__":
    main()
