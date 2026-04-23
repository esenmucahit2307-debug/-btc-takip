import streamlit as st
import ccxt
import pandas as pd
import numpy as np
from scipy.signal import argrelextrema
from datetime import datetime
from collections import Counter
import time
from streamlit.components.v1 import html

st.set_page_config(page_title="Canlı Kripto Dashboard", layout="wide")

# ==================== BAŞLIK ====================
st.title("📈 CANLI KRİPTO DASHBOARD")
st.markdown("**Binance + Bybit + Bitget + OKX** | Gerçek anlık grafik | Güçlü Destek/Direnç (3+ Borsa) | Scalp Sinyalleri")

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
        "1 Dakika": "1m", "5 Dakika": "5m", "15 Dakika": "15m",
        "30 Dakika": "30m", "1 Saat": "1h", "4 Saat": "4h",
        "1 Gün": "1d", "1 Hafta": "1w"
    }
    
    secili_zaman = st.selectbox("⏱️ Zaman dilimi:", list(zaman_dilimleri.keys()), index=3)
    tf_kodu = zaman_dilimleri[secili_zaman]
    
    # TradingView için interval dönüşümü
    tf_map = {"1m": "1", "5m": "5", "15m": "15", "30m": "30", "1h": "60", "4h": "240", "1d": "1D", "1w": "1W"}
    tv_tf = tf_map.get(tf_kodu, "60")
    
    st.markdown("---")
    
    st.subheader("📊 Göstergeler")
    destek_acik = st.checkbox("🟢 Destekleri Göster", value=True)
    direnc_acik = st.checkbox("🔴 Dirençleri Göster", value=True)
    scalp_acik = st.checkbox("🎯 Scalp Sinyallerini Göster", value=True)
    
    st.markdown("---")
    
    if st.button("🔄 Destek/Dirençleri Yenile", use_container_width=True):
        st.rerun()
    
    st.caption(f"🕐 Son güncelleme: {datetime.now().strftime('%H:%M:%S')}")
    st.info("📌 Grafik CANLI olarak akar. Destek/Dirençler sayfa yenilendiğinde güncellenir.")

# ==================== TRADINGVIEW CANLI GRAFİK ====================
st.subheader(f"📊 {coin_adi} CANLI GRAFİK - {secili_zaman}")

tv_widget = f"""
<div class="tradingview-widget-container">
  <div id="tradingview_chart"></div>
  <script type="text/javascript" src="https://s3.tradingview.com/tv.js"></script>
  <script type="text/javascript">
  new TradingView.widget({{
    "width": "100%",
    "height": 550,
    "symbol": "BINANCE:{coin_adi}",
    "interval": "{tv_tf}",
    "timezone": "Europe/Istanbul",
    "theme": "dark",
    "style": "1",
    "locale": "tr",
    "toolbar_bg": "#131722",
    "enable_publishing": false,
    "allow_symbol_change": false,
    "container_id": "tradingview_chart",
    "studies": [
        "MASimple@tv-basicstudies",
        "RSI@tv-basicstudies"
    ]
  }});
  </script>
</div>
"""

html(tv_widget, height=600)

# ==================== FONKSİYONLAR ====================
def veri_cek(borsa, sembol, zaman_dilimi, limit=300):
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

# ==================== CANLI FİYATLAR ====================
st.subheader(f"💰 {coin_adi} CANLI FİYATLAR")

fiyat_cols = st.columns(4)
anlik_fiyatlar = []
for idx, (borsa_adi, borsa) in enumerate(BORSALAR.items()):
    fiyat, degisim = anlik_fiyat_al(borsa, secilen_coin)
    if fiyat:
        anlik_fiyatlar.append(fiyat)
        with fiyat_cols[idx]:
            st.metric(borsa_adi, f"${fiyat:,.2f}", f"{degisim:.2f}%" if degisim else None)

ortalama_fiyat = sum(anlik_fiyatlar) / len(anlik_fiyatlar) if anlik_fiyatlar else 0

# ==================== DESTEK/DİRENÇ HESAPLAMA ====================
with st.spinner("Güçlü Destek/Direnç seviyeleri hesaplanıyor..."):
    tum_direncler, tum_destekler, ana_df = [], [], None
    
    for borsa_adi, borsa in BORSALAR.items():
        df = veri_cek(borsa, secilen_coin, tf_kodu, limit=300)
        if df is not None and len(df) > 0:
            if ana_df is None:
                ana_df = df
            
            if tf_kodu in ['1m', '5m']:
                order_val = 8
            elif tf_kodu in ['15m', '30m']:
                order_val = 10
            else:
                order_val = 12
            
            direnc, destek = seviye_bul(df, order=order_val)
            tum_direncler.append(direnc)
            tum_destekler.append(destek)
    
    # Ortak seviyeleri bul (3+ borsa)
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

# ==================== DESTEK/DİRENÇ LİSTESİ ====================
st.markdown("---")
st.subheader("📊 GÜÇLÜ DESTEK/DİRENÇ SEVİYELERİ (3+ Borsa)")

col_sup, col_res = st.columns(2)

with col_sup:
    st.markdown("### 🟢 DESTEK")
    if ortak_destek:
        for seviye, guc in ortak_destek[:8]:
            if guc == 4:
                st.markdown(f"**🔥 ${seviye:,.2f}** - {guc}/4 borsa (Çok Güçlü)")
            else:
                st.markdown(f"**✅ ${seviye:,.2f}** - {guc}/4 borsa (Güçlü)")
    else:
        st.info("🔍 Destek seviyesi bulunamadı")

with col_res:
    st.markdown("### 🔴 DİRENÇ")
    if ortak_direnc:
        for seviye, guc in ortak_direnc[:8]:
            if guc == 4:
                st.markdown(f"**🔥 ${seviye:,.2f}** - {guc}/4 borsa (Çok Güçlü)")
            else:
                st.markdown(f"**✅ ${seviye:,.2f}** - {guc}/4 borsa (Güçlü)")
    else:
        st.info("🔍 Direnç seviyesi bulunamadı")

# ==================== SCALP SİNYALİ ====================
if scalp_acik and ana_df is not None and len(ana_df) > 20:
    son_kapanis = ana_df['kapanis'].iloc[-1]
    onceki_kapanis = ana_df['kapanis'].iloc[-2]
    
    en_yakin_destek = ortak_destek[0][0] if ortak_destek else None
    en_yakin_direnc = ortak_direnc[0][0] if ortak_direnc else None
    
    mesafe_destek = ((ortalama_fiyat - en_yakin_destek) / ortalama_fiyat * 100) if en_yakin_destek else 100
    mesafe_direnc = ((en_yakin_direnc - ortalama_fiyat) / ortalama_fiyat * 100) if en_yakin_direnc else 100
    
    scalp_sinyali = None
    
    # LONG sinyali
    if mesafe_destek < 1.5 and en_yakin_destek and son_kapanis > onceki_kapanis:
        scalp_sinyali = {
            'tip': 'LONG',
            'giris': ortalama_fiyat,
            'hedef': en_yakin_direnc if en_yakin_direnc else ortalama_fiyat * 1.02,
            'stop': en_yakin_destek - (ortalama_fiyat * 0.005),
            'destek': en_yakin_destek,
            'direnc': en_yakin_direnc
        }
    # SHORT sinyali
    elif mesafe_direnc < 1.5 and en_yakin_direnc and son_kapanis < onceki_kapanis:
        scalp_sinyali = {
            'tip': 'SHORT',
            'giris': ortalama_fiyat,
            'hedef': en_yakin_destek if en_yakin_destek else ortalama_fiyat * 0.98,
            'stop': en_yakin_direnc + (ortalama_fiyat * 0.005),
            'destek': en_yakin_destek,
            'direnc': en_yakin_direnc
        }
    
    if scalp_sinyali:
        st.markdown("---")
        st.subheader(f"🎯 GÜNCEL {scalp_sinyali['tip']} SCALP SİNYALİ")
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("📍 Giriş", f"${scalp_sinyali['giris']:,.2f}")
            st.metric("🎯 Hedef", f"${scalp_sinyali['hedef']:,.2f}")
        with col2:
            st.metric("🛑 Stop", f"${scalp_sinyali['stop']:,.2f}")
            if scalp_sinyali['destek']:
                st.metric("🟢 Destek", f"${scalp_sinyali['destek']:,.2f}")
        with col3:
            if scalp_sinyali['direnc']:
                st.metric("🔴 Direnç", f"${scalp_sinyali['direnc']:,.2f}")
            if scalp_sinyali['tip'] == 'LONG':
                kar_orani = ((scalp_sinyali['hedef'] - scalp_sinyali['giris']) / scalp_sinyali['giris'] * 100)
            else:
                kar_orani = ((scalp_sinyali['giris'] - scalp_sinyali['hedef']) / scalp_sinyali['giris'] * 100)
            st.metric("📈 Kar", f"%{kar_orani:.2f}")

# ==================== BİLGİ ====================
st.markdown("---")
st.info("💡 **Bilgi:** Grafik TradingView altyapısı ile **CANLI** olarak güncellenir. Destek/Direnç seviyeleri sağ menüdeki 'Yenile' butonu ile güncellenir.")
