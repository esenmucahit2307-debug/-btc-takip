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

st.set_page_config(page_title="Canlı Kripto Dashboard", layout="wide")

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
st.title("📈 CANLI KRİPTO DASHBOARD")
st.markdown("**Binance + Bybit + Bitget + OKX** | 4 Borsa | Canlı Grafik | Destek/Direnç | Scalp Sinyalleri")

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
    
    zaman_dilimleri = {
        "5 Dakika": "5m", "15 Dakika": "15m", "30 Dakika": "30m",
        "1 Saat": "1h", "4 Saat": "4h", "1 Gün": "1d"
    }
    
    secili_zaman = st.selectbox("⏱️ Zaman dilimi:", list(zaman_dilimleri.keys()), index=1)
    tf_kodu = zaman_dilimleri[secili_zaman]
    
    st.markdown("---")
    
    st.subheader("🎯 Göstergeler")
    scalp_acik = st.checkbox("Scalp Sinyallerini Göster", value=True)
    
    st.markdown("---")
    
    st.subheader("🤖 TELEGRAM")
    
    if st.button("📨 Test Mesajı Gönder", use_container_width=True):
        with st.spinner("Gönderiliyor..."):
            if telegram_mesaj_gonder("✅ Bot çalışıyor! Scalp sinyalleri buraya gelecek."):
                st.success("✅ Mesaj gönderildi!")
            else:
                st.error("❌ Hata!")
    
    st.markdown("---")
    
    if st.button("🔄 Yenile", use_container_width=True):
        st.rerun()
    
    st.success(f"✅ {len(BORSALAR)} Borsa Aktif")
    st.caption(f"🕐 {datetime.now().strftime('%H:%M:%S')}")

# ==================== FONKSİYONLAR ====================
def veri_cek(borsa, sembol, zaman_dilimi, limit=150):
    try:
        bardata = borsa.fetch_ohlcv(sembol, zaman_dilimi, limit=limit)
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

def seviye_bul(df, order=10):
    if df is None or len(df) < 20:
        return [], []
    
    son_fiyat = df['kapanis'].iloc[-1]
    if son_fiyat < 50:
        yuvarla = 2
    elif son_fiyat < 200:
        yuvarla = 10
    else:
        yuvarla = 50
    
    tepeler = argrelextrema(df['yuksek'].values, np.greater_equal, order=order)[0]
    dipler = argrelextrema(df['dusuk'].values, np.less_equal, order=order)[0]
    
    direncler = [round(df['yuksek'].iloc[t] / yuvarla) * yuvarla for t in tepeler]
    destekler = [round(df['dusuk'].iloc[d] / yuvarla) * yuvarla for d in dipler]
    
    return list(set(direncler)), list(set(destekler))

def grafik_ciz(df, baslik):
    if df is None or len(df) == 0:
        return go.Figure()
    
    fig = go.Figure()
    
    fig.add_trace(go.Candlestick(
        x=df.index,
        open=df['acilis'],
        high=df['yuksek'],
        low=df['dusuk'],
        close=df['kapanis'],
        name='Fiyat'
    ))
    
    fig.update_layout(
        height=500,
        title=baslik,
        template="plotly_dark",
        xaxis_title="Zaman",
        yaxis_title="Fiyat (USDT)",
        xaxis_rangeslider_visible=False,
        dragmode="zoom"
    )
    
    return fig

# ==================== CANLI FİYATLAR ====================
st.subheader(f"💰 {coin_adi} CANLI FİYATLAR")

cols = st.columns(4)
anlik_fiyatlar = []
for idx, (borsa_adi, borsa) in enumerate(BORSALAR.items()):
    fiyat, degisim = anlik_fiyat_al(borsa, secilen_coin)
    if fiyat:
        anlik_fiyatlar.append(fiyat)
        with cols[idx]:
            st.metric(borsa_adi, f"${fiyat:,.2f}", f"{degisim:.2f}%" if degisim else None)

ortalama_fiyat = sum(anlik_fiyatlar) / len(anlik_fiyatlar) if anlik_fiyatlar else 0
st.metric("📊 ORTALAMA FİYAT", f"${ortalama_fiyat:,.2f}")

# ==================== GRAFİK ====================
with st.spinner("Grafik yükleniyor..."):
    ana_df = None
    for borsa_adi, borsa in BORSALAR.items():
        df = veri_cek(borsa, secilen_coin, tf_kodu)
        if df is not None:
            ana_df = df
            break
    
    if ana_df is not None:
        fig = grafik_ciz(ana_df, f"{coin_adi} - {secili_zaman} (4 Borsa Verisi)")
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.error("Veri alınamadı")

# ==================== DESTEK/DİRENÇ HESAPLA ====================
with st.spinner("Destek/Direnç hesaplanıyor..."):
    tum_direncler, tum_destekler = [], []
    
    for borsa_adi, borsa in BORSALAR.items():
        df = veri_cek(borsa, secilen_coin, tf_kodu)
        if df is not None:
            order_val = 10 if tf_kodu in ['15m', '30m'] else 12
            direnc, destek = seviye_bul(df, order=order_val)
            tum_direncler.append(direnc)
            tum_destekler.append(destek)
    
    tum_tum_direncler = [item for alt in tum_direncler for item in alt]
    tum_tum_destekler = [item for alt in tum_destekler for item in alt]
    
    direnc_sayac = Counter(tum_tum_direncler)
    destek_sayac = Counter(tum_tum_destekler)
    
    tum_direnc = [(s, c) for s, c in direnc_sayac.items()]
    tum_destek = [(s, c) for s, c in destek_sayac.items()]
    
    tum_direnc.sort(key=lambda x: x[1], reverse=True)
    tum_destek.sort(key=lambda x: x[1], reverse=True)

# ==================== SCALP SİNYALİ ====================
scalp_sinyali = None

if scalp_acik:
    son_df = None
    for borsa_adi, borsa in BORSALAR.items():
        df = veri_cek(borsa, secilen_coin, tf_kodu)
        if df is not None:
            son_df = df
            break
    
    if son_df is not None and len(son_df) > 20:
        son_kapanis = son_df['kapanis'].iloc[-1]
        onceki_kapanis = son_df['kapanis'].iloc[-2]
        
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
        
        if mesafe_destek < 1.5 and en_yakin_destek and son_kapanis > onceki_kapanis:
            scalp_sinyali = {'tip': 'LONG', 'coin': coin_adi, 'fiyat': ortalama_fiyat, 'destek': en_yakin_destek, 'direnc': en_yakin_direnc}
        elif mesafe_direnc < 1.5 and en_yakin_direnc and son_kapanis < onceki_kapanis:
            scalp_sinyali = {'tip': 'SHORT', 'coin': coin_adi, 'fiyat': ortalama_fiyat, 'destek': en_yakin_destek, 'direnc': en_yakin_direnc}

# ==================== TELEGRAM'A GÖNDER ====================
if scalp_sinyali:
    sinyal_id = f"{scalp_sinyali['coin']}_{scalp_sinyali['tip']}_{scalp_sinyali['fiyat']:.0f}"
    
    if sinyal_id not in st.session_state.gonderilen_sinyaller:
        st.session_state.gonderilen_sinyaller.append(sinyal_id)
        
        mesaj = f"""🚨 YENİ SCALP SİNYALİ! 🚨

{'🟢 LONG' if scalp_sinyali['tip'] == 'LONG' else '🔴 SHORT'} {scalp_sinyali['coin']}

📍 Giriş: ${scalp_sinyali['fiyat']:,.2f}
🟢 Destek: ${scalp_sinyali['destek']:,.2f}
🔴 Direnç: ${scalp_sinyali['direnc']:,.2f}

⏰ {datetime.now().strftime('%H:%M:%S')}"""
        
        telegram_mesaj_gonder(mesaj)
        st.success(f"📨 {scalp_sinyali['tip']} sinyali Telegram'a gönderildi!")

# ==================== SCALP SİNYALİ GÖSTER ====================
if scalp_sinyali:
    if scalp_sinyali['tip'] == 'LONG':
        st.success(f"🎯 **LONG SCALP SİNYALİ - {scalp_sinyali['coin']}**")
        st.markdown(f"📍 Giriş: **${scalp_sinyali['fiyat']:,.2f}** | 🟢 Destek: **${scalp_sinyali['destek']:,.2f}** | 🔴 Direnç: **${scalp_sinyali['direnc']:,.2f}**")
    else:
        st.error(f"🎯 **SHORT SCALP SİNYALİ - {scalp_sinyali['coin']}**")
        st.markdown(f"📍 Giriş: **${scalp_sinyali['fiyat']:,.2f}** | 🟢 Destek: **${scalp_sinyali['destek']:,.2f}** | 🔴 Direnç: **${scalp_sinyali['direnc']:,.2f}**")

# ==================== DESTEK/DİRENÇ LİSTESİ ====================
st.markdown("---")
st.subheader("📊 DESTEK/DİRENÇ SEVİYELERİ (4 Borsa)")

col1, col2 = st.columns(2)

with col1:
    st.markdown("### 🟢 DESTEK")
    for seviye, guc in tum_destek[:8]:
        if guc == 4:
            st.markdown(f"🔥 **${seviye:,.2f}** - {guc}/4 Borsa (Çok Güçlü)")
        elif guc == 3:
            st.markdown(f"✅ **${seviye:,.2f}** - {guc}/4 Borsa (Güçlü)")
        elif guc == 2:
            st.markdown(f"🟡 **${seviye:,.2f}** - {guc}/4 Borsa (Orta)")
        else:
            st.markdown(f"⚪ **${seviye:,.2f}** - {guc}/4 Borsa (Zayıf)")

with col2:
    st.markdown("### 🔴 DİRENÇ")
    for seviye, guc in tum_direnc[:8]:
        if guc == 4:
            st.markdown(f"🔥 **${seviye:,.2f}** - {guc}/4 Borsa (Çok Güçlü)")
        elif guc == 3:
            st.markdown(f"✅ **${seviye:,.2f}** - {guc}/4 Borsa (Güçlü)")
        elif guc == 2:
            st.markdown(f"🟡 **${seviye:,.2f}** - {guc}/4 Borsa (Orta)")
        else:
            st.markdown(f"⚪ **${seviye:,.2f}** - {guc}/4 Borsa (Zayıf)")

st.caption("💡 Grafik, 4 borsanın verisiyle oluşturulur | Sinyal geldiğinde Telegram'a gider")
