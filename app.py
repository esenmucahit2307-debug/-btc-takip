import streamlit as st
import ccxt
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from scipy.signal import argrelextrema
from datetime import datetime
from collections import Counter
import time
import random

st.set_page_config(page_title="TradingView Tarzı Dashboard", layout="wide")

# ==================== 30+ COİN LİSTESİ ====================
coin_listesi = [
    "BTC/USDT", "ETH/USDT", "SOL/USDT", "XRP/USDT", "DOGE/USDT",
    "ADA/USDT", "AVAX/USDT", "DOT/USDT", "LINK/USDT", "MATIC/USDT",
    "UNI/USDT", "ATOM/USDT", "LTC/USDT", "BCH/USDT", "NEAR/USDT",
    "APT/USDT", "ARB/USDT", "OP/USDT", "INJ/USDT", "SUI/USDT",
    "PEPE/USDT", "WIF/USDT", "FLOKI/USDT", "BONK/USDT", "SHIB/USDT",
    "TON/USDT", "TRX/USDT", "ETC/USDT", "FIL/USDT", "AAVE/USDT"
]

# ==================== HER KALDIRAÇ İÇİN RENK ====================
KALDIRAC_RENKLERI = {
    3: '#00FF00',      # 3x - Yeşil
    5: '#00CED1',      # 5x - Turkuaz
    10: '#FFD700',     # 10x - Altın Sarısı
    20: '#FF8C00',     # 20x - Turuncu
    50: '#FF0000'      # 50x - Kırmızı
}

KALDIRAC_ADLARI = {
    3: "3x (Düşük Risk)",
    5: "5x (Orta Risk)",
    10: "10x (Yüksek Risk)",
    20: "20x (Çok Yüksek Risk)",
    50: "50x (Maksimum Risk)"
}

# ==================== BAŞLIK ====================
st.title("📈 CANLI KRİPTO DASHBOARD")
st.caption("TradingView tarzı | Her kaldıraç farklı renk | Tasfiye hacimleri gösteriliyor")

# ==================== KENAR ÇUBUĞU ====================
with st.sidebar:
    st.header("⚙️ PANEL AYARLARI")
    
    # 1. COIN SEÇİMİ
    st.subheader("💰 Coin Seçimi")
    secilen_coin = st.selectbox("Coin seç:", coin_listesi, index=0)
    coin_adi = secilen_coin.split("/")[0]
    
    st.markdown("---")
    
    # 2. ZAMAN DİLİMİ
    st.subheader("⏱️ Zaman Dilimi")
    zaman_dilimleri = {
        "1 Dakika": "1m", "3 Dakika": "3m", "5 Dakika": "5m",
        "15 Dakika": "15m", "30 Dakika": "30m", "1 Saat": "1h",
        "2 Saat": "2h", "4 Saat": "4h", "6 Saat": "6h",
        "12 Saat": "12h", "1 Gün": "1d", "1 Hafta": "1w"
    }
    
    secili_zaman = st.selectbox("Zaman dilimi seç:", list(zaman_dilimleri.keys()), index=4)
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
    
    # 4. DESTEK/DİRENÇ AÇ/KAPAT
    st.subheader("📊 Destek/Direnç")
    destek_acik = st.checkbox("🟢 Destek Çizgilerini Göster", value=True)
    direnc_acik = st.checkbox("🔴 Direnç Çizgilerini Göster", value=True)
    
    st.markdown("---")
    
    # 5. LİQUİDATION (TASFİYE) AYARLARI
    st.subheader("🔥 Liquidation (Tasfiye) Haritası")
    liq_acik = st.checkbox("📊 Liquidation Haritasını Göster", value=True)
    
    if liq_acik:
        st.markdown("**Kaldıraç Çarpanlarını Seç (Her biri farklı renk):**")
        col1, col2 = st.columns(2)
        with col1:
            k3x = st.checkbox("🟢 3x (Düşük Risk)", value=True)
            k5x = st.checkbox("🔵 5x (Orta Risk)", value=True)
            k10x = st.checkbox("🟡 10x (Yüksek Risk)", value=True)
        with col2:
            k20x = st.checkbox("🟠 20x (Çok Yüksek)", value=True)
            k50x = st.checkbox("🔴 50x (Maksimum)", value=True)
        
        secili_kaldiraclar = []
        if k3x: secili_kaldiraclar.append(3)
        if k5x: secili_kaldiraclar.append(5)
        if k10x: secili_kaldiraclar.append(10)
        if k20x: secili_kaldiraclar.append(20)
        if k50x: secili_kaldiraclar.append(50)
        
        if len(secili_kaldiraclar) == 0:
            st.warning("⚠️ En az bir kaldıraç seçin!")
            secili_kaldiraclar = [3, 5, 10]
    else:
        secili_kaldiraclar = []
    
    st.markdown("---")
    
    # 6. YENİLEME AYARI
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

def tahmini_hacim_hesapla(fiyat, kaldirac):
    """Tahmini tasfiye hacmini hesaplar (Coinglass benzeri)"""
    # BTC için tahmini açık pozisyon büyüklüğü
    base_oi = {
        "BTC": 15000000000,  # 15 Milyar dolar
        "ETH": 8000000000,   # 8 Milyar dolar
        "SOL": 2000000000,   # 2 Milyar dolar
        "XRP": 1000000000,   # 1 Milyar dolar
        "DOGE": 500000000    # 500 Milyon dolar
    }
    
    coin_adi = secilen_coin.split("/")[0]
    oi = base_oi.get(coin_adi, 500000000)
    
    # Kaldıraç bazında hacim oranı
    oran = {
        3: 0.15,   # 3x: %15'i
        5: 0.25,   # 5x: %25'i
        10: 0.35,  # 10x: %35'i
        20: 0.15,  # 20x: %15'i
        50: 0.10   # 50x: %10'u
    }
    
    hacim = oi * oran.get(kaldirac, 0.1)
    return int(hacim)

def tasfiye_seviyeleri_hesapla(guncel_fiyat, kaldiraclar):
    """Seçilen kaldıraçlara göre tasfiye seviyelerini hesaplar"""
    long_tasfiye = []
    short_tasfiye = []
    
    for k in kaldiraclar:
        long_price = round(guncel_fiyat * (1 - 1/k) / 100) * 100
        short_price = round(guncel_fiyat * (1 + 1/k) / 100) * 100
        hacim = tahmini_hacim_hesapla(guncel_fiyat, k)
        
        long_tasfiye.append({
            'kaldirac': k,
            'fiyat': long_price,
            'hacim': hacim,
            'renk': KALDIRAC_RENKLERI.get(k, '#FFFFFF')
        })
        
        short_tasfiye.append({
            'kaldirac': k,
            'fiyat': short_price,
            'hacim': hacim,
            'renk': KALDIRAC_RENKLERI.get(k, '#FFFFFF')
        })
    
    # Fiyata göre sırala
    long_tasfiye = sorted(long_tasfiye, key=lambda x: x['fiyat'], reverse=True)
    short_tasfiye = sorted(short_tasfiye, key=lambda x: x['fiyat'])
    
    return {
        'long': long_tasfiye,
        'short': short_tasfiye
    }

def grafik_ciz(df, baslik, ortak_direnc, ortak_destek, tasfiye, guncel_fiyat, 
               destek_acik, direnc_acik, liq_acik):
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
    if destek_acik:
        for seviye in ortak_destek:
            fig.add_hline(y=seviye, line_dash="solid", line_color="green", line_width=2,
                         annotation_text=f"🟢 DESTEK {seviye:.0f}", annotation_position="top right")
    
    # Direnç çizgileri
    if direnc_acik:
        for seviye in ortak_direnc:
            fig.add_hline(y=seviye, line_dash="solid", line_color="red", line_width=2,
                         annotation_text=f"🔴 DİRENÇ {seviye:.0f}", annotation_position="top right")
    
    # Liquidation çizgileri - HER KALDIRAÇ FARKLI RENK
    if liq_acik:
        for item in tasfiye.get('long', []):
            fig.add_hline(y=item['fiyat'], line_dash="dash", 
                         line_color=item['renk'], line_width=2,
                         annotation_text=f"🔥 LONG {item['kaldirac']}x | ${item['fiyat']:.0f}", 
                         annotation_position="bottom left")
        
        for item in tasfiye.get('short', []):
            fig.add_hline(y=item['fiyat'], line_dash="dash", 
                         line_color=item['renk'], line_width=2,
                         annotation_text=f"💀 SHORT {item['kaldirac']}x | ${item['fiyat']:.0f}", 
                         annotation_position="top left")
    
    # Güncel fiyat
    fig.add_hline(y=guncel_fiyat, line_dash="dot", line_color="white", line_width=1.5,
                 annotation_text=f"📍 GÜNCEL {guncel_fiyat:.0f}", annotation_position="top left")
    
    # Grafik ayarları
    fig.update_layout(
        height=600,
        title=baslik,
        template="plotly_dark",
        xaxis_title="Zaman",
        yaxis_title="Fiyat (USDT)",
        xaxis=dict(rangeslider=dict(visible=False), type="date", fixedrange=False),
        yaxis=dict(fixedrange=False),
        dragmode="zoom",
        hovermode='closest'
    )
    
    return fig

# ==================== ANA İŞLEM ====================
with st.spinner("Veriler yükleniyor..."):
    
    # ==================== CANLI FİYAT TAKİBİ ====================
    st.subheader(f"📊 {coin_adi} Canlı Fiyat Takibi")
    
    fiyat_cols = st.columns(len(secili_borsalar))
    
    anlik_fiyatlar = []
    for idx, borsa_adi in enumerate(secili_borsalar):
        borsa = tum_borsalar[borsa_adi]
        fiyat, degisim = anlik_fiyat_al(borsa, secilen_coin)
        if fiyat:
            anlik_fiyatlar.append(fiyat)
            with fiyat_cols[idx]:
                st.metric(
                    label=f"{borsa_adi}",
                    value=f"${fiyat:,.0f}",
                    delta=f"{degisim:.2f}%" if degisim else None
                )
    
    ortalama_fiyat = sum(anlik_fiyatlar) / len(anlik_fiyatlar) if anlik_fiyatlar else 0
    
    # Bilgi kartları
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("💰 Ortalama Fiyat", f"${ortalama_fiyat:,.0f}" if ortalama_fiyat else "-")
    with col2:
        st.metric("⏱️ Zaman Dilimi", secili_zaman)
    with col3:
        st.metric("🏛️ Borsa Sayısı", len(secili_borsalar))
    with col4:
        st.metric("🔄 Yenileme", f"{yenileme_araligi} sn")
    
    # Aktif göstergeler
    aktifler = []
    if destek_acik: aktifler.append("🟢 Destek")
    if direnc_acik: aktifler.append("🔴 Direnç")
    if liq_acik and secili_kaldiraclar: 
        aktifler.append(f"🔥 Liquidation ({', '.join(map(str, secili_kaldiraclar))}x)")
    
    if aktifler:
        st.info(f"📌 **Aktif Göstergeler:** {' | '.join(aktifler)}")
    
    st.markdown("---")
    
    # ==================== ANA GRAFİK ====================
    st.subheader("📈 Mum Grafiği (Yakınlaştırmak için sürükle, çift tıkla sıfırla)")
    
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
    if liq_acik and secili_kaldiraclar:
        tasfiye = tasfiye_seviyeleri_hesapla(ortalama_fiyat if ortalama_fiyat else 70000, secili_kaldiraclar)
    else:
        tasfiye = {'long': [], 'short': []}
    
    # Grafik başlığı
    grafik_baslik = f"{coin_adi}/USDT - {secili_zaman} | {', '.join(secili_borsalar)}"
    
    # Grafiği çiz
    if ana_df is not None:
        fig = grafik_ciz(ana_df, grafik_baslik, ortak_direnc, ortak_destek, 
                         tasfiye, ortalama_fiyat, destek_acik, direnc_acik, liq_acik)
        
        config = {
            'scrollZoom': True,
            'doubleClick': 'reset',
            'displayModeBar': True,
            'modeBarButtonsToRemove': ['lasso2d', 'select2d'],
            'responsive': True
        }
        
        st.plotly_chart(fig, use_container_width=True, config=config)
        
        # ==================== TASFİYE BÖLGELERİ LİSTESİ (Altta) ====================
        if liq_acik and secili_kaldiraclar and (tasfiye['long'] or tasfiye['short']):
            st.markdown("---")
            st.subheader("🔥 LİQUİDATION (TASFİYE) BÖLGELERİ")
            st.caption("Her kaldıraç farklı renkte gösterilir. Hacimler tahminidir (24s OI bazlı).")
            
            col_long, col_short = st.columns(2)
            
            with col_long:
                st.markdown("### 📉 LONG TASFİYE (Aşağı Yön)")
                st.markdown("Bu fiyatlarda **uzun pozisyonlar** tasfiye olur:")
                
                for item in tasfiye['long']:
                    hacim_m = item['hacim'] / 1_000_000
                    renk = item['renk']
                    st.markdown(
                        f"<div style='border-left: 4px solid {renk}; padding-left: 10px; margin: 5px 0;'>"
                        f"<b style='color:{renk}'>⚡ {item['kaldirac']}x</b> | "
                        f"Fiyat: <b>${item['fiyat']:,.0f}</b> | "
                        f"Tahmini Hacim: <b>${hacim_m:.1f}M</b>"
                        f"</div>", 
                        unsafe_allow_html=True
                    )
                
                if not tasfiye['long']:
                    st.info("Long tasfiye seviyesi bulunamadı")
            
            with col_short:
                st.markdown("### 📈 SHORT TASFİYE (Yukarı Yön)")
                st.markdown("Bu fiyatlarda **kısa pozisyonlar** tasfiye olur:")
                
                for item in tasfiye['short']:
                    hacim_m = item['hacim'] / 1_000_000
                    renk = item['renk']
                    st.markdown(
                        f"<div style='border-left: 4px solid {renk}; padding-left: 10px; margin: 5px 0;'>"
                        f"<b style='color:{renk}'>⚡ {item['kaldirac']}x</b> | "
                        f"Fiyat: <b>${item['fiyat']:,.0f}</b> | "
                        f"Tahmini Hacim: <b>${hacim_m:.1f}M</b>"
                        f"</div>", 
                        unsafe_allow_html=True
                    )
                
                if not tasfiye['short']:
                    st.info("Short tasfiye seviyesi bulunamadı")
            
            # Renk açıklamaları
            st.markdown("---")
            st.markdown("**📌 Kaldıraç Renkleri:**")
            renk_cols = st.columns(5)
            for idx, k in enumerate(secili_kaldiraclar):
                with renk_cols[idx % 5]:
                    st.markdown(f"<span style='color:{KALDIRAC_RENKLERI.get(k, '#FFF')}'>⬤</span> {k}x - {KALDIRAC_ADLARI.get(k, '')}", unsafe_allow_html=True)
        
        # Destek/direnç listesi
        elif destek_acik or direnc_acik:
            st.markdown("---")
            col_a, col_b = st.columns(2)
            with col_a:
                if destek_acik:
                    st.markdown(f"### 🟢 ORTAK DESTEK SEVİYELERİ")
                    if ortak_destek:
                        for s in ortak_destek[:8]:
                            st.markdown(f"- **${s:,.0f}**")
                    else:
                        st.info("Henüz ortak destek seviyesi bulunamadı")
            with col_b:
                if direnc_acik:
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

st.caption("💡 **İpucu:** Sol menüden Destek/Direnç/Liquidation çizgilerini açıp kapatabilirsiniz. Her kaldıraç farklı renktedir. Tasfiye hacimleri tahminidir.")
