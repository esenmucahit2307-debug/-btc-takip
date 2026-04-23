import streamlit as st
import ccxt
import pandas as pd
import numpy as np
from scipy.signal import argrelextrema
from datetime import datetime
from collections import Counter
import time
import requests
import plotly.graph_objects as go

st.set_page_config(page_title="Scalp Sinyal Botu", layout="wide")

# ==================== TELEGRAM ====================
TELEGRAM_TOKEN = "8621122847:AAFvkF1gvqogowpt8UvkBTTRItUuGUVpd5g"
TELEGRAM_CHAT_ID = "6514368425"

def telegram_mesaj_gonder(mesaj):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        payload = {"chat_id": TELEGRAM_CHAT_ID, "text": mesaj, "parse_mode": "HTML"}
        requests.post(url, json=payload, timeout=5)
        return True
    except:
        return False

# ==================== 3 BORSA ====================
BORSALAR = {
    'Binance': ccxt.binance(),
    'Bitget': ccxt.bitget(),
    'OKX': ccxt.okx()
}

# ==================== OTURUM ====================
if 'gonderilen_sinyaller' not in st.session_state:
    st.session_state.gonderilen_sinyaller = []

# ==================== BAŞLIK ====================
st.title("⚡ SCALP SİNYAL BOTU")
st.markdown("**Binance + Bitget + OKX | 15dk + 1s onay | SADECE ÇOK GÜÇLÜ SİNYALLER**")

# ==================== KENAR ÇUBUĞU ====================
with st.sidebar:
    st.header("⚙️ AYARLAR")
    secilen_coin = st.selectbox("💰 Coin:", ["BTC/USDT", "ETH/USDT", "SOL/USDT", "ZEC/USDT", "APT/USDT", "SUI/USDT"], index=0)
    coin_adi = secilen_coin.split("/")[0]
    st.markdown("---")
    st.success("✅ 3 Borsa: Binance, Bitget, OKX")
    st.info("📌 SINYAL KRİTERLERİ: Minimum 85 PUAN")
    if st.button("🔄 Yenile", use_container_width=True):
        st.rerun()
    st.caption(f"🕐 {datetime.now().strftime('%H:%M:%S')}")

# ==================== FONKSİYONLAR ====================
def veri_cek(borsa, sembol, timeframe='15m', limit=150):
    try:
        bars = borsa.fetch_ohlcv(sembol, timeframe, limit=limit)
        df = pd.DataFrame(bars, columns=['zaman', 'acilis', 'yuksek', 'dusuk', 'kapanis', 'hacim'])
        df['zaman'] = pd.to_datetime(df['zaman'], unit='ms')
        df.set_index('zaman', inplace=True)
        return df
    except:
        return None

def anlik_fiyat_al(borsa, sembol):
    try:
        ticker = borsa.fetch_ticker(sembol)
        return ticker['last'], ticker['percentage'] if 'percentage' in ticker else 0
    except:
        return None, None

def seviye_bul(df, order=10, yuvarla=50):
    if df is None or len(df) < 20:
        return [], []
    son_fiyat = df['kapanis'].iloc[-1]
    if son_fiyat < 50: yuvarla = 2
    elif son_fiyat < 200: yuvarla = 10
    else: yuvarla = 50
    tepeler = argrelextrema(df['yuksek'].values, np.greater_equal, order=order)[0]
    dipler = argrelextrema(df['dusuk'].values, np.less_equal, order=order)[0]
    direncler = [round(df['yuksek'].iloc[t] / yuvarla) * yuvarla for t in tepeler]
    destekler = [round(df['dusuk'].iloc[d] / yuvarla) * yuvarla for d in dipler]
    return list(set(direncler)), list(set(destekler))

def rsi_hesapla(df, period=14):
    delta = df['kapanis'].diff()
    gain = delta.where(delta > 0, 0).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    return rsi

def macd_hesapla(df, fast=12, slow=26, signal=9):
    ema_fast = df['kapanis'].ewm(span=fast, adjust=False).mean()
    ema_slow = df['kapanis'].ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    hist = macd_line - signal_line
    return macd_line, signal_line, hist

def ema_kesisme(df, short=9, long=21):
    ema_short = df['kapanis'].ewm(span=short, adjust=False).mean()
    ema_long = df['kapanis'].ewm(span=long, adjust=False).mean()
    if ema_short.iloc[-1] > ema_long.iloc[-1] and ema_short.iloc[-2] <= ema_long.iloc[-2]:
        return 1
    elif ema_short.iloc[-1] < ema_long.iloc[-1] and ema_short.iloc[-2] >= ema_long.iloc[-2]:
        return -1
    return 0

def adx_hesapla(df, period=14):
    high = df['yuksek']
    low = df['dusuk']
    close = df['kapanis']
    plus_dm = high.diff()
    minus_dm = low.diff()
    plus_dm[plus_dm < 0] = 0
    minus_dm[minus_dm > 0] = 0
    tr = pd.concat([high - low, (high - close.shift()).abs(), (low - close.shift()).abs()], axis=1).max(axis=1)
    atr = tr.rolling(window=period).mean()
    plus_di = 100 * (plus_dm.ewm(alpha=1/period).mean() / atr)
    minus_di = 100 * (minus_dm.abs().ewm(alpha=1/period).mean() / atr)
    dx = (abs(plus_di - minus_di) / (plus_di + minus_di)) * 100
    adx = dx.rolling(window=period).mean()
    return adx.iloc[-1] if not pd.isna(adx.iloc[-1]) else 20

def stoch_rsi_hesapla(df, period=14, smoothK=3, smoothD=3):
    rsi_vals = rsi_hesapla(df, period)
    stochrsi = (rsi_vals - rsi_vals.rolling(period).min()) / (rsi_vals.rolling(period).max() - rsi_vals.rolling(period).min())
    k = stochrsi.rolling(smoothK).mean() * 100
    d = k.rolling(smoothD).mean()
    return k.iloc[-1], d.iloc[-1]

def atr_hesapla(df, period=14):
    high = df['yuksek']
    low = df['dusuk']
    close = df['kapanis']
    tr = pd.concat([high - low, (high - close.shift()).abs(), (low - close.shift()).abs()], axis=1).max(axis=1)
    return tr.rolling(window=period).mean().iloc[-1]

def hacim_kontrol(df, oran=1.5):
    son = df['hacim'].iloc[-1]
    ort = df['hacim'].rolling(20).mean().iloc[-1]
    return son > ort * oran

def trend_onay_1s(sembol):
    for borsa in BORSALAR.values():
        df = veri_cek(borsa, sembol, '1h', 30)
        if df is not None:
            son_kapanis = df['kapanis'].iloc[-1]
            ma20 = df['kapanis'].rolling(20).mean().iloc[-1]
            return "YUKARI" if son_kapanis > ma20 else "AGI"
    return "YATAY"

def grafik_ciz(df, baslik):
    if df is None or len(df) == 0:
        return go.Figure()
    fig = go.Figure()
    fig.add_trace(go.Candlestick(
        x=df.index, open=df['acilis'], high=df['yuksek'],
        low=df['dusuk'], close=df['kapanis'], name='Fiyat'
    ))
    fig.update_layout(height=500, title=baslik, template="plotly_dark", xaxis_rangeslider_visible=False)
    return fig

# ==================== CANLI FİYATLAR ====================
st.subheader(f"💰 {coin_adi} CANLI FİYAT")
cols = st.columns(3)
anlik_fiyatlar = []
for idx, (borsa_adi, borsa) in enumerate(BORSALAR.items()):
    fiyat, deg = anlik_fiyat_al(borsa, secilen_coin)
    if fiyat:
        anlik_fiyatlar.append(fiyat)
        with cols[idx]:
            st.metric(borsa_adi, f"${fiyat:,.2f}", f"{deg:.2f}%" if deg else None)
ortalama_fiyat = sum(anlik_fiyatlar)/len(anlik_fiyatlar) if anlik_fiyatlar else 0
st.metric("📊 ORTALAMA", f"${ortalama_fiyat:,.2f}")

# ==================== GRAFİK ====================
with st.spinner("Grafik yükleniyor..."):
    ana_df = None
    for borsa in BORSALAR.values():
        df = veri_cek(borsa, secilen_coin, '15m', 100)
        if df is not None:
            ana_df = df
            break
    if ana_df is not None:
        fig = grafik_ciz(ana_df, f"{coin_adi} - 15 Dakika")
        st.plotly_chart(fig, use_container_width=True)

# ==================== DESTEK/DİRENÇ ====================
with st.spinner("Destek/Direnç analizi yapılıyor..."):
    tum_direncler, tum_destekler, son_df = [], [], None
    for borsa in BORSALAR.values():
        df = veri_cek(borsa, secilen_coin, '15m', 200)
        if df is not None:
            if son_df is None: son_df = df
            d, s = seviye_bul(df, order=12)
            tum_direncler.append(d)
            tum_destekler.append(s)
    flat_direnc = [item for sub in tum_direncler for item in sub]
    flat_destek = [item for sub in tum_destekler for item in sub]
    direnc_sayac = Counter(flat_direnc)
    destek_sayac = Counter(flat_destek)
    tum_direnc = sorted(direnc_sayac.items(), key=lambda x: x[1], reverse=True)
    tum_destek = sorted(destek_sayac.items(), key=lambda x: x[1], reverse=True)

# ==================== SCALP SİNYALİ (SADECE 85+ PUAN) ====================
scalp_sinyali = None
if son_df is not None and len(son_df) > 30:
    rsi_val = rsi_hesapla(son_df).iloc[-1]
    _, _, hist = macd_hesapla(son_df)
    macd_trend = 1 if hist.iloc[-1] > 0 and hist.iloc[-1] > hist.iloc[-2] else (-1 if hist.iloc[-1] < 0 and hist.iloc[-1] < hist.iloc[-2] else 0)
    ema_cross = ema_kesisme(son_df)
    adx_val = adx_hesapla(son_df)
    stoch_k, _ = stoch_rsi_hesapla(son_df)
    hacim_artti = hacim_kontrol(son_df, 1.5)
    atr_val = atr_hesapla(son_df)
    mum_yukselen = son_df['kapanis'].iloc[-1] > son_df['kapanis'].iloc[-2]
    
    en_yakin_destek = None
    for seviye, _ in tum_destek:
        if seviye < ortalama_fiyat:
            if en_yakin_destek is None or seviye > en_yakin_destek:
                en_yakin_destek = seviye
    en_yakin_direnc = None
    for seviye, _ in tum_direnc:
        if seviye > ortalama_fiyat:
            if en_yakin_direnc is None or seviye < en_yakin_direnc:
                en_yakin_direnc = seviye
    
    mesafe_destek = ((ortalama_fiyat - en_yakin_destek) / ortalama_fiyat * 100) if en_yakin_destek else 100
    mesafe_direnc = ((en_yakin_direnc - ortalama_fiyat) / ortalama_fiyat * 100) if en_yakin_direnc else 100
    trend_1s = trend_onay_1s(secilen_coin)
    
    # LONG PUAN (DAHA SIKI)
    long_puan = 0
    if mesafe_destek < 0.8: long_puan += 25
    elif mesafe_destek < 1.2: long_puan += 15
    if mum_yukselen: long_puan += 15
    if 40 < rsi_val < 55: long_puan += 15
    if macd_trend == 1: long_puan += 15
    if ema_cross == 1: long_puan += 15
    if adx_val > 30: long_puan += 15
    if hacim_artti: long_puan += 15
    if trend_1s == "YUKARI": long_puan += 15
    
    # SHORT PUAN (DAHA SIKI)
    short_puan = 0
    if mesafe_direnc < 0.8: short_puan += 25
    elif mesafe_direnc < 1.2: short_puan += 15
    if not mum_yukselen: short_puan += 15
    if 45 < rsi_val < 60: short_puan += 15
    if macd_trend == -1: short_puan += 15
    if ema_cross == -1: short_puan += 15
    if adx_val > 30: short_puan += 15
    if hacim_artti: short_puan += 15
    if trend_1s == "AGI": short_puan += 15
    
    # SADECE 85+ PUAN
    if long_puan >= 85:
        hedef = ortalama_fiyat + (atr_val * 1.2)
        stop = ortalama_fiyat - (atr_val * 0.8)
        scalp_sinyali = {
            'tip': 'LONG', 'coin': coin_adi, 'fiyat': ortalama_fiyat,
            'hedef': hedef, 'stop': stop, 'puan': long_puan,
            'destek': en_yakin_destek, 'direnc': en_yakin_direnc,
            'rsi': round(rsi_val,1), 'adx': round(adx_val,1),
            'macd': 'Yükselen' if macd_trend==1 else 'Düşen',
            'hacim': 'Güçlü' if hacim_artti else 'Normal',
            'trend_1s': trend_1s
        }
    elif short_puan >= 85:
        hedef = ortalama_fiyat - (atr_val * 1.2)
        stop = ortalama_fiyat + (atr_val * 0.8)
        scalp_sinyali = {
            'tip': 'SHORT', 'coin': coin_adi, 'fiyat': ortalama_fiyat,
            'hedef': hedef, 'stop': stop, 'puan': short_puan,
            'destek': en_yakin_destek, 'direnc': en_yakin_direnc,
            'rsi': round(rsi_val,1), 'adx': round(adx_val,1),
            'macd': 'Düşen' if macd_trend==-1 else 'Yükselen',
            'hacim': 'Güçlü' if hacim_artti else 'Normal',
            'trend_1s': trend_1s
        }

# ==================== TELEGRAM GÖNDER ====================
if scalp_sinyali:
    sig_id = f"{scalp_sinyali['coin']}_{scalp_sinyali['tip']}_{scalp_sinyali['fiyat']:.0f}"
    if sig_id not in st.session_state.gonderilen_sinyaller:
        st.session_state.gonderilen_sinyaller.append(sig_id)
        
        msg = f"""🔥 <b>ÇOK GÜÇLÜ SCALP SİNYALİ!</b> 🔥

<b>{'🟢 LONG' if scalp_sinyali['tip']=='LONG' else '🔴 SHORT'} {scalp_sinyali['coin']}</b>
📍 Giriş: <b>${scalp_sinyali['fiyat']:,.2f}</b>
🎯 Hedef: <b>${scalp_sinyali['hedef']:,.2f}</b>
🛑 Stop: <b>${scalp_sinyali['stop']:,.2f}</b>

📊 <b>Güven Puanı:</b> {scalp_sinyali['puan']}/100

📈 RSI: {scalp_sinyali['rsi']} | ADX: {scalp_sinyali['adx']}
📉 MACD: {scalp_sinyali['macd']} | Hacim: {scalp_sinyali['hacim']}
⏰ 1s Trend: {scalp_sinyali['trend_1s']}

🟢 Destek: ${scalp_sinyali['destek']:.0f}
🔴 Direnç: ${scalp_sinyali['direnc']:.0f}

⏱️ {datetime.now().strftime('%H:%M:%S')} (15dk+1s onay)
💡 İşlemi manuel aç"""
        telegram_mesaj_gonder(msg)
        st.success(f"📨 {scalp_sinyali['tip']} sinyali Telegram'a gönderildi (Puan: {scalp_sinyali['puan']})")

# ==================== SİNYAL GÖSTER ====================
if scalp_sinyali:
    st.markdown("---")
    if scalp_sinyali['tip'] == 'LONG':
        st.success(f"🎯 **LONG SİNYALİ - PUAN: {scalp_sinyali['puan']}**")
    else:
        st.error(f"🎯 **SHORT SİNYALİ - PUAN: {scalp_sinyali['puan']}**")
    c1, c2, c3 = st.columns(3)
    c1.metric("📍 Giriş", f"${scalp_sinyali['fiyat']:,.2f}")
    c1.metric("🎯 Hedef", f"${scalp_sinyali['hedef']:,.2f}")
    c2.metric("🛑 Stop", f"${scalp_sinyali['stop']:,.2f}")
    c2.metric("RSI/ADX", f"{scalp_sinyali['rsi']} / {scalp_sinyali['adx']}")
    c3.metric("📈 1s Trend", scalp_sinyali['trend_1s'])
    c3.metric("💪 Hacim", scalp_sinyali['hacim'])
else:
    st.info("🔍 Çok güçlü sinyal yok (85+ puan gerekli)")

# ==================== DESTEK/DİRENÇ TABLOSU ====================
st.markdown("---")
st.subheader("📊 DESTEK/DİRENÇ (15dk, 3 Borsa)")
col1, col2 = st.columns(2)
with col1:
    st.markdown("**🟢 DESTEK**")
    for s, g in tum_destek[:6]:
        st.markdown(f"{'🔥' if g>=3 else '✅' if g>=2 else '🟡'} **${s:,.2f}** ({g}/3)")
with col2:
    st.markdown("**🔴 DİRENÇ**")
    for s, g in tum_direnc[:6]:
        st.markdown(f"{'🔥' if g>=3 else '✅' if g>=2 else '🟡'} **${s:,.2f}** ({g}/3)")

st.caption("💡 **Sinyal kriterleri:** 15dk + 1s onay, MINIMUM 85 PUAN, Hacim artışı, ADX>30, Trend onayı")
