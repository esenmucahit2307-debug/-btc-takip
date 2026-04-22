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

# ==================== 40+ COİN LİSTESİ ====================
coin_listesi = [
    "BTC/USDT", "ETH/USDT", "BNB/USDT", "SOL/USDT", "XRP/USDT",
    "DOGE/USDT", "ADA/USDT", "TRX/USDT", "TON/USDT", "AVAX/USDT",
    "DOT/USDT", "LTC/USDT", "NEAR/USDT", "APT/USDT", "SUI/USDT",
    "ATOM/USDT", "LINK/USDT", "UNI/USDT", "AAVE/USDT", "MATIC/USDT",
    "ARB/USDT", "OP/USDT", "INJ/USDT", "ETC/USDT", "FIL/USDT",
    "PEPE/USDT", "WIF/USDT", "FLOKI/USDT", "SHIB/USDT", "ZEC/USDT"
]

# ==================== HER KALDIRAÇ İÇİN RENK ====================
KALDIRAC_RENKLERI = {3: '#00FF00', 5: '#00CED1', 10: '#FFD700', 20: '#FF8C00', 50: '#FF0000'}

# ==================== DESTEK/DİRENÇ GÜÇ RENKLERİ (Tüm seviyeler) ====================
GUÇ_RENKLERI = {
    4: {'renk': '#00FF00', 'kalınlık': 4.0, 'etiket': '🔷 ÇOK GÜÇLÜ (4/4 Borsa)'},
    3: {'renk': '#32CD32', 'kalınlık': 3.0, 'etiket': '🟢 GÜÇLÜ (3/4 Borsa)'},
    2: {'renk': '#7CFC00', 'kalınlık': 2.2, 'etiket': '🟡 ORTA (2/4 Borsa)'},
    1: {'renk': '#ADFF2F', 'kalınlık': 1.5, 'etiket': '🔸 ZAYIF (1/4 Borsa)'}
}

DIRENC_GUÇ_RENKLERI = {
    4: {'renk': '#FF0000', 'kalınlık': 4.0, 'etiket': '🔷 ÇOK GÜÇLÜ (4/4 Borsa)'},
    3: {'renk': '#FF4444', 'kalınlık': 3.0, 'etiket': '🔴 GÜÇLÜ (3/4 Borsa)'},
    2: {'renk': '#FF6666', 'kalınlık': 2.2, 'etiket': '🟠 ORTA (2/4 Borsa)'},
    1: {'renk': '#FF9999', 'kalınlık': 1.5, 'etiket': '🔸 ZAYIF (1/4 Borsa)'}
}

# ==================== BAŞLIK ====================
st.title("📈 CANLI KRİPTO DASHBOARD")
st.caption("TradingView tarzı | 10.000 bar geçmiş (2020 öncesi) | Güç skalalı Destek/Direnç")

# ==================== KENAR ÇUBUĞU ====================
with st.sidebar:
    st.header("⚙️ PANEL AYARLARI")
    
    secilen_coin = st.selectbox("💰 Coin seç:", coin_listesi, index=0)
    coin_adi = secilen_coin.split("/")[0]
    
    st.markdown("---")
    
    zaman_dilimleri = {
        "5 Dakika": "5m", "15 Dakika": "15m", "30 Dakika": "30m",
        "1 Saat": "1h", "2 Saat": "2h", "4 Saat": "4h",
        "1 Gün": "1d", "1 Hafta": "1w"
    }
    
    secili_zaman = st.selectbox("⏱️ Zaman dilimi:", list(zaman_dilimleri.keys()), index=3)
    tf_kodu = zaman_dilimleri[secili_zaman]
    
    st.markdown("---")
    
    tum_borsalar = {
        'Binance': ccxt.binance(),
        'Bybit': ccxt.bybit(),
        'Bitget': ccxt.bitget(),
        'OKX': ccxt.okx()
    }
    
    secili_borsalar = st.multiselect("🏛️ Borsalar:", list(tum_borsalar.keys()), default=list(tum_borsalar.keys()))
    if len(secili_borsalar) == 0:
        st.error("❌ En az bir borsa seçin!")
        st.stop()
    
    st.markdown("---")
    
    destek_acik = st.checkbox("🟢 Destek Çizgileri (Tüm Güçler)", value=True)
    direnc_acik = st.checkbox("🔴 Direnç Çizgileri (Tüm Güçler)", value=True)
    
    st.markdown("---")
    
    liq_acik = st.checkbox("🔥 Liquidation Haritası", value=True)
    if liq_acik:
        col1, col2 = st.columns(2)
        with col1:
            k3x = st.checkbox("3x", value=True)
            k5x = st.checkbox("5x", value=True)
            k10x = st.checkbox("10x", value=True)
        with col2:
            k20x = st.checkbox("20x", value=True)
            k50x = st.checkbox("50x", value=True)
        
        secili_kaldiraclar = []
        if k3x: secili_kaldiraclar.append(3)
        if k5x: secili_kaldiraclar.append(5)
        if k10x: secili_kaldiraclar.append(10)
        if k20x: secili_kaldiraclar.append(20)
        if k50x: secili_kaldiraclar.append(50)
        if not secili_kaldiraclar:
            secili_kaldiraclar = [3, 5, 10]
    else:
        secili_kaldiraclar = []
    
    st.markdown("---")
    
    yenileme_araligi = st.select_slider("🔄 Yenileme sıklığı:", options=[10, 15, 30, 60], value=15)
    
    if st.button("🔄 Şimdi Yenile", use_container_width=True):
        st.rerun()
    
    st.caption(f"🕐 Son: {datetime.now().strftime('%H:%M:%S')}")

# ==================== BORSALARI HAZIRLA ====================
borsalar = {adi: tum_borsalar[adi] for adi in secili_borsalar}

# ==================== FONKSİYONLAR ====================
def veri_cek(borsa, sembol, zaman_dilimi, limit=10000):
    """10.000 bar geçmiş veri çeker (2020 öncesine gider)"""
    try:
        st.info(f"📥 {borsa} verisi çekiliyor... (10.000 bar)")
        bardata = borsa.fetch_ohlcv(sembol, zaman_dilimi, limit=limit)
        df = pd.DataFrame(bardata, columns=['zaman', 'acilis', 'yuksek', 'dusuk', 'kapanis', 'hacim'])
        df['zaman'] = pd.to_datetime(df['zaman'], unit='ms')
        df.set_index('zaman', inplace=True)
        return df
    except Exception as e:
        st.warning(f"{borsa} veri çekilemedi: {str(e)[:50]}")
        return None

def anlik_fiyat_al(borsa, sembol):
    try:
        ticker = borsa.fetch_ticker(sembol)
        return ticker['last'], ticker['percentage'] if 'percentage' in ticker else 0
    except:
        return None, None

def seviye_bul(df, order=8, yuvarla=20):
    """Destek ve direnç seviyelerini bulur"""
    if df is None or len(df) < 20:
        return [], []
    
    # Fiyat aralığına göre yuvarlama değerini ayarla
    son_fiyat = df['kapanis'].iloc[-1]
    if son_fiyat < 1:
        yuvarla = 0.05
    elif son_fiyat < 10:
        yuvarla = 0.5
    elif son_fiyat < 50:
        yuvarla = 2
    elif son_fiyat < 200:
        yuvarla = 10
    else:
        yuvarla = 50
    
    tepeler = argrelextrema(df['yuksek'].values, np.greater_equal, order=order)[0]
    dipler = argrelextrema(df['dusuk'].values, np.less_equal, order=order)[0]
    
    direncler = [round(df['yuksek'].iloc[t] / yuvarla) * yuvarla for t in tepeler]
    destekler = [round(df['dusuk'].iloc[d] / yuvarla) * yuvarla for d in dipler]
    
    # Tekrarları temizle ve sırala
    direncler = sorted(list(set(direncler)))
    destekler = sorted(list(set(destekler)))
    
    return direncler, destekler

def ortak_seviye_bul_tum(tum_direncler, tum_destekler):
    """Tüm seviyeleri bul (kaç borsada görüldüğüyle birlikte)"""
    direnc_sayac = Counter()
    for alt_liste in tum_direncler:
        for item in alt_liste:
            direnc_sayac[item] += 1
    
    destek_sayac = Counter()
    for alt_liste in tum_destekler:
        for item in alt_liste:
            destek_sayac[item] += 1
    
    # Tüm seviyeleri al
    ortak_direnc = [(seviye, sayi) for seviye, sayi in direnc_sayac.items()]
    ortak_destek = [(seviye, sayi) for seviye, sayi in destek_sayac.items()]
    
    # Güce göre sırala (en güçlü önce)
    ortak_direnc.sort(key=lambda x: x[1], reverse=True)
    ortak_destek.sort(key=lambda x: x[1], reverse=True)
    
    return ortak_direnc, ortak_destek

def tahmini_hacim_hesapla(fiyat, kaldirac, coin_adi):
    base_oi = {"BTC": 15000000000, "ETH": 8000000000, "BNB": 2000000000, "SOL": 2000000000, "XRP": 1000000000}
    oi = base_oi.get(coin_adi, 200000000)
    oran = {3: 0.15, 5: 0.25, 10: 0.35, 20: 0.15, 50: 0.10}
    return int(oi * oran.get(kaldirac, 0.1))

def tasfiye_seviyeleri_hesapla(guncel_fiyat, kaldiraclar, coin_adi):
    long_tasfiye, short_tasfiye = [], []
    for k in kaldiraclar:
        long_price = round(guncel_fiyat * (1 - 1/k))
        short_price = round(guncel_fiyat * (1 + 1/k))
        hacim = tahmini_hacim_hesapla(guncel_fiyat, k, coin_adi)
        long_tasfiye.append({'kaldirac': k, 'fiyat': long_price, 'hacim': hacim, 'renk': KALDIRAC_RENKLERI.get(k, '#FFF')})
        short_tasfiye.append({'kaldirac': k, 'fiyat': short_price, 'hacim': hacim, 'renk': KALDIRAC_RENKLERI.get(k, '#FFF')})
    return {'long': sorted(long_tasfiye, key=lambda x: x['fiyat'], reverse=True), 'short': sorted(short_tasfiye, key=lambda x: x['fiyat'])}

def grafik_ciz(df, baslik, ortak_direnc, ortak_destek, tasfiye, guncel_fiyat, destek_acik, direnc_acik, liq_acik):
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
    
    # Destek çizgileri (Tüm güçler)
    if destek_acik:
        for seviye, guc in ortak_destek[:15]:  # En fazla 15 seviye
            g_info = GUÇ_RENKLERI.get(guc, GUÇ_RENKLERI[1])
            fig.add_hline(y=seviye, line_dash="solid", line_color=g_info['renk'], line_width=g_info['kalınlık'],
                         annotation_text=f"🟢 {g_info['etiket']} {seviye:.2f}", annotation_position="top right")
    
    # Direnç çizgileri (Tüm güçler)
    if direnc_acik:
        for seviye, guc in ortak_direnc[:15]:
            g_info = DIRENC_GUÇ_RENKLERI.get(guc, DIRENC_GUÇ_RENKLERI[1])
            fig.add_hline(y=seviye, line_dash="solid", line_color=g_info['renk'], line_width=g_info['kalınlık'],
                         annotation_text=f"🔴 {g_info['etiket']} {seviye:.2f}", annotation_position="top right")
    
    # Liquidation
    if liq_acik:
        for item in tasfiye.get('long', []):
            fig.add_hline(y=item['fiyat'], line_dash="dash", line_color=item['renk'], line_width=2,
                         annotation_text=f"🔥 LONG {item['kaldirac']}x", annotation_position="bottom left")
        for item in tasfiye.get('short', []):
            fig.add_hline(y=item['fiyat'], line_dash="dash", line_color=item['renk'], line_width=2,
                         annotation_text=f"💀 SHORT {item['kaldirac']}x", annotation_position="top left")
    
    # Güncel fiyat
    fig.add_hline(y=guncel_fiyat, line_dash="dot", line_color="white", line_width=1.5,
                 annotation_text=f"📍 GÜNCEL {guncel_fiyat:.2f}", annotation_position="top left")
    
    # Grafik ayarları - TAM EKRAN KAYDIRMA VE YAKINLAŞTIRMA
    fig.update_layout(
        height=700,
        title=baslik,
        template="plotly_dark",
        xaxis_title="Zaman (2020 öncesine kadar)",
        yaxis_title="Fiyat (USDT)",
        xaxis=dict(
            rangeslider=dict(visible=False),
            type="date",
            fixedrange=False,
            tickformat="%Y-%m-%d"
        ),
        yaxis=dict(fixedrange=False),
        dragmode="zoom",
        hovermode='closest'
    )
    return fig

# ==================== ANA İŞLEM ====================
st.subheader(f"📊 {coin_adi} Canlı Fiyat Takibi")

# Canlı fiyatlar
fiyat_cols = st.columns(len(secili_borsalar))
anlik_fiyatlar = []
for idx, borsa_adi in enumerate(secili_borsalar):
    borsa = tum_borsalar[borsa_adi]
    fiyat, degisim = anlik_fiyat_al(borsa, secilen_coin)
    if fiyat:
        anlik_fiyatlar.append(fiyat)
        with fiyat_cols[idx]:
            st.metric(label=f"{borsa_adi}", value=f"${fiyat:,.4f}" if fiyat < 1 else f"${fiyat:,.2f}",
                     delta=f"{degisim:.2f}%" if degisim else None)

ortalama_fiyat = sum(anlik_fiyatlar) / len(anlik_fiyatlar) if anlik_fiyatlar else 0

col1, col2, col3, col4, col5 = st.columns(5)
with col1: st.metric("💰 Ortalama", f"${ortalama_fiyat:,.4f}" if ortalama_fiyat < 1 else f"${ortalama_fiyat:,.2f}")
with col2: st.metric("⏱️ Zaman", secili_zaman)
with col3: st.metric("🏛️ Borsa", len(secili_borsalar))
with col4: st.metric("📊 Bar", "10.000")
with col5: st.metric("🔄 Yenileme", f"{yenileme_araligi} sn")

st.markdown("---")

# ==================== VERİ ÇEKME (10.000 BAR) ====================
with st.spinner(f"📥 10.000 bar geçmiş veri çekiliyor (2020 öncesine gidiyor)... Bu 10-20 saniye sürebilir"):
    
    tum_direncler, tum_destekler, ana_df = [], [], None
    
    for borsa_adi, borsa in borsalar.items():
        df = veri_cek(borsa, secilen_coin, tf_kodu, limit=10000)
        if df is not None:
            if ana_df is None: 
                ana_df = df
            
            # Coin fiyatına göre order değeri
            son_fiyat = df['kapanis'].iloc[-1]
            if son_fiyat < 10:
                order_val = 6
            elif son_fiyat < 100:
                order_val = 8
            else:
                order_val = 10
            
            direnc, destek = seviye_bul(df, order=order_val)
            tum_direncler.append(direnc)
            tum_destekler.append(destek)
            st.success(f"✅ {borsa_adi} verisi çekildi: {len(df)} bar")
    
    # Tüm seviyeleri bul (güç skalalı)
    ortak_direnc, ortak_destek = ortak_seviye_bul_tum(tum_direncler, tum_destekler)
    
    # Tasfiye
    if liq_acik and secili_kaldiraclar:
        tasfiye = tasfiye_seviyeleri_hesapla(ortalama_fiyat, secili_kaldiraclar, coin_adi)
    else:
        tasfiye = {'long': [], 'short': []}
    
    st.success(f"✅ Toplam {len(ortak_destek)} destek, {len(ortak_direnc)} direnç seviyesi bulundu")

# ==================== GRAFİK ====================
st.subheader("📈 Mum Grafiği - Fare ile kaydır, çift tıkla sıfırla")

if ana_df is not None:
    # Grafik başlığında veri aralığını göster
    veri_baslangic = ana_df.index[0].strftime('%Y-%m-%d')
    veri_bitis = ana_df.index[-1].strftime('%Y-%m-%d')
    
    fig = grafik_ciz(ana_df, f"{coin_adi}/USDT - {secili_zaman} | Veri: {veri_baslangic} - {veri_bitis} (10.000 Bar)", 
                     ortak_direnc, ortak_destek, tasfiye, ortalama_fiyat, 
                     destek_acik, direnc_acik, liq_acik)
    
    config = {
        'scrollZoom': True,
        'doubleClick': 'reset',
        'displayModeBar': True,
        'modeBarButtonsToRemove': ['lasso2d', 'select2d'],
        'displaylogo': False,
        'responsive': True
    }
    
    st.plotly_chart(fig, use_container_width=True, config=config)
    
    # ==================== DESTEK LİSTESİ (Güç sıralı) ====================
    if destek_acik and ortak_destek:
        st.markdown("---")
        st.subheader("🟢 DESTEK SEVİYELERİ (Güçlüden Zayıfa)")
        for seviye, guc in ortak_destek[:12]:
            g_info = GUÇ_RENKLERI.get(guc, GUÇ_RENKLERI[1])
            yuzde = (guc / len(secili_borsalar)) * 100
            st.markdown(f"<div style='border-left: 4px solid {g_info['renk']}; padding-left: 10px; margin: 5px 0;'>"
                       f"<b style='color:{g_info['renk']}'>⬤ ${seviye:,.4f if seviye < 1 else seviye:,.2f}</b> | "
                       f"{g_info['etiket']} | {guc}/{len(secili_borsalar)} borsa (%{yuzde:.0f})</div>", unsafe_allow_html=True)
    
    if direnc_acik and ortak_direnc:
        st.markdown("---")
        st.subheader("🔴 DİRENÇ SEVİYELERİ (Güçlüden Zayıfa)")
        for seviye, guc in ortak_direnc[:12]:
            g_info = DIRENC_GUÇ_RENKLERI.get(guc, DIRENC_GUÇ_RENKLERI[1])
            yuzde = (guc / len(secili_borsalar)) * 100
            st.markdown(f"<div style='border-left: 4px solid {g_info['renk']}; padding-left: 10px; margin: 5px 0;'>"
                       f"<b style='color:{g_info['renk']}'>⬤ ${seviye:,.4f if seviye < 1 else seviye:,.2f}</b> | "
                       f"{g_info['etiket']} | {guc}/{len(secili_borsalar)} borsa (%{yuzde:.0f})</div>", unsafe_allow_html=True)
    
    # ==================== TASFİYE LİSTESİ ====================
    if liq_acik and secili_kaldiraclar and (tasfiye['long'] or tasfiye['short']):
        st.markdown("---")
        st.subheader("🔥 LİQUİDATION (TASFİYE) BÖLGELERİ")
        col_l, col_s = st.columns(2)
        with col_l:
            st.markdown("### 📉 LONG TASFİYE")
            for item in tasfiye['long']:
                st.markdown(f"<div style='border-left: 4px solid {item['renk']}; padding-left: 10px;'>"
                           f"<b style='color:{item['renk']}'>⚡ {item['kaldirac']}x</b> | ${item['fiyat']:,.2f} | ${item['hacim']/1e6:.1f}M</div>", unsafe_allow_html=True)
        with col_s:
            st.markdown("### 📈 SHORT TASFİYE")
            for item in tasfiye['short']:
                st.markdown(f"<div style='border-left: 4px solid {item['renk']}; padding-left: 10px;'>"
                           f"<b style='color:{item['renk']}'>⚡ {item['kaldirac']}x</b> | ${item['fiyat']:,.2f} | ${item['hacim']/1e6:.1f}M</div>", unsafe_allow_html=True)
else:
    st.error("❌ Veri alınamadı.")

# ==================== OTOMATİK YENİLEME ====================
if 'son_yenileme' not in st.session_state:
    st.session_state.son_yenileme = time.time()

gecen_sure = time.time() - st.session_state.son_yenileme
if gecen_sure > yenileme_araligi:
    st.session_state.son_yenileme = time.time()
    st.rerun()
else:
    st.info(f"🔄 {int(yenileme_araligi - gecen_sure)} saniye içinde yenilenecek...")

st.caption("💡 **Özellikler:** 10.000 bar (2020 öncesi) | Tüm güçlerde destek/direnç gösterilir | Fare ile kaydır/yakınlaştır | Çift tıkla sıfırla")
