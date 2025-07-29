# app.py
import streamlit as st
import pandas as pd
import yfinance as yf
import json
import pyperclip
import plotly.express as px
import io
import os
from datetime import date

# 오늘 날짜
today = date.today()
st.set_page_config(page_title="📊 포트폴리오 트래커", layout="wide")
st.title("📈 종목 수익률 계산기")

# 세션 초기화
if "stocks" not in st.session_state:
    st.session_state.stocks = []

if "trade_history" not in st.session_state:
    st.session_state.trade_history = []

# 데이터 디렉토리 생성
os.makedirs("data", exist_ok=True)

# ------------------ 종목 추가 ------------------
st.subheader("🧾 종목 추가")
with st.form("stock_form"):
    col1, col2, col3 = st.columns([3, 1, 2])
    with col1:
        symbol = st.text_input("종목코드 (예: AAPL, TSLA)", value="").upper()
    with col2:
        quantity = st.number_input("수량", min_value=1, step=1)
    with col3:
        buy_price = st.number_input("매수단가 ($)", min_value=0.0, step=0.01)
    submitted = st.form_submit_button("추가하기")

    if submitted:
        stock_info = yf.Ticker(symbol)
        current_price = stock_info.history(period="1d")["Close"].iloc[-1]
        st.session_state.stocks.append({
            "symbol": symbol,
            "quantity": quantity,
            "buy_price": buy_price,
            "current_price": round(current_price, 2),
        })
        st.success(f"{symbol} 추가 완료!")

# ------------------ 저장 기능 ------------------
st.subheader("💾 포트폴리오 저장")
save_path = f"data/{today}.json"
if st.button("💾 오늘 기록 저장"):
    with open(save_path, "w") as f:
        json.dump(st.session_state.stocks, f, indent=2)
    st.success(f"{today} 저장 완료!")

# ------------------ 불러오기 기능 ------------------
load_date = st.date_input("📅 불러올 날짜 선택", value=today)
load_file_path = f"data/{load_date}.json"
if os.path.exists(load_file_path):
    if st.button("📂 포트폴리오 불러오기"):
        with open(load_file_path, "r") as f:
            loaded_data = json.load(f)
        st.session_state.stocks = loaded_data
        st.success(f"{load_date} 포트폴리오 불러오기 완료!")

# ------------------ 포트폴리오 테이블 ------------------
st.subheader("📋 현재 포트폴리오")
if st.session_state.stocks:
    df = pd.DataFrame(st.session_state.stocks)
    df["수익"] = (df["current_price"] - df["buy_price"]) * df["quantity"]
    df["수익률(%)"] = ((df["current_price"] - df["buy_price"]) / df["buy_price"]) * 100
    st.dataframe(df)
    total_profit = df["수익"].sum()
    st.markdown(f"### 💰 총 수익: ${round(total_profit, 2)}")

# ------------------ 매매 기록 ------------------
st.subheader("📝 매수/매도 이력 기록")
with st.form("trade_form"):
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        action = st.selectbox("유형", ["매수", "매도"])
    with col2:
        trade_symbol = st.text_input("종목코드 (기록)").upper()
    with col3:
        trade_quantity = st.number_input("수량", min_value=1, step=1, key="trade_qty")
    with col4:
        trade_price = st.number_input("단가 ($)", min_value=0.0, step=0.01, key="trade_price")
    submitted_trade = st.form_submit_button("기록하기")

    if submitted_trade:
        record = {
            "date": str(today),
            "action": action,
            "symbol": trade_symbol,
            "quantity": trade_quantity,
            "price": trade_price
        }

        if action == "매도":
            for s in st.session_state.stocks:
                if s["symbol"] == trade_symbol:
                    buy_price = s["buy_price"]
                    record["수익"] = round((trade_price - buy_price) * trade_quantity, 2)
                    record["수익률(%)"] = round(((trade_price - buy_price) / buy_price) * 100, 2)

        trade_log_file = "data/trades.json"
        if os.path.exists(trade_log_file):
            with open(trade_log_file, "r") as f:
                trade_data = json.load(f)
        else:
            trade_data = []

        trade_data.append(record)
        st.session_state.trade_history = trade_data

        with open(trade_log_file, "w") as f:
            json.dump(trade_data, f, indent=2)
        st.success("매매기록 저장 완료!")

# ------------------ 거래 히스토리 ------------------
st.subheader("📘 매매 히스토리")
if os.path.exists("data/trades.json"):
    with open("data/trades.json", "r") as f:
        trade_data = json.load(f)
    df_trades = pd.DataFrame(trade_data)
    st.dataframe(df_trades)

# ------------------ 문장 생성 및 복사 ------------------
st.subheader("📄 오늘의 요약 문장")
if st.session_state.stocks:
    summary = f"오늘 총 수익은 ${round(total_profit,2)} 입니다."
    st.text_area("📋 생성 문장", summary, height=80)
    st.code("Ctrl+C 또는 마우스로 복사해주세요")

# ------------------ 시각화 ------------------
st.subheader("📊 섹터 시각화 (임시)")
# 이후 섹터 API 연동 시 여기 추가 예정
