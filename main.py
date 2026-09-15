import streamlit as st
import pandas as pd
import requests
from datetime import datetime, timedelta
import zoneinfo

# -------------------------------------------------------------------
# 페이지 기본 설정
# -------------------------------------------------------------------
st.set_page_config(
    page_title="어제 박스오피스 순위",
    page_icon="🎬",
    layout="wide"
)

st.title("🎬 어제 일별 박스오피스 순위")

# -------------------------------------------------------------------
# 1. secrets에서 API 키 가져오기
# -------------------------------------------------------------------
if "KOBIS_KEY" not in st.secrets:
    st.error("💡 Streamlit Secrets에 'KOBIS_KEY'가 설정되어 있지 않습니다.")
    st.info("Streamlit Cloud 설정(Secrets)에서 KOBIS_KEY = '발급받은키' 형태로 등록했는지 확인해 주세요.")
    st.stop()

api_key = st.secrets["KOBIS_KEY"]

# -------------------------------------------------------------------
# 2. 한국 시간(KST) 기준 '어제' 날짜 계산하기
# -------------------------------------------------------------------
# 배포 서버는 해외 시각(UTC)일 수 있으므로 Asia/Seoul 타임존을 명시합니다.
kst_zone = zoneinfo.ZoneInfo("Asia/Seoul")
now_kst = datetime.now(kst_zone)
yesterday = now_kst - timedelta(days=1)
target_date = yesterday.strftime("%Y%m%d")  # YYYYMMDD 포맷 생성
formatted_date = yesterday.strftime("%Y년 %m월 %d일")

st.caption(f"📅 기준일자: **{formatted_date}** (한국 시간 기준 어제)")

# -------------------------------------------------------------------
# 3. KOBIS API 데이터 요청하기
# -------------------------------------------------------------------
url = "https://www.kobis.or.kr/kobisopenapi/webservice/rest/boxoffice/searchDailyBoxOfficeList.json"
params = {
    "key": api_key,
    "targetDt": target_date
}

try:
    response = requests.get(url, params=params, timeout=10)
    response.raise_for_status()
    data = response.json()
except requests.exceptions.RequestException as e:
    st.error("⚠️ 영화진흥위원회 API 통신 중 연결 오류가 발생했습니다.")
    st.info("인터넷 연결 상태나 요청 주소가 올바른지 확인해 주세요.")
    st.stop()

# -------------------------------------------------------------------
# 4. API 예외 및 에러 처리 (KOBIS 응답 검증)
# -------------------------------------------------------------------
# KOBIS는 키가 틀려도 200 OK를 반환하고 'faultInfo'라는 키를 보냅니다.
if "faultInfo" in data:
    st.error("⚠️ KOBIS API 인증 오류가 발생했습니다.")
    st.warning(f"오류 메시지: {data['faultInfo'].get('message', '알 수 없는 오류')}")
    st.info("👉 Streamlit Secrets에 입력한 'KOBIS_KEY' 값이 정확한지 다시 확인해 주세요.")
    st.stop()

box_office_result = data.get("boxOfficeResult", {})
daily_list = box_office_result.get("dailyBoxOfficeList", [])

# 검색 결과 목록이 비어있는 경우
if not daily_list:
    st.warning("⚠️ 어제 일자 박스오피스 데이터가 존재하지 않거나 집계 중입니다.")
    st.info("API 서버 집계가 아직 완료되지 않았을 수 있으니 잠시 후 다시 시도해 주세요.")
    st.stop()

# -------------------------------------------------------------------
# 5. 데이터 전처리 (문자열 -> 숫자 변환)
# -------------------------------------------------------------------
df = pd.DataFrame(daily_list)

# KOBIS API는 모든 숫자를 문자열로 돌려주므로 숫자형으로 변환합니다.
numeric_columns = ["rank", "audiCnt", "audiAcc", "scrnCnt"]
for col in numeric_columns:
    df[col] = pd.to_numeric(df[col], errors="coerce")

# -------------------------------------------------------------------
# 6. 1위 영화 지표 카드 표시 (Metric Cards)
# -------------------------------------------------------------------
top_movie = df.iloc[0]

st.markdown("### 🏆 어제 박스오피스 1위")
st.subheader(top_movie["movieNm"])

col1, col2, col3 = st.columns(3)
with col1:
    st.metric(
        label="일일 관객수",
        value=f"{top_movie['audiCnt']:,} 명"
    )
with col2:
    st.metric(
        label="누적 관객수",
        value=f"{top_movie['audiAcc']:,} 명"
    )
with col3:
    st.metric(
        label="스크린수",
        value=f"{top_movie['scrnCnt']:,} 개"
    )

st.divider()

# -------------------------------------------------------------------
# 7. 관객수 상위 5편 막대그래프
# -------------------------------------------------------------------
st.markdown("### 📊 관객수 상위 5개 영화")

df_top5 = df.head(5).copy()
# 시각화 시 가독성을 위해 차트용 수치 칼럼 지정
st.bar_chart(
    data=df_top5,
    x="movieNm",
    y="audiCnt",
    use_container_width=True
)

st.divider()

# -------------------------------------------------------------------
# 8. 전체 박스오피스 순위 표 (Table)
# -------------------------------------------------------------------
st.markdown("### 📋 전체 박스오피스 순위 (1~10위)")

# 출력할 컬럼 선택 및 이름 변경
display_df = df[["rank", "movieNm", "openDt", "audiCnt", "audiAcc", "scrnCnt"]].copy()
display_df.columns = ["순위", "영화명", "개봉일", "관객수", "누적관객", "스크린수"]

# 표 형태로 출력 (숫자 콤마 포맷팅 포함)
st.dataframe(
    display_df,
    hide_index=True,
    use_container_width=True,
    column_config={
        "순위": st.column_config.NumberColumn("순위", format="%d위"),
        "관객수": st.column_config.NumberColumn("관객수", format="%d명"),
        "누적관객": st.column_config.NumberColumn("누적관객", format="%d명"),
        "스크린수": st.column_config.NumberColumn("스크린수", format="%d개")
    }
)
