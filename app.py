import streamlit as st
import pandas as pd
import yfinance as yf
import json
import io
import os
from datetime import date, datetime

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

# 데이터 폴더 확인
os.makedirs("data", exist_ok=True)
history_file = "data/portfolio_data.json"
settings_file = "data/settings.json"

# 자동 데이터 로드 함수
def load_portfolio_data():
    if os.path.exists(history_file):
        with open(history_file, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data.get("stocks", []), data.get("cash", 0.0), data.get("transactions", []), data.get("target_settings", {})
    return [], 0.0, [], {}

# 자동 데이터 저장 함수
def save_portfolio_data():
    data = {
        "stocks": st.session_state.stocks,
        "cash": st.session_state.cash_amount,
        "transactions": st.session_state.transactions,
        "target_settings": st.session_state.target_settings,
        "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    with open(history_file, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

# 세션 상태 초기화 및 자동 로드
if "mobile_mode" not in st.session_state:
    st.session_state.mobile_mode = False
if "initialized" not in st.session_state:
    # 앱 시작 시 기존 데이터 자동 로드
    stocks, cash, transactions, target_settings = load_portfolio_data()
    st.session_state.stocks = stocks
    st.session_state.cash_amount = cash
    st.session_state.transactions = transactions
    st.session_state.target_settings = target_settings
    st.session_state.initialized = True

# 모바일 모드 토글
st.session_state.mobile_mode = st.checkbox("📱 모바일 모드", value=st.session_state.mobile_mode)

# 💰 보유 현금 입력
st.subheader("💰 보유 현금")
new_cash = st.number_input("보유 현금 ($)", min_value=0.0, step=100.0, format="%.2f", value=st.session_state.cash_amount, key="main_cash_input")

# 현금 변경 시 자동 저장
if new_cash != st.session_state.cash_amount:
    st.session_state.cash_amount = new_cash
    save_portfolio_data()

st.markdown("---")

# 📝 종목 관리
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
        
        submitted = st.form_submit_button("매수하기", use_container_width=True)
        
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
                    st.success(f"{symbol} 매수 완료!")
                
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
                
                # 자동 저장
                save_portfolio_data()
                st.rerun()
                
            except Exception as e:
                st.error(f"현재가를 불러오는 데 실패했습니다: {e}")

with tab2:
    st.subheader("💰 매도 기록")
    
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
                
                # 자동 저장
                save_portfolio_data()
                st.success(f"{sell_symbol} {sell_quantity}주 매도 완료!")
                st.rerun()
    else:
        st.info("보유 종목이 없습니다.")

with tab3:
    st.subheader("⚙️ 목표 설정")
    
    # 목표 수익률 설정
    st.write("**🎯 종목별 목표 설정**")
    if st.session_state.stocks:
        settings_changed = False
        for stock in st.session_state.stocks:
            symbol = stock["종목"]
            col1, col2, col3 = st.columns(3)
            
            with col1:
                target_return = st.number_input(
                    f"{symbol} 목표수익률(%)", 
                    value=st.session_state.target_settings.get(f"{symbol}_target", 20.0),
                    key=f"target_{symbol}"
                )
                if st.session_state.target_settings.get(f"{symbol}_target") != target_return:
                    st.session_state.target_settings[f"{symbol}_target"] = target_return
                    settings_changed = True
            
            with col2:
                stop_loss = st.number_input(
                    f"{symbol} 손절선(%)", 
                    value=st.session_state.target_settings.get(f"{symbol}_stop", -10.0),
                    max_value=0.0,
                    key=f"stop_{symbol}"
                )
                if st.session_state.target_settings.get(f"{symbol}_stop") != stop_loss:
                    st.session_state.target_settings[f"{symbol}_stop"] = stop_loss
                    settings_changed = True
            
            with col3:
                take_profit = st.number_input(
                    f"{symbol} 익절선(%)", 
                    value=st.session_state.target_settings.get(f"{symbol}_take", 25.0),
                    min_value=0.0,
                    key=f"take_{symbol}"
                )
                if st.session_state.target_settings.get(f"{symbol}_take") != take_profit:
                    st.session_state.target_settings[f"{symbol}_take"] = take_profit
                    settings_changed = True
        
        # 설정 변경 시 자동 저장
        if settings_changed:
            save_portfolio_data()
    else:
        st.info("보유 종목이 없습니다.")

# 거래 내역 표시
if st.session_state.transactions:
    st.markdown("---")
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
        
        # 업데이트 후 자동 저장
        save_portfolio_data()
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
    total_assets = total_value + st.session_state.cash_amount
    
    if st.session_state.mobile_mode:
        st.metric("💰 총 투자금액", f"${total_investment:,.2f}")
        st.metric("📈 총 평가금액", f"${total_value:,.2f}")
        st.metric("💹 총 수익률", f"{total_return_rate:.2f}%", f"${total_profit:,.2f}")
        st.metric("💵 연간 예상 배당금", f"${total_dividend:,.2f}")
        st.metric("🏦 총 자산", f"${total_assets:,.2f}")
    else:
        col1, col2, col3, col4, col5 = st.columns(5)
        with col1:
            st.metric("💰 총 투자금액", f"${total_investment:,.2f}")
        with col2:
            st.metric("📈 총 평가금액", f"${total_value:,.2f}")
        with col3:
            st.metric("💹 총 수익률", f"{total_return_rate:.2f}%", f"${total_profit:,.2f}")
        with col4:
            st.metric("💵 연간 예상 배당금", f"${total_dividend:,.2f}")
        with col5:
            st.metric("🏦 총 자산", f"${total_assets:,.2f}")

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
st.subheader("💡 종목 추천 문장 자동 생성")

if st.button("✍️ 추천 요청 문장 생성"):
    try:
        holdings = st.session_state.stocks
        if not holdings:
            st.warning("먼저 종목을 추가해주세요.")
        else:
            text = f"""현재 포트폴리오 구성은 다음과 같아:
- 보유 현금: ${st.session_state.cash_amount:,.2f}
"""
            
            for stock in holdings:
                text += f"- {stock['종목']}: {stock['수량']}주 (매수단가 ${stock['매수단가']}, 현재가 ${stock['현재가']}, 수익률 {stock['수익률(%)']:.2f}%)\n"
            
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

# 🔔 알림/경고 기능
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

st.markdown("---")
st.subheader("📥 데이터 백업")

if st.session_state.mobile_mode:
    if st.session_state.stocks:
        df = pd.DataFrame(st.session_state.stocks)
        df["평가금액"] = df["현재가"] * df["수량"]
        df["투자금액"] = df["매수단가"] * df["수량"]

        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
            df.to_excel(writer, index=False, sheet_name="포트폴리오")
            if st.session_state.transactions:
                df_trans = pd.DataFrame(st.session_state.transactions)
                df_trans.to_excel(writer, index=False, sheet_name="거래내역")

        st.download_button(
            label="📥 전체 데이터 엑셀 다운로드",
            data=buffer.getvalue(),
            file_name=f"portfolio_backup_{date.today()}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True
        )
    
    # JSON 백업
    if os.path.exists(history_file):
        with open(history_file, "r", encoding="utf-8") as f:
            json_data = f.read()
        
        st.download_button(
            label="📥 JSON 백업 다운로드",
            data=json_data.encode('utf-8'),
            file_name=f"portfolio_backup_{date.today()}.json",
            mime="application/json",
            use_container_width=True
        )
else:
    col1, col2 = st.columns(2)

    with col1:
        if st.session_state.stocks:
            df = pd.DataFrame(st.session_state.stocks)
            df["평가금액"] = df["현재가"] * df["수량"]
            df["투자금액"] = df["매수단가"] * df["수량"]

            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
                df.to_excel(writer, index=False, sheet_name="포트폴리오")
                if st.session_state.transactions:
                    df_trans = pd.DataFrame(st.session_state.transactions)
                    df_trans.to_excel(writer, index=False, sheet_name="거래내역")

            st.download_button(
                label="📥 전체 데이터 엑셀 다운로드",
                data=buffer.getvalue(),
                file_name=f"portfolio_backup_{date.today()}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

    with col2:
        if os.path.exists(history_file):
            with open(history_file, "r", encoding="utf-8") as f:
                json_data = f.read()
            
            st.download_button(
                label="📥 JSON 백업 다운로드",
                data=json_data.encode('utf-8'),
                file_name=f"portfolio_backup_{date.today()}.json",
                mime="application/json"
            )

# 앱 정보
st.markdown("---")
with st.expander("ℹ️ 앱 정보 및 사용법"):
    st.markdown("""
    ### 🚀 주요 기능
    - **자동 누적 기록**: 매수/매도/현금 변경 시 자동 저장
    - **실시간 포트폴리오**: 현재가 업데이트 및 수익률 계산
    - **거래 내역 관리**: 모든 매수/매도 기록 자동 추적
    - **목표 관리**: 종목별 목표수익률, 손절선, 익절선 설정
    - **스마트 알림**: 목표 달성, 손절선 도달, 포트폴리오 위험 알림
    - **AI 추천**: GPT용 포트폴리오 분석 문장 자동 생성
    - **배당 추적**: 종목별 배당 수익률 및 예상 배당금 계산
    - **모바일 지원**: 스마트폰에서도 편리하게 사용 가능
    
    ### 💡 사용 팁
    - 앱을 시작하면 기존 데이터가 자동으로 로드됩니다
    - 매수/매도/현금 변경 시 자동으로 저장되므로 별도 저장 불필요
    - 현재가 업데이트 버튼으로 최신 데이터를 반영하세요
    - 목표 설정을 통해 체계적인 투자 계획을 수립하세요
    - 정기적으로 데이터 백업을 받아두세요
    
    ### 🔧 핵심 기능
    - ✅ 자동 데이터 로드 및 저장
    - ✅ 실시간 매수/매도 기록
    - ✅ 현재가 업데이트 및 수익률 계산
    - ✅ 목표 수익률/손절선/익절선 설정
    - ✅ 스마트 알림 시스템
    - ✅ 배당금 추적 기능
    - ✅ 보유 현금 관리
    - ✅ 포트폴리오 분석 및 경고
    - ✅ 모바일 친화적 디자인
    - ✅ 데이터 백업 기능
    
    ### 📝 데이터 구조
    - 모든 데이터는 `data/portfolio_data.json`에 자동 저장
    - 포트폴리오, 현금, 거래내역, 목표설정이 하나의 파일에 통합 관리
    - 실시간 자동 저장으로 데이터 손실 방지
    """)