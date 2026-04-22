import streamlit as st
import ccxt
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from scipy.signal import argrelextrema
from datetime import datetime, timedelta
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
KALDIRAC_RENKLERI = {3: '#00FF00', 5: '#00CED1', 10: '#FFD700', 20: '#FF8C00', 50: '#FF0000'}

# ==================== DESTEK/DİRENÇ GÜÇ RENKLERİ ====================
GUÇ_RENKLERI = {
    4: {'renk': '#00FF00', 'kalınlık': 3.5, 'etiket': 'ÇOK GÜÇLÜ'},
    3: {'renk': '#32CD32', 'kalınlık': 2.8, 'etiket': 'GÜÇLÜ'},
    2: {'renk': '#7CFC00', 'kalınlık': 2.0, 'etiket': 'ORTA'},
    1: {'renk': '#ADFF2F', 'kalınlık': 1.5, 'etiket': 'ZAYIF'}
}

DIRENC_GUÇ_RENKLERI = {
    4: {'renk': '#FF0000', 'kalınlık': 3.5, 'etiket': 'ÇOK GÜÇLÜ'},
    3: {'renk': '#FF4444', 'kalınlık': 2.8, 'etiket': 'GÜÇLÜ'},
    2: {'renk': '#FF6666', 'kalınlık': 2.0, 'etiket': 'ORTA'},
    1: {'renk': '#FF9999', 'kalınlık': 1.5, 'etiket': 'ZAYIF'}
}

# ==================== BAŞLIK ====================
st.title("📈 CANLI KRİPTO DASHBOARD")
st.caption("TradingView tarzı | 1000+ bar geçmiş | Long/Short Scalp Sinyalleri")

# ==================== KENAR ÇUBUĞU ====================
with st.sidebar:
    st.header("⚙️ PANEL AYARLARI")
    
    secilen_coin = st.selectbox("💰 Coin seç:", coin_listesi, index=0)
    coin_adi = secilen_coin.split("/")[0]
    
    st.markdown("---")
    
    zaman_dilimleri = {
        "1 Dakika": "1m", "3 Dakika": "3m", "5 Dakika": "5m",
        "15 Dakika": "15m", "30 Dakika": "30m", "1 Saat": "1h",
        "2 Saat": "2h", "4 Saat": "4h", "6 Saat": "6h",
        "12 Saat": "12h", "1 Gün": "1d", "1 Hafta": "1w"
    }
    
    secili_zaman = st.selectbox("⏱️ Zaman dilimi:", list(zaman_dilimleri.keys()), index=4)
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
    
    destek_acik = st.checkbox("🟢 Destek Çizgileri", value=True)
    direnc_acik = st.checkbox("🔴 Direnç Çizgileri", value=True)
    
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
    
    yenileme_araligi = st.select_slider("🔄 Yenileme sıklığı:", options=[5, 10, 15, 30, 60], value=10)
    
    if st.button("🔄 Şimdi Yenile", use_container_width=True):
        st.rerun()
    
    st.caption(f"🕐 Son: {datetime.now().strftime('%H:%M:%S')}")

# ==================== BORSALARI HAZIRLA ====================
borsalar = {adi: tum_borsalar[adi] for adi in secili_borsalar}

# ==================== FONKSİYONLAR ====================
def veri_cek(borsa, sembol, zaman_dilimi, limit=1000):
    """1000 bar geçmiş veri çeker"""
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
    direnc_sayac = Counter()
    for alt_liste in tum_direncler:
        for item in alt_liste:
            direnc_sayac[item] += 1
    destek_sayac = Counter()
    for alt_liste in tum_destekler:
        for item in alt_liste:
            destek_sayac[item] += 1
    
    ortak_direnc = [(seviye, sayi) for seviye, sayi in direnc_sayac.items()]
    ortak_destek = [(seviye, sayi) for seviye, sayi in destek_sayac.items()]
    ortak_direnc.sort(key=lambda x: x[1], reverse=True)
    ortak_destek.sort(key=lambda x: x[1], reverse=True)
    return ortak_direnc, ortak_destek

def tahmini_hacim_hesapla(fiyat, kaldirac, coin_adi):
    base_oi = {"BTC": 15000000000, "ETH": 8000000000, "SOL": 2000000000, "XRP": 1000000000, "DOGE": 500000000}
    oi = base_oi.get(coin_adi, 500000000)
    oran = {3: 0.15, 5: 0.25, 10: 0.35, 20: 0.15, 50: 0.10}
    return int(oi * oran.get(kaldirac, 0.1))

def tasfiye_seviyeleri_hesapla(guncel_fiyat, kaldiraclar, coin_adi):
    long_tasfiye, short_tasfiye = [], []
    for k in kaldiraclar:
        long_price = round(guncel_fiyat * (1 - 1/k) / 100) * 100
        short_price = round(guncel_fiyat * (1 + 1/k) / 100) * 100
        hacim = tahmini_hacim_hesapla(guncel_fiyat, k, coin_adi)
        long_tasfiye.append({'kaldirac': k, 'fiyat': long_price, 'hacim': hacim, 'renk': KALDIRAC_RENKLERI.get(k, '#FFF')})
        short_tasfiye.append({'kaldirac': k, 'fiyat': short_price, 'hacim': hacim, 'renk': KALDIRAC_RENKLERI.get(k, '#FFF')})
    return {'long': sorted(long_tasfiye, key=lambda x: x['fiyat'], reverse=True), 'short': sorted(short_tasfiye, key=lambda x: x['fiyat'])}

def scalp_sinyalleri_uret(df, guncel_fiyat, ortak_destek, ortak_direnc):
    """Long/Short scalp sinyalleri üretir"""
    sinyaller = {'long': [], 'short': [], 'neutral': []}
    
    if df is None or len(df) < 20:
        return sinyaller
    
    son_fiyat = guncel_fiyat
    son_kapanis = df['kapanis'].iloc[-1]
    onceki_kapanis = df['kapanis'].iloc[-2]
    rsi_hesapla = (df['kapanis'].diff().clip(-1, 1).rolling(14).mean() * 100)
    
    trend = "YUKARI" if son_kapanis > df['kapanis'].rolling(20).mean().iloc[-1] else "AGI"
    
    # En yakın destek ve direnç
    en_yakin_destek = None
    for seviye, _ in ortak_destek:
        if seviye < son_fiyat:
            if en_yakin_destek is None or seviye > en_yakin_destek:
                en_yakin_destek = seviye
    
    en_yakin_direnc = None
    for seviye, _ in ortak_direnc:
        if seviye > son_fiyat:
            if en_yakin_direnc is None or seviye < en_yakin_direnc:
                en_yakin_direnc = seviye
    
    mesafe_destek = ((son_fiyat - en_yakin_destek) / son_fiyat * 100) if en_yakin_destek else 100
    mesafe_direnc = ((en_yakin_direnc - son_fiyat) / son_fiyat * 100) if en_yakin_direnc else 100
    
    # LONG Sinyalleri
    if son_kapanis > onceki_kapanis * 1.002:
        sinyaller['long'].append({
            'seviye': 'Hafif', 'neden': '📈 Fiyat yükseliş trendinde', 'hedef': en_yakin_direnc, 'zarar_kes': en_yakin_destek
        })
    if mesafe_destek < 1.5 and en_yakin_destek:
        sinyaller['long'].append({
            'seviye': 'Güçlü', 'neden': f'🔥 Destek bölgesine yakın ({mesafe_destek:.1f}%)', 'hedef': en_yakin_direnc, 'zarar_kes': en_yakin_destek - 50
        })
    if trend == "YUKARI":
        sinyaller['long'].append({
            'seviye': 'Orta', 'neden': '📊 Genel trend yukarı yönlü', 'hedef': en_yakin_direnc, 'zarar_kes': en_yakin_destek
        })
    
    # SHORT Sinyalleri
    if son_kapanis < onceki_kapanis * 0.998:
        sinyaller['short'].append({
            'seviye': 'Hafif', 'neden': '📉 Fiyat düşüş trendinde', 'hedef': en_yakin_destek, 'zarar_kes': en_yakin_direnc
        })
    if mesafe_direnc < 1.5 and en_yakin_direnc:
        sinyaller['short'].append({
            'seviye': 'Güçlü', 'neden': f'🔥 Direnç bölgesine yakın ({mesafe_direnc:.1f}%)', 'hedef': en_yakin_destek, 'zarar_kes': en_yakin_direnc + 50
        })
    if trend == "AGI":
        sinyaller['short'].append({
            'seviye': 'Orta', 'neden': '📊 Genel trend aşağı yönlü', 'hedef': en_yakin_destek, 'zarar_kes': en_yakin_direnc
        })
    
    return sinyaller

def grafik_ciz(df, baslik, ortak_direnc, ortak_destek, tasfiye, guncel_fiyat, destek_acik, direnc_acik, liq_acik):
    if df is None or len(df) == 0:
        fig = go.Figure()
        fig.add_annotation(text="Veri alınamadı", showarrow=False)
        return fig
    
    fig = go.Figure()
    
    fig.add_trace(go.Candlestick(
        x=df.index, open=df['acilis'], high=df['yuksek'],
        low=df['dusuk'], close=df['kapanis'], name='Fiyat'
    ))
    
    if destek_acik:
        for seviye, guc in ortak_destek:
            g_info = GUÇ_RENKLERI.get(guc, GUÇ_RENKLERI[1])
            fig.add_hline(y=seviye, line_dash="solid", line_color=g_info['renk'], line_width=g_info['kalınlık'],
                         annotation_text=f"🟢 DESTEK {seviye:.0f} | {g_info['etiket']}", annotation_position="top right")
    
    if direnc_acik:
        for seviye, guc in ortak_direnc:
            g_info = DIRENC_GUÇ_RENKLERI.get(guc, DIRENC_GUÇ_RENKLERI[1])
            fig.add_hline(y=seviye, line_dash="solid", line_color=g_info['renk'], line_width=g_info['kalınlık'],
                         annotation_text=f"🔴 DİRENÇ {seviye:.0f} | {g_info['etiket']}", annotation_position="top right")
    
    if liq_acik:
        for item in tasfiye.get('long', []):
            fig.add_hline(y=item['fiyat'], line_dash="dash", line_color=item['renk'], line_width=2,
                         annotation_text=f"🔥 LONG {item['kaldirac']}x", annotation_position="bottom left")
        for item in tasfiye.get('short', []):
            fig.add_hline(y=item['fiyat'], line_dash="dash", line_color=item['renk'], line_width=2,
                         annotation_text=f"💀 SHORT {item['kaldirac']}x", annotation_position="top left")
    
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
with st.spinner("1000+ bar geçmiş veri yükleniyor..."):
    
    st.subheader(f"📊 {coin_adi} Canlı Fiyat Takibi")
    
    fiyat_cols = st.columns(len(secili_borsalar))
    anlik_fiyatlar = []
    for idx, borsa_adi in enumerate(secili_borsalar):
        borsa = tum_borsalar[borsa_adi]
        fiyat, degisim = anlik_fiyat_al(borsa, secilen_coin)
        if fiyat:
            anlik_fiyatlar.append(fiyat)
            with fiyat_cols[idx]:
                st.metric(label=f"{borsa_adi}", value=f"${fiyat:,.0f}", delta=f"{degisim:.2f}%" if degisim else None)
    
    ortalama_fiyat = sum(anlik_fiyatlar) / len(anlik_fiyatlar) if anlik_fiyatlar else 0
    
    col1, col2, col3, col4, col5 = st.columns(5)
    with col1: st.metric("💰 Ortalama", f"${ortalama_fiyat:,.0f}")
    with col2: st.metric("⏱️ Zaman", secili_zaman)
    with col3: st.metric("🏛️ Borsa", len(secili_borsalar))
    with col4: st.metric("📊 Bar", "1000+")
    with col5: st.metric("🔄 Yenileme", f"{yenileme_araligi} sn")
    
    st.markdown("---")
    
    # Veri çekme (1000 bar)
    tum_direncler, tum_destekler, ana_df = [], [], None
    
    for borsa_adi, borsa in borsalar.items():
        df = veri_cek(borsa, secilen_coin, tf_kodu, limit=1000)
        if df is not None:
            if ana_df is None: ana_df = df
            if tf_kodu in ['1m','3m','5m']: order_val = 8
            elif tf_kodu in ['15m','30m']: order_val = 10
            elif tf_kodu in ['1h']: order_val = 12
            elif tf_kodu in ['2h','4h']: order_val = 14
            else: order_val = 16
            
            direnc, destek = seviye_bul(df, order=order_val)
            tum_direncler.append(direnc)
            tum_destekler.append(destek)
    
    ortak_direnc, ortak_destek = ortak_seviye_bul_guc_hesapli(tum_direncler, tum_destekler)
    
    if liq_acik and secili_kaldiraclar:
        tasfiye = tasfiye_seviyeleri_hesapla(ortalama_fiyat, secili_kaldiraclar, coin_adi)
    else:
        tasfiye = {'long': [], 'short': []}
    
    # Scalp Sinyalleri
    sinyaller = scalp_sinyalleri_uret(ana_df, ortalama_fiyat, ortak_destek, ortak_direnc)
    
    # ==================== SCALP SİNYALLERİ ====================
    st.subheader("🎯 LONG/SHORT SCALP SİNYALLERİ")
    
    col_signal1, col_signal2, col_signal3 = st.columns(3)
    
    with col_signal1:
        st.markdown("### 📈 LONG SİNYALLERİ")
        if sinyaller['long']:
            for s in sinyaller['long'][:3]:
                renk = "🟢" if s['seviye'] == "Güçlü" else "🟡"
                st.markdown(f"{renk} **{s['seviye']} LONG**")
                st.caption(f"• {s['neden']}")
                if s.get('hedef'):
                    st.caption(f"🎯 Hedef: ${s['hedef']:,.0f}")
                if s.get('zarar_kes'):
                    st.caption(f"🛑 Stop: ${s['zarar_kes']:,.0f}")
                st.markdown("---")
        else:
            st.info("🟡 LONG sinyali yok")
    
    with col_signal2:
        st.markdown("### 📉 SHORT SİNYALLERİ")
        if sinyaller['short']:
            for s in sinyaller['short'][:3]:
                renk = "🔴" if s['seviye'] == "Güçlü" else "🟠"
                st.markdown(f"{renk} **{s['seviye']} SHORT**")
                st.caption(f"• {s['neden']}")
                if s.get('hedef'):
                    st.caption(f"🎯 Hedef: ${s['hedef']:,.0f}")
                if s.get('zarar_kes'):
                    st.caption(f"🛑 Stop: ${s['zarar_kes']:,.0f}")
                st.markdown("---")
        else:
            st.info("🟠 SHORT sinyali yok")
    
    with col_signal3:
        st.markdown("### 📊 PİYASA ANALİZİ")
        if ana_df is not None:
            son_fiyat = ortalama_fiyat
            en_yakin_destek = ortak_destek[0][0] if ortak_destek else None
            en_yakin_direnc = ortak_direnc[0][0] if ortak_direnc else None
            
            st.metric("📍 Güncel Fiyat", f"${son_fiyat:,.0f}")
            if en_yakin_destek:
                st.metric("🟢 En Yakın Destek", f"${en_yakin_destek:,.0f}", delta=f"{(son_fiyat - en_yakin_destek)/son_fiyat*100:.1f}% aşağı")
            if en_yakin_direnc:
                st.metric("🔴 En Yakın Direnç", f"${en_yakin_direnc:,.0f}", delta=f"{(en_yakin_direnc - son_fiyat)/son_fiyat*100:.1f}% yukarı")
    
    st.markdown("---")
    st.subheader("📈 Mum Grafiği (Fare ile kaydır, çift tıkla sıfırla | OK butonu için grafik üzerindeki reset'e tıkla)")
    
    if ana_df is not None:
        fig = grafik_ciz(ana_df, f"{coin_adi}/USDT - {secili_zaman} (1000+ Bar)", ortak_direnc, ortak_destek, tasfiye, ortalama_fiyat, destek_acik, direnc_acik, liq_acik)
        
        config = {
            'scrollZoom': True,
            'doubleClick': 'reset',
            'displayModeBar': True,
            'modeBarButtonsToRemove': ['lasso2d', 'select2d'],
            'displaylogo': False,
            'responsive': True,
            'toImageButtonOptions': {'format': 'png', 'filename': f'{coin_adi}_{secili_zaman}', 'scale': 2}
        }
        
        st.plotly_chart(fig, use_container_width=True, config=config)
        
        # ==================== DESTEK LİSTESİ ====================
        if destek_acik and ortak_destek:
            st.markdown("---")
            st.subheader("🟢 DESTEK SEVİYELERİ (Güçlüden Zayıfa)")
            for seviye, guc in ortak_destek[:10]:
                g_info = GUÇ_RENKLERI.get(guc, GUÇ_RENKLERI[1])
                yuzde = (guc / len(secili_borsalar)) * 100
                st.markdown(f"<div style='border-left: 4px solid {g_info['renk']}; padding-left: 10px; margin: 5px 0;'>"
                           f"<b style='color:{g_info['renk']}'>⬤ ${seviye:,.0f}</b> | {g_info['etiket']} | {guc}/{len(secili_borsalar)} borsa (%{yuzde:.0f})</div>", unsafe_allow_html=True)
        
        if direnc_acik and ortak_direnc:
            st.markdown("---")
            st.subheader("🔴 DİRENÇ SEVİYELERİ (Güçlüden Zayıfa)")
            for seviye, guc in ortak_direnc[:10]:
                g_info = DIRENC_GUÇ_RENKLERI.get(guc, DIRENC_GUÇ_RENKLERI[1])
                yuzde = (guc / len(secili_borsalar)) * 100
                st.markdown(f"<div style='border-left: 4px solid {g_info['renk']}; padding-left: 10px; margin: 5px 0;'>"
                           f"<b style='color:{g_info['renk']}'>⬤ ${seviye:,.0f}</b> | {g_info['etiket']} | {guc}/{len(secili_borsalar)} borsa (%{yuzde:.0f})</div>", unsafe_allow_html=True)
        
        # ==================== TASFİYE LİSTESİ ====================
        if liq_acik and secili_kaldiraclar and (tasfiye['long'] or tasfiye['short']):
            st.markdown("---")
            st.subheader("🔥 LİQUİDATION (TASFİYE) BÖLGELERİ")
            col_l, col_s = st.columns(2)
            with col_l:
                st.markdown("### 📉 LONG TASFİYE")
                for item in tasfiye['long']:
                    st.markdown(f"<div style='border-left: 4px solid {item['renk']}; padding-left: 10px;'>"
                               f"<b style='color:{item['renk']}'>⚡ {item['kaldirac']}x</b> | ${item['fiyat']:,.0f} | ${item['hacim']/1e6:.1f}M</div>", unsafe_allow_html=True)
            with col_s:
                st.markdown("### 📈 SHORT TASFİYE")
                for item in tasfiye['short']:
                    st.markdown(f"<div style='border-left: 4px solid {item['renk']}; padding-left: 10px;'>"
                               f"<b style='color:{item['renk']}'>⚡ {item['kaldirac']}x</b> | ${item['fiyat']:,.0f} | ${item['hacim']/1e6:.1f}M</div>", unsafe_allow_html=True)
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

st.caption("💡 **Özellikler:** 1000+ bar geçmiş | Fare ile kaydırma/yakınlaştırma | OK butonu için çift tık | Long/Short scalp sinyalleri | Güçlüden zayıfa destek/direnç")
