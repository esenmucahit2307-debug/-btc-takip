import streamlit as st
import ccxt
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from scipy.signal import argrelextrema
from datetime import datetime
from collections import Counter
import time

st.set_page_config(page_title="TradingView Tarzı BTC Dashboard", layout="wide")

# ==================== BAŞLIK ====================
st.title("📈 CANLI KRİPTO DASHBOARD")
st.caption("TradingView tarzı | Gerçek zamanlı veri | Çoklu borsa")

# ==================== KENAR ÇUBUĞU (Tüm ayarlar burada) ====================
with st.sidebar:
    st.header("⚙️ PANEL AYARLARI")
    
    # 1. COIN SEÇİMİ
    st.subheader("💰 Coin Seçimi")
    coin_list = ["BTC/USDT", "ETH/USDT", "SOL/USDT", "XRP/USDT", "DOGE/USDT", "ADA/USDT", "AVAX/USDT"]
    secilen_coin = st.selectbox("Coin seç:", coin_list, index=0)
    coin_adi = secilen_coin.split("/")[0]
    
    st.markdown("---")
    
    # 2. ZAMAN DİLİMİ SEÇİMİ
    st.subheader("⏱️ Zaman Dilimi")
    zaman_dilimleri = {
        "1 Dakika": "1m",
        "3 Dakika": "3m",
        "5 Dakika": "5m",
        "15 Dakika": "15m",
        "30 Dakika": "30m",
        "1 Saat": "1h",
        "2 Saat": "2h",
        "4 Saat": "4h",
        "6 Saat": "6h",
        "12 Saat": "12h",
        "1 Gün": "1d",
        "1 Hafta": "1w"
    }
    
    secili_zaman = st.selectbox("Zaman dilimi seç:", list(zaman_dilimleri.keys()), index=4)
    tf_kodu = zaman_dilimleri[secili_zaman]
    
    st.markdown("---")
    
    # 3. BORSA SEÇİMİ (Çoklu seçim)
    st.subheader("🏛️ Borsalar")
    tum_borsalar = {
        'Binance': ccxt.binance(),
        'Bybit': ccxt.bybit(),
        'Bitget': ccxt.bitget(),
        'OKX': ccxt.okx()
    }
    
    secili_borsalar = st.multiselect(
        "Kullanılacak borsalar (en az 1 seç):",
        options=list(tum_borsalar.keys()),
        default=["Binance", "Bybit"]
    )
    
    if len(secili_borsalar) == 0:
        st.error("❌ En az bir borsa seçmelisiniz!")
        st.stop()
    
    st.markdown("---")
    
    # 4. GÖSTERGELER (Ne gösterilsin?)
    st.subheader("📊 Göstergeler")
    goster_destek_direnc = st.checkbox("🟢 Destek/Direnç (4 borsa ortak)", value=True)
    goster_long_tasfiye = st.checkbox("🔥 Long Tasfiye Bölgeleri", value=True)
    goster_short_tasfiye = st.checkbox("💀 Short Tasfiye Bölgeleri", value=True)
    goster_emirler = st.checkbox("📌 Borsa Emirleri (Alış/Satış)", value=False)
    
    st.markdown("---")
    
    # 5. OTOMATİK YENİLEME
    st.subheader("🔄 Otomatik Yenileme")
    yenileme_araligi = st.select_slider(
        "Yenileme sıklığı:",
        options=[5, 10, 15, 30, 60, 120],
        value=30
    )
    st.caption(f"Her {yenileme_araligi} saniyede bir yenilenecek")
    
    # Manuel yenileme butonu
    if st.button("🔄 Şimdi Yenile", use_container_width=True):
        st.rerun()
    
    st.markdown("---")
    st.caption(f"🕐 Son güncelleme: {datetime.now().strftime('%H:%M:%S')}")

# ==================== BORSALARI HAZIRLA ====================
borsalar = {}
for borsa_adi in secili_borsalar:
    borsalar[borsa_adi] = tum_borsalar[borsa_adi]

# ==================== FONKSİYONLAR ====================
def veri_cek(borsa, sembol, zaman_dilimi, limit=150):
    """OHLCV verisi çeker"""
    try:
        bardata = borsa.fetch_ohlcv(sembol, zaman_dilimi, limit=limit)
        df = pd.DataFrame(bardata, columns=['zaman', 'acilis', 'yuksek', 'dusuk', 'kapanis', 'hacim'])
        df['zaman'] = pd.to_datetime(df['zaman'], unit='ms')
        df.set_index('zaman', inplace=True)
        return df
    except Exception as e:
        return None

def seviye_bul(df, order=10, yuvarla=50):
    """Destek ve direnç seviyelerini bulur"""
    if df is None or len(df) < 20:
        return [], []
    tepeler = argrelextrema(df['yuksek'].values, np.greater_equal, order=order)[0]
    dipler = argrelextrema(df['dusuk'].values, np.less_equal, order=order)[0]
    direncler = [round(df['yuksek'].iloc[t] / yuvarla) * yuvarla for t in tepeler]
    destekler = [round(df['dusuk'].iloc[d] / yuvarla) * yuvarla for d in dipler]
    return list(set(direncler)), list(set(destekler))

def ortak_seviye_bul(tum_direncler, tum_destekler, min_borsa=2):
    """Seçilen borsaların ortak destek/direnç seviyelerini bulur"""
    if len(tum_direncler) < min_borsa:
        return [], []
    direnc_sayac = Counter([item for alt_liste in tum_direncler for item in alt_liste])
    destek_sayac = Counter([item for alt_liste in tum_destekler for item in alt_liste])
    ortak_direnc = [seviye for seviye, sayi in direnc_sayac.items() if sayi >= min_borsa]
    ortak_destek = [seviye for seviye, sayi in destek_sayac.items() if sayi >= min_borsa]
    return sorted(ortak_direnc), sorted(ortak_destek)

def tasfiye_seviyeleri_hesapla(guncel_fiyat):
    """Kaldıraç oranlarına göre tasfiye seviyelerini hesaplar"""
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

def emirleri_getir(borsa, sembol):
    """Borsadan alış/satış emirlerini getirir"""
    try:
        orderbook = borsa.fetch_order_book(sembol, limit=10)
        bids = orderbook['bids'][:5]
        asks = orderbook['asks'][:5]
        return bids, asks
    except:
        return [], []

def grafik_ciz(df, baslik, ortak_direnc, ortak_destek, tasfiye, guncel_fiyat, borsa_emirleri=None):
    """Ana grafiği çizer"""
    if df is None or len(df) == 0:
        fig = go.Figure()
        fig.add_annotation(text="Veri alınamadı", showarrow=False)
        return fig
    
    fig = go.Figure()
    
    # Mum grafiği
    fig.add_trace(go.Candlestick(
        x=df.index,
        open=df['acilis'],
        high=df['yuksek'],
        low=df['dusuk'],
        close=df['kapanis'],
        name=f'{baslik} Fiyat'
    ))
    
    # Destek çizgileri
    if goster_destek_direnc:
        for seviye in ortak_destek:
            fig.add_hline(y=seviye, line_dash="solid", line_color="green", line_width=2,
                         annotation_text=f"🟢 DESTEK {seviye:.0f}", annotation_position="top right")
        
        for seviye in ortak_direnc:
            fig.add_hline(y=seviye, line_dash="solid", line_color="red", line_width=2,
                         annotation_text=f"🔴 DİRENÇ {seviye:.0f}", annotation_position="top right")
    
    # Long tasfiye bölgeleri
    if goster_long_tasfiye:
        for seviye in tasfiye['long']:
            fig.add_hline(y=seviye, line_dash="dash", line_color="darkred", line_width=2,
                         annotation_text=f"🔥 LONG TASFİYE {seviye:.0f}", annotation_position="bottom left")
    
    # Short tasfiye bölgeleri
    if goster_short_tasfiye:
        for seviye in tasfiye['short']:
            fig.add_hline(y=seviye, line_dash="dash", line_color="purple", line_width=2,
                         annotation_text=f"💀 SHORT TASFİYE {seviye:.0f}", annotation_position="top left")
    
    # Güncel fiyat
    fig.add_hline(y=guncel_fiyat, line_dash="dot", line_color="white", line_width=1.5,
                 annotation_text=f"📍 GÜNCEL {guncel_fiyat:.0f}", annotation_position="top left")
    
    # Borsa emirleri (isteğe bağlı)
    if goster_emirler and borsa_emirleri:
        for borsa_adi, (bids, asks) in borsa_emirleri.items():
            if bids:
                fig.add_trace(go.Scatter(
                    x=[df.index[-1]] * len(bids),
                    y=[b[0] for b in bids],
                    mode='markers',
                    marker=dict(size=8, color='cyan', symbol='triangle-up'),
                    name=f'📥 {borsa_adi} Alış',
                    text=[f"{borsa_adi} ALIŞ\nFiyat: {b[0]:.0f}\nMiktar: {b[1]:.2f}" for b in bids],
                    hoverinfo='text'
                ))
            if asks:
                fig.add_trace(go.Scatter(
                    x=[df.index[-1]] * len(asks),
                    y=[a[0] for a in asks],
                    mode='markers',
                    marker=dict(size=8, color='orange', symbol='triangle-down'),
                    name=f'📤 {borsa_adi} Satış',
                    text=[f"{borsa_adi} SATIŞ\nFiyat: {a[0]:.0f}\nMiktar: {a[1]:.2f}" for a in asks],
                    hoverinfo='text'
                ))
    
    fig.update_layout(
        height=600,
        title=baslik,
        template="plotly_dark",
        xaxis_title="Zaman",
        yaxis_title="Fiyat (USDT)",
        xaxis_rangeslider_visible=False,
        hovermode='closest'
    )
    return fig

# ==================== ANA İŞLEM ====================
with st.spinner("Veriler yükleniyor..."):
    # Güncel fiyatı al
    guncel_fiyatlar = []
    for borsa_adi, borsa in borsalar.items():
        try:
            ticker = borsa.fetch_ticker(secilen_coin)
            guncel_fiyatlar.append(ticker['last'])
        except:
            pass
    
    guncel_fiyat = sum(guncel_fiyatlar) / len(guncel_fiyatlar) if guncel_fiyatlar else 70000
    
    # Tasfiye seviyeleri
    tasfiye = tasfiye_seviyeleri_hesapla(guncel_fiyat)
    
    # Üst bilgi kartları
    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:
        st.metric(f"💰 {coin_adi} Fiyatı", f"${guncel_fiyat:,.0f}")
    with col2:
        st.metric("📊 Zaman", secili_zaman)
    with col3:
        st.metric("🏛️ Borsa", f"{len(secili_borsalar)} Borsa")
    with col4:
        st.metric("🔥 Long Tasfiye", f"{tasfiye['long'][0] if tasfiye['long'] else '-'}")
    with col5:
        st.metric("💀 Short Tasfiye", f"{tasfiye['short'][0] if tasfiye['short'] else '-'}")
    
    st.markdown("---")
    
    # Veri çekme
    tum_direncler = []
    tum_destekler = []
    ana_df = None
    borsa_emirleri = {}
    
    for borsa_adi, borsa in borsalar.items():
        df = veri_cek(borsa, secilen_coin, tf_kodu)
        if df is not None:
            if ana_df is None:
                ana_df = df
            
            # Zaman dilimine göre order değeri
            if tf_kodu in ['1m', '3m', '5m', '15m']:
                order_val = 6
            elif tf_kodu in ['30m', '1h']:
                order_val = 8
            elif tf_kodu in ['2h', '4h', '6h']:
                order_val = 10
            else:
                order_val = 12
            
            direnc, destek = seviye_bul(df, order=order_val)
            tum_direncler.append(direnc)
            tum_destekler.append(destek)
        
        # Emirleri al
        if goster_emirler:
            bids, asks = emirleri_getir(borsa, secilen_coin)
            borsa_emirleri[borsa_adi] = (bids, asks)
    
    # Ortak destek/direnç
    ortak_direnc, ortak_destek = ortak_seviye_bul(tum_direncler, tum_destekler, min_borsa=2)
    
    # Grafik başlığı
    grafik_baslik = f"{coin_adi}/USDT - {secili_zaman} | {', '.join(secili_borsalar)}"
    
    # Grafiği çiz
    if ana_df is not None:
        fig = grafik_ciz(ana_df, grafik_baslik, ortak_direnc, ortak_destek, tasfiye, guncel_fiyat, borsa_emirleri if goster_emirler else None)
        st.plotly_chart(fig, use_container_width=True)
        
        # Destek/direnç listesi
        col_a, col_b = st.columns(2)
        with col_a:
            st.markdown(f"### 🟢 ORTAK DESTEK SEVİYELERİ")
            for s in ortak_destek[:5]:
                st.markdown(f"- **${s:,.0f}**")
            if not ortak_destek:
                st.info("Henüz ortak destek seviyesi bulunamadı")
        
        with col_b:
            st.markdown(f"### 🔴 ORTAK DİRENÇ SEVİYELERİ")
            for r in ortak_direnc[:5]:
                st.markdown(f"- **${r:,.0f}**")
            if not ortak_direnc:
                st.info("Henüz ortak direnç seviyesi bulunamadı")
    else:
        st.error("❌ Veri alınamadı. Lütfen farklı borsa veya zaman dilimi seçin.")

# ==================== OTOMATİK YENİLEME ====================
if 'son_yenileme' not in st.session_state:
    st.session_state.son_yenileme = time.time()

gecen_sure = time.time() - st.session_state.son_yenileme
if gecen_sure > yenileme_araligi:
    st.session_state.son_yenileme = time.time()
    st.rerun()
else:
    st.info(f"🔄 {int(yenileme_araligi - gecen_sure)} saniye içinde otomatik yenilenecek...")

st.caption("💡 **İpucu:** Sol menüden coin, zaman dilimi, borsa ve göstergeleri değiştirebilirsiniz. Sayfa otomatik yenilenir.")
