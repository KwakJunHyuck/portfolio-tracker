import streamlit as st
import pandas as pd
import yfinance as yf
import json
import plotly.express as px
import plotly.graph_objects as go
import io
import os
from datetime import date, datetime, timedelta

st.set_page_config(
    page_title="📊 포트폴리오 트래커", 
    layout="wide",
    initial_sidebar_state="collapsed"
)

# CSS for mobile-friendly design
st.markdown("""
<style>
    .stMetric > div > div > div > div {
        font-size: 0.8rem;
    }
    .stDataFrame {
        font-size: 0.8rem;
    }
    @media (max-width: 768px) {
        .stSelectbox > div > div > div {
            font-size: 0.9rem;
        }
        .stNumberInput > div > div > input {
            font-size: 0.9rem;
        }
    }
</style>
""", unsafe_allow_html=True)

st.title("📈 스마트 포트폴리오 트래커")

# 세션 상태 초기화
if "stocks" not in st.session_state:
    st.session_state.stocks = []
if "transactions" not in st.session_state:
    st.session_state.transactions = []
if "mobile_mode" not in st.session_state:
    st.session_state.mobile_mode = False
if "target_settings" not in st.session_state:
    st.session_state.target_settings = {}
if "target_allocation" not in st.session_state:
    st.session_state.target_allocation = {}

# 데이터 폴더 확인
os.makedirs("data", exist_ok=True)
history_file = "data/history.json"
transactions_file = "data/transactions.json"
settings_file = "data/settings.json"

# 설정 불러오기
def load_settings():
    if os.path.exists(settings_file):
        with open(settings_file, "r", encoding="utf-8") as f:
            settings = json.load(f)
            st.session_state.target_settings = settings.get("target_settings", {})
            st.session_state.target_allocation = settings.get("target_allocation", {})

def save_settings():
    settings = {
        "target_settings": st.session_state.target_settings,
        "target_allocation": st.session_state.target_allocation
    }
    with open(settings_file, "w", encoding="utf-8") as f:
        json.dump(settings, f, indent=2, ensure_ascii=False)

load_settings()

# 시장 지수 데이터 가져오기
@st.cache_data(ttl=3600)  # 1시간 캐시
def get_market_data():
    try:
        # S&P 500, NASDAQ, 다우존스 데이터
        spy = yf.Ticker("SPY")
        qqq = yf.Ticker("QQQ") 
        dia = yf.Ticker("DIA")
        
        period = "1y"
        spy_data = spy.history(period=period)
        qqq_data = qqq.history(period=period)
        dia_data = dia.history(period=period)
        
        # 1년 수익률 계산
        spy_return = ((spy_data["Close"][-1] / spy_data["Close"][0]) - 1) * 100
        qqq_return = ((qqq_data["Close"][-1] / qqq_data["Close"][0]) - 1) * 100
        dia_return = ((dia_data["Close"][-1] / dia_data["Close"][0]) - 1) * 100
        
        return {
            "SPY": {"return": spy_return, "data": spy_data},
            "QQQ": {"return": qqq_return, "data": qqq_data},
            "DIA": {"return": dia_return, "data": dia_data}
        }
    except:
        return None

# 모바일 모드 토글
st.session_state.mobile_mode = st.checkbox("📱 모바일 모드", value=st.session_state.mobile_mode)

# 모바일 친화적 레이아웃 설정
if st.session_state.mobile_mode:
    col_ratio = [1]
    chart_height = 300
    use_full_width = True
else:
    col_ratio = [3, 1]
    chart_height = 400
    use_full_width = True

# 🔄 포트폴리오 불러오기 기능
st.subheader("🔄 포트폴리오 불러오기")

if st.session_state.mobile_mode:
    if os.path.exists(history_file):
        with open(history_file, "r", encoding="utf-8") as f:
            history_data = json.load(f)
        
        if history_data:
            available_dates = sorted(history_data.keys(), reverse=True)
            selected_date = st.selectbox("불러올 날짜 선택", available_dates)
        else:
            st.info("저장된 포트폴리오가 없습니다.")
            selected_date = None
    else:
        st.info("저장된 포트폴리오가 없습니다.")
        selected_date = None
    
    if selected_date and st.button("📂 포트폴리오 불러오기", use_container_width=True):
        loaded_data = history_data[selected_date]
        st.session_state.stocks = loaded_data["stocks"]
        st.success(f"{selected_date} 포트폴리오를 불러왔습니다!")
        st.rerun()
else:
    col1, col2 = st.columns([3, 1])
    with col1:
        if os.path.exists(history_file):
            with open(history_file, "r", encoding="utf-8") as f:
                history_data = json.load(f)
            
            if history_data:
                available_dates = sorted(history_data.keys(), reverse=True)
                selected_date = st.selectbox("불러올 날짜 선택", available_dates)
            else:
                st.info("저장된 포트폴리오가 없습니다.")
                selected_date = None
        else:
            st.info("저장된 포트폴리오가 없습니다.")
            selected_date = None
    
    with col2:
        if selected_date and st.button("📂 포트폴리오 불러오기"):
            loaded_data = history_data[selected_date]
            st.session_state.stocks = loaded_data["stocks"]
            st.success(f"{selected_date} 포트폴리오를 불러왔습니다!")
            st.rerun()

st.markdown("---")

# 📝 종목 추가/수정
st.subheader("📝 종목 관리")

# 탭으로 구분
tab1, tab2, tab3 = st.tabs(["➕ 종목 추가", "📊 매매 기록", "⚙️ 설정"])

with tab1:
    with st.form("stock_form"):
        if st.session_state.mobile_mode:
            symbol = st.text_input("종목코드 (예: AAPL, TSLA)").upper()
            col_mobile = st.columns(2)
            with col_mobile[0]:
                quantity = st.number_input("수량", min_value=1, step=1)
            with col_mobile[1]:
                avg_price = st.number_input("매수단가 ($)", min_value=0.01, step=0.01, format="%.2f")
        else:
            col1, col2, col3 = st.columns([2, 1, 1])
            with col1:
                symbol = st.text_input("종목코드 (예: AAPL, TSLA)").upper()
            with col2:
                quantity = st.number_input("수량", min_value=1, step=1)
            with col3:
                avg_price = st.number_input("매수단가 ($)", min_value=0.01, step=0.01, format="%.2f")
        
        submitted = st.form_submit_button("추가하기", use_container_width=True)
        
        if submitted and symbol:
            try:
                stock = yf.Ticker(symbol)
                current_price = stock.history(period="1d")["Close"].iloc[-1]
                
                # 배당 수익률 가져오기
                info = stock.info
                dividend_yield = info.get('dividendYield', 0)
                if dividend_yield:
                    dividend_yield = dividend_yield * 100
                else:
                    dividend_yield = 0
                
                profit = (current_price - avg_price) * quantity
                profit_rate = (profit / (avg_price * quantity)) * 100
                
                # 기존 종목이 있는지 확인
                existing_stock = None
                for i, s in enumerate(st.session_state.stocks):
                    if s["종목"] == symbol:
                        existing_stock = i
                        break
                
                new_stock = {
                    "종목": symbol,
                    "수량": quantity,
                    "매수단가": avg_price,
                    "현재가": round(current_price, 2),
                    "수익": round(profit, 2),
                    "수익률(%)": round(profit_rate, 2),
                    "배당수익률(%)": round(dividend_yield, 2) if dividend_yield else 0
                }
                
                if existing_stock is not None:
                    # 기존 종목 업데이트 (평균단가 계산)
                    old_stock = st.session_state.stocks[existing_stock]
                    total_quantity = old_stock["수량"] + quantity
                    avg_cost = ((old_stock["수량"] * old_stock["매수단가"]) + (quantity * avg_price)) / total_quantity
                    
                    new_stock["수량"] = total_quantity
                    new_stock["매수단가"] = round(avg_cost, 2)
                    new_stock["수익"] = round((current_price - avg_cost) * total_quantity, 2)
                    new_stock["수익률(%)"] = round(((current_price - avg_cost) / avg_cost) * 100, 2)
                    
                    st.session_state.stocks[existing_stock] = new_stock
                    st.success(f"{symbol} 기존 보유분과 합쳐졌습니다!")
                else:
                    st.session_state.stocks.append(new_stock)
                    st.success(f"{symbol} 추가 완료!")
                
                # 매매 기록 추가
                transaction = {
                    "날짜": datetime.now().strftime("%Y-%m-%d %H:%M"),
                    "종목": symbol,
                    "거래유형": "매수",
                    "수량": quantity,
                    "가격": avg_price,
                    "총액": quantity * avg_price
                }
                st.session_state.transactions.append(transaction)
                
            except Exception as e:
                st.error(f"현재가를 불러오는 데 실패했습니다: {e}")

with tab2:
    st.subheader("💰 매수/매도 기록")
    
    # 매도 기능
    if st.session_state.stocks:
        with st.form("sell_form"):
            if st.session_state.mobile_mode:
                stock_options = [s["종목"] for s in st.session_state.stocks]
                sell_symbol = st.selectbox("매도할 종목", stock_options)
                col_mobile = st.columns(2)
                with col_mobile[0]:
                    max_quantity = next(s["수량"] for s in st.session_state.stocks if s["종목"] == sell_symbol)
                    sell_quantity = st.number_input("매도 수량", min_value=1, max_value=max_quantity, step=1)
                with col_mobile[1]:
                    sell_price = st.number_input("매도단가 ($)", min_value=0.01, step=0.01, format="%.2f")
            else:
                col1, col2, col3 = st.columns([2, 1, 1])
                with col1:
                    stock_options = [s["종목"] for s in st.session_state.stocks]
                    sell_symbol = st.selectbox("매도할 종목", stock_options)
                with col2:
                    max_quantity = next(s["수량"] for s in st.session_state.stocks if s["종목"] == sell_symbol)
                    sell_quantity = st.number_input("매도 수량", min_value=1, max_value=max_quantity, step=1)
                with col3:
                    sell_price = st.number_input("매도단가 ($)", min_value=0.01, step=0.01, format="%.2f")
            
            sell_submitted = st.form_submit_button("매도하기", use_container_width=True)
            
            if sell_submitted:
                # 매도 처리
                for i, stock in enumerate(st.session_state.stocks):
                    if stock["종목"] == sell_symbol:
                        if stock["수량"] == sell_quantity:
                            # 전량 매도
                            st.session_state.stocks.pop(i)
                        else:
                            # 일부 매도
                            stock["수량"] -= sell_quantity
                            # 현재가 업데이트하여 수익 재계산
                            try:
                                current_price = yf.Ticker(sell_symbol).history(period="1d")["Close"].iloc[-1]
                                stock["현재가"] = round(current_price, 2)
                                profit = (current_price - stock["매수단가"]) * stock["수량"]
                                stock["수익"] = round(profit, 2)
                                stock["수익률(%)"] = round((profit / (stock["매수단가"] * stock["수량"])) * 100, 2)
                            except:
                                pass
                        break
                
                # 매매 기록 추가
                transaction = {
                    "날짜": datetime.now().strftime("%Y-%m-%d %H:%M"),
                    "종목": sell_symbol,
                    "거래유형": "매도",
                    "수량": sell_quantity,
                    "가격": sell_price,
                    "총액": sell_quantity * sell_price
                }
                st.session_state.transactions.append(transaction)
                st.success(f"{sell_symbol} {sell_quantity}주 매도 완료!")
                st.rerun()

with tab3:
    st.subheader("⚙️ 목표 설정")
    
    # 목표 수익률 설정
    st.write("**🎯 종목별 목표 설정**")
    if st.session_state.stocks:
        for stock in st.session_state.stocks:
            symbol = stock["종목"]
            col1, col2, col3 = st.columns(3)
            
            with col1:
                target_return = st.number_input(
                    f"{symbol} 목표수익률(%)", 
                    value=st.session_state.target_settings.get(f"{symbol}_target", 20.0),
                    key=f"target_{symbol}"
                )
                st.session_state.target_settings[f"{symbol}_target"] = target_return
            
            with col2:
                stop_loss = st.number_input(
                    f"{symbol} 손절선(%)", 
                    value=st.session_state.target_settings.get(f"{symbol}_stop", -10.0),
                    max_value=0.0,
                    key=f"stop_{symbol}"
                )
                st.session_state.target_settings[f"{symbol}_stop"] = stop_loss
            
            with col3:
                take_profit = st.number_input(
                    f"{symbol} 익절선(%)", 
                    value=st.session_state.target_settings.get(f"{symbol}_take", 25.0),
                    min_value=0.0,
                    key=f"take_{symbol}"
                )
                st.session_state.target_settings[f"{symbol}_take"] = take_profit
    
    st.markdown("---")
    
    # 목표 비중 설정 (리밸런싱)
    st.write("**⚖️ 목표 포트폴리오 비중 설정**")
    if st.session_state.stocks:
        total_allocation = 0
        for stock in st.session_state.stocks:
            symbol = stock["종목"]
            allocation = st.number_input(
                f"{symbol} 목표비중(%)", 
                value=st.session_state.target_allocation.get(symbol, 0.0),
                min_value=0.0, max_value=100.0, step=1.0,
                key=f"allocation_{symbol}"
            )
            st.session_state.target_allocation[symbol] = allocation
            total_allocation += allocation
        
        cash_allocation = st.number_input(
            "현금 목표비중(%)", 
            value=st.session_state.target_allocation.get("현금", 20.0),
            min_value=0.0, max_value=100.0, step=1.0
        )
        st.session_state.target_allocation["현금"] = cash_allocation
        total_allocation += cash_allocation
        
        if total_allocation != 100:
            st.warning(f"총 비중이 {total_allocation:.1f}%입니다. 100%로 맞춰주세요.")
        else:
            st.success("✅ 목표 비중이 100%로 설정되었습니다.")
    
    if st.button("💾 설정 저장", use_container_width=True):
        save_settings()
        st.success("설정이 저장되었습니다!")

# 거래 내역 표시
if st.session_state.transactions:
    st.subheader("📋 최근 거래 내역")
    df_transactions = pd.DataFrame(st.session_state.transactions[-10:])  # 최근 10건만
    st.dataframe(df_transactions, use_container_width=True)

st.markdown("---")

# 포트폴리오 테이블
if st.session_state.stocks:
    st.subheader("📋 현재 포트폴리오")
    
    # 현재가 업데이트 버튼
    if st.button("🔄 현재가 업데이트", use_container_width=True):
        for stock in st.session_state.stocks:
            try:
                ticker = yf.Ticker(stock["종목"])
                current_price = ticker.history(period="1d")["Close"].iloc[-1]
                
                # 배당 수익률 업데이트
                info = ticker.info
                dividend_yield = info.get('dividendYield', 0)
                if dividend_yield:
                    dividend_yield = dividend_yield * 100
                else:
                    dividend_yield = 0
                
                stock["현재가"] = round(current_price, 2)
                stock["배당수익률(%)"] = round(dividend_yield, 2) if dividend_yield else 0
                profit = (current_price - stock["매수단가"]) * stock["수량"]
                stock["수익"] = round(profit, 2)
                stock["수익률(%)"] = round((profit / (stock["매수단가"] * stock["수량"])) * 100, 2)
            except:
                continue
        st.success("현재가가 업데이트되었습니다!")
        st.rerun()
    
    df = pd.DataFrame(st.session_state.stocks)
    df["평가금액"] = df["현재가"] * df["수량"]
    df["투자금액"] = df["매수단가"] * df["수량"]
    
    # 색상으로 수익/손실 구분하여 표시
    st.dataframe(
        df.style.applymap(
            lambda x: 'color: red' if isinstance(x, (int, float)) and x < 0 else 'color: green' if isinstance(x, (int, float)) and x > 0 else '',
            subset=['수익', '수익률(%)']
        ),
        use_container_width=True
    )

    total_profit = df["수익"].sum()
    total_investment = df["투자금액"].sum()
    total_value = df["평가금액"].sum()
    total_return_rate = (total_profit / total_investment * 100) if total_investment > 0 else 0
    total_dividend = (df["배당수익률(%)"] * df["평가금액"] / 100).sum()
    
    if st.session_state.mobile_mode:
        st.metric("💰 총 투자금액", f"${total_investment:,.2f}")
        st.metric("📈 총 평가금액", f"${total_value:,.2f}")
        st.metric("💹 총 수익률", f"{total_return_rate:.2f}%", f"${total_profit:,.2f}")
        st.metric("💵 연간 예상 배당금", f"${total_dividend:,.2f}")
    else:
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("💰 총 투자금액", f"${total_investment:,.2f}")
        with col2:
            st.metric("📈 총 평가금액", f"${total_value:,.2f}")
        with col3:
            st.metric("💹 총 수익률", f"{total_return_rate:.2f}%", f"${total_profit:,.2f}")
        with col4:
            st.metric("💵 연간 예상 배당금", f"${total_dividend:,.2f}")

# 🚨 알림 시스템 (목표 달성/손절/익절)
if st.session_state.stocks and st.session_state.target_settings:
    st.subheader("🚨 트레이딩 알림")
    alerts = []
    
    for stock in st.session_state.stocks:
        symbol = stock["종목"]
        current_return = stock["수익률(%)"]
        
        target_return = st.session_state.target_settings.get(f"{symbol}_target", 20.0)
        stop_loss = st.session_state.target_settings.get(f"{symbol}_stop", -10.0)
        take_profit = st.session_state.target_settings.get(f"{symbol}_take", 25.0)
        
        if current_return >= target_return:
            alerts.append(f"🎯 **{symbol}** 목표 수익률 달성! ({current_return:.2f}% >= {target_return:.1f}%)")
        elif current_return <= stop_loss:
            alerts.append(f"🛑 **{symbol}** 손절선 도달! ({current_return:.2f}% <= {stop_loss:.1f}%)")
        elif current_return >= take_profit:
            alerts.append(f"💰 **{symbol}** 익절 구간! ({current_return:.2f}% >= {take_profit:.1f}%)")
    
    if alerts:
        for alert in alerts:
            if "손절선" in alert:
                st.error(alert)
            elif "익절" in alert or "목표" in alert:
                st.success(alert)
    else:
        st.info("💤 현재 특별한 알림이 없습니다.")

st.markdown("---")

# 📊 시장 지수와 비교
st.subheader("📊 시장 지수 대비 성과")

market_data = get_market_data()
if market_data and st.session_state.stocks:
    df = pd.DataFrame(st.session_state.stocks)
    total_investment = (df["매수단가"] * df["수량"]).sum()
    total_value = (df["현재가"] * df["수량"]).sum()
    my_return = ((total_value / total_investment) - 1) * 100 if total_investment > 0 else 0
    
    if st.session_state.mobile_mode:
        st.metric("📈 내 포트폴리오", f"{my_return:.2f}%")
        st.metric("🏛️ S&P 500 (SPY)", f"{market_data['SPY']['return']:.2f}%")
        st.metric("💻 NASDAQ (QQQ)", f"{market_data['QQQ']['return']:.2f}%")
        st.metric("🏭 다우존스 (DIA)", f"{market_data['DIA']['return']:.2f}%")
    else:
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("📈 내 포트폴리오", f"{my_return:.2f}%")
        with col2:
            delta_spy = my_return - market_data['SPY']['return']
            st.metric("🏛️ S&P 500 (SPY)", f"{market_data['SPY']['return']:.2f}%", f"{delta_spy:+.2f}%")
        with col3:
            delta_qqq = my_return - market_data['QQQ']['return']
            st.metric("💻 NASDAQ (QQQ)", f"{market_data['QQQ']['return']:.2f}%", f"{delta_qqq:+.2f}%")
        with col4:
            delta_dia = my_return - market_data['DIA']['return']
            st.metric("🏭 다우존스 (DIA)", f"{market_data['DIA']['return']:.2f}%", f"{delta_dia:+.2f}%")
    
    # 시장 대비 성과 분석
    if my_return > market_data['SPY']['return']:
        st.success(f"🎉 S&P 500 대비 {my_return - market_data['SPY']['return']:+.2f}% 초과 수익!")
    else:
        st.warning(f"📉 S&P 500 대비 {my_return - market_data['SPY']['return']:+.2f}% 수익")

st.markdown("---")

# 리밸런싱 제안
if st.session_state.stocks and st.session_state.target_allocation:
    st.subheader("⚖️ 리밸런싱 제안")
    
    df = pd.DataFrame(st.session_state.stocks)
    df["평가금액"] = df["현재가"] * df["수량"]
    
    cash_input = st.number_input("보유 현금 ($)", min_value=0.0, step=100.0, format="%.2f", value=0.0)
    total_assets = df["평가금액"].sum() + cash_input
    
    if total_assets > 0:
        rebalancing_suggestions = []
        
        # 현재 비중 vs 목표 비중
        for stock in st.session_state.stocks:
            symbol = stock["종목"]
            current_value = stock["현재가"] * stock["수량"]
            current_weight = (current_value / total_assets) * 100
            target_weight = st.session_state.target_allocation.get(symbol, 0)
            
            if abs(current_weight - target_weight) > 5:  # 5% 이상 차이
                target_value = total_assets * target_weight / 100
                diff_value = target_value - current_value
                diff_shares = diff_value / stock["현재가"]
                
                if diff_value > 0:
                    rebalancing_suggestions.append(f"📈 **{symbol}** {abs(diff_shares):.0f}주 매수 (${diff_value:,.0f})")
                else:
                    rebalancing_suggestions.append(f"📉 **{symbol}** {abs(diff_shares):.0f}주 매도 (${abs(diff_value):,.0f})")
        
        # 현금 비중 체크
        current_cash_weight = (cash_input / total_assets) * 100
        target_cash_weight = st.session_state.target_allocation.get("현금", 20)
        
        if abs(current_cash_weight - target_cash_weight) > 5:
            target_cash_value = total_assets * target_cash_weight / 100
            diff_cash = target_cash_value - cash_input
            
            if diff_cash > 0:
                rebalancing_suggestions.append(f"💵 현금 비중 증대 필요: ${diff_cash:,.0f}")
            else:
                rebalancing_suggestions.append(f"💸 현금 비중 감소 가능: ${abs(diff_cash):,.0f}")
        
        if rebalancing_suggestions:
            st.write("**🔄 리밸런싱 제안사항:**")
            for suggestion in rebalancing_suggestions:
                st.write(f"- {suggestion}")
        else:
            st.success("✅ 포트폴리오가 목표 비중에 맞게 잘 구성되어 있습니다!")

st.markdown("---")
st.subheader("💡 종목 추천 문장 자동 생성")

if st.button("✍️ 추천 요청 문장 생성"):
    try:
        holdings = st.session_state.stocks
        if not holdings:
            st.warning("먼저 종목을 추가해주세요.")
        else:
            # 시장 데이터 포함
            market_info = ""
            if market_data:
                market_info = f"""
📊 시장 현황 참고:
- S&P 500: {market_data['SPY']['return']:+.2f}%
- NASDAQ: {market_data['QQQ']['return']:+.2f}%
- 다우존스: {market_data['DIA']['return']:+.2f}%
"""
            
            text = f"""현재 포트폴리오 구성은 다음과 같아:
- 보유 현금: ${cash_input:,.2f}
"""
            
            for stock in holdings:
                text += f"- {stock['종목']}: {stock['수량']}주 (매수단가 ${stock['매수단가']}, 현재가 ${stock['현재가']}, 수익률 {stock['수익률(%)']:.2f}%)\n"
            
            text += market_info
            
            # 목표 설정 정보 추가
            if st.session_state.target_settings:
                text += "\n🎯 현재 설정된 목표:\n"
                for stock in holdings:
                    symbol = stock['종목']
                    target = st.session_state.target_settings.get(f"{symbol}_target", 20)
                    stop = st.session_state.target_settings.get(f"{symbol}_stop", -10)
                    take = st.session_state.target_settings.get(f"{symbol}_take", 25)
                    text += f"- {symbol}: 목표 {target}%, 손절 {stop}%, 익절 {take}%\n"
            
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
- 시장 지수(S&P 500, NASDAQ) 대비 내 포트폴리오 성과 분석도 포함해줘

📌 단, 현재 주가 수준에서 매수 가능한 종목만 추천해줘.
📌 1주당 가격은 $500 이하인 종목만 포함해줘.
            """.strip()
            
            st.text_area("📨 복사해서 GPT 추천 요청에 붙여넣기", value=text, height=400, key="recommendation_text")
            
            # 다운로드 버튼으로 대체
            st.download_button(
                label="📋 텍스트 파일로 다운로드",
                data=text.encode('utf-8'),
                file_name=f"portfolio_recommendation_{date.today()}.txt",
                mime="text/plain",
                use_container_width=True
            )

    except Exception as e:
        st.error(f"추천 문장 생성 중 오류 발생: {e}")

st.markdown("---")
st.subheader("📊 수익률 시각화")

if st.session_state.stocks:
    df = pd.DataFrame(st.session_state.stocks)
    df["평가금액"] = df["현재가"] * df["수량"]

    # 1️⃣ 종목별 수익률 차트
    fig1 = px.bar(df, x="종목", y="수익률(%)",
                  color="수익률(%)", color_continuous_scale="RdYlGn",
                  title="📈 종목별 수익률(%)", text="수익률(%)")
    fig1.update_traces(texttemplate='%{text:.2f}%', textposition='outside')
    fig1.update_layout(yaxis_title="수익률 (%)", xaxis_title="종목", height=chart_height)
    st.plotly_chart(fig1, use_container_width=True)

    # 2️⃣ 총 자산 구성 비율
    st.subheader("💰 총 자산 구성 (현금 + 주식 평가금액)")
    asset_pie = df[["종목", "평가금액"]].copy()
    if cash_input > 0:
        asset_pie.loc[len(asset_pie.index)] = ["현금", cash_input]
    
    fig2 = px.pie(asset_pie, names="종목", values="평가금액", title="💼 자산 구성 비율")
    fig2.update_traces(textposition='inside', textinfo='percent+label')
    fig2.update_layout(height=chart_height)
    st.plotly_chart(fig2, use_container_width=True)

    # 3️⃣ 손익 분포 차트
    fig3 = px.bar(df, x="종목", y="수익",
                  color="수익", color_continuous_scale="RdYlGn",
                  title="💰 종목별 손익 ($)", text="수익")
    fig3.update_traces(texttemplate='$%{text:.2f}', textposition='outside')
    fig3.update_layout(yaxis_title="손익 ($)", xaxis_title="종목", height=chart_height)
    st.plotly_chart(fig3, use_container_width=True)

    # 4️⃣ 시장 지수와 포트폴리오 비교 차트
    if market_data:
        total_investment = (df["매수단가"] * df["수량"]).sum()
        total_value = (df["현재가"] * df["수량"]).sum()
        my_return = ((total_value / total_investment) - 1) * 100 if total_investment > 0 else 0
        
        comparison_data = {
            '구분': ['내 포트폴리오', 'S&P 500', 'NASDAQ', '다우존스'],
            '수익률(%)': [my_return, market_data['SPY']['return'], market_data['QQQ']['return'], market_data['DIA']['return']]
        }
        df_comparison = pd.DataFrame(comparison_data)
        
        fig4 = px.bar(df_comparison, x="구분", y="수익률(%)",
                      color="수익률(%)", color_continuous_scale="RdYlGn",
                      title="📊 시장 지수 대비 성과 비교", text="수익률(%)")
        fig4.update_traces(texttemplate='%{text:.2f}%', textposition='outside')
        fig4.update_layout(height=chart_height)
        st.plotly_chart(fig4, use_container_width=True)

else:
    st.info("먼저 종목을 추가해주세요.")

# 날짜 선택
st.markdown("---")
st.subheader("📅 포트폴리오 기록 저장")

today = st.date_input("📌 저장할 날짜 선택", value=date.today())

if st.session_state.mobile_mode:
    if st.button("💾 포트폴리오 저장", use_container_width=True):
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
    
    if st.button("💾 거래내역 저장", use_container_width=True):
        if st.session_state.transactions:
            with open(transactions_file, "w", encoding="utf-8") as f:
                json.dump(st.session_state.transactions, f, indent=2, ensure_ascii=False)
            st.success("거래내역이 저장되었습니다.")
        else:
            st.warning("저장할 거래내역이 없습니다.")
else:
    col1, col2 = st.columns(2)
    with col1:
        if st.button("💾 포트폴리오 저장"):
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

    with col2:
        if st.button("💾 거래내역 저장"):
            if st.session_state.transactions:
                with open(transactions_file, "w", encoding="utf-8") as f:
                    json.dump(st.session_state.transactions, f, indent=2, ensure_ascii=False)
                st.success("거래내역이 저장되었습니다.")
            else:
                st.warning("저장할 거래내역이 없습니다.")

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
            total_value = sum(stock["수량"] * stock["현재가"] for stock in entry["stocks"])
            avg_profit_rate = (total_profit / total_cost * 100) if total_cost > 0 else 0
            total_assets = total_value + entry.get("cash", 0)
            
            history_list.append({
                "날짜": day,
                "총 수익": round(total_profit, 2),
                "평균 수익률(%)": round(avg_profit_rate, 2),
                "총 자산": round(total_assets, 2),
                "투자금액": round(total_cost, 2),
                "평가금액": round(total_value, 2)
            })

        df_history = pd.DataFrame(history_list)

        # 수익률 변화 라인차트
        fig_profit = px.line(df_history, x="날짜", y="총 수익", title="💰 날짜별 총 수익 추이")
        fig_profit.update_layout(height=chart_height)
        st.plotly_chart(fig_profit, use_container_width=True)

        fig_rate = px.line(df_history, x="날짜", y="평균 수익률(%)", title="📈 날짜별 평균 수익률(%)")
        fig_rate.update_layout(height=chart_height)
        st.plotly_chart(fig_rate, use_container_width=True)
        
        # 총 자산 추이
        fig_assets = px.line(df_history, x="날짜", y=["투자금액", "평가금액", "총 자산"], 
                           title="💼 총 자산 추이")
        fig_assets.update_layout(height=chart_height)
        st.plotly_chart(fig_assets, use_container_width=True)
    else:
        st.info("아직 저장된 기록이 없습니다.")
else:
    st.info("아직 포트폴리오를 저장하지 않았습니다.")

st.markdown("---")
st.subheader("📥 데이터 다운로드")

if st.session_state.mobile_mode:
    if st.session_state.stocks:
        df = pd.DataFrame(st.session_state.stocks)
        df["평가금액"] = df["현재가"] * df["수량"]
        df["투자금액"] = df["매수단가"] * df["수량"]

        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
            df.to_excel(writer, index=False, sheet_name="포트폴리오")

        st.download_button(
            label="📥 포트폴리오 엑셀 다운로드",
            data=buffer.getvalue(),
            file_name=f"portfolio_{date.today()}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True
        )
    
    if st.session_state.transactions:
        df_trans = pd.DataFrame(st.session_state.transactions)
        
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
            df_trans.to_excel(writer, index=False, sheet_name="거래내역")

        st.download_button(
            label="📥 거래내역 엑셀 다운로드",
            data=buffer.getvalue(),
            file_name=f"transactions_{date.today()}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True
        )
    
    if os.path.exists(history_file):
        with open(history_file, "r", encoding="utf-8") as f:
            history_json = f.read()
        
        st.download_button(
            label="📥 전체 히스토리 다운로드",
            data=history_json.encode('utf-8'),
            file_name=f"portfolio_history_{date.today()}.json",
            mime="application/json",
            use_container_width=True
        )
else:
    col1, col2, col3 = st.columns(3)

    with col1:
        if st.session_state.stocks:
            df = pd.DataFrame(st.session_state.stocks)
            df["평가금액"] = df["현재가"] * df["수량"]
            df["투자금액"] = df["매수단가"] * df["수량"]

            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
                df.to_excel(writer, index=False, sheet_name="포트폴리오")

            st.download_button(
                label="📥 포트폴리오 엑셀 다운로드",
                data=buffer.getvalue(),
                file_name=f"portfolio_{date.today()}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

    with col2:
        if st.session_state.transactions:
            df_trans = pd.DataFrame(st.session_state.transactions)
            
            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
                df_trans.to_excel(writer, index=False, sheet_name="거래내역")

            st.download_button(
                label="📥 거래내역 엑셀 다운로드",
                data=buffer.getvalue(),
                file_name=f"transactions_{date.today()}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

    with col3:
        if os.path.exists(history_file):
            with open(history_file, "r", encoding="utf-8") as f:
                history_json = f.read()
            
            st.download_button(
                label="📥 전체 히스토리 다운로드",
                data=history_json.encode('utf-8'),
                file_name=f"portfolio_history_{date.today()}.json",
                mime="application/json"
            )

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
    sector_summary = df_sector.groupby("섹터", as_index=False)["평가금액"].sum()
    fig1 = px.pie(sector_summary, names="섹터", values="평가금액", title="💼 섹터별 평가금액 비중")
    fig1.update_traces(textposition='inside', textinfo='percent+label')
    fig1.update_layout(height=chart_height)
    st.plotly_chart(fig1, use_container_width=True)

    # 2️⃣ 섹터별 평균 수익률 막대차트
    df_avg = df_sector.groupby("섹터", as_index=False)["수익률(%)"].mean()
    fig2 = px.bar(df_avg, x="섹터", y="수익률(%)",
                  color="수익률(%)", color_continuous_scale="RdYlGn",
                  title="📈 섹터별 평균 수익률", text="수익률(%)")
    fig2.update_traces(texttemplate='%{text:.2f}%', textposition='outside')
    fig2.update_layout(height=chart_height)
    st.plotly_chart(fig2, use_container_width=True)
else:
    st.info("먼저 종목을 입력해주세요.")

# 📊 추가 분석 기능
st.markdown("---")
st.subheader("📊 포트폴리오 분석")

if st.session_state.stocks:
    df = pd.DataFrame(st.session_state.stocks)
    df["평가금액"] = df["현재가"] * df["수량"]
    df["투자금액"] = df["매수단가"] * df["수량"]
    
    if st.session_state.mobile_mode:
        # 최고/최저 수익률 종목
        best_stock = df.loc[df["수익률(%)"].idxmax()]
        worst_stock = df.loc[df["수익률(%)"].idxmin()]
        
        st.subheader("🏆 수익률 순위")
        st.success(f"**최고 수익률**: {best_stock['종목']} ({best_stock['수익률(%)']:.2f}%)")
        st.error(f"**최저 수익률**: {worst_stock['종목']} ({worst_stock['수익률(%)']:.2f}%)")
        
        # 포트폴리오 요약 통계
        st.subheader("📈 포트폴리오 통계")
        st.write(f"보유 종목 수: {len(df)}개")
        st.write(f"평균 수익률: {df['수익률(%)'].mean():.2f}%")
        st.write(f"수익률 표준편차: {df['수익률(%)'].std():.2f}%")
        
        positive_stocks = (df["수익률(%)"] > 0).sum()
        st.write(f"수익 종목: {positive_stocks}/{len(df)}개")
    else:
        col1, col2 = st.columns(2)
        
        with col1:
            # 최고/최저 수익률 종목
            best_stock = df.loc[df["수익률(%)"].idxmax()]
            worst_stock = df.loc[df["수익률(%)"].idxmin()]
            
            st.subheader("🏆 수익률 순위")
            st.success(f"**최고 수익률**: {best_stock['종목']} ({best_stock['수익률(%)']:.2f}%)")
            st.error(f"**최저 수익률**: {worst_stock['종목']} ({worst_stock['수익률(%)']:.2f}%)")
        
        with col2:
            # 포트폴리오 요약 통계
            st.subheader("📈 포트폴리오 통계")
            st.write(f"보유 종목 수: {len(df)}개")
            st.write(f"평균 수익률: {df['수익률(%)'].mean():.2f}%")
            st.write(f"수익률 표준편차: {df['수익률(%)'].std():.2f}%")
            
            positive_stocks = (df["수익률(%)"] > 0).sum()
            st.write(f"수익 종목: {positive_stocks}/{len(df)}개")

# 🔔 알림/경고 기능
st.markdown("---")
st.subheader("🔔 포트폴리오 알림")

if st.session_state.stocks:
    df = pd.DataFrame(st.session_state.stocks)
    df["평가금액"] = df["현재가"] * df["수량"]
    
    warnings = []
    
    # 손실 경고
    loss_stocks = df[df["수익률(%)"] < -10]
    if not loss_stocks.empty:
        warnings.append("⚠️ **10% 이상 손실 종목**")
        for _, stock in loss_stocks.iterrows():
            warnings.append(f"   - {stock['종목']}: {stock['수익률(%)']:.2f}%")
    
    # 집중도 경고 (한 종목이 50% 이상)
    total_value = df["평가금액"].sum()
    if total_value > 0:
        df["비중"] = df["평가금액"] / total_value * 100
        concentrated_stocks = df[df["비중"] > 50]
        if not concentrated_stocks.empty:
            warnings.append("⚠️ **과도한 집중 투자 (50% 이상)**")
            for _, stock in concentrated_stocks.iterrows():
                warnings.append(f"   - {stock['종목']}: {stock['비중']:.1f}%")
    
    if warnings:
        for warning in warnings:
            st.warning(warning)
    else:
        st.success("✅ 포트폴리오 상태가 양호합니다!")

# 앱 정보
st.markdown("---")
with st.expander("ℹ️ 앱 정보 및 사용법"):
    st.markdown("""
    ### 🚀 주요 기능
    - **포트폴리오 관리**: 종목 추가/수정/삭제, 매수/매도 기록
    - **실시간 데이터**: 현재가 자동 조회 및 수익률 계산
    - **시각화**: 다양한 차트로 포트폴리오 분석
    - **데이터 저장**: 일별 포트폴리오 히스토리 관리
    - **AI 추천**: GPT용 포트폴리오 분석 문장 자동 생성
    - **목표 관리**: 종목별 목표수익률, 손절선, 익절선 설정
    - **리밸런싱**: 목표 비중 대비 현재 비중 분석 및 제안
    - **시장 비교**: S&P 500, NASDAQ, 다우존스 대비 성과 분석
    - **배당 추적**: 종목별 배당 수익률 및 예상 배당금 계산
    - **모바일 지원**: 스마트폰에서도 편리하게 사용 가능
    
    ### 💡 사용 팁
    - 매일 포트폴리오를 저장하여 수익률 추이를 확인하세요
    - 현재가 업데이트 버튼으로 최신 데이터를 반영하세요
    - 섹터별 분산투자 현황을 확인하여 리스크를 관리하세요
    - 거래내역을 꾸준히 기록하여 투자 패턴을 분석하세요
    - 목표 설정을 통해 체계적인 투자 계획을 수립하세요
    - 시장 지수와 비교하여 포트폴리오 성과를 객관적으로 평가하세요
    - 모바일 모드를 활용하여 언제 어디서나 포트폴리오를 확인하세요
    
    ### 🔧 구현된 모든 기능
    - ✅ 포트폴리오 불러오기 기능
    - ✅ 매수/매도 기록 기능  
    - ✅ 클립보드 복사 대신 파일 다운로드 제공
    - ✅ 실시간 현재가 업데이트
    - ✅ 포트폴리오 분석 및 알림 기능
    - ✅ 목표 수익률/손절선/익절선 설정
    - ✅ 배당금 추적 기능
    - ✅ 리밸런싱 제안 시스템
    - ✅ 시장 지수 대비 성과 분석
    - ✅ 모바일 친화적 반응형 디자인
    """)