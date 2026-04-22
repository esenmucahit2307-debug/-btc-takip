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

# ==================== 30+ COİN LİSTESİ ====================
coin_listesi = [
    "BTC/USDT", "ETH/USDT", "SOL/USDT", "XRP/USDT", "DOGE/USDT",
    "ADA/USDT", "AVAX/USDT", "DOT/USDT", "LINK/USDT", "MATIC/USDT",
    "UNI/USDT", "ATOM/USDT", "LTC/USDT", "BCH/USDT", "NEAR/USDT",
    "APT/USDT", "ARB/USDT", "OP/USDT", "INJ/USDT", "SUI/USDT",
    "PEPE/USDT", "WIF/USDT", "FLOKI/USDT", "BONK/USDT", "SHIB/USDT",
    "TON/USDT", "TRX/USDT", "ETC/USDT", "FIL/USDT", "AAVE/USDT"
]

# ==================== BAŞLIK ====================
st.title("📈 CANLI KRİPTO DASHBOARD")
st.caption("TradingView tarzı | Gerçek zamanlı veri | Yakınlaştır/Kaydır | Saniyelik fiyat takibi")

# ==================== KENAR ÇUBUĞU ====================
with st.sidebar:
    st.header("⚙️ PANEL AYARLARI")
    
    # 1. COIN SEÇİMİ (30+ coin)
    st.subheader("💰 Coin Seçimi")
    secilen_coin = st.selectbox("Coin seç:", coin_listesi, index=0)
    coin_adi = secilen_coin.split("/")[0]
    
    st.markdown("---")
    
    # 2. ZAMAN DİLİMİ (1dk'dan başlıyor)
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
    
    secili_zaman = st.selectbox("Zaman dilimi seç:", list(zaman_dilimleri.keys()), index=3)
    tf_kodu = zaman_dilimleri[secili_zaman]
    
    st.markdown("---")
    
    # 3. BORSA SEÇİMİ
    st.subheader("🏛️ Borsalar")
    tum_borsalar = {
        'Binance': ccxt.binance(),
        'Bybit': ccxt.bybit(),
        'Bitget': ccxt.bitget(),
        'OKX': ccxt.okx()
    }
    
    secili_borsalar = st.multiselect(
        "Kullanılacak borsalar:",
        options=list(tum_borsalar.keys()),
        default=["Binance", "Bybit"]
    )
    
    if len(secili_borsalar) == 0:
        st.error("❌ En az bir borsa seçmelisiniz!")
        st.stop()
    
    st.markdown("---")
    
    # 4. GÖSTERGELER
    st.subheader("📊 Göstergeler")
    goster_destek_direnc = st.checkbox("🟢 Destek/Direnç", value=True)
    goster_long_tasfiye = st.checkbox("🔥 Long Tasfiye", value=True)
    goster_short_tasfiye = st.checkbox("💀 Short Tasfiye", value=True)
    
    st.markdown("---")
    
    # 5. YENİLEME AYARI
    st.subheader("🔄 Canlı Güncelleme")
    yenileme_araligi = st.select_slider(
        "Yenileme sıklığı:",
        options=[2, 5, 10, 15, 30, 60],
        value=10,
        format_func=lambda x: f"{x} saniye"
    )
    
    if st.button("🔄 Şimdi Yenile", use_container_width=True):
        st.rerun()
    
    st.markdown("---")
    st.caption(f"🕐 Son güncelleme: {datetime.now().strftime('%H:%M:%S')}")

# ==================== BORSALARI HAZIRLA ====================
borsalar = {}
for borsa_adi in secili_borsalar:
    borsalar[borsa_adi] = tum_borsalar[borsa_adi]

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

def anlik_fiyat_al(borsa, sembol):
    try:
        ticker = borsa.fetch_ticker(sembol)
        return ticker['last'], ticker['percentage'] if 'percentage' in ticker else 0
    except:
        return None, None

def seviye_bul(df, order=10, yuvarla=50):
    if df is None or len(df) < 20:
        return [], []
    tepeler = argrelextrema(df['yuksek'].values, np.greater_equal, order=order)[0]
    dipler = argrelextrema(df['dusuk'].values, np.less_equal, order=order)[0]
    direncler = [round(df['yuksek'].iloc[t] / yuvarla) * yuvarla for t in tepeler]
    destekler = [round(df['dusuk'].iloc[d] / yuvarla) * yuvarla for d in dipler]
    return list(set(direncler)), list(set(destekler))

def ortak_seviye_bul(tum_direncler, tum_destekler, min_borsa=2):
    if len(tum_direncler) < min_borsa:
        return [], []
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
    
    # Mum grafiği
    fig.add_trace(go.Candlestick(
        x=df.index,
        open=df['acilis'],
        high=df['yuksek'],
        low=df['dusuk'],
        close=df['kapanis'],
        name=f'{baslik} Fiyat'
    ))
    
    # Destek/Direnç
    if goster_destek_direnc:
        for seviye in ortak_destek:
            fig.add_hline(y=seviye, line_dash="solid", line_color="green", line_width=2,
                         annotation_text=f"🟢 DESTEK {seviye:.0f}", annotation_position="top right")
        for seviye in ortak_direnc:
            fig.add_hline(y=seviye, line_dash="solid", line_color="red", line_width=2,
                         annotation_text=f"🔴 DİRENÇ {seviye:.0f}", annotation_position="top right")
    
    # Tasfiye bölgeleri
    if goster_long_tasfiye:
        for seviye in tasfiye['long']:
            fig.add_hline(y=seviye, line_dash="dash", line_color="darkred", line_width=2,
                         annotation_text=f"🔥 LONG TASFİYE {seviye:.0f}", annotation_position="bottom left")
    
    if goster_short_tasfiye:
        for seviye in tasfiye['short']:
            fig.add_hline(y=seviye, line_dash="dash", line_color="purple", line_width=2,
                         annotation_text=f"💀 SHORT TASFİYE {seviye:.0f}", annotation_position="top left")
    
    # Güncel fiyat
    fig.add_hline(y=guncel_fiyat, line_dash="dot", line_color="white", line_width=1.5,
                 annotation_text=f"📍 GÜNCEL {guncel_fiyat:.0f}", annotation_position="top left")
    
    # Grafik ayarları - YAKINLAŞTIRMA VE KAYDIRMA İÇİN
    fig.update_layout(
        height=600,
        title=baslik,
        template="plotly_dark",
        xaxis_title="Zaman",
        yaxis_title="Fiyat (USDT)",
        xaxis=dict(
            rangeslider=dict(visible=False),
            type="date",
            fixedrange=False  # Kaydırmaya izin ver
        ),
        yaxis=dict(
            fixedrange=False  # Yakınlaştırmaya izin ver
        ),
        dragmode="zoom",  # Yakınlaştırma modu
        hovermode='closest'
    )
    
    return fig

# ==================== ANA İŞLEM ====================
with st.spinner("Veriler yükleniyor..."):
    
    # ==================== SANİYELİK FİYAT TAKİBİ ====================
    st.subheader(f"📊 {coin_adi} Canlı Fiyat Takibi")
    
    # Canlı fiyat satırı
    fiyat_cols = st.columns(len(secili_borsalar))
    
    anlik_fiyatlar = []
    for idx, borsa_adi in enumerate(secili_borsalar):
        borsa = tum_borsalar[borsa_adi]
        fiyat, degisim = anlik_fiyat_al(borsa, secilen_coin)
        if fiyat:
            anlik_fiyatlar.append(fiyat)
            renk = "🟢" if degisim and degisim > 0 else "🔴" if degisim and degisim < 0 else "⚪"
            with fiyat_cols[idx]:
                st.metric(
                    label=f"{borsa_adi}",
                    value=f"${fiyat:,.0f}",
                    delta=f"{degisim:.2f}%" if degisim else None,
                    delta_color="normal"
                )
    
    ortalama_fiyat = sum(anlik_fiyatlar) / len(anlik_fiyatlar) if anlik_fiyatlar else 0
    
    # Ortalama fiyat kartı
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("💰 Ortalama Fiyat", f"${ortalama_fiyat:,.0f}" if ortalama_fiyat else "-")
    with col2:
        st.metric("⏱️ Zaman Dilimi", secili_zaman)
    with col3:
        st.metric("🏛️ Borsa Sayısı", len(secili_borsalar))
    with col4:
        st.metric("🔄 Yenileme", f"{yenileme_araligi} sn")
    
    st.markdown("---")
    
    # ==================== ANA GRAFİK ====================
    st.subheader("📈 Mum Grafiği (Yakınlaştırmak için fare/parmakla sürükle, çift tıkla sıfırla)")
    
    # Veri çekme
    tum_direncler = []
    tum_destekler = []
    ana_df = None
    
    for borsa_adi, borsa in borsalar.items():
        df = veri_cek(borsa, secilen_coin, tf_kodu)
        if df is not None:
            if ana_df is None:
                ana_df = df
            
            if tf_kodu in ['1m', '3m', '5m']:
                order_val = 5
            elif tf_kodu in ['15m', '30m']:
                order_val = 7
            elif tf_kodu in ['1h']:
                order_val = 9
            elif tf_kodu in ['2h', '4h']:
                order_val = 11
            else:
                order_val = 13
            
            direnc, destek = seviye_bul(df, order=order_val)
            tum_direncler.append(direnc)
            tum_destekler.append(destek)
    
    # Ortak destek/direnç
    ortak_direnc, ortak_destek = ortak_seviye_bul(tum_direncler, tum_destekler, min_borsa=2)
    
    # Tasfiye seviyeleri
    tasfiye = tasfiye_seviyeleri(ortalama_fiyat if ortalama_fiyat else 70000)
    
    # Grafik başlığı
    grafik_baslik = f"{coin_adi}/USDT - {secili_zaman} | {', '.join(secili_borsalar)}"
    
    # Grafiği çiz
    if ana_df is not None:
        fig = grafik_ciz(ana_df, grafik_baslik, ortak_direnc, ortak_destek, tasfiye, ortalama_fiyat)
        
        # Konfigürasyon - mobil için dokunmatik destek
        config = {
            'scrollZoom': True,      # Fare tekerleği ile zoom
            'doubleClick': 'reset',  # Çift tıkla sıfırla
            'displayModeBar': True,  # Araç çubuğu göster
            'modeBarButtonsToRemove': ['lasso2d', 'select2d'],
            'responsive': True       # Mobil uyumlu
        }
        
        st.plotly_chart(fig, use_container_width=True, config=config)
        
        # Destek/direnç listesi
        col_a, col_b = st.columns(2)
        with col_a:
            st.markdown(f"### 🟢 ORTAK DESTEK SEVİYELERİ")
            if ortak_destek:
                for s in ortak_destek[:8]:
                    st.markdown(f"- **${s:,.0f}**")
            else:
                st.info("Henüz ortak destek seviyesi bulunamadı")
        
        with col_b:
            st.markdown(f"### 🔴 ORTAK DİRENÇ SEVİYELERİ")
            if ortak_direnc:
                for r in ortak_direnc[:8]:
                    st.markdown(f"- **${r:,.0f}**")
            else:
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

st.caption("💡 **İpucu:** Grafiğin üzerinde fare/parmakla yakınlaştırıp uzaklaştırabilir, sağa sola kaydırabilirsiniz. Sol menüden coin, zaman dilimi ve borsa değiştirebilirsiniz.")
