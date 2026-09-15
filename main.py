요청하신 기능을 모두 반영하여 수정한 main.py 전체 코드입니다.

수정된 main.py
Python
import streamlit as st
import pandas as pd
import requests
from datetime import datetime, timedelta
import zoneinfo

# -------------------------------------------------------------------
# 페이지 기본 설정
# -------------------------------------------------------------------
st.set_page_config(
    page_title="일별 박스오피스 조회",
    page_icon="🎬",
    layout="wide"
)

st.title("🎬 일별 박스오피스 순위 조회")

# -------------------------------------------------------------------
# 1. secrets에서 API 키 가져오기
# -------------------------------------------------------------------
if "KOBIS_KEY" not in st.secrets:
    st.error("💡 Streamlit Secrets에 'KOBIS_KEY'가 설정되어 있지 않습니다.")
    st.info("Streamlit Cloud 설정(Secrets)에서 KOBIS_KEY = '발급받은키' 형태로 등록했는지 확인해 주세요.")
    st.stop()

api_key = st.secrets["KOBIS_KEY"]

# -------------------------------------------------------------------
# 2. 날짜 선택기 (KST 기준, 최대 어제 날짜까지 허용)
# -------------------------------------------------------------------
# 배포 서버 시각 대신 한국 시간(Asia/Seoul)을 기준으로 기준일을 잡습니다.
kst_zone = zoneinfo.ZoneInfo("Asia/Seoul")
today_kst = datetime.now(kst_zone).date()
max_date = today_kst - timedelta(days=1)  # 오늘 건 집계 전이므로 어제가 선택 가능한 최댓값

# 사이드바에서 날짜를 선택하도록 입력창 배치
selected_date = st.sidebar.date_input(
    label="📅 조회할 날짜 선택",
    value=max_date,
    max_value=max_date
)

target_date = selected_date.strftime("%Y%m%d")  # API 전달용 여덟 자리 문자열 (YYYYMMDD)
formatted_date = selected_date.strftime("%Y년 %m월 %d일")

st.caption(f"📅 **조회 날짜:** {formatted_date}")

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
except requests.exceptions.RequestException:
    st.error("⚠️ 영화진흥위원회 API 통신 중 연결 오류가 발생했습니다.")
    st.info("인터넷 연결 상태나 요청 주소가 올바른지 확인해 주세요.")
    st.stop()

# -------------------------------------------------------------------
# 4. API 예외 및 에러 처리 (KOBIS 응답 검증)
# -------------------------------------------------------------------
# KOBIS는 키가 틀려도 200 OK를 반환하고 'faultInfo' 키를 보냅니다.
if "faultInfo" in data:
    st.error("⚠️ KOBIS API 인증 오류가 발생했습니다.")
    st.warning(f"오류 메시지: {data['faultInfo'].get('message', '알 수 없는 오류')}")
    st.info("👉 Streamlit Secrets에 입력한 'KOBIS_KEY' 값이 정확한지 다시 확인해 주세요.")
    st.stop()

box_office_result = data.get("boxOfficeResult", {})
daily_list = box_office_result.get("dailyBoxOfficeList", [])

# 선택한 날짜의 데이터 목록이 비어있는 경우
if not daily_list:
    st.warning("⚠️ 그날은 아직 집계 전입니다.")
    st.info("선택하신 날짜의 박스오피스 데이터가 아직 준비되지 않았거나 제공되지 않습니다. 다른 날짜를 선택해 주세요.")
    st.stop()

# -------------------------------------------------------------------
# 5. 데이터 전처리
# -------------------------------------------------------------------
df = pd.DataFrame(daily_list)

# API 응답값이 모두 문자열이므로 계산/비교를 위해 숫자형으로 변환합니다.
numeric_columns = ["rank", "rankInten", "audiCnt", "audiAcc", "scrnCnt"]
for col in numeric_columns:
    df[col] = pd.to_numeric(df[col], errors="coerce")

# 5-1. 순위 증감(rankInten)에 따라 화살표 포맷팅
def format_rank_change(change):
    if change > 0:
        return f"🔺 {change}"   # 순위 상승 (빨간 위 화살표)
    elif change < 0:
        return f"🔹 {abs(change)}" # 순위 하강 (파란 아래 화살표)
    else:
        return "-"              # 변동 없음

df["순위변동"] = df["rankInten"].apply(format_rank_change)

# 5-2. 누적 관객 수 100만 명 이상 영화 이름 옆에 🏆 이모지 추가
def format_movie_title(row):
    title = row["movieNm"]
    if row["audiAcc"] >= 1_000_000:
        return f"🏆 {title}"
    return title

df["영화명_디스플레이"] = df.apply(format_movie_title, axis=1)

# -------------------------------------------------------------------
# 6. 1위 영화 지표 카드 표시 (Metric Cards)
# -------------------------------------------------------------------
top_movie = df.iloc[0]

st.markdown("### 🏆 해당 일자 박스오피스 1위")
st.subheader(top_movie["영화명_디스플레이"])

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

# 출력용 데이터프레임 구성
display_df = df[[
    "rank", 
    "순위변동", 
    "영화명_디스플레이", 
    "openDt", 
    "audiCnt", 
    "audiAcc", 
    "scrnCnt"
]].copy()

display_df.columns = ["순위", "변동", "영화명", "개봉일", "관객수", "누적관객", "스크린수"]

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
