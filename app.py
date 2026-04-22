import streamlit as st
import ccxt
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from scipy.signal import argrelextrema
from datetime import datetime
from collections import Counter
import time

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

# ==================== DESTEK/DİRENÇ GÜÇ RENKLERİ ====================
# Kaç borsada ortak olduğuna göre renk ve kalınlık
GUÇ_RENKLERI = {
    4: {'renk': '#00FF00', 'kalınlık': 3.5, 'etiket': 'ÇOK GÜÇLÜ (4/4 Borsa)'},      # 4 borsa - Yeşil kalın
    3: {'renk': '#32CD32', 'kalınlık': 2.8, 'etiket': 'GÜÇLÜ (3/4 Borsa)'},          # 3 borsa - Açık yeşil
    2: {'renk': '#7CFC00', 'kalınlık': 2.0, 'etiket': 'ORTA (2/4 Borsa)'},           # 2 borsa - Limon yeşili
    1: {'renk': '#ADFF2F', 'kalınlık': 1.5, 'etiket': 'ZAYIF (1/4 Borsa)'}           # 1 borsa - Açık sarı
}

# Direnç için renkler (kırmızı tonları)
DIRENC_GUÇ_RENKLERI = {
    4: {'renk': '#FF0000', 'kalınlık': 3.5, 'etiket': 'ÇOK GÜÇLÜ (4/4 Borsa)'},      # 4 borsa - Kırmızı kalın
    3: {'renk': '#FF4444', 'kalınlık': 2.8, 'etiket': 'GÜÇLÜ (3/4 Borsa)'},          # 3 borsa - Açık kırmızı
    2: {'renk': '#FF6666', 'kalınlık': 2.0, 'etiket': 'ORTA (2/4 Borsa)'},           # 2 borsa - Daha açık
    1: {'renk': '#FF9999', 'kalınlık': 1.5, 'etiket': 'ZAYIF (1/4 Borsa)'}           # 1 borsa - En açık
}

# ==================== BAŞLIK ====================
st.title("📈 CANLI KRİPTO DASHBOARD")
st.caption("TradingView tarzı | Destek/Direnç güçlerine göre renklendirilmiş | Coinglass tipi Liquidation")

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
        default=["Binance", "Bybit", "Bitget", "OKX"]
    )
    
    if len(secili_borsalar) == 0:
        st.error("❌ En az bir borsa seçmelisiniz!")
        st.stop()
    
    max_borsa = len(secili_borsalar)
    
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
            k3x = st.checkbox("🟢 3x", value=True)
            k5x = st.checkbox("🔵 5x", value=True)
            k10x = st.checkbox("🟡 10x", value=True)
        with col2:
            k20x = st.checkbox("🟠 20x", value=True)
            k50x = st.checkbox("🔴 50x", value=True)
        
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

def ortak_seviye_bul_guc_hesapli(tum_direncler, tum_destekler):
    """Her seviyenin kaç borsada görüldüğünü ve gücünü hesaplar"""
    direnc_sayac = Counter()
    for alt_liste in tum_direncler:
        for item in alt_liste:
            direnc_sayac[item] += 1
    
    destek_sayac = Counter()
    for alt_liste in tum_destekler:
        for item in alt_liste:
            destek_sayac[item] += 1
    
    # Güç bilgisi ile birlikte listele (güce göre sırala - en güçlü önce)
    ortak_direnc = [(seviye, sayi) for seviye, sayi in direnc_sayac.items()]
    ortak_destek = [(seviye, sayi) for seviye, sayi in destek_sayac.items()]
    
    # Güce göre sırala (en güçlü önce)
    ortak_direnc.sort(key=lambda x: x[1], reverse=True)
    ortak_destek.sort(key=lambda x: x[1], reverse=True)
    
    return ortak_direnc, ortak_destek

def tahmini_hacim_hesapla(fiyat, kaldirac, coin_adi):
    """Tahmini tasfiye hacmini hesaplar"""
    base_oi = {
        "BTC": 15000000000,
        "ETH": 8000000000,
        "SOL": 2000000000,
        "XRP": 1000000000,
        "DOGE": 500000000
    }
    oi = base_oi.get(coin_adi, 500000000)
    
    oran = {3: 0.15, 5: 0.25, 10: 0.35, 20: 0.15, 50: 0.10}
    hacim = oi * oran.get(kaldirac, 0.1)
    return int(hacim)

def tasfiye_seviyeleri_hesapla(guncel_fiyat, kaldiraclar, coin_adi):
    long_tasfiye = []
    short_tasfiye = []
    
    for k in kaldiraclar:
        long_price = round(guncel_fiyat * (1 - 1/k) / 100) * 100
        short_price = round(guncel_fiyat * (1 + 1/k) / 100) * 100
        hacim = tahmini_hacim_hesapla(guncel_fiyat, k, coin_adi)
        
        long_tasfiye.append({
            'kaldirac': k, 'fiyat': long_price, 'hacim': hacim,
            'renk': KALDIRAC_RENKLERI.get(k, '#FFFFFF')
        })
        short_tasfiye.append({
            'kaldirac': k, 'fiyat': short_price, 'hacim': hacim,
            'renk': KALDIRAC_RENKLERI.get(k, '#FFFFFF')
        })
    
    long_tasfiye = sorted(long_tasfiye, key=lambda x: x['fiyat'], reverse=True)
    short_tasfiye = sorted(short_tasfiye, key=lambda x: x['fiyat'])
    
    return {'long': long_tasfiye, 'short': short_tasfiye}

def grafik_ciz(df, baslik, ortak_direnc, ortak_destek, tasfiye, guncel_fiyat, 
               destek_acik, direnc_acik, liq_acik, max_borsa):
    if df is None or len(df) == 0:
        fig = go.Figure()
        fig.add_annotation(text="Veri alınamadı", showarrow=False)
        return fig
    
    fig = go.Figure()
    
    # Mum grafiği
    fig.add_trace(go.Candlestick(
        x=df.index, open=df['acilis'], high=df['yuksek'],
        low=df['dusuk'], close=df['kapanis'], name='Fiyat'
    ))
    
    # Destek çizgileri - GÜCÜNE GÖRE RENK VE KALINLIK
    if destek_acik:
        for seviye, guc in ortak_destek:
            guc_info = GUÇ_RENKLERI.get(guc, GUÇ_RENKLERI[1])
            fig.add_hline(y=seviye, line_dash="solid", 
                         line_color=guc_info['renk'], 
                         line_width=guc_info['kalınlık'],
                         annotation_text=f"🟢 DESTEK {seviye:.0f} | {guc_info['etiket']}", 
                         annotation_position="top right")
    
    # Direnç çizgileri - GÜCÜNE GÖRE RENK VE KALINLIK
    if direnc_acik:
        for seviye, guc in ortak_direnc:
            guc_info = DIRENC_GUÇ_RENKLERI.get(guc, DIRENC_GUÇ_RENKLERI[1])
            fig.add_hline(y=seviye, line_dash="solid", 
                         line_color=guc_info['renk'], 
                         line_width=guc_info['kalınlık'],
                         annotation_text=f"🔴 DİRENÇ {seviye:.0f} | {guc_info['etiket']}", 
                         annotation_position="top right")
    
    # Liquidation çizgileri
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
    
    fig.update_layout(
        height=650, title=baslik, template="plotly_dark",
        xaxis_title="Zaman", yaxis_title="Fiyat (USDT)",
        xaxis=dict(rangeslider=dict(visible=False), type="date", fixedrange=False),
        yaxis=dict(fixedrange=False), dragmode="zoom", hovermode='closest'
    )
    return fig

# ==================== ANA İŞLEM ====================
with st.spinner("Veriler yükleniyor..."):
    
    # Canlı fiyat takibi
    st.subheader(f"📊 {coin_adi} Canlı Fiyat Takibi")
    
    fiyat_cols = st.columns(len(secili_borsalar))
    anlik_fiyatlar = []
    for idx, borsa_adi in enumerate(secili_borsalar):
        borsa = tum_borsalar[borsa_adi]
        fiyat, degisim = anlik_fiyat_al(borsa, secilen_coin)
        if fiyat:
            anlik_fiyatlar.append(fiyat)
            with fiyat_cols[idx]:
                st.metric(label=f"{borsa_adi}", value=f"${fiyat:,.0f}",
                         delta=f"{degisim:.2f}%" if degisim else None)
    
    ortalama_fiyat = sum(anlik_fiyatlar) / len(anlik_fiyatlar) if anlik_fiyatlar else 0
    
    # Bilgi kartları
    col1, col2, col3, col4 = st.columns(4)
    with col1: st.metric("💰 Ortalama Fiyat", f"${ortalama_fiyat:,.0f}" if ortalama_fiyat else "-")
    with col2: st.metric("⏱️ Zaman Dilimi", secili_zaman)
    with col3: st.metric("🏛️ Borsa Sayısı", len(secili_borsalar))
    with col4: st.metric("🔄 Yenileme", f"{yenileme_araligi} sn")
    
    st.markdown("---")
    st.subheader("📈 Mum Grafiği (Yakınlaştırmak için sürükle)")
    
    # Veri çekme
    tum_direncler, tum_destekler, ana_df = [], [], None
    
    for borsa_adi, borsa in borsalar.items():
        df = veri_cek(borsa, secilen_coin, tf_kodu)
        if df is not None:
            if ana_df is None: ana_df = df
            if tf_kodu in ['1m','3m','5m']: order_val = 5
            elif tf_kodu in ['15m','30m']: order_val = 7
            elif tf_kodu in ['1h']: order_val = 9
            elif tf_kodu in ['2h','4h']: order_val = 11
            else: order_val = 13
            
            direnc, destek = seviye_bul(df, order=order_val)
            tum_direncler.append(direnc)
            tum_destekler.append(destek)
    
    # Güç hesaplı ortak seviyeler
    ortak_direnc, ortak_destek = ortak_seviye_bul_guc_hesapli(tum_direncler, tum_destekler)
    
    # Tasfiye
    if liq_acik and secili_kaldiraclar:
        tasfiye = tasfiye_seviyeleri_hesapla(ortalama_fiyat, secili_kaldiraclar, coin_adi)
    else:
        tasfiye = {'long': [], 'short': []}
    
    if ana_df is not None:
        fig = grafik_ciz(ana_df, f"{coin_adi}/USDT - {secili_zaman}", ortak_direnc, ortak_destek,
                         tasfiye, ortalama_fiyat, destek_acik, direnc_acik, liq_acik, len(secili_borsalar))
        
        config = {'scrollZoom': True, 'doubleClick': 'reset', 'displayModeBar': True, 'responsive': True}
        st.plotly_chart(fig, use_container_width=True, config=config)
        
        # ==================== DESTEK LİSTESİ (Güç sıralı) ====================
        if destek_acik and ortak_destek:
            st.markdown("---")
            st.subheader("🟢 DESTEK SEVİYELERİ (Güçlüden Zayıfa)")
            st.caption("Kaç borsada görüldüğüne göre renklendirilmiştir. Kalın çizgi = Daha güçlü.")
            
            for seviye, guc in ortak_destek[:10]:
                guc_info = GUÇ_RENKLERI.get(guc, GUÇ_RENKLERI[1])
                renk = guc_info['renk']
                etiket = guc_info['etiket']
                yuzde = (guc / len(secili_borsalar)) * 100
                st.markdown(
                    f"<div style='border-left: 4px solid {renk}; padding-left: 10px; margin: 5px 0;'>"
                    f"<b style='color:{renk}'>⬤ ${seviye:,.0f}</b> | "
                    f"<b>{etiket}</b> | "
                    f"Görülme: {guc}/{len(secili_borsalar)} borsa ({yuzde:.0f}%)"
                    f"</div>", unsafe_allow_html=True
                )
        
        # ==================== DİRENÇ LİSTESİ ====================
        if direnc_acik and ortak_direnc:
            st.markdown("---")
            st.subheader("🔴 DİRENÇ SEVİYELERİ (Güçlüden Zayıfa)")
            
            for seviye, guc in ortak_direnc[:10]:
                guc_info = DIRENC_GUÇ_RENKLERI.get(guc, DIRENC_GUÇ_RENKLERI[1])
                renk = guc_info['renk']
                etiket = guc_info['etiket']
                yuzde = (guc / len(secili_borsalar)) * 100
                st.markdown(
                    f"<div style='border-left: 4px solid {renk}; padding-left: 10px; margin: 5px 0;'>"
                    f"<b style='color:{renk}'>⬤ ${seviye:,.0f}</b> | "
                    f"<b>{etiket}</b> | "
                    f"Görülme: {guc}/{len(secili_borsalar)} borsa ({yuzde:.0f}%)"
                    f"</div>", unsafe_allow_html=True
                )
        
        # ==================== TASFİYE LİSTESİ ====================
        if liq_acik and secili_kaldiraclar and (tasfiye['long'] or tasfiye['short']):
            st.markdown("---")
            st.subheader("🔥 LİQUİDATION (TASFİYE) BÖLGELERİ")
            
            col_long, col_short = st.columns(2)
            with col_long:
                st.markdown("### 📉 LONG TASFİYE (Aşağı Yön)")
                for item in tasfiye['long']:
                    hacim_m = item['hacim'] / 1_000_000
                    st.markdown(
                        f"<div style='border-left: 4px solid {item['renk']}; padding-left: 10px; margin: 5px 0;'>"
                        f"<b style='color:{item['renk']}'>⚡ {item['kaldirac']}x</b> | "
                        f"Fiyat: <b>${item['fiyat']:,.0f}</b> | "
                        f"Hacim: <b>${hacim_m:.1f}M</b>"
                        f"</div>", unsafe_allow_html=True
                    )
            
            with col_short:
                st.markdown("### 📈 SHORT TASFİYE (Yukarı Yön)")
                for item in tasfiye['short']:
                    hacim_m = item['hacim'] / 1_000_000
                    st.markdown(
                        f"<div style='border-left: 4px solid {item['renk']}; padding-left: 10px; margin: 5px 0;'>"
                        f"<b style='color:{item['renk']}'>⚡ {item['kaldirac']}x</b> | "
                        f"Fiyat: <b>${item['fiyat']:,.0f}</b> | "
                        f"Hacim: <b>${hacim_m:.1f}M</b>"
                        f"</div>", unsafe_allow_html=True
                    )
    else:
        st.error("❌ Veri alınamadı.")

# Otomatik yenileme
if 'son_yenileme' not in st.session_state:
    st.session_state.son_yenileme = time.time()

gecen_sure = time.time() - st.session_state.son_yenileme
if gecen_sure > yenileme_araligi:
    st.session_state.son_yenileme = time.time()
    st.rerun()
else:
    st.info(f"🔄 {int(yenileme_araligi - gecen_sure)} saniye içinde yenilenecek...")

st.caption("💡 **Güç Seviyeleri:** 4/4 borsa = Çok Güçlü (Kalın yeşil/kırmızı) | 1/4 borsa = Zayıf (İnce açık renk)")
