import streamlit as st
import ccxt
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from scipy.signal import argrelextrema
from datetime import datetime
from collections import Counter
import time

st.set_page_config(page_title="Canlı BTC Dashboard", layout="wide")

st.title("🔥 CANLI BTC DESTEK/DİRENÇ + TASFİYE HARİTASI")
st.caption(f"Son güncelleme: {datetime.now().strftime('%H:%M:%S')} | Veri: Binance + Bybit + Bitget + OKX")

borsalar = {
    'Binance': ccxt.binance(),
    'Bybit': ccxt.bybit(),
    'Bitget': ccxt.bitget(),
    'OKX': ccxt.okx()
}

sembol = "BTC/USDT"

def veri_cek(borsa, sembol, zaman_dilimi, limit=100):
    try:
        bardata = borsa.fetch_ohlcv(sembol, zaman_dilimi, limit=limit)
        df = pd.DataFrame(bardata, columns=['zaman', 'acilis', 'yuksek', 'dusuk', 'kapanis', 'hacim'])
        df['zaman'] = pd.to_datetime(df['zaman'], unit='ms')
        df.set_index('zaman', inplace=True)
        return df
    except:
        return None

def seviye_bul(df, order=10, yuvarla=50):
    if df is None or len(df) < 20:
        return [], []
    tepeler = argrelextrema(df['yuksek'].values, np.greater_equal, order=order)[0]
    dipler = argrelextrema(df['dusuk'].values, np.less_equal, order=order)[0]
    direncler = [round(df['yuksek'].iloc[t] / yuvarla) * yuvarla for t in tepeler]
    destekler = [round(df['dusuk'].iloc[d] / yuvarla) * yuvarla for d in dipler]
    return list(set(direncler)), list(set(destekler))

def ortak_seviye_bul(tum_direncler, tum_destekler, min_borsa=2):
    direnc_sayac = Counter([item for alt_liste in tum_direncler for item in alt_liste])
    destek_sayac = Counter([item for alt_liste in tum_destekler for item in alt_liste])
    ortak_direnc = [seviye for seviye, sayi in direnc_sayac.items() if sayi >= min_borsa]
    ortak_destek = [seviye for seviye, sayi in destek_sayac.items() if sayi >= min_borsa]
    return sorted(ortak_direnc), sorted(ortak_destek)

def tasfiye_seviyeleri(guncel_fiyat):
    kaldiraclar = [3, 5, 10, 20, 50]
    long_tasfiye = []
    short_tasfiye = []
    for k in kaldiraclar:
        long_tasfiye.append(round(guncel_fiyat * (1 - 1/k) / 100) * 100)
        short_tasfiye.append(round(guncel_fiyat * (1 + 1/k) / 100) * 100)
    return {
        'long': sorted(list(set(long_tasfiye))),
        'short': sorted(list(set(short_tasfiye)))
    }

def grafik_ciz(df, baslik, ortak_direnc, ortak_destek, tasfiye, guncel_fiyat):
    if df is None or len(df) == 0:
        fig = go.Figure()
        fig.add_annotation(text="Veri alınamadı", showarrow=False)
        return fig
    
    fig = go.Figure()
    
    fig.add_trace(go.Candlestick(
        x=df.index, open=df['acilis'], high=df['yuksek'],
        low=df['dusuk'], close=df['kapanis'], name='BTC'
    ))
    
    for seviye in ortak_destek:
        fig.add_hline(y=seviye, line_dash="solid", line_color="green", line_width=2,
                     annotation_text=f"🟢 DESTEK {seviye:.0f}")
    
    for seviye in ortak_direnc:
        fig.add_hline(y=seviye, line_dash="solid", line_color="red", line_width=2,
                     annotation_text=f"🔴 DİRENÇ {seviye:.0f}")
    
    for seviye in tasfiye['long']:
        fig.add_hline(y=seviye, line_dash="dash", line_color="darkred", line_width=2,
                     annotation_text=f"🔥 LONG TASFİYE {seviye:.0f}")
    
    for seviye in tasfiye['short']:
        fig.add_hline(y=seviye, line_dash="dash", line_color="purple", line_width=2,
                     annotation_text=f"💀 SHORT TASFİYE {seviye:.0f}")
    
    fig.add_hline(y=guncel_fiyat, line_dash="dot", line_color="white", line_width=1.5,
                 annotation_text=f"📍 GÜNCEL {guncel_fiyat:.0f}")
    
    fig.update_layout(height=550, template="plotly_dark", xaxis_rangeslider_visible=False)
    return fig

# Güncel fiyat
guncel_fiyatlar = []
for borsa in borsalar.values():
    try:
        ticker = borsa.fetch_ticker(sembol)
        guncel_fiyatlar.append(ticker['last'])
    except:
        pass
guncel_fiyat = sum(guncel_fiyatlar) / len(guncel_fiyatlar) if guncel_fiyatlar else 70000

tasfiye = tasfiye_seviyeleri(guncel_fiyat)

# Kenar çubuğu
with st.sidebar:
    st.header("⚙️ AYARLAR")
    secilen_coin = st.selectbox("Coin seç:", ["BTC/USDT", "ETH/USDT", "SOL/USDT"])
    st.markdown("---")
    st.markdown("🟢 **Düz Yeşil** = Destek")
    st.markdown("🔴 **Düz Kırmızı** = Direnç")
    st.markdown("🔴 **Kesik Koyu Kırmızı** = Long Tasfiye")
    st.markdown("🟣 **Kesik Mor** = Short Tasfiye")
    st.info("Sayfa her 30 saniyede yenilenir")
    if st.button("🔄 Şimdi Yenile"):
        st.rerun()

# Üst kartlar
col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric("💰 BTC Fiyatı", f"${guncel_fiyat:,.0f}")
with col2:
    st.metric("🔥 Long Tasfiye", f"{tasfiye['long'][:2] if tasfiye['long'] else 'Bulunamadı'}")
with col3:
    st.metric("💀 Short Tasfiye", f"{tasfiye['short'][:2] if tasfiye['short'] else 'Bulunamadı'}")
with col4:
    st.metric("📊 Borsa", f"{len(borsalar)} Borsa")

st.markdown("---")
st.subheader("📈 TÜM ZAMAN DİLİMLERİ")

zaman_dilimleri = {
    "30 Dakika": "30m", "1 Saat": "1h", "4 Saat": "4h",
    "1 Gün": "1d", "1 Hafta": "1w"
}

zaman_listesi = list(zaman_dilimleri.items())

for satir in range(0, len(zaman_listesi), 2):
    sutunlar = st.columns(2)
    for i in range(2):
        if satir + i < len(zaman_listesi):
            tf_adi, tf_kodu = zaman_listesi[satir + i]
            with sutunlar[i]:
                st.markdown(f"**🕐 {tf_adi}**")
                
                tum_direncler, tum_destekler, ana_df = [], [], None
                
                for borsa in borsalar.values():
                    df = veri_cek(borsa, secilen_coin, tf_kodu)
                    if df is not None:
                        if ana_df is None:
                            ana_df = df
                        order_val = 8 if tf_kodu in ['30m', '1h'] else (10 if tf_kodu == '4h' else 12)
                        direnc, destek = seviye_bul(df, order=order_val)
                        tum_direncler.append(direnc)
                        tum_destekler.append(destek)
                
                ortak_direnc, ortak_destek = ortak_seviye_bul(tum_direncler, tum_destekler)
                
                if ana_df is not None:
                    fig = grafik_ciz(ana_df, f"{secilen_coin} - {tf_adi}", ortak_direnc, ortak_destek, tasfiye, guncel_fiyat)
                    st.plotly_chart(fig, use_container_width=True)
                    
                    col_a, col_b = st.columns(2)
                    with col_a:
                        st.markdown(f"🟢 **Destek:** {ortak_destek[:2] if ortak_destek else 'Bulunamadı'}")
                    with col_b:
                        st.markdown(f"🔴 **Direnç:** {ortak_direnc[:2] if ortak_direnc else 'Bulunamadı'}")
                else:
                    st.error("❌ Veri alınamadı")

# Otomatik yenileme
st.markdown("---")
if 'son_yenileme' not in st.session_state:
    st.session_state.son_yenileme = time.time()

gecen_sure = time.time() - st.session_state.son_yenileme
if gecen_sure > 30:
    st.session_state.son_yenileme = time.time()
    st.rerun()
else:
    st.info(f"🔄 {int(30 - gecen_sure)} saniye içinde otomatik yenilenecek...")
