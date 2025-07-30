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
import shutil
import time

st.set_page_config(
    page_title="📊 포트폴리오 트래커", 
    layout="wide",
    initial_sidebar_state="collapsed"
)

# CSS for mobile-friendly design + 복사 버튼 스타일
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
    
    /* 복사 버튼 스타일 */
    .copy-button {
        background: linear-gradient(90deg, #4CAF50, #45a049);
        color: white;
        border: none;
        padding: 8px 16px;
        border-radius: 4px;
        cursor: pointer;
        font-size: 14px;
        margin: 5px 0;
        width: 100%;
    }
    .copy-button:hover {
        background: linear-gradient(90deg, #45a049, #4CAF50);
    }
    
    /* 통화 토글 스타일 */
    .currency-toggle {
        background-color: #f0f2f6;
        padding: 10px;
        border-radius: 8px;
        margin: 10px 0;
    }
</style>

<script>
function copyToClipboard(text) {
    navigator.clipboard.writeText(text).then(function() {
        alert('텍스트가 클립보드에 복사되었습니다!');
    }, function(err) {
        console.error('복사 실패: ', err);
    });
}
</script>
""", unsafe_allow_html=True)

st.title("📈 스마트 포트폴리오 트래커")

# 한국 시간대 설정
KST = pytz.timezone('Asia/Seoul')
COMMISSION_RATE = 0.0025  # 0.25% 수수료

# USD to KRW 환율 (실시간 또는 고정값)
def get_usd_to_krw_rate():
    """USD to KRW 환율 가져오기"""
    try:
        # 실시간 환율 가져오기
        krw_ticker = yf.Ticker("KRW=X")
        rate = krw_ticker.history(period="1d")["Close"].iloc[-1]
        return rate
    except:
        # 실패 시 기본값 (대략적인 환율)
        return 1320.0  # 2024년 기준 대략적인 환율

# 통화 변환 함수들
def format_currency(amount, currency="USD", exchange_rate=1320.0):
    """금액을 선택된 통화로 포맷"""
    if currency == "KRW":
        krw_amount = amount * exchange_rate
        return f"₩{krw_amount:,.0f}"
    else:
        return f"${amount:,.2f}"

def get_currency_symbol(currency="USD"):
    """통화 기호 반환"""
    return "₩" if currency == "KRW" else "$"

# 다중 데이터 폴더 설정 (데이터 유실 방지)
PRIMARY_DATA_DIR = "data"
BACKUP_DATA_DIR = "data_backup"
SECONDARY_BACKUP_DIR = "data_backup2"

# 필요한 폴더들 생성
for folder in [PRIMARY_DATA_DIR, BACKUP_DATA_DIR, SECONDARY_BACKUP_DIR]:
    os.makedirs(folder, exist_ok=True)

# 파일 경로들
PRIMARY_FILE = os.path.join(PRIMARY_DATA_DIR, "portfolio_data.json")
BACKUP_FILE = os.path.join(BACKUP_DATA_DIR, "portfolio_data.json")
SECONDARY_BACKUP_FILE = os.path.join(SECONDARY_BACKUP_DIR, "portfolio_data.json")
DAILY_HISTORY_FILE = os.path.join(PRIMARY_DATA_DIR, "daily_history.json")

def get_korean_time():
    return datetime.now(KST).strftime("%Y-%m-%d %H:%M:%S")

def get_korean_date():
    return datetime.now(KST).strftime("%Y-%m-%d")

# 통화 설정 초기화
if "currency_mode" not in st.session_state:
    st.session_state.currency_mode = "USD"

if "exchange_rate" not in st.session_state:
    st.session_state.exchange_rate = get_usd_to_krw_rate()

# 통화 선택 위젯
st.markdown('<div class="currency-toggle">', unsafe_allow_html=True)
col_currency1, col_currency2, col_currency3 = st.columns([2, 2, 2])

with col_currency1:
    currency_mode = st.selectbox("💱 통화 선택", ["USD", "KRW"], 
                                index=0 if st.session_state.currency_mode == "USD" else 1)
    if currency_mode != st.session_state.currency_mode:
        st.session_state.currency_mode = currency_mode

with col_currency2:
    if st.button("🔄 환율 업데이트"):
        st.session_state.exchange_rate = get_usd_to_krw_rate()
        st.success(f"환율 업데이트: 1 USD = ₩{st.session_state.exchange_rate:,.0f}")

with col_currency3:
    st.metric("💱 현재 환율", f"₩{st.session_state.exchange_rate:,.0f}")

st.markdown('</div>', unsafe_allow_html=True)

# 다중 백업 저장 함수 (데이터 유실 방지)
def save_portfolio_data_secure():
    """
    3중 백업으로 데이터 유실 방지:
    1. 기본 파일 저장
    2. 백업 폴더에 복사
    3. 보조 백업 폴더에 복사
    4. 브라우저 세션 스토리지 활용
    """
    data = {
        "stocks": st.session_state.stocks,
        "cash": st.session_state.cash_amount,
        "transactions": st.session_state.transactions,
        "target_settings": st.session_state.target_settings,
        "realized_pnl": st.session_state.realized_pnl,
        "stock_memos": st.session_state.stock_memos,
        "total_commission": st.session_state.total_commission,
        "best_worst_trades": st.session_state.best_worst_trades,
        "currency_mode": st.session_state.currency_mode,
        "exchange_rate": st.session_state.exchange_rate,
        "last_updated": get_korean_time(),
        "backup_timestamp": time.time()
    }
    
    # JSON 문자열로 변환
    json_data = json.dumps(data, indent=2, ensure_ascii=False)
    
    try:
        # 1. 기본 파일 저장
        with open(PRIMARY_FILE, "w", encoding="utf-8") as f:
            f.write(json_data)
        
        # 2. 첫 번째 백업 폴더에 저장
        with open(BACKUP_FILE, "w", encoding="utf-8") as f:
            f.write(json_data)
        
        # 3. 두 번째 백업 폴더에 저장
        with open(SECONDARY_BACKUP_FILE, "w", encoding="utf-8") as f:
            f.write(json_data)
        
        # 4. 세션 상태에도 JSON 백업 저장
        st.session_state.json_backup = json_data
        
        # 성공 메시지 (너무 자주 표시되지 않도록 조건부)
        if not hasattr(st.session_state, 'last_save_time') or \
           time.time() - st.session_state.last_save_time > 30:  # 30초마다 한 번만
            st.toast("✅ 데이터 자동 저장 완료", icon="💾")
            st.session_state.last_save_time = time.time()
        
        return True
        
    except Exception as e:
        st.error(f"❌ 데이터 저장 실패: {e}")
        return False

# 복구 우선순위로 데이터 로드
def load_portfolio_data_secure():
    """
    복구 우선순위:
    1. 기본 파일
    2. 첫 번째 백업
    3. 두 번째 백업
    4. 세션 상태 백업
    """
    
    # 파일들을 우선순위대로 시도
    files_to_try = [PRIMARY_FILE, BACKUP_FILE, SECONDARY_BACKUP_FILE]
    
    for file_path in files_to_try:
        if os.path.exists(file_path):
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                
                # 데이터 무결성 검사
                if validate_data_integrity(data):
                    if file_path != PRIMARY_FILE:
                        st.warning(f"⚠️ 백업 파일에서 데이터를 복구했습니다: {file_path}")
                    
                    # 새로운 필드들 추가 (기존 데이터 호환성)
                    currency_mode = data.get("currency_mode", "USD")
                    exchange_rate = data.get("exchange_rate", 1320.0)
                    
                    return (data.get("stocks", []), 
                           data.get("cash", 0.0), 
                           data.get("transactions", []), 
                           data.get("target_settings", {}),
                           data.get("realized_pnl", []),
                           data.get("stock_memos", {}),
                           data.get("total_commission", 0.0),
                           data.get("best_worst_trades", {"best": None, "worst": None}),
                           currency_mode,
                           exchange_rate)
                
            except Exception as e:
                st.warning(f"파일 {file_path} 로드 실패: {e}")
                continue
    
    # 세션 상태에서 백업 시도
    if hasattr(st.session_state, 'json_backup'):
        try:
            data = json.loads(st.session_state.json_backup)
            if validate_data_integrity(data):
                st.warning("⚠️ 세션 백업에서 데이터를 복구했습니다.")
                return (data.get("stocks", []), 
                       data.get("cash", 0.0), 
                       data.get("transactions", []), 
                       data.get("target_settings", {}),
                       data.get("realized_pnl", []),
                       data.get("stock_memos", {}),
                       data.get("total_commission", 0.0),
                       data.get("best_worst_trades", {"best": None, "worst": None}),
                       data.get("currency_mode", "USD"),
                       data.get("exchange_rate", 1320.0))
        except:
            pass
    
    # 모든 복구 시도 실패
    st.error("❌ 모든 백업 파일이 손상되었습니다. 새로 시작합니다.")
    return [], 0.0, [], {}, [], {}, 0.0, {"best": None, "worst": None}, "USD", 1320.0

# 데이터 무결성 검사
def validate_data_integrity(data):
    """데이터가 올바른 구조를 가지고 있는지 검사"""
    required_keys = ["stocks", "cash", "transactions"]
    
    if not isinstance(data, dict):
        return False
    
    for key in required_keys:
        if key not in data:
            return False
    
    # stocks가 리스트인지 확인
    if not isinstance(data["stocks"], list):
        return False
    
    # cash가 숫자인지 확인
    if not isinstance(data["cash"], (int, float)):
        return False
    
    return True

# 자동 타임스탬프 백업 (일정 시간마다)
def create_timestamped_backup():
    """타임스탬프가 포함된 백업 파일 생성"""
    if os.path.exists(PRIMARY_FILE):
        timestamp = get_korean_time().replace(":", "-").replace(" ", "_")
        timestamped_file = os.path.join(BACKUP_DATA_DIR, f"portfolio_backup_{timestamp}.json")
        
        try:
            shutil.copy2(PRIMARY_FILE, timestamped_file)
            
            # 오래된 백업 파일 정리 (7개 이상 시 삭제)
            backup_files = [f for f in os.listdir(BACKUP_DATA_DIR) if f.startswith("portfolio_backup_")]
            if len(backup_files) > 7:
                backup_files.sort()
                for old_file in backup_files[:-7]:
                    os.remove(os.path.join(BACKUP_DATA_DIR, old_file))
            
            return True
        except Exception as e:
            st.warning(f"타임스탬프 백업 실패: {e}")
            return False
    return False

# 일별 히스토리 저장 (안전한 버전)
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
        if os.path.exists(DAILY_HISTORY_FILE):
            try:
                with open(DAILY_HISTORY_FILE, "r", encoding="utf-8") as f:
                    daily_history = json.load(f)
            except:
                daily_history = {}
        
        # 오늘 데이터 업데이트
        daily_history[today] = {
            "total_investment": total_investment,
            "total_value": total_value,
            "total_profit": total_profit,
            "total_return_rate": total_return_rate,
            "total_assets": total_assets,
            "cash": st.session_state.cash_amount,
            "stock_count": len(st.session_state.stocks),
            "exchange_rate": st.session_state.exchange_rate
        }
        
        # 안전한 저장 (임시 파일 사용)
        temp_file = DAILY_HISTORY_FILE + ".tmp"
        try:
            with open(temp_file, "w", encoding="utf-8") as f:
                json.dump(daily_history, f, indent=2, ensure_ascii=False)
            
            # 성공적으로 저장되면 원본 파일로 이동
            shutil.move(temp_file, DAILY_HISTORY_FILE)
            
        except Exception as e:
            # 임시 파일 정리
            if os.path.exists(temp_file):
                os.remove(temp_file)
            st.warning(f"일별 히스토리 저장 실패: {e}")

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

if "initialized" not in st.session_state:
    # 앱 시작 시 기존 데이터 자동 로드
    (stocks, cash, transactions, target_settings, 
     realized_pnl, stock_memos, total_commission, best_worst_trades,
     currency_mode, exchange_rate) = load_portfolio_data_secure()
    st.session_state.stocks = stocks
    st.session_state.cash_amount = cash
    st.session_state.transactions = transactions
    st.session_state.target_settings = target_settings
    st.session_state.realized_pnl = realized_pnl
    st.session_state.stock_memos = stock_memos
    st.session_state.total_commission = total_commission
    st.session_state.best_worst_trades = best_worst_trades
    st.session_state.currency_mode = currency_mode
    st.session_state.exchange_rate = exchange_rate
    st.session_state.initialized = True
    
    # 초기 로드 후 즉시 백업 생성
    save_portfolio_data_secure()

# 자동 백업 시스템 (1시간마다)
if "last_auto_backup" not in st.session_state:
    st.session_state.last_auto_backup = time.time()

current_time = time.time()
if current_time - st.session_state.last_auto_backup > 3600:  # 1시간 = 3600초
    if create_timestamped_backup():
        st.session_state.last_auto_backup = current_time
        st.toast("🕐 자동 백업 생성됨", icon="⏰")

# 데이터 상태 모니터링
st.subheader("📊 데이터 상태")
col1, col2, col3, col4 = st.columns(4)

with col1:
    backup_count = len([f for f in os.listdir(BACKUP_DATA_DIR) if f.startswith("portfolio_backup_")])
    st.metric("🗂️ 백업 파일", f"{backup_count}개")

with col2:
    if os.path.exists(PRIMARY_FILE):
        file_size = os.path.getsize(PRIMARY_FILE)
        st.metric("📁 파일 크기", f"{file_size} bytes")
    else:
        st.metric("📁 파일 크기", "0 bytes")

with col3:
    if hasattr(st.session_state, 'last_save_time'):
        last_save = datetime.fromtimestamp(st.session_state.last_save_time).strftime("%H:%M:%S")
        st.metric("💾 마지막 저장", last_save)
    else:
        st.metric("💾 마지막 저장", "없음")

with col4:
    # 수동 백업 버튼
    if st.button("🔄 수동 백업"):
        if create_timestamped_backup():
            st.success("✅ 수동 백업 완료!")
        else:
            st.error("❌ 백업 실패!")

# 모바일 모드 토글
st.session_state.mobile_mode = st.checkbox("📱 모바일 모드", value=st.session_state.mobile_mode)

# 데이터 백업 불러오기 기능
st.subheader("📤 데이터 백업 불러오기")
uploaded_file = st.file_uploader("JSON 백업 파일 업로드", type=['json'])
if uploaded_file is not None:
    try:
        backup_data = json.load(uploaded_file)
        
        # 데이터 무결성 검사
        if validate_data_integrity(backup_data):
            st.session_state.stocks = backup_data.get("stocks", [])
            st.session_state.cash_amount = backup_data.get("cash", 0.0)
            st.session_state.transactions = backup_data.get("transactions", [])
            st.session_state.target_settings = backup_data.get("target_settings", {})
            st.session_state.realized_pnl = backup_data.get("realized_pnl", [])
            st.session_state.stock_memos = backup_data.get("stock_memos", {})
            st.session_state.total_commission = backup_data.get("total_commission", 0.0)
            st.session_state.best_worst_trades = backup_data.get("best_worst_trades", {"best": None, "worst": None})
            st.session_state.currency_mode = backup_data.get("currency_mode", "USD")
            st.session_state.exchange_rate = backup_data.get("exchange_rate", 1320.0)
            
            # 즉시 안전한 저장
            save_portfolio_data_secure()
            st.success("백업 데이터를 성공적으로 불러왔습니다!")
            st.rerun()
        else:
            st.error("❌ 백업 파일의 데이터 구조가 올바르지 않습니다.")
            
    except Exception as e:
        st.error(f"백업 파일 로드 중 오류: {e}")

st.markdown("---")

# 💰 보유 현금 입력
st.subheader("💰 보유 현금")
currency_symbol = get_currency_symbol(st.session_state.currency_mode)
current_cash_display = st.session_state.cash_amount if st.session_state.currency_mode == "USD" else st.session_state.cash_amount * st.session_state.exchange_rate

new_cash_input = st.number_input(f"보유 현금 ({currency_symbol})", min_value=0.0, step=100.0 if st.session_state.currency_mode == "USD" else 100000.0, 
                                format="%.2f" if st.session_state.currency_mode == "USD" else "%.0f", 
                                value=current_cash_display, key="main_cash_input")

# 입력값을 USD로 변환하여 저장
if st.session_state.currency_mode == "KRW":
    new_cash_usd = new_cash_input / st.session_state.exchange_rate
else:
    new_cash_usd = new_cash_input

# 현금 변경 시 자동 저장
if abs(new_cash_usd - st.session_state.cash_amount) > 0.01:  # 소수점 오차 고려
    st.session_state.cash_amount = new_cash_usd
    save_portfolio_data_secure()

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
                    st.error(f"현금이 부족합니다! 필요금액: {format_currency(final_cost, st.session_state.currency_mode, st.session_state.exchange_rate)}, "
                           f"보유현금: {format_currency(st.session_state.cash_amount, st.session_state.currency_mode, st.session_state.exchange_rate)}")
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
                    
                    # 안전한 자동 저장
                    save_portfolio_data_secure()
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
                
                # 안전한 자동 저장
                save_portfolio_data_secure()
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
            save_portfolio_data_secure()
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
    
    # 거래 내역에 통화 정보 추가
    if st.session_state.currency_mode == "KRW":
        df_transactions_display = df_transactions.copy()
        for col in ['가격', '총액', '수수료', '실제비용', '실제수익']:
            if col in df_transactions_display.columns:
                df_transactions_display[col] = df_transactions_display[col].apply(
                    lambda x: f"₩{x * st.session_state.exchange_rate:,.0f}" if pd.notna(x) else x
                )
        st.dataframe(df_transactions_display, use_container_width=True)
    else:
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
    
    # 통화에 따른 제목 변경
    currency_text = "원화" if st.session_state.currency_mode == "KRW" else "달러"
    fig = px.pie(asset_data, names="종목", values="평가금액", 
                 title=f"💼 자산 구성 비율 (현금 포함, {currency_text} 기준)")
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
        # 업데이트 후 안전한 자동 저장
        save_portfolio_data_secure()
        st.success("현재가가 업데이트되었습니다!")
        st.rerun()
    
    df = pd.DataFrame(st.session_state.stocks)
    df["평가금액"] = df["현재가"] * df["수량"]
    df["투자금액"] = df["매수단가"] * df["수량"]
    
    # 통화 변환을 위한 데이터프레임 복사
    if st.session_state.currency_mode == "KRW":
        df_display = df.copy()
        # 금액 관련 컬럼들을 원화로 변환
        currency_columns = ["매수단가", "현재가", "수익", "평가금액", "투자금액"]
        for col in currency_columns:
            if col in df_display.columns:
                df_display[col] = df_display[col] * st.session_state.exchange_rate
        
        # 원화 표시를 위한 포맷팅
        df_display["매수단가"] = df_display["매수단가"].apply(lambda x: f"₩{x:,.0f}")
        df_display["현재가"] = df_display["현재가"].apply(lambda x: f"₩{x:,.0f}")
        df_display["수익"] = df_display["수익"].apply(lambda x: f"₩{x:,.0f}")
        df_display["평가금액"] = df_display["평가금액"].apply(lambda x: f"₩{x:,.0f}")
        df_display["투자금액"] = df_display["투자금액"].apply(lambda x: f"₩{x:,.0f}")
    else:
        df_display = df
    
    # 색상으로 수익/손실 구분하여 표시
    st.dataframe(
        df_display.style.applymap(
            lambda x: 'color: red' if isinstance(x, (int, float)) and x < 0 else 'color: green' if isinstance(x, (int, float)) and x > 0 else '',
            subset=['수익률(%)'] if st.session_state.currency_mode == "KRW" else ['수익', '수익률(%)']
        ),
        use_container_width=True
    )

    total_profit = df["수익"].sum()
    total_investment = df["투자금액"].sum()
    total_value = df["평가금액"].sum()
    total_return_rate = (total_profit / total_investment * 100) if total_investment > 0 else 0
    total_assets = total_value + st.session_state.cash_amount
    
    if st.session_state.mobile_mode:
        st.metric("💰 총 투자금액", format_currency(total_investment, st.session_state.currency_mode, st.session_state.exchange_rate))
        st.metric("📈 총 평가금액", format_currency(total_value, st.session_state.currency_mode, st.session_state.exchange_rate))
        st.metric("💹 총 수익률", f"{total_return_rate:.2f}%", format_currency(total_profit, st.session_state.currency_mode, st.session_state.exchange_rate))
        st.metric("🏦 총 자산", format_currency(total_assets, st.session_state.currency_mode, st.session_state.exchange_rate))
        st.metric("💸 누적 수수료", format_currency(st.session_state.total_commission, st.session_state.currency_mode, st.session_state.exchange_rate))
    else:
        col1, col2, col3, col4, col5 = st.columns(5)
        with col1:
            st.metric("💰 총 투자금액", format_currency(total_investment, st.session_state.currency_mode, st.session_state.exchange_rate))
        with col2:
            st.metric("📈 총 평가금액", format_currency(total_value, st.session_state.currency_mode, st.session_state.exchange_rate))
        with col3:
            st.metric("💹 총 수익률", f"{total_return_rate:.2f}%", format_currency(total_profit, st.session_state.currency_mode, st.session_state.exchange_rate))
        with col4:
            st.metric("🏦 총 자산", format_currency(total_assets, st.session_state.currency_mode, st.session_state.exchange_rate))
        with col5:
            st.metric("💸 누적 수수료", format_currency(st.session_state.total_commission, st.session_state.currency_mode, st.session_state.exchange_rate))

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
        
        st.metric("총 실현손익", format_currency(total_realized, st.session_state.currency_mode, st.session_state.exchange_rate))
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
            avg_holding = 2.5  # 단타 기준 추정값
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
        
        if st.session_state.currency_mode == "KRW":
            monthly_summary["실현손익"] = monthly_summary["실현손익"] * st.session_state.exchange_rate
            monthly_summary.columns = [f"월 실현손익({get_currency_symbol(st.session_state.currency_mode)})", "평균 수익률(%)", "거래 횟수"]
        else:
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
        
        if st.session_state.currency_mode == "KRW":
            weekly_summary["실현손익"] = weekly_summary["실현손익"] * st.session_state.exchange_rate
            weekly_summary.columns = [f"주 실현손익({get_currency_symbol(st.session_state.currency_mode)})", "평균 수익률(%)", "거래 횟수"]
        else:
            weekly_summary.columns = ["주 실현손익($)", "평균 수익률(%)", "거래 횟수"]
        
        st.write("**📊 주별 성과 (최근 4주)**")
        st.dataframe(weekly_summary)

# 히스토리 데이터 시각화
st.markdown("---")
st.subheader("📈 히스토리 및 추이 분석")

if os.path.exists(DAILY_HISTORY_FILE):
    with open(DAILY_HISTORY_FILE, "r", encoding="utf-8") as f:
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
            
            if st.session_state.currency_mode == "KRW":
                # 각 날짜의 환율을 사용하여 변환 (없으면 현재 환율 사용)
                display_df["total_profit"] = display_df.apply(
                    lambda row: row["total_profit"] * history_df.loc[row.name].get("exchange_rate", st.session_state.exchange_rate), axis=1
                )
                display_df["total_assets"] = display_df.apply(
                    lambda row: row["total_assets"] * history_df.loc[row.name].get("exchange_rate", st.session_state.exchange_rate), axis=1
                )
                display_df.columns = ["수익률(%)", f"수익금액({get_currency_symbol(st.session_state.currency_mode)})", f"총자산({get_currency_symbol(st.session_state.currency_mode)})"]
            else:
                display_df.columns = ["수익률(%)", "수익금액($)", "총자산($)"]
            
            display_df = display_df.round(2 if st.session_state.currency_mode == "USD" else 0)
            st.dataframe(display_df.tail(10))  # 최근 10일
        
        with col2:
            st.write("**📊 자산 구성 변화**")
            recent_data = history_df.tail(1).iloc[0]
            recent_exchange_rate = recent_data.get("exchange_rate", st.session_state.exchange_rate)
            
            st.metric("현재 총자산", format_currency(recent_data['total_assets'], st.session_state.currency_mode, recent_exchange_rate))
            st.metric("현재 투자금액", format_currency(recent_data['total_investment'], st.session_state.currency_mode, recent_exchange_rate))
            st.metric("현재 평가금액", format_currency(recent_data['total_value'], st.session_state.currency_mode, recent_exchange_rate))
            st.metric("보유 종목 수", f"{recent_data['stock_count']}개")
        
        # 총자산 추이 그래프
        currency_text = "원화" if st.session_state.currency_mode == "KRW" else "달러"
        st.write(f"**📈 총자산 추이 그래프 ({currency_text} 기준)**")
        fig = go.Figure()
        
        # 통화 변환
        if st.session_state.currency_mode == "KRW":
            # 각 날짜의 환율을 사용하여 변환
            investment_data = [row["total_investment"] * history_df.loc[idx].get("exchange_rate", st.session_state.exchange_rate) 
                             for idx, row in history_df.iterrows()]
            value_data = [row["total_value"] * history_df.loc[idx].get("exchange_rate", st.session_state.exchange_rate) 
                         for idx, row in history_df.iterrows()]
            assets_data = [row["total_assets"] * history_df.loc[idx].get("exchange_rate", st.session_state.exchange_rate) 
                          for idx, row in history_df.iterrows()]
        else:
            investment_data = history_df['total_investment'].tolist()
            value_data = history_df['total_value'].tolist()
            assets_data = history_df['total_assets'].tolist()
        
        fig.add_trace(go.Scatter(
            x=history_df.index, 
            y=investment_data,
            name='투자금액',
            line=dict(color='blue')
        ))
        
        fig.add_trace(go.Scatter(
            x=history_df.index, 
            y=value_data,
            name='평가금액',
            line=dict(color='green')
        ))
        
        fig.add_trace(go.Scatter(
            x=history_df.index, 
            y=assets_data,
            name='총자산',
            line=dict(color='red', width=3)
        ))
        
        currency_symbol = get_currency_symbol(st.session_state.currency_mode)
        fig.update_layout(
            title=f"투자금액 vs 평가금액 vs 총자산 추이 ({currency_text})",
            xaxis_title="날짜",
            yaxis_title=f"금액 ({currency_symbol})",
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

# 간단한 복사 버튼 생성 함수
def create_simple_copy_button(button_text="📋 클립보드에 복사"):
    """간단한 복사 버튼 HTML 생성"""
    return f"""
    <div style="margin: 10px 0;">
        <button style="
            background: linear-gradient(90deg, #4CAF50, #45a049);
            color: white;
            border: none;
            padding: 12px 24px;
            border-radius: 8px;
            cursor: pointer;
            font-size: 16px;
            font-weight: bold;
            width: 100%;
            box-shadow: 0 2px 5px rgba(0,0,0,0.2);
        " onclick="
            // 텍스트 영역에서 텍스트 가져오기
            const textArea = document.querySelector('[data-testid=stTextArea] textarea');
            if (textArea) {{
                textArea.select();
                textArea.setSelectionRange(0, 99999);
                navigator.clipboard.writeText(textArea.value).then(() => {{
                    alert('✅ 텍스트가 클립보드에 복사되었습니다!');
                }}).catch(() => {{
                    try {{
                        document.execCommand('copy');
                        alert('✅ 텍스트가 클립보드에 복사되었습니다!');
                    }} catch (err) {{
                        alert('❌ 복사에 실패했습니다. Ctrl+A, Ctrl+C로 수동 복사해주세요.');
                    }}
                }});
            }}
        ">{button_text}</button>
    </div>
    """

st.subheader("💡 종목 추천 문장 자동 생성")

if st.button("✍️ 추천 요청 문장 생성"):
    try:
        holdings = st.session_state.stocks
        if not holdings:
            st.warning("먼저 종목을 추가해주세요.")
        else:
            # 현재 통화 설정에 따른 텍스트 생성
            currency_text = "원화" if st.session_state.currency_mode == "KRW" else "달러"
            currency_symbol = get_currency_symbol(st.session_state.currency_mode)
            
            text = f"""아래는 오늘 기준 내 미국 주식 포트폴리오 전체 구성이다:
* 보유 현금: {format_currency(st.session_state.cash_amount, st.session_state.currency_mode, st.session_state.exchange_rate)}
* 누적 수수료: {format_currency(st.session_state.total_commission, st.session_state.currency_mode, st.session_state.exchange_rate)}
"""
            
            for stock in holdings:
                if st.session_state.currency_mode == "KRW":
                    buy_price_display = f"₩{stock['매수단가'] * st.session_state.exchange_rate:,.0f}"
                    current_price_display = f"₩{stock['현재가'] * st.session_state.exchange_rate:,.0f}"
                else:
                    buy_price_display = f"${stock['매수단가']}"
                    current_price_display = f"${stock['현재가']}"
                
                text += f"* {stock['종목']}: {stock['수량']}주 (매수단가 {buy_price_display}, 현재가 {current_price_display}, 수익률 {stock['수익률(%)']:.2f}%)\n"
            
            # 성과 요약 추가
            if st.session_state.realized_pnl:
                df_pnl = pd.DataFrame(st.session_state.realized_pnl)
                total_realized = df_pnl["실현손익"].sum()
                win_trades = len(df_pnl[df_pnl["실현손익"] > 0])
                total_trades = len(df_pnl)
                win_rate = (win_trades / total_trades * 100) if total_trades > 0 else 0
                
                text += f"""
* 총 실현손익: {format_currency(total_realized, st.session_state.currency_mode, st.session_state.exchange_rate)}
* 승률: {win_rate:.1f}% ({win_trades}/{total_trades})
* 총 거래 완료: {total_trades}건
"""
            
            text += f"""

📌 이 포트폴리오를 바탕으로 아래 전략을 도출해줘:

1. **현재 보유 중인 각 종목에 대해**
   * 보유 지속 vs 익절 vs 손절 여부 판단
   * 전략이 필요한 경우 몇 주를 매도하거나 추가 매수할지
   * 판단 기준은 기술적 분석 / 뉴스 / 수급 흐름 / AI 예측 / 실적 모멘텀 등
   * 단기/중기/장기 관점에서 구분해 설명해줘

2. **오늘 기준으로 전체 미국 시장 중**
   * 지금 이 시점에서 매수해야 할 **진짜 가치 있는 종목이 있다면 1~2개 추천해줘**
   * 단, **1주당 가격이 $500 이하**, **지금 당장 매수 가능한 가격대**, **상승 확률 70% 이상인 종목만**
   * 각 종목은 다음 정보를 포함해줘:
     • 추천 매수가 / 손절가 / 익절가 / 예상 보유 기간
     • 상승 확률 (%) / 추천 점수 (100점 만점)
     • 선정 이유 (기술 분석 / 뉴스 / 수급 흐름 각각 따로 설명)

3. **과매매는 피하고 싶으니**,
   * **보유 종목 리밸런싱이 불필요하다면 '유지' 판단을 명확히 내려줘**
   * 신규 매수는 **정말 매력적인 종목일 경우에만 추천해줘**

4. **총 자산 기준으로 종목별 비중이 적절한지도 평가해줘**
   * 각 종목별 투자금액/비중
   * 현금 보유 비중은 **시장 상황을 반영하여 추천 수준 제시**

5. **수수료 0.25%를 고려한 실질 매매 전략**을 포함해줘

            """.strip()
            
            st.text_area("📨 복사해서 GPT 추천 요청에 붙여넣기", value=text, height=400, key="recommendation_text")
            
            # 간단한 복사 버튼 추가
            copy_button_html = create_simple_copy_button("📋 클립보드에 복사하기")
            st.markdown(copy_button_html, unsafe_allow_html=True)
            
            # 다운로드 버튼
            st.download_button(
                label="📁 텍스트 파일로 다운로드",
                data=text.encode('utf-8'),
                file_name=f"portfolio_recommendation_{get_korean_date()}_{st.session_state.currency_mode}.txt",
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
    commission_threshold = 1000 if st.session_state.currency_mode == "USD" else 1000000
    if st.session_state.total_commission > (commission_threshold / st.session_state.exchange_rate if st.session_state.currency_mode == "KRW" else commission_threshold):
        warnings.append(f"💸 **높은 수수료**: 총 {format_currency(st.session_state.total_commission, st.session_state.currency_mode, st.session_state.exchange_rate)} 지출")
    
    if warnings:
        for warning in warnings:
            st.warning(warning)
    else:
        st.success("✅ 포트폴리오 상태가 양호합니다!")

st.markdown("---")

# 🗂️ 고급 백업 및 복원 기능
st.subheader("🗂️ 고급 데이터 관리")

col1, col2, col3 = st.columns(3)

with col1:
    st.write("**📋 데이터 백업**")
    if st.session_state.stocks:
        # 엑셀 백업
        df = pd.DataFrame(st.session_state.stocks)
        df["평가금액"] = df["현재가"] * df["수량"]
        df["투자금액"] = df["매수단가"] * df["수량"]

        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
            # 현재 포트폴리오 (통화별로 시트 생성)
            df_usd = df.copy()
            df_usd.to_excel(writer, index=False, sheet_name="현재포트폴리오_USD")
            
            # 원화 시트 추가
            df_krw = df.copy()
            currency_columns = ["매수단가", "현재가", "수익", "평가금액", "투자금액"]
            for col in currency_columns:
                if col in df_krw.columns:
                    df_krw[col] = df_krw[col] * st.session_state.exchange_rate
            df_krw.to_excel(writer, index=False, sheet_name="현재포트폴리오_KRW")
            
            # 거래내역
            if st.session_state.transactions:
                df_trans = pd.DataFrame(st.session_state.transactions)
                df_trans.to_excel(writer, index=False, sheet_name="거래내역")
            
            # 실현손익
            if st.session_state.realized_pnl:
                df_pnl = pd.DataFrame(st.session_state.realized_pnl)
                df_pnl.to_excel(writer, index=False, sheet_name="실현손익")
            
            # 일별히스토리
            if os.path.exists(DAILY_HISTORY_FILE):
                with open(DAILY_HISTORY_FILE, "r", encoding="utf-8") as f:
                    daily_history = json.load(f)
                if daily_history:
                    df_history = pd.DataFrame.from_dict(daily_history, orient='index')
                    df_history.to_excel(writer, sheet_name="일별히스토리")

        st.download_button(
            label="📥 엑셀 백업",
            data=buffer.getvalue(),
            file_name=f"portfolio_complete_{get_korean_date()}_{st.session_state.currency_mode}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True
        )

    # JSON 백업
    if os.path.exists(PRIMARY_FILE):
        with open(PRIMARY_FILE, "r", encoding="utf-8") as f:
            json_data = f.read()
        
        st.download_button(
            label="📥 JSON 백업",
            data=json_data.encode('utf-8'),
            file_name=f"portfolio_backup_{get_korean_date()}_{st.session_state.currency_mode}.json",
            mime="application/json",
            use_container_width=True
        )

with col2:
    st.write("**🔄 백업 파일 관리**")
    
    # 사용 가능한 백업 파일 목록
    backup_files = [f for f in os.listdir(BACKUP_DATA_DIR) if f.startswith("portfolio_backup_")]
    if backup_files:
        backup_files.sort(reverse=True)  # 최신순
        selected_backup = st.selectbox("백업 파일 선택", backup_files)
        
        if st.button("🔄 선택된 백업 복원", use_container_width=True):
            backup_path = os.path.join(BACKUP_DATA_DIR, selected_backup)
            try:
                shutil.copy2(backup_path, PRIMARY_FILE)
                st.success(f"✅ {selected_backup} 복원 완료! 새로고침됩니다.")
                st.rerun()
            except Exception as e:
                st.error(f"❌ 백업 복원 실패: {e}")
    else:
        st.info("사용 가능한 백업 파일이 없습니다.")

with col3:
    st.write("**🧹 데이터 관리**")
    
    # 오래된 백업 파일 정리
    if st.button("🗑️ 오래된 백업 정리", use_container_width=True):
        backup_files = [f for f in os.listdir(BACKUP_DATA_DIR) if f.startswith("portfolio_backup_")]
        if len(backup_files) > 5:
            backup_files.sort()
            deleted_count = 0
            for old_file in backup_files[:-5]:  # 최신 5개만 유지
                os.remove(os.path.join(BACKUP_DATA_DIR, old_file))
                deleted_count += 1
            st.success(f"✅ {deleted_count}개의 오래된 백업 파일을 삭제했습니다.")
        else:
            st.info("정리할 백업 파일이 없습니다.")
    
    # 전체 데이터 초기화 (위험)
    st.write("⚠️ **위험 구역**")
    if st.button("🔴 전체 데이터 초기화", use_container_width=True):
        if st.checkbox("정말로 모든 데이터를 삭제하시겠습니까?"):
            # 백업 생성 후 초기화
            create_timestamped_backup()
            
            # 세션 상태 초기화
            st.session_state.stocks = []
            st.session_state.cash_amount = 0.0
            st.session_state.transactions = []
            st.session_state.target_settings = {}
            st.session_state.realized_pnl = []
            st.session_state.stock_memos = {}
            st.session_state.total_commission = 0.0
            st.session_state.best_worst_trades = {"best": None, "worst": None}
            st.session_state.currency_mode = "USD"
            st.session_state.exchange_rate = 1320.0
            
            # 파일들 삭제
            for file_path in [PRIMARY_FILE, DAILY_HISTORY_FILE]:
                if os.path.exists(file_path):
                    os.remove(file_path)
            
            st.success("✅ 모든 데이터가 초기화되었습니다. (백업 생성됨)")
            st.rerun()

# 앱 정보
st.markdown("---")
with st.expander("ℹ️ 개선된 앱 정보 및 새로운 기능"):
    st.markdown(f"""
    ### 🆕 **새로운 기능들 (v2.1)**
    - **💱 다중 통화 지원**: USD/KRW 선택 가능, 실시간 환율 업데이트
    - **📋 스마트 복사 기능**: 추천 문장을 클릭 한 번으로 클립보드에 복사
    - **💰 통화별 데이터 표시**: 모든 금액을 선택한 통화로 표시
    - **📊 통화별 엑셀 백업**: USD/KRW 두 시트로 백업 파일 생성
    - **🔄 환율 자동 저장**: 일별 히스토리에 환율 정보 포함
    - **📈 통화별 차트**: 선택한 통화 기준으로 모든 차트 표시
    
    ### 🛡️ **데이터 보호 기능**
    - **3중 백업 시스템**: 기본 파일 + 2개 백업 폴더에 동시 저장
    - **자동 타임스탬프 백업**: 1시간마다 자동으로 시간 기록된 백업 생성
    - **데이터 무결성 검사**: 파일 손상 시 자동으로 백업에서 복구
    - **세션 백업**: 브라우저 메모리에도 백업 저장
    - **안전한 파일 저장**: 임시 파일 사용으로 저장 중 오류 방지
    - **복구 우선순위**: 기본 → 백업1 → 백업2 → 세션 순으로 자동 복구
    
    ### 💱 **통화 기능 사용법**
    - **통화 선택**: 페이지 상단에서 USD/KRW 선택
    - **환율 업데이트**: "환율 업데이트" 버튼으로 실시간 환율 적용
    - **자동 변환**: 모든 금액이 선택한 통화로 자동 변환 표시
    - **백업 호환성**: 기존 USD 데이터와 완전 호환
    - **현재 환율**: {st.session_state.exchange_rate:,.0f} KRW/USD
    
    ### 📋 **복사 기능 사용법**
    - **추천 문장 생성**: "추천 요청 문장 생성" 버튼 클릭
    - **원클릭 복사**: "클립보드에 복사하기" 버튼으로 즉시 복사
    - **자동 알림**: 복사 완료 시 알림 메시지 표시
    - **브라우저 호환**: 모든 주요 브라우저에서 작동
    - **오류 처리**: 복사 실패 시 대체 방법 자동 실행
    
    ### 🚀 **기존 핵심 기능들**
    - **완전 자동 저장**: 모든 변경사항이 즉시 3중 백업으로 저장
    - **데이터 유실 방지**: 파일 손상, 브라우저 종료 등에도 데이터 보호
    - **오프라인 작동**: 인터넷 없이도 완벽하게 작동 (환율 업데이트 제외)
    - **실현손익 추적**: 매도 시 실제 손익 자동 계산 및 기록
    - **수수료 관리**: 0.25% 수수료 자동 계산 및 누적 추적
    - **성과 분석**: 월별/주별 수익률, 승률, 거래 통계
    - **스마트 알림**: 목표 달성, 손절선 도달, 수익률/손실률 알림
    - **모바일 최적화**: 반응형 디자인으로 모든 기기에서 사용 가능
    
    ### 💡 **사용 팁**
    - **통화 전환**: 언제든지 USD ↔ KRW 전환 가능, 데이터 손실 없음
    - **환율 업데이트**: 중요한 거래 전에 환율 업데이트 권장
    - **복사 기능**: ChatGPT에 바로 붙여넣기 가능한 완성된 문장 생성
    - **백업 관리**: 정기적으로 엑셀/JSON 백업을 PC에 저장 권장
    - **성능 최적화**: 너무 많은 백업 파일 시 "오래된 백업 정리" 사용
    
    ### 📊 **지원되는 데이터**
    - ✅ 보유 종목 및 수량 (통화별 표시)
    - ✅ 매수/매도 거래 내역 (통화별 변환)
    - ✅ 실현손익 기록 (통화별 요약)
    - ✅ 종목별 메모
    - ✅ 목표 설정값
    - ✅ 일별 히스토리 (환율 포함)
    - ✅ 수수료 누적액 (통화별 표시)
    - ✅ 최고/최악 거래 기록
    - ✅ 현금 보유액 (통화별 입력/표시)
    - ✅ 환율 정보 및 이력
    
    이제 한국 투자자들도 원화 기준으로 편리하게 포트폴리오를 관리할 수 있습니다! 🇰🇷💰
    """)

# 페이지 하단 상태바
st.markdown("---")
currency_status = f"💱 {st.session_state.currency_mode} 모드 (환율: ₩{st.session_state.exchange_rate:,.0f})"
st.caption(f"📊 **포트폴리오 트래커 v2.1** | {currency_status} | "
          f"마지막 업데이트: {get_korean_time() if hasattr(st.session_state, 'last_save_time') else '없음'} | "
          f"💾 자동 저장 활성화 | 🛡️ 3중 백업 보호")

# 실시간 데이터 상태 표시 (사이드바 없이 하단에)
if st.session_state.stocks:
    total_value = sum(stock['수량'] * stock['현재가'] for stock in st.session_state.stocks)
    total_assets = total_value + st.session_state.cash_amount
    st.info(f"💼 현재 {len(st.session_state.stocks)}개 종목 보유 중 | "
           f"💰 총 자산: {format_currency(total_assets, st.session_state.currency_mode, st.session_state.exchange_rate)} | "
           f"📈 총 거래: {len(st.session_state.transactions)}건")