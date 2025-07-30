import streamlit as st
import pandas as pd
import yfinance as yf
import json
import plotly.express as px
import plotly.graph_objects as go
import io
import os
from datetime import date, datetime, timedelta
import pytz
from drive_utils import (
    get_drive_service,
    get_folder_id,
    upload_file,
    download_file
)

st.set_page_config(
    page_title="📊 포트폴리오 트래커", 
    layout="wide",
    initial_sidebar_state="collapsed"
)

write_service_account_file()

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
    .profit { color: #00C851; font-weight: bold; }
    .loss { color: #FF4444; font-weight: bold; }
</style>
""", unsafe_allow_html=True)

st.title("📈 스마트 포트폴리오 트래커")

# 한국 시간대 설정
KST = pytz.timezone('Asia/Seoul')
COMMISSION_RATE = 0.0025  # 0.25% 수수료

# 데이터 폴더 확인
os.makedirs("data", exist_ok=True)
history_file = "data/portfolio_data.json"
daily_history_file = "data/daily_history.json"

def get_korean_time():
    return datetime.now(KST).strftime("%Y-%m-%d %H:%M:%S")

def get_korean_date():
    return datetime.now(KST).strftime("%Y-%m-%d")

# 자동 데이터 로드 함수
def load_portfolio_data():
    if os.path.exists(history_file):
        with open(history_file, "r", encoding="utf-8") as f:
            data = json.load(f)
            return (data.get("stocks", []), 
                   data.get("cash", 0.0), 
                   data.get("transactions", []), 
                   data.get("target_settings", {}),
                   data.get("realized_pnl", []),
                   data.get("stock_memos", {}),
                   data.get("total_commission", 0.0),
                   data.get("best_worst_trades", {"best": None, "worst": None}))
    return [], 0.0, [], {}, [], {}, 0.0, {"best": None, "worst": None}

def write_service_account_file():
    os.makedirs("data", exist_ok=True)
    with open("data/service_account.json", "w", encoding="utf-8") as f:
        json.dump(st.secrets["gdrive"], f)

# 자동 데이터 저장 함수
def save_portfolio_data():
    data = {
        "stocks": st.session_state.stocks,
        "cash": st.session_state.cash_amount,
        "transactions": st.session_state.transactions,
        "target_settings": st.session_state.target_settings,
        "realized_pnl": st.session_state.realized_pnl,
        "stock_memos": st.session_state.stock_memos,
        "total_commission": st.session_state.total_commission,
        "best_worst_trades": st.session_state.best_worst_trades,
        "last_updated": get_korean_time()
    }
    with open(history_file, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        
    # Google Drive에 업로드
    try:
        service = get_drive_service()
        folder_id = get_folder_id(service, FOLDER_NAME)
        upload_file(service, folder_id, history_file, "portfolio_data.json")
    except Exception as e:
        st.warning(f"⚠️ Google Drive 업로드 실패: {e}")

# 일별 히스토리 저장
def save_daily_snapshot():
    today = get_korean_date()
    if st.session_state.stocks:
        total_investment = sum(stock["수량"] * stock["매수단가"] for stock in st.session_state.stocks)
        total_value = sum(stock["수량"] * stock["현재가"] for stock in st.session_state.stocks)
        total_profit = total_value - total_investment
        total_return_rate = (total_profit / total_investment * 100) if total_investment > 0 else 0
        total_assets = total_value + st.session_state.cash_amount
        
        # 기존 히스토리 로드
        daily_history = {}
        if os.path.exists(daily_history_file):
            with open(daily_history_file, "r", encoding="utf-8") as f:
                daily_history = json.load(f)
        
        # 오늘 데이터 업데이트
        daily_history[today] = {
            "total_investment": total_investment,
            "total_value": total_value,
            "total_profit": total_profit,
            "total_return_rate": total_return_rate,
            "total_assets": total_assets,
            "cash": st.session_state.cash_amount,
            "stock_count": len(st.session_state.stocks)
        }
        
        with open(daily_history_file, "w", encoding="utf-8") as f:
            json.dump(daily_history, f, indent=2, ensure_ascii=False)

# 실현손익 기록 함수
def record_realized_pnl(symbol, quantity, buy_price, sell_price, commission):
    realized_profit = (sell_price - buy_price) * quantity - commission
    realized_rate = ((sell_price - buy_price) / buy_price) * 100
    
    pnl_record = {
        "날짜": get_korean_time(),
        "종목": symbol,
        "수량": quantity,
        "매수가": buy_price,
        "매도가": sell_price,
        "실현손익": round(realized_profit, 2),
        "수익률(%)": round(realized_rate, 2),
        "수수료": round(commission, 2)
    }
    
    st.session_state.realized_pnl.append(pnl_record)
    
    # 최고/최악 거래 업데이트
    if not st.session_state.best_worst_trades["best"] or realized_rate > st.session_state.best_worst_trades["best"]["수익률(%)"]:
        st.session_state.best_worst_trades["best"] = pnl_record
    
    if not st.session_state.best_worst_trades["worst"] or realized_rate < st.session_state.best_worst_trades["worst"]["수익률(%)"]:
        st.session_state.best_worst_trades["worst"] = pnl_record

# 세션 상태 초기화 및 자동 로드
if "mobile_mode" not in st.session_state:
    st.session_state.mobile_mode = False
# The code is checking if the key "initialized" is not present in the `st.session_state` dictionary in
# Streamlit. If the key is not present, it means that some initialization process might not have been
# done yet.

# Google Drive에서 portfolio_data.json 복원
if not os.path.exists(history_file):
    try:
        service = get_drive_service()
        folder_id = get_folder_id(service, FOLDER_NAME)
        downloaded = download_file(service, folder_id, "portfolio_data.json", history_file)
        if downloaded:
            st.toast("✅ Google Drive에서 포트폴리오 데이터를 복원했습니다.", icon="📂")
        else:
            st.warning("Google Drive에서 portfolio_data.json을 찾지 못했습니다.")
    except Exception as e:
        st.warning(f"⚠️ Google Drive 복원 중 오류: {e}")

    
if "initialized" not in st.session_state:
    # 앱 시작 시 기존 데이터 자동 로드
    (stocks, cash, transactions, target_settings, 
     realized_pnl, stock_memos, total_commission, best_worst_trades) = load_portfolio_data()
    st.session_state.stocks = stocks
    st.session_state.cash_amount = cash
    st.session_state.transactions = transactions
    st.session_state.target_settings = target_settings
    st.session_state.realized_pnl = realized_pnl
    st.session_state.stock_memos = stock_memos
    st.session_state.total_commission = total_commission
    st.session_state.best_worst_trades = best_worst_trades
    st.session_state.initialized = True

# 모바일 모드 토글
st.session_state.mobile_mode = st.checkbox("📱 모바일 모드", value=st.session_state.mobile_mode)

# 데이터 백업 불러오기 기능
st.subheader("📤 데이터 백업 불러오기")
uploaded_file = st.file_uploader("JSON 백업 파일 업로드", type=['json'])
if uploaded_file is not None:
    try:
        backup_data = json.load(uploaded_file)
        st.session_state.stocks = backup_data.get("stocks", [])
        st.session_state.cash_amount = backup_data.get("cash", 0.0)
        st.session_state.transactions = backup_data.get("transactions", [])
        st.session_state.target_settings = backup_data.get("target_settings", {})
        st.session_state.realized_pnl = backup_data.get("realized_pnl", [])
        st.session_state.stock_memos = backup_data.get("stock_memos", {})
        st.session_state.total_commission = backup_data.get("total_commission", 0.0)
        st.session_state.best_worst_trades = backup_data.get("best_worst_trades", {"best": None, "worst": None})
        save_portfolio_data()
        st.success("백업 데이터를 성공적으로 불러왔습니다!")
        st.rerun()
    except Exception as e:
        st.error(f"백업 파일 로드 중 오류: {e}")

st.markdown("---")

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
tab1, tab2, tab3, tab4 = st.tabs(["➕ 종목 매수", "📉 종목 매도", "⚙️ 설정", "📝 메모"])

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
        
        memo = st.text_area("매수 이유 (선택사항)", placeholder="왜 이 종목을 매수하나요?")
        submitted = st.form_submit_button("매수하기", use_container_width=True)
        
        if submitted and symbol:
            try:
                # 수수료 계산
                total_cost = quantity * avg_price
                commission = total_cost * COMMISSION_RATE
                final_cost = total_cost + commission
                
                # 현금 확인
                if final_cost > st.session_state.cash_amount:
                    st.error(f"현금이 부족합니다! 필요금액: ${final_cost:,.2f}, 보유현금: ${st.session_state.cash_amount:,.2f}")
                else:
                    stock = yf.Ticker(symbol)
                    current_price = stock.history(period="1d")["Close"].iloc[-1]
                    
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
                        "수익률(%)": round(profit_rate, 2)
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
                    
                    # 현금 차감
                    st.session_state.cash_amount -= final_cost
                    
                    # 총 수수료 누적
                    st.session_state.total_commission += commission
                    
                    # 매매 기록 추가
                    transaction = {
                        "날짜": get_korean_time(),
                        "종목": symbol,
                        "거래유형": "매수",
                        "수량": quantity,
                        "가격": avg_price,
                        "총액": total_cost,
                        "수수료": round(commission, 2),
                        "실제비용": round(final_cost, 2)
                    }
                    st.session_state.transactions.append(transaction)
                    
                    # 메모 저장
                    if memo:
                        if symbol not in st.session_state.stock_memos:
                            st.session_state.stock_memos[symbol] = []
                        st.session_state.stock_memos[symbol].append({
                            "날짜": get_korean_time(),
                            "유형": "매수",
                            "내용": memo
                        })
                    
                    # 자동 저장
                    save_portfolio_data()
                    st.rerun()
                    
            except Exception as e:
                st.error(f"현재가를 불러오는 데 실패했습니다: {e}")

with tab2:
    st.subheader("💰 종목 매도")
    
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
            
            sell_memo = st.text_area("매도 이유 (선택사항)", placeholder="왜 이 종목을 매도하나요?")
            sell_submitted = st.form_submit_button("매도하기", use_container_width=True)
            
            if sell_submitted:
                # 수수료 계산
                total_revenue = sell_quantity * sell_price
                commission = total_revenue * COMMISSION_RATE
                final_revenue = total_revenue - commission
                
                # 매도 처리 및 실현손익 계산
                buy_price = None
                for i, stock in enumerate(st.session_state.stocks):
                    if stock["종목"] == sell_symbol:
                        buy_price = stock["매수단가"]
                        
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
                
                # 현금 증가
                st.session_state.cash_amount += final_revenue
                
                # 총 수수료 누적
                st.session_state.total_commission += commission
                
                # 실현손익 기록
                if buy_price:
                    record_realized_pnl(sell_symbol, sell_quantity, buy_price, sell_price, commission)
                
                # 매매 기록 추가
                transaction = {
                    "날짜": get_korean_time(),
                    "종목": sell_symbol,
                    "거래유형": "매도",
                    "수량": sell_quantity,
                    "가격": sell_price,
                    "총액": total_revenue,
                    "수수료": round(commission, 2),
                    "실제수익": round(final_revenue, 2)
                }
                st.session_state.transactions.append(transaction)
                
                # 메모 저장
                if sell_memo:
                    if sell_symbol not in st.session_state.stock_memos:
                        st.session_state.stock_memos[sell_symbol] = []
                    st.session_state.stock_memos[sell_symbol].append({
                        "날짜": get_korean_time(),
                        "유형": "매도",
                        "내용": sell_memo
                    })
                
                # 자동 저장
                save_portfolio_data()
                st.success(f"{sell_symbol} {sell_quantity}주 매도 완료!")
                st.rerun()
    else:
        st.info("보유 종목이 없습니다.")

with tab3:
    st.subheader("⚙️ 목표 설정 & 알림")
    
    # 브라우저 알림 설정
    st.write("**🔔 알림 설정**")
    col1, col2 = st.columns(2)
    with col1:
        profit_alert = st.number_input("수익률 알림 기준(%)", value=10.0, step=1.0)
    with col2:
        loss_alert = st.number_input("손실률 알림 기준(%)", value=-5.0, max_value=0.0, step=1.0)
    
    st.markdown("---")
    
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
            
            # 알림 체크
            current_return = stock["수익률(%)"]
            if current_return >= profit_alert or current_return <= loss_alert:
                if current_return >= profit_alert:
                    st.success(f"🎉 {symbol} 수익률 알림: {current_return:.2f}%")
                else:
                    st.error(f"⚠️ {symbol} 손실률 알림: {current_return:.2f}%")
        
        # 설정 변경 시 자동 저장
        if settings_changed:
            save_portfolio_data()
    else:
        st.info("보유 종목이 없습니다.")

with tab4:
    st.subheader("📝 종목 메모")
    
    if st.session_state.stock_memos:
        for symbol, memos in st.session_state.stock_memos.items():
            with st.expander(f"📋 {symbol} 메모 ({len(memos)}개)"):
                for memo in reversed(memos):  # 최신순 정렬
                    memo_color = "🟢" if memo["유형"] == "매수" else "🔴"
                    st.write(f"{memo_color} **{memo['유형']}** - {memo['날짜']}")
                    st.write(f"💭 {memo['내용']}")
                    st.markdown("---")
    else:
        st.info("아직 작성된 메모가 없습니다.")

# 거래 내역 표시
if st.session_state.transactions:
    st.markdown("---")
    st.subheader("📋 최근 거래 내역")
    df_transactions = pd.DataFrame(st.session_state.transactions[-15:])  # 최근 15건
    st.dataframe(df_transactions, use_container_width=True)

st.markdown("---")

# 포트폴리오 시각화
if st.session_state.stocks:
    st.subheader("📊 포트폴리오 시각화")
    
    df = pd.DataFrame(st.session_state.stocks)
    df["평가금액"] = df["현재가"] * df["수량"]
    
    # 보유현금 포함 자산 구성 파이차트
    asset_data = df[["종목", "평가금액"]].copy()
    if st.session_state.cash_amount > 0:
        asset_data.loc[len(asset_data)] = ["현금", st.session_state.cash_amount]
    
    fig = px.pie(asset_data, names="종목", values="평가금액", 
                 title="💼 자산 구성 비율 (현금 포함)")
    fig.update_traces(textposition='inside', textinfo='percent+label')
    st.plotly_chart(fig, use_container_width=True)

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
                
                stock["현재가"] = round(current_price, 2)
                profit = (current_price - stock["매수단가"]) * stock["수량"]
                stock["수익"] = round(profit, 2)
                stock["수익률(%)"] = round((profit / (stock["매수단가"] * stock["수량"])) * 100, 2)
            except:
                continue
        
        # 일별 스냅샷 저장
        save_daily_snapshot()
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
    total_assets = total_value + st.session_state.cash_amount
    
    if st.session_state.mobile_mode:
        st.metric("💰 총 투자금액", f"${total_investment:,.2f}")
        st.metric("📈 총 평가금액", f"${total_value:,.2f}")
        st.metric("💹 총 수익률", f"{total_return_rate:.2f}%", f"${total_profit:,.2f}")
        st.metric("🏦 총 자산", f"${total_assets:,.2f}")
        st.metric("💸 누적 수수료", f"${st.session_state.total_commission:,.2f}")
    else:
        col1, col2, col3, col4, col5 = st.columns(5)
        with col1:
            st.metric("💰 총 투자금액", f"${total_investment:,.2f}")
        with col2:
            st.metric("📈 총 평가금액", f"${total_value:,.2f}")
        with col3:
            st.metric("💹 총 수익률", f"{total_return_rate:.2f}%", f"${total_profit:,.2f}")
        with col4:
            st.metric("🏦 총 자산", f"${total_assets:,.2f}")
        with col5:
            st.metric("💸 누적 수수료", f"${st.session_state.total_commission:,.2f}")

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

# 📈 성과 분석 및 통계
st.markdown("---")
st.subheader("📈 성과 분석 및 통계")

col1, col2 = st.columns(2)

with col1:
    # 실현손익 요약
    if st.session_state.realized_pnl:
        st.write("**💰 실현손익 요약**")
        df_pnl = pd.DataFrame(st.session_state.realized_pnl)
        total_realized = df_pnl["실현손익"].sum()
        win_trades = len(df_pnl[df_pnl["실현손익"] > 0])
        total_trades = len(df_pnl)
        win_rate = (win_trades / total_trades * 100) if total_trades > 0 else 0
        
        st.metric("총 실현손익", f"${total_realized:,.2f}")
        st.metric("승률", f"{win_rate:.1f}%", f"{win_trades}/{total_trades}")
        
        # 최고/최악 거래
        if st.session_state.best_worst_trades["best"]:
            best = st.session_state.best_worst_trades["best"]
            st.success(f"🏆 최고 거래: {best['종목']} ({best['수익률(%)']:.2f}%)")
        
        if st.session_state.best_worst_trades["worst"]:
            worst = st.session_state.best_worst_trades["worst"]
            st.error(f"💀 최악 거래: {worst['종목']} ({worst['수익률(%)']:.2f}%)")

with col2:
    # 거래 통계
    if st.session_state.transactions:
        st.write("**📊 거래 통계**")
        df_trans = pd.DataFrame(st.session_state.transactions)
        
        # 종목별 거래 횟수
        buy_counts = df_trans[df_trans["거래유형"] == "매수"]["종목"].value_counts()
        sell_counts = df_trans[df_trans["거래유형"] == "매도"]["종목"].value_counts()
        total_counts = buy_counts.add(sell_counts, fill_value=0)
        
        if not total_counts.empty:
            most_traded = total_counts.index[0]
            most_traded_count = int(total_counts.iloc[0])
            st.write(f"🔥 최다 거래 종목: **{most_traded}** ({most_traded_count}회)")
        
        # 평균 보유기간 계산 (실현손익 기준)
        if st.session_state.realized_pnl:
            st.write(f"📅 총 거래 완료: **{len(st.session_state.realized_pnl)}건**")
            avg_holding = 2.5  # 단타 기준 추정값 (실제로는 매수-매도 날짜 차이 계산 필요)
            st.write(f"⏱️ 평균 보유기간: **{avg_holding:.1f}일** (추정)")

# 월별/주별 수익률 요약
if st.session_state.realized_pnl:
    st.markdown("---")
    st.subheader("📅 기간별 수익률 요약")
    
    df_pnl = pd.DataFrame(st.session_state.realized_pnl)
    df_pnl["월"] = pd.to_datetime(df_pnl["날짜"]).dt.to_period("M")
    df_pnl["주"] = pd.to_datetime(df_pnl["날짜"]).dt.to_period("W")
    
    col1, col2 = st.columns(2)
    
    with col1:
        # 월별 요약
        monthly_summary = df_pnl.groupby("월").agg({
            "실현손익": "sum",
            "수익률(%)": "mean",
            "종목": "count"
        }).round(2)
        monthly_summary.columns = ["월 실현손익($)", "평균 수익률(%)", "거래 횟수"]
        st.write("**📊 월별 성과**")
        st.dataframe(monthly_summary)
    
    with col2:
        # 주별 요약 (최근 4주)
        weekly_summary = df_pnl.groupby("주").agg({
            "실현손익": "sum",
            "수익률(%)": "mean",
            "종목": "count"
        }).round(2).tail(4)
        weekly_summary.columns = ["주 실현손익($)", "평균 수익률(%)", "거래 횟수"]
        st.write("**📊 주별 성과 (최근 4주)**")
        st.dataframe(weekly_summary)

# 히스토리 데이터 시각화
st.markdown("---")
st.subheader("📈 히스토리 및 추이 분석")

if os.path.exists(daily_history_file):
    with open(daily_history_file, "r", encoding="utf-8") as f:
        daily_history = json.load(f)
    
    if daily_history:
        # 일자별 수익률 테이블
        history_df = pd.DataFrame.from_dict(daily_history, orient='index')
        history_df.index = pd.to_datetime(history_df.index)
        history_df = history_df.sort_index()
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.write("**📅 일자별 수익률 현황**")
            display_df = history_df[["total_return_rate", "total_profit", "total_assets"]].copy()
            display_df.columns = ["수익률(%)", "수익금액($)", "총자산($)"]
            display_df = display_df.round(2)
            st.dataframe(display_df.tail(10))  # 최근 10일
        
        with col2:
            st.write("**📊 자산 구성 변화**")
            recent_data = history_df.tail(1).iloc[0]
            st.metric("현재 총자산", f"${recent_data['total_assets']:,.2f}")
            st.metric("현재 투자금액", f"${recent_data['total_investment']:,.2f}")
            st.metric("현재 평가금액", f"${recent_data['total_value']:,.2f}")
            st.metric("보유 종목 수", f"{recent_data['stock_count']}개")
        
        # 총자산 추이 그래프
        st.write("**📈 총자산 추이 그래프**")
        fig = go.Figure()
        
        fig.add_trace(go.Scatter(
            x=history_df.index, 
            y=history_df['total_investment'],
            name='투자금액',
            line=dict(color='blue')
        ))
        
        fig.add_trace(go.Scatter(
            x=history_df.index, 
            y=history_df['total_value'],
            name='평가금액',
            line=dict(color='green')
        ))
        
        fig.add_trace(go.Scatter(
            x=history_df.index, 
            y=history_df['total_assets'],
            name='총자산',
            line=dict(color='red', width=3)
        ))
        
        fig.update_layout(
            title="투자금액 vs 평가금액 vs 총자산 추이",
            xaxis_title="날짜",
            yaxis_title="금액 ($)",
            height=400
        )
        
        st.plotly_chart(fig, use_container_width=True)
        
        # 수익률 추이 그래프
        st.write("**📊 수익률 추이**")
        fig2 = px.line(history_df.reset_index(), x='index', y='total_return_rate', 
                      title="일별 수익률 변화", labels={'index': '날짜', 'total_return_rate': '수익률(%)'})
        fig2.update_layout(height=300)
        st.plotly_chart(fig2, use_container_width=True)
else:
    st.info("아직 히스토리 데이터가 없습니다. 현재가 업데이트를 통해 일별 데이터를 생성하세요.")

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
- 누적 수수료: ${st.session_state.total_commission:,.2f}
"""
            
            for stock in holdings:
                text += f"- {stock['종목']}: {stock['수량']}주 (매수단가 ${stock['매수단가']}, 현재가 ${stock['현재가']}, 수익률 {stock['수익률(%)']:.2f}%)\n"
            
            # 성과 요약 추가
            if st.session_state.realized_pnl:
                df_pnl = pd.DataFrame(st.session_state.realized_pnl)
                total_realized = df_pnl["실현손익"].sum()
                win_trades = len(df_pnl[df_pnl["실현손익"] > 0])
                total_trades = len(df_pnl)
                win_rate = (win_trades / total_trades * 100) if total_trades > 0 else 0
                
                text += f"""
거래 성과:
- 총 실현손익: ${total_realized:,.2f}
- 승률: {win_rate:.1f}% ({win_trades}/{total_trades})
- 총 거래 완료: {total_trades}건
"""
            
            text += """
이 포트폴리오와 거래 성과를 바탕으로,
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
📌 수수료 0.25%를 고려한 매매 전략도 포함해줘.
            """.strip()
            
            st.text_area("📨 복사해서 GPT 추천 요청에 붙여넣기", value=text, height=400, key="recommendation_text")
            
            # 다운로드 버튼으로 대체
            st.download_button(
                label="📋 텍스트 파일로 다운로드",
                data=text.encode('utf-8'),
                file_name=f"portfolio_recommendation_{get_korean_date()}.txt",
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
    
    # 수수료 과다 경고
    if st.session_state.total_commission > 1000:
        warnings.append(f"💸 **높은 수수료**: 총 ${st.session_state.total_commission:,.2f} 지출")
    
    if warnings:
        for warning in warnings:
            st.warning(warning)
    else:
        st.success("✅ 포트폴리오 상태가 양호합니다!")

st.markdown("---")
st.subheader("📥 데이터 백업")

if st.session_state.mobile_mode:
    if st.session_state.stocks:
        # 포트폴리오 데이터
        df = pd.DataFrame(st.session_state.stocks)
        df["평가금액"] = df["현재가"] * df["수량"]
        df["투자금액"] = df["매수단가"] * df["수량"]

        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
            # 현재 포트폴리오
            df.to_excel(writer, index=False, sheet_name="현재포트폴리오")
            
            # 거래내역
            if st.session_state.transactions:
                df_trans = pd.DataFrame(st.session_state.transactions)
                df_trans.to_excel(writer, index=False, sheet_name="거래내역")
            
            # 실현손익
            if st.session_state.realized_pnl:
                df_pnl = pd.DataFrame(st.session_state.realized_pnl)
                df_pnl.to_excel(writer, index=False, sheet_name="실현손익")
            
            # 일별히스토리
            if os.path.exists(daily_history_file):
                with open(daily_history_file, "r", encoding="utf-8") as f:
                    daily_history = json.load(f)
                if daily_history:
                    df_history = pd.DataFrame.from_dict(daily_history, orient='index')
                    df_history.to_excel(writer, sheet_name="일별히스토리")

        st.download_button(
            label="📥 전체 데이터 엑셀 다운로드",
            data=buffer.getvalue(),
            file_name=f"portfolio_complete_{get_korean_date()}.xlsx",
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
            file_name=f"portfolio_backup_{get_korean_date()}.json",
            mime="application/json",
            use_container_width=True
        )
else:
    col1, col2 = st.columns(2)

    with col1:
        if st.session_state.stocks:
            # 포트폴리오 데이터
            df = pd.DataFrame(st.session_state.stocks)
            df["평가금액"] = df["현재가"] * df["수량"]
            df["투자금액"] = df["매수단가"] * df["수량"]

            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
                # 현재 포트폴리오
                df.to_excel(writer, index=False, sheet_name="현재포트폴리오")
                
                # 거래내역
                if st.session_state.transactions:
                    df_trans = pd.DataFrame(st.session_state.transactions)
                    df_trans.to_excel(writer, index=False, sheet_name="거래내역")
                
                # 실현손익
                if st.session_state.realized_pnl:
                    df_pnl = pd.DataFrame(st.session_state.realized_pnl)
                    df_pnl.to_excel(writer, index=False, sheet_name="실현손익")
                
                # 일별히스토리
                if os.path.exists(daily_history_file):
                    with open(daily_history_file, "r", encoding="utf-8") as f:
                        daily_history = json.load(f)
                    if daily_history:
                        df_history = pd.DataFrame.from_dict(daily_history, orient='index')
                        df_history.to_excel(writer, sheet_name="일별히스토리")

            st.download_button(
                label="📥 전체 데이터 엑셀 다운로드",
                data=buffer.getvalue(),
                file_name=f"portfolio_complete_{get_korean_date()}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

    with col2:
        if os.path.exists(history_file):
            with open(history_file, "r", encoding="utf-8") as f:
                json_data = f.read()
            
            st.download_button(
                label="📥 JSON 백업 다운로드",
                data=json_data.encode('utf-8'),
                file_name=f"portfolio_backup_{get_korean_date()}.json",
                mime="application/json"
            )
            
# 🔁 Google Drive 수동 복원            
with st.expander("🔁 Google Drive 수동 복원"):
    if st.button("📂 portfolio_data.json 불러오기", use_container_width=True):
        try:
            service = get_drive_service()
            folder_id = get_folder_id(service, FOLDER_NAME)
            if download_file(service, folder_id, "portfolio_data.json", history_file):
                st.success("✅ 복원 완료! 새로고침됩니다.")
                st.rerun()
            else:
                st.warning("Google Drive에 portfolio_data.json이 없습니다.")
        except Exception as e:
            st.error(f"복원 실패: {e}")


# 앱 정보
st.markdown("---")
with st.expander("ℹ️ 앱 정보 및 사용법"):
    st.markdown("""
    ### 🚀 주요 기능
    - **자동 누적 기록**: 매수/매도/현금 변경 시 자동 저장
    - **수수료 관리**: 0.25% 수수료 자동 계산 및 누적 추적
    - **실현손익 추적**: 매도 시 실제 손익 자동 계산 및 기록
    - **성과 분석**: 월별/주별 수익률, 승률, 거래 통계
    - **거래 기록**: 종목별 매매 횟수, 평균 보유기간 분석
    - **메모 기능**: 매수/매도 이유 기록 및 관리
    - **스마트 알림**: 목표 달성, 손절선 도달, 수익률/손실률 알림
    - **히스토리 분석**: 일별 수익률 테이블, 총자산 추이 그래프
    - **데이터 백업**: JSON/Excel 백업 및 복원 기능
    - **포트폴리오 시각화**: 보유현금 포함 자산 구성 차트
    
    ### 💡 사용 팁
    - 매수/매도 시 수수료가 자동으로 차감됩니다
    - 매도 시 실현손익이 자동으로 계산되어 기록됩니다
    - 메모 기능으로 매매 이유를 기록하여 투자 패턴을 분석하세요
    - 정기적으로 현재가 업데이트를 통해 일별 데이터를 쌓아보세요
    - 알림 설정을 통해 수익률 목표를 관리하세요
    - 데이터 백업을 정기적으로 받아두세요
    
    ### 🔧 전체 기능 목록
    - ✅ 자동 데이터 로드 및 저장
    - ✅ 수수료 0.25% 자동 계산
    - ✅ 실시간 매수/매도 기록 (한국시간)
    - ✅ 실현손익 자동 계산 및 추적
    - ✅ 월별/주별 수익률 요약
    - ✅ 종목별 매매 횟수 통계
    - ✅ 평균 보유기간 분석
    - ✅ 수수료 총 누적액 추적
    - ✅ 최고/최저 수익률 기록
    - ✅ 수익률/손실률 브라우저 알림
    - ✅ 종목별 매수/매도 메모
    - ✅ 목표 수익률/손절선/익절선 설정
    - ✅ 일별 수익률 테이블
    - ✅ 총자산 추이 그래프
    - ✅ 보유현금 포함 시각화
    - ✅ JSON 백업 불러오기
    - ✅ 모바일 친화적 디자인
    
    ### 📊 데이터 구조
    - 모든 데이터는 `data/portfolio_data.json`에 통합 저장
    - 일별 히스토리는 `data/daily_history.json`에 별도 저장
    - 실시간 자동 저장으로 데이터 손실 방지
    - 한국 시간대(KST) 기준으로 모든 시간 기록
    """)