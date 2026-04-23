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
st.markdown("**Binance + Bybit + Bitget + OKX** (4 Borsa) | Gerçek anlık fiyatlar | Destek/Direnç (Tüm seviyeler)")

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
    
    if st.button("🔄 Destek/Dirençleri Yenile", use_container_width=True):
        st.rerun()
    
    st.success("✅ Binance + Bybit + Bitget + OKX (4 Borsa)")
    st.caption(f"🕐 Son güncelleme: {datetime.now().strftime('%H:%M:%S')}")

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

# ==================== CANLI FİYATLAR ====================
st.subheader(f"💰 {coin_adi} CANLI FİYATLAR (4 Borsa - 1 Saniye)")

def anlik_fiyat_al(borsa, sembol):
    try:
        ticker = borsa.fetch_ticker(sembol)
        return ticker['last'], ticker['percentage'] if 'percentage' in ticker else 0
    except:
        return None, None

# Fiyatları göster
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

# ==================== DESTEK/DİRENÇ HESAPLA (4 BORSA) ====================
with st.spinner("4 borsadan destek/direnç seviyeleri hesaplanıyor..."):
    tum_direncler = []
    tum_destekler = []
    
    for borsa_adi, borsa in BORSALAR.items():
        df = veri_cek(borsa, secilen_coin, tf_kodu, limit=200)
        if df is not None and len(df) > 0:
            if tf_kodu in ['5m']:
                order_val = 8
            elif tf_kodu in ['15m', '30m']:
                order_val = 10
            else:
                order_val = 12
            
            direnc, destek = seviye_bul(df, order=order_val)
            tum_direncler.append(direnc)
            tum_destekler.append(destek)
            st.success(f"✅ {borsa_adi} verisi alındı: {len(direnc)} direnç, {len(destek)} destek")
    
    # TÜM SEVİYELERİ BİRLEŞTİR (4 borsa)
    tum_tum_direncler = []
    for alt_liste in tum_direncler:
        tum_tum_direncler.extend(alt_liste)
    
    tum_tum_destekler = []
    for alt_liste in tum_destekler:
        tum_tum_destekler.extend(alt_liste)
    
    # Her seviyenin kaç borsada görüldüğünü hesapla
    direnc_sayac = Counter(tum_tum_direncler)
    destek_sayac = Counter(tum_tum_destekler)
    
    # Tüm seviyeleri al (1,2,3,4 borsa)
    tum_direnc_seviyeleri = [(seviye, sayi) for seviye, sayi in direnc_sayac.items()]
    tum_destek_seviyeleri = [(seviye, sayi) for seviye, sayi in destek_sayac.items()]
    
    # Güce göre sırala (en güçlü önce)
    tum_direnc_seviyeleri.sort(key=lambda x: x[1], reverse=True)
    tum_destek_seviyeleri.sort(key=lambda x: x[1], reverse=True)

# ==================== DESTEK/DİRENÇ GÖSTER ====================
st.markdown("---")
st.subheader("📊 DESTEK/DİRENÇ SEVİYELERİ (4 Borsa)")

col_sup, col_res = st.columns(2)

with col_sup:
    st.markdown("### 🟢 DESTEK SEVİYELERİ")
    if tum_destek_seviyeleri:
        for seviye, guc in tum_destek_seviyeleri[:12]:
            if guc == 4:
                st.markdown(f"**🔥 ${seviye:,.2f}** - {guc}/4 borsa (Çok Güçlü - Tüm borsalar)")
            elif guc == 3:
                st.markdown(f"**✅ ${seviye:,.2f}** - {guc}/4 borsa (Güçlü)")
            elif guc == 2:
                st.markdown(f"**🟡 ${seviye:,.2f}** - {guc}/4 borsa (Orta)")
            else:
                st.markdown(f"**⚪ ${seviye:,.2f}** - {guc}/4 borsa (Zayıf)")
    else:
        st.info("🔍 Destek seviyesi bulunamadı")
    
    st.caption(f"Toplam {len(tum_destek_seviyeleri)} destek seviyesi")

with col_res:
    st.markdown("### 🔴 DİRENÇ SEVİYELERİ")
    if tum_direnc_seviyeleri:
        for seviye, guc in tum_direnc_seviyeleri[:12]:
            if guc == 4:
                st.markdown(f"**🔥 ${seviye:,.2f}** - {guc}/4 borsa (Çok Güçlü - Tüm borsalar)")
            elif guc == 3:
                st.markdown(f"**✅ ${seviye:,.2f}** - {guc}/4 borsa (Güçlü)")
            elif guc == 2:
                st.markdown(f"**🟡 ${seviye:,.2f}** - {guc}/4 borsa (Orta)")
            else:
                st.markdown(f"**⚪ ${seviye:,.2f}** - {guc}/4 borsa (Zayıf)")
    else:
        st.info("🔍 Direnç seviyesi bulunamadı")
    
    st.caption(f"Toplam {len(tum_direnc_seviyeleri)} direnç seviyesi")

# ==================== ÖZET BİLGİ ====================
st.markdown("---")
st.info(f"""
**📊 ÖZET:**
- 🔥 **4/4 borsa** = Tüm borsalarda görülen seviye (Çok Güçlü)
- ✅ **3/4 borsa** = 3 borsada görülen seviye (Güçlü)
- 🟡 **2/4 borsa** = 2 borsada görülen seviye (Orta)
- ⚪ **1/4 borsa** = Tek borsada görülen seviye (Zayıf)

**📌 Toplam:** {len(tum_destek_seviyeleri)} destek + {len(tum_direnc_seviyeleri)} direnç seviyesi bulundu.
""")

st.caption("💡 **Nasıl çalışır?** 4 borsanın (Binance, Bybit, Bitget, OKX) verileri kullanılır. Her seviyenin kaç borsada görüldüğü belirtilir.")
