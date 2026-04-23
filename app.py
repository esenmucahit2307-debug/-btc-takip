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
st.markdown("**Binance + Bybit + Bitget + OKX** (4 Borsa) | Destek/Direnç | SCALP SİNYALLERİ (BTC, ETH, SOL, ZEC, APT, SUI)")

# ==================== COİN LİSTESİ (SADECE SCALP COİNLER) ====================
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
    scalp_acik = st.checkbox("🎯 Scalp Sinyallerini Göster", value=True)
    
    st.markdown("---")
    
    if st.button("🔄 Yenile", use_container_width=True):
        st.rerun()
    
    st.success("✅ Binance + Bybit + Bitget + OKX (4 Borsa)")
    st.info("🎯 Scalp sinyalleri: BTC, ETH, SOL, ZEC, APT, SUI")
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
st.subheader(f"💰 {coin_adi} CANLI FİYATLAR (4 Borsa)")

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

# ==================== DESTEK/DİRENÇ HESAPLA ====================
with st.spinner("4 borsadan destek/direnç seviyeleri hesaplanıyor..."):
    tum_direncler = []
    tum_destekler = []
    son_df = None
    
    for borsa_adi, borsa in BORSALAR.items():
        df = veri_cek(borsa, secilen_coin, tf_kodu, limit=200)
        if df is not None and len(df) > 0:
            if son_df is None:
                son_df = df
            
            if tf_kodu in ['5m']:
                order_val = 8
            elif tf_kodu in ['15m', '30m']:
                order_val = 10
            else:
                order_val = 12
            
            direnc, destek = seviye_bul(df, order=order_val)
            tum_direncler.append(direnc)
            tum_destekler.append(destek)
    
    # Tüm seviyeleri birleştir
    tum_tum_direncler = []
    for alt_liste in tum_direncler:
        tum_tum_direncler.extend(alt_liste)
    
    tum_tum_destekler = []
    for alt_liste in tum_destekler:
        tum_tum_destekler.extend(alt_liste)
    
    # Her seviyenin kaç borsada görüldüğünü hesapla
    direnc_sayac = Counter(tum_tum_direncler)
    destek_sayac = Counter(tum_tum_destekler)
    
    # Tüm seviyeleri al
    tum_direnc_seviyeleri = [(seviye, sayi) for seviye, sayi in direnc_sayac.items()]
    tum_destek_seviyeleri = [(seviye, sayi) for seviye, sayi in destek_sayac.items()]
    
    # Güce göre sırala
    tum_direnc_seviyeleri.sort(key=lambda x: x[1], reverse=True)
    tum_destek_seviyeleri.sort(key=lambda x: x[1], reverse=True)

# ==================== SCALP SİNYALİ ÜRET ====================
scalp_sinyali = None

if scalp_acik and son_df is not None and len(son_df) > 20:
    son_kapanis = son_df['kapanis'].iloc[-1]
    onceki_kapanis = son_df['kapanis'].iloc[-2]
    
    # En yakın destek ve direnç
    en_yakin_destek = None
    for seviye, _ in tum_destek_seviyeleri:
        if seviye < ortalama_fiyat:
            if en_yakin_destek is None or seviye > en_yakin_destek:
                en_yakin_destek = seviye
    
    en_yakin_direnc = None
    for seviye, _ in tum_direnc_seviyeleri:
        if seviye > ortalama_fiyat:
            if en_yakin_direnc is None or seviye < en_yakin_direnc:
                en_yakin_direnc = seviye
    
    if en_yakin_destek:
        mesafe_destek = (ortalama_fiyat - en_yakin_destek) / ortalama_fiyat * 100
    else:
        mesafe_destek = 100
    
    if en_yakin_direnc:
        mesafe_direnc = (en_yakin_direnc - ortalama_fiyat) / ortalama_fiyat * 100
    else:
        mesafe_direnc = 100
    
    # LONG SİNYALİ (Desteğe yakın ve yükseliş)
    if mesafe_destek < 1.5 and en_yakin_destek and son_kapanis > onceki_kapanis:
        scalp_sinyali = {
            'tip': 'LONG',
            'giris': ortalama_fiyat,
            'hedef': en_yakin_direnc if en_yakin_direnc else ortalama_fiyat * 1.02,
            'stop': en_yakin_destek - (ortalama_fiyat * 0.005),
            'destek': en_yakin_destek,
            'direnc': en_yakin_direnc,
            'mesafe': round(mesafe_destek, 2)
        }
    
    # SHORT SİNYALİ (Dirence yakın ve düşüş)
    elif mesafe_direnc < 1.5 and en_yakin_direnc and son_kapanis < onceki_kapanis:
        scalp_sinyali = {
            'tip': 'SHORT',
            'giris': ortalama_fiyat,
            'hedef': en_yakin_destek if en_yakin_destek else ortalama_fiyat * 0.98,
            'stop': en_yakin_direnc + (ortalama_fiyat * 0.005),
            'destek': en_yakin_destek,
            'direnc': en_yakin_direnc,
            'mesafe': round(mesafe_direnc, 2)
        }

# ==================== SCALP SİNYALİ GÖSTER ====================
if scalp_sinyali:
    st.markdown("---")
    if scalp_sinyali['tip'] == 'LONG':
        st.success(f"🎯 **GÜNCEL LONG SCALP SİNYALİ - {coin_adi}**")
    else:
        st.error(f"🎯 **GÜNCEL SHORT SCALP SİNYALİ - {coin_adi}**")
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("📍 Giriş Fiyatı", f"${scalp_sinyali['giris']:,.2f}")
        st.metric("🎯 Hedef", f"${scalp_sinyali['hedef']:,.2f}")
    with col2:
        st.metric("🛑 Stop Loss", f"${scalp_sinyali['stop']:,.2f}")
        if scalp_sinyali['destek']:
            st.metric("🟢 Destek", f"${scalp_sinyali['destek']:,.2f}")
    with col3:
        if scalp_sinyali['direnc']:
            st.metric("🔴 Direnç", f"${scalp_sinyali['direnc']:,.2f}")
        if scalp_sinyali['tip'] == 'LONG':
            kar_orani = ((scalp_sinyali['hedef'] - scalp_sinyali['giris']) / scalp_sinyali['giris'] * 100)
        else:
            kar_orani = ((scalp_sinyali['giris'] - scalp_sinyali['hedef']) / scalp_sinyali['giris'] * 100)
        st.metric("📈 Potansiyel Kar", f"%{kar_orani:.2f}")
        st.metric("📊 Mesafe", f"%{scalp_sinyali['mesafe']}")
else:
    if scalp_acik:
        st.info("🔍 Şu anda scalp sinyali yok")

# ==================== DESTEK/DİRENÇ GÖSTER ====================
st.markdown("---")
st.subheader("📊 DESTEK/DİRENÇ SEVİYELERİ (4 Borsa)")

col_sup, col_res = st.columns(2)

with col_sup:
    st.markdown("### 🟢 DESTEK")
    if tum_destek_seviyeleri:
        for seviye, guc in tum_destek_seviyeleri[:10]:
            if guc == 4:
                st.markdown(f"**🔥 ${seviye:,.2f}** - {guc}/4 (Çok Güçlü)")
            elif guc == 3:
                st.markdown(f"**✅ ${seviye:,.2f}** - {guc}/4 (Güçlü)")
            elif guc == 2:
                st.markdown(f"**🟡 ${seviye:,.2f}** - {guc}/4 (Orta)")
            else:
                st.markdown(f"**⚪ ${seviye:,.2f}** - {guc}/4 (Zayıf)")
    else:
        st.info("Destek bulunamadı")

with col_res:
    st.markdown("### 🔴 DİRENÇ")
    if tum_direnc_seviyeleri:
        for seviye, guc in tum_direnc_seviyeleri[:10]:
            if guc == 4:
                st.markdown(f"**🔥 ${seviye:,.2f}** - {guc}/4 (Çok Güçlü)")
            elif guc == 3:
                st.markdown(f"**✅ ${seviye:,.2f}** - {guc}/4 (Güçlü)")
            elif guc == 2:
                st.markdown(f"**🟡 ${seviye:,.2f}** - {guc}/4 (Orta)")
            else:
                st.markdown(f"**⚪ ${seviye:,.2f}** - {guc}/4 (Zayıf)")
    else:
        st.info("Direnç bulunamadı")

# ==================== ÖZET ====================
st.markdown("---")
st.caption(f"💡 **Toplam:** {len(tum_destek_seviyeleri)} destek + {len(tum_direnc_seviyeleri)} direnç | Scalp sinyalleri sadece {', '.join(coin_listesi)} coinleri için üretilir.")
