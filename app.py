import streamlit as st
import pandas as pd
import yfinance as yf
import json
import pyperclip
import plotly.express as px
import io
import os
from datetime import date

st.set_page_config(page_title="📊 포트폴리오 트래커", layout="wide")
st.title("📈 종목 수익률 계산기")

# 세션 상태 초기화
if "stocks" not in st.session_state:
    st.session_state.stocks = []

st.subheader("📝 종목 추가")

with st.form("stock_form"):
    col1, col2, col3 = st.columns([2, 1, 1])
    
    with col1:
        symbol = st.text_input("종목코드 (예: AAPL, TSLA)").upper()
    with col2:
        quantity = st.number_input("수량", min_value=1, step=1)
    with col3:
        avg_price = st.number_input("매수단가 ($)", min_value=0.01, step=0.01, format="%.2f")
    
    submitted = st.form_submit_button("추가하기")
    
    if submitted:
        try:
            stock = yf.Ticker(symbol)
            current_price = stock.history(period="1d")["Close"].iloc[-1]
            profit = (current_price - avg_price) * quantity
            profit_rate = (profit / (avg_price * quantity)) * 100
            
            st.session_state.stocks.append({
                "종목": symbol,
                "수량": quantity,
                "매수단가": avg_price,
                "현재가": round(current_price, 2),
                "수익": round(profit, 2),
                "수익률(%)": round(profit_rate, 2)
            })
            st.success(f"{symbol} 추가 완료!")
        except Exception as e:
            st.error(f"현재가를 불러오는 데 실패했습니다: {e}")

# 포트폴리오 테이블
if st.session_state.stocks:
    st.subheader("📋 현재 포트폴리오")
    df = pd.DataFrame(st.session_state.stocks)
    st.dataframe(df, use_container_width=True)

    total_profit = df["수익"].sum()
    st.markdown(f"### 💰 총 수익: ${total_profit:,.2f}")

st.markdown("---")
st.subheader("💡 종목 추천 문장 자동 생성")

cash_input = st.number_input("보유 현금 ($)", min_value=0.0, step=100.0, format="%.2f")

if st.button("✍️ 추천 요청 문장 생성"):
    try:
        holdings = st.session_state.stocks
        if not holdings:
            st.warning("먼저 종목을 추가해주세요.")
        else:
            text = f"현재 포트폴리오 구성은 다음과 같아:\n"
            text += f"- 보유 현금: ${cash_input:,.2f}\n"
            for stock in holdings:
                text += f"- {stock['종목']}: {stock['수량']}주 (매수단가 ${stock['매수단가']}, 현재가 ${stock['현재가']})\n"
            
            text += """
이 포트폴리오와 현금을 바탕으로,
1) 오늘 기준으로 가장 안정적인 1~4주 보유 스윙 종목 1개
2) 1주일 이내 급등 가능성이 높은 고위험 단기 종목 1개
를 각각 추천해줘.

그리고 다음 정보를 반드시 포함해줘:
- 추천 매수가 / 손절가 / 익절가 / 예상 보유 기간
- 상승 확률 (%) / 추천 점수 (100점 만점)
- 선정 이유: 기술 분석 / 뉴스 / 수급 흐름

📌 아래 리밸런싱 전략을 구체적으로 알려줘:
- 어떤 종목을 **몇 주 매도하고**
- 추천 받은 종목을 **몇 주 매수하면 좋을지**
- 총 투자 금액 기준으로 각 종목에 얼마씩 배분하는 게 적절한지
- 보유 현금 비중은 전체 자산 대비 어느 정도가 적절할지도 알려줘

📌 단, 현재 주가 수준에서 매수 가능한 종목만 추천해줘.
📌 1주당 가격은 $500 이하인 종목만 포함해줘.
            """.strip()
            
            st.text_area("📨 복사해서 GPT 추천 요청에 붙여넣기", value=text, height=400)

            if st.button("📋 클립보드 복사"):
                pyperclip.copy(text)
                st.success("클립보드에 복사되었습니다!")

    except Exception as e:
        st.error(f"추천 문장 생성 중 오류 발생: {e}")


st.markdown("---")
st.subheader("📊 수익률 시각화")

if st.session_state.stocks:
    df = pd.DataFrame(st.session_state.stocks)

    # 1️⃣ 종목별 수익률 차트
    fig1 = px.bar(df, x="종목", y="수익률(%)",
                  color="수익률(%)", color_continuous_scale="RdYlGn",
                  title="📈 종목별 수익률(%)", text="수익률(%)")
    fig1.update_traces(texttemplate='%{text:.2f}%', textposition='outside')
    fig1.update_layout(yaxis_title="수익률 (%)", xaxis_title="종목", height=400)
    st.plotly_chart(fig1, use_container_width=True)

    # 2️⃣ 총 자산 구성 비율
    st.subheader("💰 총 자산 구성 (현금 + 주식 평가금액)")
    cash = cash_input
    df["평가금액"] = df["현재가"] * df["수량"]
    asset_pie = df[["종목", "평가금액"]].copy()
    asset_pie.loc[len(asset_pie.index)] = ["현금", cash]
    
    fig2 = px.pie(asset_pie, names="종목", values="평가금액", title="💼 자산 구성 비율")
    fig2.update_traces(textposition='inside', textinfo='percent+label')
    st.plotly_chart(fig2, use_container_width=True)
else:
    st.info("먼저 종목을 추가해주세요.")
    

# 데이터 폴더 확인
os.makedirs("data", exist_ok=True)
history_file = "data/history.json"

# 날짜 선택
st.markdown("---")
st.subheader("📅 포트폴리오 기록 저장")

today = st.date_input("📌 저장할 날짜 선택", value=date.today())

if st.button("💾 오늘 포트폴리오 저장"):
    if st.session_state.stocks:
        record = {
            "date": today.strftime("%Y-%m-%d"),
            "cash": cash_input,
            "stocks": st.session_state.stocks
        }

        # 기존 데이터 로드
        if os.path.exists(history_file):
            with open(history_file, "r", encoding="utf-8") as f:
                history_data = json.load(f)
        else:
            history_data = {}

        # 저장
        history_data[record["date"]] = record
        with open(history_file, "w", encoding="utf-8") as f:
            json.dump(history_data, f, indent=2, ensure_ascii=False)

        st.success(f"{record['date']} 기록이 저장되었습니다.")
    else:
        st.warning("먼저 종목을 입력해주세요.")
        

# 수익 추이 시각화
st.subheader("📈 히스토리 수익 추이")

if os.path.exists(history_file):
    with open(history_file, "r", encoding="utf-8") as f:
        history_data = json.load(f)

    if history_data:
        history_list = []
        for day, entry in sorted(history_data.items()):
            total_profit = sum(stock["수익"] for stock in entry["stocks"])
            total_cost = sum(stock["수량"] * stock["매수단가"] for stock in entry["stocks"])
            avg_profit_rate = (total_profit / total_cost * 100) if total_cost > 0 else 0
            history_list.append({
                "날짜": day,
                "총 수익": round(total_profit, 2),
                "평균 수익률(%)": round(avg_profit_rate, 2)
            })

        df_history = pd.DataFrame(history_list)

        # 수익률 변화 라인차트
        fig_profit = px.line(df_history, x="날짜", y="총 수익", title="💰 날짜별 총 수익 추이")
        st.plotly_chart(fig_profit, use_container_width=True)

        fig_rate = px.line(df_history, x="날짜", y="평균 수익률(%)", title="📈 날짜별 평균 수익률(%)")
        st.plotly_chart(fig_rate, use_container_width=True)
    else:
        st.info("아직 저장된 기록이 없습니다.")
else:
    st.info("아직 포트폴리오를 저장하지 않았습니다.")


st.markdown("---")
st.subheader("📥 Excel 다운로드")

if st.session_state.stocks:
    df = pd.DataFrame(st.session_state.stocks)
    df["평가금액"] = df["현재가"] * df["수량"]

    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="포트폴리오")

    st.download_button(
        label="📥 종목 데이터 엑셀 다운로드",
        data=buffer.getvalue(),
        file_name="portfolio.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
else:
    st.info("종목이 없습니다. 먼저 포트폴리오를 추가해주세요.")

st.markdown("---")
st.subheader("🧠 섹터/산업별 분산 시각화")

if st.session_state.stocks:
    sector_list = []

    for stock in st.session_state.stocks:
        symbol = stock["종목"]
        quantity = stock["수량"]
        price = stock["현재가"]
        try:
            info = yf.Ticker(symbol).info
            sector = info.get("sector", "Unknown") or "Unknown"
        except:
            sector = "Unknown"

        value = quantity * price
        profit = stock["수익"]
        cost = stock["수량"] * stock["매수단가"]
        rate = (profit / cost * 100) if cost > 0 else 0

        sector_list.append({
            "섹터": sector,
            "종목": symbol,
            "평가금액": value,
            "수익률(%)": rate
        })

    df_sector = pd.DataFrame(sector_list)

    # 1️⃣ 섹터별 평가금액 비중 파이차트
    fig1 = px.pie(df_sector, names="섹터", values="평가금액", title="💼 섹터별 평가금액 비중")
    fig1.update_traces(textposition='inside', textinfo='percent+label')
    st.plotly_chart(fig1, use_container_width=True)

    # 2️⃣ 섹터별 평균 수익률 막대차트
    df_avg = df_sector.groupby("섹터", as_index=False)["수익률(%)"].mean()
    fig2 = px.bar(df_avg, x="섹터", y="수익률(%)",
                  color="수익률(%)", color_continuous_scale="RdYlGn",
                  title="📈 섹터별 평균 수익률", text="수익률(%)")
    fig2.update_traces(texttemplate='%{text:.2f}%', textposition='outside')
    st.plotly_chart(fig2, use_container_width=True)
else:
    st.info("먼저 종목을 입력해주세요.")
