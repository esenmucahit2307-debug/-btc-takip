import streamlit as st
import ccxt
import pandas as pd
import numpy as np
from scipy.signal import argrelextrema
from datetime import datetime
from collections import Counter
import time
import asyncio
import json
from streamlit.components.v1 import html

st.set_page_config(page_title="Canlı Kripto Dashboard", layout="wide")

# ==================== BAŞLIK ====================
st.title("📈 CANLI KRİPTO DASHBOARD")
st.markdown("**Binance + Bybit + Bitget + OKX** | Gerçek anlık fiyatlar | Güçlü Destek/Direnç (3+ Borsa)")

# ==================== COİN LİSTESİ ====================
coin_listesi = ["BTC/USDT", "ETH/USDT", "SOL/USDT", "ZEC/USDT", "APT/USDT", "SUI/USDT"]

# ==================== 4 BORSA ====================
BORSALAR = {
    'Binance': ccxt.binance(),
    'Bybit': ccxt.bybit(),
    'Bitget': ccxt.bitget(),
    'OKX': ccxt.okx()
}

# ==================== KENAR ÇUBUĞU ====================
with st.sidebar:
    st.header("⚙️ AYARLAR")
    
    secilen_coin = st.selectbox("💰 Coin seç:", coin_listesi, index=0)
    coin_adi = secilen_coin.split("/")[0]
    
    st.markdown("---")
    
    zaman_dilimleri = {
        "5 Dakika": "5m", "15 Dakika": "15m", "30 Dakika": "30m",
        "1 Saat": "1h", "4 Saat": "4h", "1 Gün": "1d", "1 Hafta": "1w"
    }
    
    secili_zaman = st.selectbox("⏱️ Zaman dilimi:", list(zaman_dilimleri.keys()), index=2)
    tf_kodu = zaman_dilimleri[secili_zaman]
    
    tf_map = {"5m": "5", "15m": "15", "30m": "30", "1h": "60", "4h": "240", "1d": "1D", "1w": "1W"}
    tv_tf = tf_map.get(tf_kodu, "60")
    
    st.markdown("---")
    
    st.subheader("📊 Göstergeler")
    destek_acik = st.checkbox("🟢 Destekleri Göster", value=True)
    direnc_acik = st.checkbox("🔴 Dirençleri Göster", value=True)
    
    st.markdown("---")
    
    if st.button("🔄 Yenile", use_container_width=True):
        st.rerun()
    
    st.caption(f"🕐 Son: {datetime.now().strftime('%H:%M:%S')}")

# ==================== TRADINGVIEW GRAFİK ====================
st.subheader(f"📊 {coin_adi} GRAFİK - {secili_zaman}")

tv_widget = f"""
<div class="tradingview-widget-container">
  <div id="tradingview_chart"></div>
  <script type="text/javascript" src="https://s3.tradingview.com/tv.js"></script>
  <script type="text/javascript">
  new TradingView.widget({{
    "width": "100%",
    "height": 500,
    "symbol": "BINANCE:{coin_adi}",
    "interval": "{tv_tf}",
    "timezone": "Europe/Istanbul",
    "theme": "dark",
    "style": "1",
    "locale": "tr",
    "enable_publishing": false,
    "allow_symbol_change": false,
    "container_id": "tradingview_chart"
  }});
  </script>
</div>
"""
html(tv_widget, height=550)

# ==================== CANLI FİYAT GÜNCELLEME ====================
st.subheader(f"💰 {coin_adi} CANLI FİYATLAR")

# Placeholder'lar
fiyat_placeholders = {}
for borsa_adi in BORSALAR.keys():
    fiyat_placeholders[borsa_adi] = st.empty()

# Bilgi placeholder'ı
info_placeholder = st.empty()

# Destek/direnç placeholder'ı
dd_placeholder = st.empty()

# ==================== FONKSİYONLAR ====================
def veri_cek(borsa, sembol, zaman_dilimi, limit=200):
    try:
        bardata = borsa.fetch_ohlcv(sembol, zaman_dilimi, limit=limit)
        df = pd.DataFrame(bardata, columns=['zaman', 'acilis', 'yuksek', 'dusuk', 'kapanis', 'hacim'])
        df['zaman'] = pd.to_datetime(df['zaman'], unit='ms')
        df.set_index('zaman', inplace=True)
        return df
    except:
        return None

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

def anlik_fiyat_al(borsa, sembol):
    try:
        ticker = borsa.fetch_ticker(sembol)
        return ticker['last'], ticker['percentage'] if 'percentage' in ticker else 0
    except:
        return None, None

def destek_direnc_hesapla(coin, tf):
    tum_direncler, tum_destekler, ana_df = [], [], None
    
    for borsa_adi, borsa in BORSALAR.items():
        df = veri_cek(borsa, coin, tf, limit=200)
        if df is not None and len(df) > 0:
            if ana_df is None:
                ana_df = df
            
            if tf in ['5m']:
                order_val = 8
            elif tf in ['15m', '30m']:
                order_val = 10
            else:
                order_val = 12
            
            direnc, destek = seviye_bul(df, order=order_val)
            tum_direncler.append(direnc)
            tum_destekler.append(destek)
    
    direnc_sayac = Counter()
    for alt_liste in tum_direncler:
        for item in alt_liste:
            direnc_sayac[item] += 1
    
    destek_sayac = Counter()
    for alt_liste in tum_destekler:
        for item in alt_liste:
            destek_sayac[item] += 1
    
    ortak_direnc = [(seviye, sayi) for seviye, sayi in direnc_sayac.items() if sayi >= 3]
    ortak_destek = [(seviye, sayi) for seviye, sayi in destek_sayac.items() if sayi >= 3]
    
    ortak_direnc.sort(key=lambda x: x[1], reverse=True)
    ortak_destek.sort(key=lambda x: x[1], reverse=True)
    
    return ortak_direnc, ortak_destek, ana_df

# ==================== DESTEK/DİRENÇ GÖSTER ====================
def destek_direnc_goster(ortak_destek, ortak_direnc):
    col_sup, col_res = st.columns(2)
    
    with col_sup:
        st.markdown("### 🟢 DESTEK SEVİYELERİ (3+ Borsa)")
        if ortak_destek:
            for seviye, guc in ortak_destek[:6]:
                if guc == 4:
                    st.markdown(f"**🔥 ${seviye:,.2f}** - {guc}/4 borsa (Çok Güçlü)")
                else:
                    st.markdown(f"**✅ ${seviye:,.2f}** - {guc}/4 borsa (Güçlü)")
        else:
            st.info("🔍 Destek seviyesi bulunamadı")
    
    with col_res:
        st.markdown("### 🔴 DİRENÇ SEVİYELERİ (3+ Borsa)")
        if ortak_direnc:
            for seviye, guc in ortak_direnc[:6]:
                if guc == 4:
                    st.markdown(f"**🔥 ${seviye:,.2f}** - {guc}/4 borsa (Çok Güçlü)")
                else:
                    st.markdown(f"**✅ ${seviye:,.2f}** - {guc}/4 borsa (Güçlü)")
        else:
            st.info("🔍 Direnç seviyesi bulunamadı")
    
    return col_sup, col_res

# ==================== İLK YÜKLEME ====================
ortak_direnc, ortak_destek, ana_df = destek_direnc_hesapla(secilen_coin, tf_kodu)

# ==================== CANLI DÖNGÜ ====================
info_placeholder.info("🔄 Canlı fiyatlar akıyor... Destek/Dirençler sayfa yenilendiğinde güncellenir.")

# Sonsuz döngü ile canlı fiyat güncelleme
for i in range(100):  # 100 döngü
    # Fiyatları güncelle
    for borsa_adi, borsa in BORSALAR.items():
        fiyat, degisim = anlik_fiyat_al(borsa, secilen_coin)
        if fiyat:
            with fiyat_placeholders[borsa_adi]:
                st.metric(borsa_adi, f"${fiyat:,.2f}", f"{degisim:.2f}%" if degisim else None)
    
    time.sleep(1)  # 1 saniye bekle
    
    # Her 30 döngüde bir sayfayı yenile (destek/direnç güncellemek için)
    if i % 30 == 0 and i > 0:
        st.rerun()

# ==================== DESTEK/DİRENÇ GÖSTERİMİ ====================
st.markdown("---")
destek_direnc_goster(ortak_destek, ortak_direnc)

st.caption("💡 **Nasıl çalışır?** Fiyatlar 1 saniyede bir güncellenir. Destek/Dirençler sayfa yenilendiğinde güncellenir (30 saniye).")
