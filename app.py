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

st.set_page_config(page_title="Ultra Scalp Dashboard", layout="wide")

# ==================== TELEGRAM AYARLARI ====================
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

# ==================== BAŞLIK ====================
st.title("⚡ ULTRA SCALP BOT")
st.markdown("**15dk + 1saat onay | 4 Borsa | Likidite Simülasyonu | 7 Gösterge | Sinyal Skoru**")

# ==================== COİN LİSTESİ ====================
coin_listesi = ["BTC/USDT", "ETH/USDT", "SOL/USDT", "ZEC/USDT", "APT/USDT", "SUI/USDT"]

# ==================== 4 BORSA ====================
BORSALAR = {
    'Binance': ccxt.binance(),
    'Bybit': ccxt.bybit(),
    'Bitget': ccxt.bitget(),
    'OKX': ccxt.okx()
}

# ==================== OTURUM ====================
if 'gonderilen_sinyaller' not in st.session_state:
    st.session_state.gonderilen_sinyaller = []

# ==================== KENAR ÇUBUĞU ====================
with st.sidebar:
    st.header("⚙️ AYARLAR")
    secilen_coin = st.selectbox("💰 Coin seç:", coin_listesi, index=0)
    coin_adi = secilen_coin.split("/")[0]
    st.markdown("---")
    st.success("✅ **15dk ana sinyal + 1saat onay**")
    st.info("📊 Göstergeler: RSI, MACD, EMA, ADX, StochRSI, Hacim, Likidite")
    st.markdown("---")
    if st.button("🔄 Yenile", use_container_width=True):
        st.rerun()
    st.caption(f"🕐 {datetime.now().strftime('%H:%M:%S')}")

# ==================== FONKSİYONLAR ====================
def veri_cek(borsa, sembol, timeframe='15m', limit=150):
    try:
        bardata = borsa.fetch_ohlcv(sembol, timeframe, limit=limit)
        df = pd.DataFrame(bardata, columns=['zaman', 'acilis', 'yuksek', 'dusuk', 'kapanis', 'hacim'])
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
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    return rsi

def macd_hesapla(df, fast=12, slow=26, signal=9):
    ema_fast = df['kapanis'].ewm(span=fast, adjust=False).mean()
    ema_slow = df['kapanis'].ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    histogram = macd_line - signal_line
    return macd_line, signal_line, histogram

def ema_kesisme(df, short=9, long=21):
    ema_short = df['kapanis'].ewm(span=short, adjust=False).mean()
    ema_long = df['kapanis'].ewm(span=long, adjust=False).mean()
    if ema_short.iloc[-1] > ema_long.iloc[-1] and ema_short.iloc[-2] <= ema_long.iloc[-2]:
        return 1  # Altın kesişim (LONG)
    elif ema_short.iloc[-1] < ema_long.iloc[-1] and ema_short.iloc[-2] >= ema_long.iloc[-2]:
        return -1 # Ölüm kesişim (SHORT)
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
    rsi = rsi_hesapla(df, period)
    stochrsi = (rsi - rsi.rolling(period).min()) / (rsi.rolling(period).max() - rsi.rolling(period).min())
    k = stochrsi.rolling(smoothK).mean() * 100
    d = k.rolling(smoothD).mean()
    return k.iloc[-1], d.iloc[-1]

def atr_hesapla(df, period=14):
    high = df['yuksek']
    low = df['dusuk']
    close = df['kapanis']
    tr = pd.concat([high - low, (high - close.shift()).abs(), (low - close.shift()).abs()], axis=1).max(axis=1)
    atr = tr.rolling(window=period).mean()
    return atr.iloc[-1]

def hacim_kontrol(df, oran=1.3):
    son_hacim = df['hacim'].iloc[-1]
    ortalama_hacim = df['hacim'].rolling(20).mean().iloc[-1]
    return son_hacim > ortalama_hacim * oran

def likidite_simulasyonu(fiyat, seviye, yon):
    # yon: 'long' veya 'short'
    if yon == 'long':
        uzaklik = abs(fiyat - seviye) / fiyat * 100
        if uzaklik < 2.0:
            return 10  # Yakın likidite güçlendirir
        elif uzaklik < 3.5:
            return 5
    else:
        uzaklik = abs(seviye - fiyat) / fiyat * 100
        if uzaklik < 2.0:
            return 10
        elif uzaklik < 3.5:
            return 5
    return 0

def trend_onay_1saat(coin_sembol):
    for borsa in BORSALAR.values():
        df_1h = veri_cek(borsa, coin_sembol, '1h', 30)
        if df_1h is not None:
            son_kapanis = df_1h['kapanis'].iloc[-1]
            ma20 = df_1h['kapanis'].rolling(20).mean().iloc[-1]
            return "YUKARI" if son_kapanis > ma20 else "AGI"
    return "YATAY"

# ==================== GRAFİK VE CANLI FİYAT ====================
st.subheader(f"💰 {coin_adi} CANLI FİYAT")
cols = st.columns(4)
anlik_fiyatlar = []
for idx, (borsa_adi, borsa) in enumerate(BORSALAR.items()):
    fiyat, degisim = anlik_fiyat_al(borsa, secilen_coin)
    if fiyat:
        anlik_fiyatlar.append(fiyat)
        with cols[idx]:
            st.metric(borsa_adi, f"${fiyat:,.2f}", f"{degisim:.2f}%" if degisim else None)
ortalama_fiyat = sum(anlik_fiyatlar)/len(anlik_fiyatlar) if anlik_fiyatlar else 0
st.metric("📊 ORTALAMA FİYAT", f"${ortalama_fiyat:,.2f}")

# ==================== DESTEK/DİRENÇ HESAPLA (15dk) ====================
with st.spinner("Destek/Direnç ve Göstergeler hesaplanıyor..."):
    # 4 borsadan 15dk veri
    tum_direncler, tum_destekler, son_df_15 = [], [], None
    for borsa in BORSALAR.values():
        df = veri_cek(borsa, secilen_coin, '15m', 200)
        if df is not None:
            if son_df_15 is None: son_df_15 = df
            d, s = seviye_bul(df, order=12)
            tum_direncler.append(d)
            tum_destekler.append(s)
    # Ortak seviyeler
    tum_tum_direnc = [item for alt in tum_direncler for item in alt]
    tum_tum_destek = [item for alt in tum_destekler for item in alt]
    direnc_sayac = Counter(tum_tum_direnc)
    destek_sayac = Counter(tum_tum_destek)
    tum_direnc = [(s, c) for s, c in direnc_sayac.items()]
    tum_destek = [(s, c) for s, c in destek_sayac.items()]
    tum_direnc.sort(key=lambda x: x[1], reverse=True)
    tum_destek.sort(key=lambda x: x[1], reverse=True)

# ==================== SCALP SİNYALİ (GÜÇ PUANLI) ====================
scalp_sinyali = None
if son_df_15 is not None:
    # 15dk göstergeler
    rsi_15 = rsi_hesapla(son_df_15).iloc[-1]
    macd_line, signal_line, hist = macd_hesapla(son_df_15)
    macd_trend = 1 if hist.iloc[-1] > 0 and hist.iloc[-1] > hist.iloc[-2] else (-1 if hist.iloc[-1] < 0 and hist.iloc[-1] < hist.iloc[-2] else 0)
    ema_cross = ema_kesisme(son_df_15)
    adx_val = adx_hesapla(son_df_15)
    stoch_k, stoch_d = stoch_rsi_hesapla(son_df_15)
    hacim_artti = hacim_kontrol(son_df_15, 1.3)
    atr_val = atr_hesapla(son_df_15)
    
    # En yakın destek/direnç
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
    
    # Mum yönü
    mum_yukselen = son_df_15['kapanis'].iloc[-1] > son_df_15['kapanis'].iloc[-2]
    
    # 1 saat trend onayı
    trend_1h = trend_onay_1saat(secilen_coin)
    
    # Likidite simülasyonu
    liq_puan_long = likidite_simulasyonu(ortalama_fiyat, en_yakin_destek, 'long') if en_yakin_destek else 0
    liq_puan_short = likidite_simulasyonu(ortalama_fiyat, en_yakin_direnc, 'short') if en_yakin_direnc else 0
    
    # Puanlama LONG
    long_puan = 0
    if mesafe_destek < 1.0: long_puan += 20
    elif mesafe_destek < 1.5: long_puan += 10
    if mum_yukselen: long_puan += 10
    if 35 < rsi_15 < 55: long_puan += 10
    if macd_trend == 1: long_puan += 15
    if ema_cross == 1: long_puan += 15
    if adx_val > 25: long_puan += 10
    if stoch_k < 20: long_puan += 10
    if hacim_artti: long_puan += 10
    if trend_1h == "YUKARI": long_puan += 10
    long_puan += liq_puan_long
    
    # Puanlama SHORT
    short_puan = 0
    if mesafe_direnc < 1.0: short_puan += 20
    elif mesafe_direnc < 1.5: short_puan += 10
    if not mum_yukselen: short_puan += 10
    if 45 < rsi_15 < 65: short_puan += 10
    if macd_trend == -1: short_puan += 15
    if ema_cross == -1: short_puan += 15
    if adx_val > 25: short_puan += 10
    if stoch_k > 80: short_puan += 10
    if hacim_artti: short_puan += 10
    if trend_1h == "AGI": short_puan += 10
    short_puan += liq_puan_short
    
    # SİNYAL KARARI (sadece 70+ puan)
    if long_puan >= 70:
        hedef_fiyat = ortalama_fiyat + (atr_val * 1.5)
        stop_fiyat = ortalama_fiyat - (atr_val * 1.0)
        scalp_sinyali = {
            'tip': 'LONG',
            'coin': coin_adi,
            'fiyat': ortalama_fiyat,
            'hedef': hedef_fiyat,
            'stop': stop_fiyat,
            'puan': long_puan,
            'destek': en_yakin_destek,
            'direnc': en_yakin_direnc,
            'rsi': round(rsi_15,1),
            'adx': round(adx_val,1),
            'macd': 'Yükselen' if macd_trend==1 else 'Düşen',
            'hacim': 'Güçlü' if hacim_artti else 'Normal',
            'trend_1h': trend_1h,
            'likidite': 'Yakın' if liq_puan_long>0 else 'Normal'
        }
    elif short_puan >= 70:
        hedef_fiyat = ortalama_fiyat - (atr_val * 1.5)
        stop_fiyat = ortalama_fiyat + (atr_val * 1.0)
        scalp_sinyali = {
            'tip': 'SHORT',
            'coin': coin_adi,
            'fiyat': ortalama_fiyat,
            'hedef': hedef_fiyat,
            'stop': stop_fiyat,
            'puan': short_puan,
            'destek': en_yakin_destek,
            'direnc': en_yakin_direnc,
            'rsi': round(rsi_15,1),
            'adx': round(adx_val,1),
            'macd': 'Düşen' if macd_trend==-1 else 'Yükselen',
            'hacim': 'Güçlü' if hacim_artti else 'Normal',
            'trend_1h': trend_1h,
            'likidite': 'Yakın' if liq_puan_short>0 else 'Normal'
        }

# ==================== TELEGRAM GÖNDER ====================
if scalp_sinyali:
    sinyal_id = f"{scalp_sinyali['coin']}_{scalp_sinyali['tip']}_{scalp_sinyali['fiyat']:.0f}"
    if sinyal_id not in st.session_state.gonderilen_sinyaller:
        st.session_state.gonderilen_sinyaller.append(sinyal_id)
        mesaj = f"""🔥 <b>ÇOK GÜÇLÜ SCALP SİNYALİ!</b> 🔥

<b>{'🟢 LONG' if scalp_sinyali['tip'] == 'LONG' else '🔴 SHORT'} {scalp_sinyali['coin']}</b>
📍 Giriş: <b>${scalp_sinyali['fiyat']:,.2f}</b>
🎯 Hedef: <b>${scalp_sinyali['hedef']:,.2f}</b>
🛑 Stop: <b>${scalp_sinyali['stop']:,.2f}</b>

📊 <b>Güven Puanı:</b> {scalp_sinyali['puan']}/100

📈 RSI: {scalp_sinyali['rsi']} | ADX: {scalp_sinyali['adx']}
📉 MACD: {scalp_sinyali['macd']} | Hacim: {scalp_sinyali['hacim']}
⏰ 1s Trend: {scalp_sinyali['trend_1h']} | Likidite: {scalp_sinyali['likidite']}

🟢 Destek: ${scalp_sinyali['destek']:.0f}
🔴 Direnç: ${scalp_sinyali['direnc']:.0f}

⏱️ {datetime.now().strftime('%H:%M:%S')} (15dk+1s onay)"""
        telegram_mesaj_gonder(mesaj)
        st.success(f"📨 {scalp_sinyali['tip']} sinyali Telegram'a gönderildi (Puan: {scalp_sinyali['puan']})")

# ==================== DASHBOARD GÖSTERİM ====================
if scalp_sinyali:
    st.markdown("---")
    if scalp_sinyali['tip'] == 'LONG':
        st.success(f"🎯 **LONG SİNYALİ - PUAN: {scalp_sinyali['puan']}**")
    else:
        st.error(f"🎯 **SHORT SİNYALİ - PUAN: {scalp_sinyali['puan']}**")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("📍 Giriş", f"${scalp_sinyali['fiyat']:,.2f}")
        st.metric("🎯 Hedef", f"${scalp_sinyali['hedef']:,.2f}")
    with col2:
        st.metric("🛑 Stop", f"${scalp_sinyali['stop']:,.2f}")
        st.metric("📊 RSI/ADX", f"{scalp_sinyali['rsi']} / {scalp_sinyali['adx']}")
    with col3:
        st.metric("📈 Trend 1s", scalp_sinyali['trend_1h'])
        st.metric("💧 Likidite", scalp_sinyali['likidite'])
else:
    st.info("🔍 Şu anda güçlü bir sinyal yok (70+ puan gerekli)")

# ==================== DESTEK/DİRENÇ LİSTESİ ====================
st.markdown("---")
st.subheader("📊 DESTEK/DİRENÇ SEVİYELERİ (4 Borsa, 15dk)")
col1, col2 = st.columns(2)
with col1:
    st.markdown("### 🟢 DESTEK")
    for seviye, guc in tum_destek[:8]:
        st.markdown(f"{'🔥' if guc>=4 else '✅' if guc>=3 else '🟡' if guc>=2 else '⚪'} **${seviye:,.2f}** - {guc}/4")
with col2:
    st.markdown("### 🔴 DİRENÇ")
    for seviye, guc in tum_direnc[:8]:
        st.markdown(f"{'🔥' if guc>=4 else '✅' if guc>=3 else '🟡' if guc>=2 else '⚪'} **${seviye:,.2f}** - {guc}/4")

st.caption("💡 **Sinyal kriterleri:** 15dk + 1saat onay | 7 gösterge | Likidite simülasyonu | Min 70 puan")
