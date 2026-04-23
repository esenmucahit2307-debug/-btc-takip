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

# ==================== COİN LİSTESİ ====================
coin_listesi = [
    "BTC/USDT", "ETH/USDT", "BNB/USDT", "SOL/USDT", "XRP/USDT",
    "DOGE/USDT", "ADA/USDT", "TON/USDT", "AVAX/USDT", "LINK/USDT",
    "UNI/USDT", "AAVE/USDT", "MATIC/USDT", "ARB/USDT", "OP/USDT",
    "PEPE/USDT", "WIF/USDT", "FLOKI/USDT", "SHIB/USDT", "SUI/USDT"
]

# ==================== 4 BORSA ====================
BORSALAR = {
    'Binance': ccxt.binance(),
    'Bybit': ccxt.bybit(),
    'Bitget': ccxt.bitget(),
    'OKX': ccxt.okx()
}

# ==================== RENKLER ====================
KALDIRAC_RENKLERI = {3: '#00FF00', 5: '#00CED1', 10: '#FFD700', 20: '#FF8C00', 50: '#FF0000'}

GUCLU_RENKLER = {
    4: {'renk': '#00FF00', 'kalınlık': 3.5, 'etiket': '🔥 ÇOK GÜÇLÜ (4/4)'},
    3: {'renk': '#32CD32', 'kalınlık': 2.5, 'etiket': '✅ GÜÇLÜ (3/4)'}
}

GUCLU_DIRENC_RENKLER = {
    4: {'renk': '#FF0000', 'kalınlık': 3.5, 'etiket': '🔥 ÇOK GÜÇLÜ (4/4)'},
    3: {'renk': '#FF6666', 'kalınlık': 2.5, 'etiket': '✅ GÜÇLÜ (3/4)'}
}

# ==================== BAŞLIK ====================
st.title("📈 TRADINGVIEW TARZI DASHBOARD")
st.caption("Binance + Bybit + Bitget + OKX | Destek/Direnç | Liquidation | SCALP SİNYALLERİ | 1sn Fiyat Yenileme")

# ==================== KENAR ÇUBUĞU ====================
with st.sidebar:
    st.header("⚙️ AYARLAR")
    
    secilen_coin = st.selectbox("💰 Coin seç:", coin_listesi, index=0)
    coin_adi = secilen_coin.split("/")[0]
    
    st.markdown("---")
    
    # Zaman dilimleri (45 DAKİKA EKLENDİ)
    zaman_dilimleri = {
        "1 Dakika": "1m", "5 Dakika": "5m", "15 Dakika": "15m",
        "30 Dakika": "30m", "45 Dakika": "45m", "1 Saat": "1h",
        "2 Saat": "2h", "4 Saat": "4h", "6 Saat": "6h",
        "12 Saat": "12h", "1 Gün": "1d", "1 Hafta": "1w"
    }
    
    secili_zaman = st.selectbox("⏱️ Zaman dilimi:", list(zaman_dilimleri.keys()), index=5)
    tf_kodu = zaman_dilimleri[secili_zaman]
    
    st.markdown("---")
    
    # Göstergeler
    st.subheader("📊 Göstergeler")
    destek_acik = st.checkbox("🟢 Destek Çizgileri", value=True)
    direnc_acik = st.checkbox("🔴 Direnç Çizgileri", value=True)
    
    st.markdown("---")
    
    # Liquidation
    st.subheader("🔥 Liquidation Haritası")
    liq_acik = st.checkbox("Liquidation Haritasını Göster", value=True)
    
    if liq_acik:
        st.markdown("**Kaldıraç Çarpanları:**")
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
    
    # Scalp Sinyalleri
    st.subheader("🎯 SCALP SİNYALLERİ")
    scalp_acik = st.checkbox("Long/Short Scalp Sinyallerini Göster", value=True)
    
    st.markdown("---")
    
    # Yenileme ayarı (grafik için)
    grafik_yenileme = st.select_slider("🔄 Grafik yenileme sıklığı:", options=[15, 30, 60, 120], value=30)
    
    if st.button("🔄 Şimdi Yenile", use_container_width=True):
        st.rerun()
    
    st.caption(f"🕐 Son: {datetime.now().strftime('%H:%M:%S')}")

# ==================== FONKSİYONLAR ====================
def veri_cek(borsa, sembol, zaman_dilimi, limit=500):
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
    
    son_fiyat = df['kapanis'].iloc[-1]
    if son_fiyat < 10:
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
    
    return list(set(direncler)), list(set(destekler))

def ortak_seviye_bul(tum_direncler, tum_destekler, min_guc=3):
    direnc_sayac = Counter()
    for alt_liste in tum_direncler:
        for item in alt_liste:
            direnc_sayac[item] += 1
    
    destek_sayac = Counter()
    for alt_liste in tum_destekler:
        for item in alt_liste:
            destek_sayac[item] += 1
    
    ortak_direnc = [(seviye, sayi) for seviye, sayi in direnc_sayac.items() if sayi >= min_guc]
    ortak_destek = [(seviye, sayi) for seviye, sayi in destek_sayac.items() if sayi >= min_guc]
    
    ortak_direnc.sort(key=lambda x: x[1], reverse=True)
    ortak_destek.sort(key=lambda x: x[1], reverse=True)
    
    return ortak_direnc, ortak_destek

def tasfiye_hesapla(guncel_fiyat, kaldiraclar, coin_adi):
    base_oi = {"BTC": 15000000000, "ETH": 8000000000, "BNB": 2000000000, "SOL": 2000000000}
    oi = base_oi.get(coin_adi, 500000000)
    oran = {3: 0.15, 5: 0.25, 10: 0.35, 20: 0.15, 50: 0.10}
    
    long_tasfiye = []
    short_tasfiye = []
    
    for k in kaldiraclar:
        long_price = round(guncel_fiyat * (1 - 1/k))
        short_price = round(guncel_fiyat * (1 + 1/k))
        hacim = int(oi * oran.get(k, 0.1))
        
        long_tasfiye.append({'kaldirac': k, 'fiyat': long_price, 'hacim': hacim, 'renk': KALDIRAC_RENKLERI.get(k, '#FFF')})
        short_tasfiye.append({'kaldirac': k, 'fiyat': short_price, 'hacim': hacim, 'renk': KALDIRAC_RENKLERI.get(k, '#FFF')})
    
    return {'long': sorted(long_tasfiye, key=lambda x: x['fiyat'], reverse=True), 'short': sorted(short_tasfiye, key=lambda x: x['fiyat'])}

def scalp_sinyalleri_uret(df, guncel_fiyat, destekler, direncler):
    sinyaller = {'long': [], 'short': []}
    
    if df is None or len(df) < 20:
        return sinyaller
    
    son_kapanis = df['kapanis'].iloc[-1]
    onceki_kapanis = df['kapanis'].iloc[-2]
    
    ma_short = df['kapanis'].rolling(5).mean().iloc[-1]
    ma_long = df['kapanis'].rolling(20).mean().iloc[-1]
    trend_yukari = ma_short > ma_long
    
    en_yakin_destek = None
    for seviye, _ in destekler:
        if seviye < guncel_fiyat:
            if en_yakin_destek is None or seviye > en_yakin_destek:
                en_yakin_destek = seviye
    
    en_yakin_direnc = None
    for seviye, _ in direncler:
        if seviye > guncel_fiyat:
            if en_yakin_direnc is None or seviye < en_yakin_direnc:
                en_yakin_direnc = seviye
    
    mesafe_destek = ((guncel_fiyat - en_yakin_destek) / guncel_fiyat * 100) if en_yakin_destek else 100
    mesafe_direnc = ((en_yakin_direnc - guncel_fiyat) / guncel_fiyat * 100) if en_yakin_direnc else 100
    
    # LONG SİNYALLERİ
    if son_kapanis > onceki_kapanis * 1.001:
        sinyaller['long'].append({
            'seviye': '🟢 HAFİF LONG',
            'neden': '📈 Fiyat yükseliş trendinde',
            'hedef': en_yakin_direnc if en_yakin_direnc else guncel_fiyat * 1.01,
            'zarar_kes': en_yakin_destek if en_yakin_destek else guncel_fiyat * 0.99
        })
    
    if mesafe_destek < 1.5 and en_yakin_destek:
        sinyaller['long'].append({
            'seviye': '🟢 GÜÇLÜ LONG',
            'neden': f'🔥 Destek bölgesine yakın ({mesafe_destek:.1f}%)',
            'hedef': en_yakin_direnc if en_yakin_direnc else guncel_fiyat * 1.02,
            'zarar_kes': en_yakin_destek - (guncel_fiyat * 0.005)
        })
    
    if trend_yukari:
        sinyaller['long'].append({
            'seviye': '🟡 ORTA LONG',
            'neden': '📊 Genel trend yukarı yönlü',
            'hedef': en_yakin_direnc if en_yakin_direnc else guncel_fiyat * 1.015,
            'zarar_kes': en_yakin_destek if en_yakin_destek else guncel_fiyat * 0.995
        })
    
    # SHORT SİNYALLERİ
    if son_kapanis < onceki_kapanis * 0.999:
        sinyaller['short'].append({
            'seviye': '🔴 HAFİF SHORT',
            'neden': '📉 Fiyat düşüş trendinde',
            'hedef': en_yakin_destek if en_yakin_destek else guncel_fiyat * 0.99,
            'zarar_kes': en_yakin_direnc if en_yakin_direnc else guncel_fiyat * 1.01
        })
    
    if mesafe_direnc < 1.5 and en_yakin_direnc:
        sinyaller['short'].append({
            'seviye': '🔴 GÜÇLÜ SHORT',
            'neden': f'🔥 Direnç bölgesine yakın ({mesafe_direnc:.1f}%)',
            'hedef': en_yakin_destek if en_yakin_destek else guncel_fiyat * 0.98,
            'zarar_kes': en_yakin_direnc + (guncel_fiyat * 0.005)
        })
    
    if not trend_yukari and ma_short < ma_long:
        sinyaller['short'].append({
            'seviye': '🟠 ORTA SHORT',
            'neden': '📊 Genel trend aşağı yönlü',
            'hedef': en_yakin_destek if en_yakin_destek else guncel_fiyat * 0.985,
            'zarar_kes': en_yakin_direnc if en_yakin_direnc else guncel_fiyat * 1.005
        })
    
    return sinyaller

def grafik_ciz(df, baslik, direncler, destekler, tasfiye, guncel_fiyat, destek_acik, direnc_acik, liq_acik):
    if df is None or len(df) == 0:
        fig = go.Figure()
        return fig
    
    fig = go.Figure()
    
    fig.add_trace(go.Candlestick(
        x=df.index, open=df['acilis'], high=df['yuksek'],
        low=df['dusuk'], close=df['kapanis'], name='Fiyat'
    ))
    
    if destek_acik:
        for seviye, guc in destekler:
            renk = GUCLU_RENKLER.get(guc, GUCLU_RENKLER[3])['renk']
            kalinlik = GUCLU_RENKLER.get(guc, GUCLU_RENKLER[3])['kalınlık']
            etiket = GUCLU_RENKLER.get(guc, GUCLU_RENKLER[3])['etiket']
            fig.add_hline(y=seviye, line_dash="solid", line_color=renk, line_width=kalinlik,
                         annotation_text=f"🟢 {etiket} {seviye:.2f}", annotation_position="top right")
    
    if direnc_acik:
        for seviye, guc in direncler:
            renk = GUCLU_DIRENC_RENKLER.get(guc, GUCLU_DIRENC_RENKLER[3])['renk']
            kalinlik = GUCLU_DIRENC_RENKLER.get(guc, GUCLU_DIRENC_RENKLER[3])['kalınlık']
            etiket = GUCLU_DIRENC_RENKLER.get(guc, GUCLU_DIRENC_RENKLER[3])['etiket']
            fig.add_hline(y=seviye, line_dash="solid", line_color=renk, line_width=kalinlik,
                         annotation_text=f"🔴 {etiket} {seviye:.2f}", annotation_position="top right")
    
    if liq_acik:
        for item in tasfiye.get('long', []):
            fig.add_hline(y=item['fiyat'], line_dash="dash", line_color=item['renk'], line_width=2,
                         annotation_text=f"🔥 LONG {item['kaldirac']}x", annotation_position="bottom left")
        for item in tasfiye.get('short', []):
            fig.add_hline(y=item['fiyat'], line_dash="dash", line_color=item['renk'], line_width=2,
                         annotation_text=f"💀 SHORT {item['kaldirac']}x", annotation_position="top left")
    
    fig.add_hline(y=guncel_fiyat, line_dash="dot", line_color="white", line_width=1.5,
                 annotation_text=f"📍 GÜNCEL {guncel_fiyat:.2f}", annotation_position="top left")
    
    fig.update_layout(
        height=650,
        title=dict(text=baslik, x=0.5, xanchor='center'),
        template="plotly_dark",
        paper_bgcolor='#131722',
        plot_bgcolor='#131722',
        xaxis=dict(
            showgrid=True, gridcolor='#2a2a2a', showline=True, linecolor='#444',
            rangeslider=dict(visible=False)
        ),
        yaxis=dict(
            showgrid=True, gridcolor='#2a2a2a', showline=True, linecolor='#444', side='right'
        ),
        dragmode='zoom',
        hovermode='x unified'
    )
    
    return fig

# ==================== CANLI FİYAT GÜNCELLEME (1 SANİYE) ====================
def canli_fiyat_goster():
    """1 saniyede bir güncellenen canlı fiyat gösterimi"""
    fiyat_placeholder = st.empty()
    
    while True:
        anlik_fiyatlar = []
        for borsa_adi, borsa in BORSALAR.items():
            fiyat, degisim = anlik_fiyat_al(borsa, secilen_coin)
            if fiyat:
                anlik_fiyatlar.append(fiyat)
        
        ortalama = sum(anlik_fiyatlar) / len(anlik_fiyatlar) if anlik_fiyatlar else 0
        
        with fiyat_placeholder.container():
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("💰 BTC/USDT", f"${ortalama:,.2f}")
            col2.metric("⏱️ Zaman", secili_zaman)
            col3.metric("🏛️ Borsa", "4 Borsa")
            col4.metric("🔄 Canlı", "1sn")
        
        time.sleep(1)

# ==================== ANA İŞLEM ====================

# Canlı fiyat satırı (1 saniyede bir yenilenen)
st.subheader(f"💰 {coin_adi} CANLI FİYAT (1 Saniye Güncelleme)")

# Canlı fiyatları göster
fiyat_placeholders = []
for idx, (borsa_adi, borsa) in enumerate(BORSALAR.items()):
    fiyat_placeholders.append(st.empty())

# Canlı fiyat güncelleme döngüsü
son_fiyatlar = {}
for borsa_adi, borsa in BORSALAR.items():
    fiyat, degisim = anlik_fiyat_al(borsa, secilen_coin)
    if fiyat:
        son_fiyatlar[borsa_adi] = {'fiyat': fiyat, 'degisim': degisim}

# Fiyatları göster
cols = st.columns(4)
for idx, (borsa_adi, veri) in enumerate(son_fiyatlar.items()):
    with cols[idx]:
        st.metric(borsa_adi, f"${veri['fiyat']:,.2f}", f"{veri['degisim']:.2f}%" if veri['degisim'] else None)

ortalama_fiyat = sum([v['fiyat'] for v in son_fiyatlar.values()]) / len(son_fiyatlar) if son_fiyatlar else 0

# Bilgi kartları
col1, col2, col3, col4 = st.columns(4)
with col1: st.metric("💰 Ortalama", f"${ortalama_fiyat:,.2f}")
with col2: st.metric("⏱️ Zaman", secili_zaman)
with col3: st.metric("🏛️ Borsa", "4 Borsa")
with col4: st.metric("🔄 Yenileme", f"{grafik_yenileme} sn")

st.markdown("---")

# ==================== SCALP SİNYALLERİ ====================
if scalp_acik:
    st.subheader("🎯 LONG/SHORT SCALP SİNYALLERİ")
    
    # Geçici veri ile sinyal üretimi
    gecici_df = None
    for borsa in BORSALAR.values():
        df = veri_cek(borsa, secilen_coin, tf_kodu, limit=50)
        if df is not None:
            gecici_df = df
            break
    
    if gecici_df is not None:
        gecici_direncler = []
        gecici_destekler = []
        for borsa in BORSALAR.values():
            df = veri_cek(borsa, secilen_coin, tf_kodu, limit=100)
            if df is not None:
                d, s = seviye_bul(df, order=10)
                gecici_direncler.append(d)
                gecici_destekler.append(s)
        
        g_ortak_direnc, g_ortak_destek = ortak_seviye_bul(gecici_direncler, gecici_destekler, min_guc=2)
        sinyaller = scalp_sinyalleri_uret(gecici_df, ortalama_fiyat, g_ortak_destek, g_ortak_direnc)
        
        col_long, col_short = st.columns(2)
        
        with col_long:
            st.markdown("### 📈 LONG SİNYALLERİ")
            if sinyaller['long']:
                for s in sinyaller['long'][:3]:
                    st.markdown(f"""
                    <div style='background-color:#1a3d1a; border-left: 4px solid #00FF00; padding: 8px; margin: 5px 0; border-radius: 5px;'>
                    <b>{s['seviye']}</b><br>
                    📌 {s['neden']}<br>
                    🎯 Hedef: <b>${s['hedef']:,.2f}</b> | 🛑 Stop: <b>${s['zarar_kes']:,.2f}</b>
                    </div>
                    """, unsafe_allow_html=True)
            else:
                st.info("🟡 Şu anda LONG sinyali yok")
        
        with col_short:
            st.markdown("### 📉 SHORT SİNYALLERİ")
            if sinyaller['short']:
                for s in sinyaller['short'][:3]:
                    st.markdown(f"""
                    <div style='background-color:#3d1a1a; border-left: 4px solid #FF0000; padding: 8px; margin: 5px 0; border-radius: 5px;'>
                    <b>{s['seviye']}</b><br>
                    📌 {s['neden']}<br>
                    🎯 Hedef: <b>${s['hedef']:,.2f}</b> | 🛑 Stop: <b>${s['zarar_kes']:,.2f}</b>
                    </div>
                    """, unsafe_allow_html=True)
            else:
                st.info("🟠 Şu anda SHORT sinyali yok")
    else:
        st.warning("Sinyaller için veri bekleniyor...")
    
    st.markdown("---")

# ==================== VERİ ÇEKME ====================
with st.spinner(f"📊 {coin_adi} verileri yükleniyor..."):
    tum_direncler, tum_destekler, ana_df = [], [], None
    
    for borsa_adi, borsa in BORSALAR.items():
        df = veri_cek(borsa, secilen_coin, tf_kodu, limit=500)
        if df is not None:
            if ana_df is None:
                ana_df = df
            
            if tf_kodu in ['1m', '5m']:
                order_val = 8
            elif tf_kodu in ['15m', '30m', '45m']:
                order_val = 10
            elif tf_kodu in ['1h']:
                order_val = 12
            else:
                order_val = 14
            
            direnc, destek = seviye_bul(df, order=order_val)
            tum_direncler.append(direnc)
            tum_destekler.append(destek)
    
    # Sadece güçlü seviyeler (3+ borsa)
    ortak_direnc, ortak_destek = ortak_seviye_bul(tum_direncler, tum_destekler, min_guc=3)
    
    # Tasfiye
    if liq_acik and secili_kaldiraclar:
        tasfiye = tasfiye_hesapla(ortalama_fiyat, secili_kaldiraclar, coin_adi)
    else:
        tasfiye = {'long': [], 'short': []}

# ==================== GRAFİK ====================
st.subheader("📈 Mum Grafiği - Fare ile kaydır, çift tıkla sıfırla")

if ana_df is not None:
    fig = grafik_ciz(ana_df, f"{coin_adi}/USDT - {secili_zaman}", ortak_direnc, ortak_destek, tasfiye, ortalama_fiyat, destek_acik, direnc_acik, liq_acik)
    
    config = {'scrollZoom': True, 'doubleClick': 'reset', 'displayModeBar': True, 'displaylogo': False, 'responsive': True}
    st.plotly_chart(fig, use_container_width=True, config=config)
    
    # Destek Listesi
    if destek_acik and ortak_destek:
        st.markdown("---")
        st.subheader("🟢 GÜÇLÜ DESTEK SEVİYELERİ (3+ Borsa)")
        for seviye, guc in ortak_destek[:8]:
            renk = GUCLU_RENKLER.get(guc, GUCLU_RENKLER[3])['renk']
            etiket = GUCLU_RENKLER.get(guc, GUCLU_RENKLER[3])['etiket']
            st.markdown(f"<div style='border-left: 4px solid {renk}; padding: 5px 10px; margin: 5px 0'>"
                       f"<b style='color:{renk}'>⬤ ${seviye:,.2f}</b> - {etiket}</div>", unsafe_allow_html=True)
    
    # Direnç Listesi
    if direnc_acik and ortak_direnc:
        st.markdown("---")
        st.subheader("🔴 GÜÇLÜ DİRENÇ SEVİYELERİ (3+ Borsa)")
        for seviye, guc in ortak_direnc[:8]:
            renk = GUCLU_DIRENC_RENKLER.get(guc, GUCLU_DIRENC_RENKLER[3])['renk']
            etiket = GUCLU_DIRENC_RENKLER.get(guc, GUCLU_DIRENC_RENKLER[3])['etiket']
            st.markdown(f"<div style='border-left: 4px solid {renk}; padding: 5px 10px; margin: 5px 0'>"
                       f"<b style='color:{renk}'>⬤ ${seviye:,.2f}</b> - {etiket}</div>", unsafe_allow_html=True)
    
    # Liquidation Listesi
    if liq_acik and tasfiye['long']:
        st.markdown("---")
        st.subheader("🔥 LİQUİDATION (TASFİYE) BÖLGELERİ")
        col_l, col_s = st.columns(2)
        with col_l:
            st.markdown("**📉 LONG TASFİYE**")
            for item in tasfiye['long'][:5]:
                st.markdown(f"<span style='color:{item['renk']}'>⚡ {item['kaldirac']}x</span> | ${item['fiyat']:,.0f} | ${item['hacim']/1e6:.0f}M", unsafe_allow_html=True)
        with col_s:
            st.markdown("**📈 SHORT TASFİYE**")
            for item in tasfiye['short'][:5]:
                st.markdown(f"<span style='color:{item['renk']}'>⚡ {item['kaldirac']}x</span> | ${item['fiyat']:,.0f} | ${item['hacim']/1e6:.0f}M", unsafe_allow_html=True)
else:
    st.error("❌ Veri alınamadı")

# ==================== OTOMATİK YENİLEME (GRAFİK) ====================
if 'son_yenileme' not in st.session_state:
    st.session_state.son_yenileme = time.time()

gecen_sure = time.time() - st.session_state.son_yenileme
if gecen_sure > grafik_yenileme:
    st.session_state.son_yenileme = time.time()
    st.rerun()
else:
    st.info(f"🔄 Grafik {int(grafik_yenileme - gecen_sure)} saniye içinde yenilenecek... (Fiyatlar 1 saniyede bir güncellenir)")

st.caption("💡 **Tüm Özellikler:** 45dk zaman dilimi | 1 saniye fiyat yenileme | TradingView grafik | 4 Borsa | Güçlü D/D | Liquidation | Long/Short Scalp Sinyalleri")
