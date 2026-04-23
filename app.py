import streamlit as st
import ccxt
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from scipy.signal import argrelextrema
from datetime import datetime, timedelta
from collections import Counter
import time
import json
import os

st.set_page_config(page_title="TradingView Tarzı Dashboard", layout="wide")

# ==================== COİN LİSTESİ (SADECE SCALP COİNLER) ====================
coin_listesi = [
    "BTC/USDT", "ETH/USDT", "SOL/USDT", "ZEC/USDT", "APT/USDT", "SUI/USDT"
]

# ==================== 4 BORSA ====================
BORSALAR = {
    'Binance': ccxt.binance(),
    'Bybit': ccxt.bybit(),
    'Bitget': ccxt.bitget(),
    'OKX': ccxt.okx()
}

# ==================== SCALP KAYITLARI İÇİN JSON DOSYASI ====================
SCALP_DOSYASI = "scalp_kayitlari.json"

def scalp_kayitlarini_yukle():
    """Geçmiş scalp sinyallerini yükler"""
    try:
        if os.path.exists(SCALP_DOSYASI):
            with open(SCALP_DOSYASI, 'r') as f:
                return json.load(f)
        else:
            return {}
    except:
        return {}

def scalp_kaydet(coin_adi, sinyal):
    """Yeni scalp sinyalini kaydeder"""
    kayitlar = scalp_kayitlarini_yukle()
    
    if coin_adi not in kayitlar:
        kayitlar[coin_adi] = []
    
    sinyal['timestamp'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    kayitlar[coin_adi].append(sinyal)
    
    # Son 100 kaydı tut
    if len(kayitlar[coin_adi]) > 100:
        kayitlar[coin_adi] = kayitlar[coin_adi][-100:]
    
    try:
        with open(SCALP_DOSYASI, 'w') as f:
            json.dump(kayitlar, f, indent=2)
    except:
        pass

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
st.caption("Binance + Bybit + Bitget + OKX | Destek/Direnç | Liquidation | SCALP SİNYALLERİ (Kayıtlı)")

# ==================== KENAR ÇUBUĞU ====================
with st.sidebar:
    st.header("⚙️ AYARLAR")
    
    secilen_coin = st.selectbox("💰 Coin seç:", coin_listesi, index=0)
    coin_adi = secilen_coin.split("/")[0]
    
    st.markdown("---")
    
    zaman_dilimleri = {
        "1 Dakika": "1m", "5 Dakika": "5m", "15 Dakika": "15m",
        "30 Dakika": "30m", "1 Saat": "1h", "2 Saat": "2h",
        "4 Saat": "4h", "1 Gün": "1d", "1 Hafta": "1w"
    }
    
    secili_zaman = st.selectbox("⏱️ Zaman dilimi:", list(zaman_dilimleri.keys()), index=3)
    tf_kodu = zaman_dilimleri[secili_zaman]
    
    st.markdown("---")
    
    # Göstergeler
    st.subheader("📊 Göstergeler")
    destek_acik = st.checkbox("🟢 Destek Çizgileri", value=True)
    direnc_acik = st.checkbox("🔴 Direnç Çizgileri", value=True)
    scalp_goster = st.checkbox("🎯 Scalp Sinyallerini Göster", value=True)
    
    st.markdown("---")
    
    # Liquidation
    st.subheader("🔥 Liquidation Haritası")
    liq_acik = st.checkbox("Liquidation Haritasını Göster", value=True)
    
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
    
    yenileme_araligi = st.select_slider("🔄 Yenileme sıklığı:", options=[15, 30, 60, 120], value=30)
    
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
    base_oi = {"BTC": 15000000000, "ETH": 8000000000, "SOL": 2000000000}
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

def scalp_sinyali_uret(df, guncel_fiyat, destekler, direncler, coin_adi):
    """Yeni scalp sinyali üretir ve kaydeder"""
    sinyal = None
    
    if df is None or len(df) < 20:
        return sinyal
    
    son_kapanis = df['kapanis'].iloc[-1]
    onceki_kapanis = df['kapanis'].iloc[-2]
    son_yuksek = df['yuksek'].iloc[-1]
    son_dusuk = df['dusuk'].iloc[-1]
    
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
    
    nearest_lq_upper = en_yakin_direnc if en_yakin_direnc else guncel_fiyat * 1.05
    nearest_lq_lower = en_yakin_destek if en_yakin_destek else guncel_fiyat * 0.95
    
    # LONG SİNYALİ
    if mesafe_destek < 1.5 and en_yakin_destek and son_kapanis > onceki_kapanis:
        sinyal = {
            'tip': 'LONG',
            'fiyat': guncel_fiyat,
            'hedef': en_yakin_direnc if en_yakin_direnc else guncel_fiyat * 1.02,
            'zarar_kes': en_yakin_destek - (guncel_fiyat * 0.005),
            'nearest_lq_upper': nearest_lq_upper,
            'nearest_lq_lower': nearest_lq_lower,
            'up_distance': round((nearest_lq_upper - guncel_fiyat) / guncel_fiyat * 100, 2),
            'dn_distance': round((guncel_fiyat - nearest_lq_lower) / guncel_fiyat * 100, 2),
            'destek': en_yakin_destek,
            'direnc': en_yakin_direnc
        }
    
    # SHORT SİNYALİ
    elif mesafe_direnc < 1.5 and en_yakin_direnc and son_kapanis < onceki_kapanis:
        sinyal = {
            'tip': 'SHORT',
            'fiyat': guncel_fiyat,
            'hedef': en_yakin_destek if en_yakin_destek else guncel_fiyat * 0.98,
            'zarar_kes': en_yakin_direnc + (guncel_fiyat * 0.005),
            'nearest_lq_upper': nearest_lq_upper,
            'nearest_lq_lower': nearest_lq_lower,
            'up_distance': round((nearest_lq_upper - guncel_fiyat) / guncel_fiyat * 100, 2),
            'dn_distance': round((guncel_fiyat - nearest_lq_lower) / guncel_fiyat * 100, 2),
            'destek': en_yakin_destek,
            'direnc': en_yakin_direnc
        }
    
    return sinyal

def grafik_ciz(df, baslik, direncler, destekler, tasfiye, guncel_fiyat, destek_acik, direnc_acik, liq_acik, scalp_sinyalleri, coin_adi):
    if df is None or len(df) == 0:
        fig = go.Figure()
        return fig
    
    fig = go.Figure()
    
    # Mum grafiği
    fig.add_trace(go.Candlestick(
        x=df.index, open=df['acilis'], high=df['yuksek'],
        low=df['dusuk'], close=df['kapanis'], name='Fiyat'
    ))
    
    # Destekler
    if destek_acik:
        for seviye, guc in destekler:
            renk = GUCLU_RENKLER.get(guc, GUCLU_RENKLER[3])['renk']
            kalinlik = GUCLU_RENKLER.get(guc, GUCLU_RENKLER[3])['kalınlık']
            etiket = GUCLU_RENKLER.get(guc, GUCLU_RENKLER[3])['etiket']
            fig.add_hline(y=seviye, line_dash="solid", line_color=renk, line_width=kalinlik,
                         annotation_text=f"🟢 {etiket} {seviye:.2f}", annotation_position="top right")
    
    # Dirençler
    if direnc_acik:
        for seviye, guc in direncler:
            renk = GUCLU_DIRENC_RENKLER.get(guc, GUCLU_DIRENC_RENKLER[3])['renk']
            kalinlik = GUCLU_DIRENC_RENKLER.get(guc, GUCLU_DIRENC_RENKLER[3])['kalınlık']
            etiket = GUCLU_DIRENC_RENKLER.get(guc, GUCLU_DIRENC_RENKLER[3])['etiket']
            fig.add_hline(y=seviye, line_dash="solid", line_color=renk, line_width=kalinlik,
                         annotation_text=f"🔴 {etiket} {seviye:.2f}", annotation_position="top right")
    
    # Liquidation
    if liq_acik:
        for item in tasfiye.get('long', []):
            fig.add_hline(y=item['fiyat'], line_dash="dash", line_color=item['renk'], line_width=2,
                         annotation_text=f"🔥 LONG {item['kaldirac']}x", annotation_position="bottom left")
        for item in tasfiye.get('short', []):
            fig.add_hline(y=item['fiyat'], line_dash="dash", line_color=item['renk'], line_width=2,
                         annotation_text=f"💀 SHORT {item['kaldirac']}x", annotation_position="top left")
    
    # GEÇMİŞ SCALP SİNYALLERİ (grafik üzerinde etiket olarak)
    if coin_adi in scalp_sinyalleri:
        for sinyal in scalp_sinyalleri[coin_adi][-20:]:  # Son 20 sinyal
            try:
                sinyal_fiyat = sinyal.get('fiyat', 0)
                sinyal_tip = sinyal.get('tip', '')
                sinyal_zaman = sinyal.get('timestamp', '')
                
                if sinyal_tip == 'LONG':
                    renk = '#00FF00'
                    sembol = '▲'
                else:
                    renk = '#FF0000'
                    sembol = '▼'
                
                # Grafikte nokta ve etiket
                fig.add_annotation(
                    x=df.index[-1],
                    y=sinyal_fiyat,
                    text=f"{sembol} {sinyal_tip} @ {sinyal_fiyat:.0f}",
                    showarrow=True,
                    arrowhead=2,
                    arrowsize=1,
                    arrowwidth=2,
                    arrowcolor=renk,
                    ax=20,
                    ay=(-30 if sinyal_tip == 'LONG' else 30),
                    bgcolor='rgba(0,0,0,0.7)',
                    font=dict(color=renk, size=10)
                )
            except:
                pass
    
    # Güncel fiyat
    fig.add_hline(y=guncel_fiyat, line_dash="dot", line_color="white", line_width=1.5,
                 annotation_text=f"📍 GÜNCEL {guncel_fiyat:.2f}", annotation_position="top left")
    
    fig.update_layout(
        height=700,
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

# ==================== ANA İŞLEM ====================

# Geçmiş scalp sinyallerini yükle
scalp_kayitlari = scalp_kayitlarini_yukle()

# Canlı fiyatlar
st.subheader(f"💰 {coin_adi} CANLI FİYAT")

son_fiyatlar = {}
for borsa_adi, borsa in BORSALAR.items():
    fiyat, degisim = anlik_fiyat_al(borsa, secilen_coin)
    if fiyat:
        son_fiyatlar[borsa_adi] = {'fiyat': fiyat, 'degisim': degisim}

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
with col4: st.metric("🔄 Yenileme", f"{yenileme_araligi} sn")

st.markdown("---")

# ==================== VERİ ÇEKME ====================
with st.spinner(f"📊 {coin_adi} verileri yükleniyor..."):
    tum_direncler, tum_destekler, ana_df = [], [], None
    
    for borsa_adi, borsa in BORSALAR.items():
        df = veri_cek(borsa, secilen_coin, tf_kodu, limit=500)
        if df is not None and len(df) > 0:
            if ana_df is None:
                ana_df = df
            
            if tf_kodu in ['1m', '5m']:
                order_val = 8
            elif tf_kodu in ['15m', '30m']:
                order_val = 10
            elif tf_kodu in ['1h']:
                order_val = 12
            else:
                order_val = 14
            
            direnc, destek = seviye_bul(df, order=order_val)
            tum_direncler.append(direnc)
            tum_destekler.append(destek)
    
    ortak_direnc, ortak_destek = ortak_seviye_bul(tum_direncler, tum_destekler, min_guc=3)
    
    if liq_acik and secili_kaldiraclar:
        tasfiye = tasfiye_hesapla(ortalama_fiyat, secili_kaldiraclar, coin_adi)
    else:
        tasfiye = {'long': [], 'short': []}
    
    # YENİ SCALP SİNYALİ ÜRET (sadece seçili coinler için)
    yeni_sinyal = None
    if scalp_goster and ana_df is not None:
        yeni_sinyal = scalp_sinyali_uret(ana_df, ortalama_fiyat, ortak_destek, ortak_direnc, coin_adi)
        
        if yeni_sinyal:
            # Daha önce aynı sinyal kaydedilmemiş mi kontrol et
            kayitlar = scalp_kayitlari.get(coin_adi, [])
            son_sinyal = kayitlar[-1] if kayitlar else None
            
            if not son_sinyal or abs(son_sinyal.get('fiyat', 0) - yeni_sinyal['fiyat']) > ortalama_fiyat * 0.005:
                scalp_kaydet(coin_adi, yeni_sinyal)
                scalp_kayitlari = scalp_kayitlarini_yukle()
                st.success(f"🎯 YENİ {yeni_sinyal['tip']} SCALP SİNYALİ! Fiyat: ${yeni_sinyal['fiyat']:,.2f}")
                time.sleep(2)
                st.rerun()

# ==================== GRAFİK ====================
st.subheader("📈 Mum Grafiği - Fare ile kaydır, çift tıkla sıfırla")

if ana_df is not None and len(ana_df) > 0:
    fig = grafik_ciz(ana_df, f"{coin_adi}/USDT - {secili_zaman}", ortak_direnc, ortak_destek, tasfiye, ortalama_fiyat, destek_acik, direnc_acik, liq_acik, scalp_kayitlari, coin_adi)
    
    config = {'scrollZoom': True, 'doubleClick': 'reset', 'displayModeBar': True, 'displaylogo': False, 'responsive': True}
    st.plotly_chart(fig, use_container_width=True, config=config)
    
    # ==================== GÜNCEL SCALP SİNYALİ (RESİMDEKİ GİBİ) ====================
    if yeni_sinyal:
        st.markdown("---")
        st.subheader(f"🎯 GÜNCEL {yeni_sinyal['tip']} SCALP SİNYALİ")
        
        col_a, col_b, col_c = st.columns(3)
        
        with col_a:
            st.metric("📍 Giriş Fiyatı", f"${yeni_sinyal['fiyat']:,.2f}")
            st.metric("🎯 Hedef", f"${yeni_sinyal['hedef']:,.2f}")
            st.metric("🛑 Stop Loss", f"${yeni_sinyal['zarar_kes']:,.2f}")
        
        with col_b:
            st.metric("📊 Nearest LQ Upper", f"${yeni_sinyal['nearest_lq_upper']:,.2f}")
            st.metric("📊 Nearest LQ Lower", f"${yeni_sinyal['nearest_lq_lower']:,.2f}")
        
        with col_c:
            st.metric("⬆️ Up Distance", f"%{yeni_sinyal['up_distance']}")
            st.metric("⬇️ Dn Distance", f"%{yeni_sinyal['dn_distance']}")
            st.metric("🟢 Destek", f"${yeni_sinyal['destek']:,.2f}" if yeni_sinyal['destek'] else "-")
            st.metric("🔴 Direnç", f"${yeni_sinyal['direnc']:,.2f}" if yeni_sinyal['direnc'] else "-")
    
    # ==================== GEÇMİŞ SCALP SİNYALLERİ LİSTESİ ====================
    if scalp_goster and coin_adi in scalp_kayitlari and scalp_kayitlari[coin_adi]:
        st.markdown("---")
        st.subheader(f"📜 GEÇMİŞ {coin_adi} SCALP SİNYALLERİ")
        
        for sinyal in reversed(scalp_kayitlari[coin_adi][-20:]):
            if sinyal['tip'] == 'LONG':
                renk = "🟢"
            else:
                renk = "🔴"
            
            st.markdown(f"""
            <div style='border-left: 4px solid {'#00FF00' if sinyal['tip'] == 'LONG' else '#FF0000'}; padding: 8px; margin: 5px 0; border-radius: 5px;'>
            <b>{renk} {sinyal['tip']} SCALP</b> | 🕐 {sinyal['timestamp']}<br>
            📍 Fiyat: <b>${sinyal['fiyat']:,.2f}</b> | 🎯 Hedef: <b>${sinyal['hedef']:,.2f}</b> | 🛑 Stop: <b>${sinyal['zarar_kes']:,.2f}</b><br>
            📊 Nearest LQ: ↑${sinyal['nearest_lq_upper']:,.0f} (↑{sinyal['up_distance']}%) | ↓${sinyal['nearest_lq_lower']:,.0f} (↓{sinyal['dn_distance']}%)
            </div>
            """, unsafe_allow_html=True)
    
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
    st.error(f"❌ {secili_zaman} için veri alınamadı.")

# ==================== OTOMATİK YENİLEME ====================
if 'son_yenileme' not in st.session_state:
    st.session_state.son_yenileme = time.time()

gecen_sure = time.time() - st.session_state.son_yenileme
if gecen_sure > yenileme_araligi:
    st.session_state.son_yenileme = time.time()
    st.rerun()
else:
    st.info(f"🔄 Grafik {int(yenileme_araligi - gecen_sure)} saniye içinde yenilenecek...")

st.caption("💡 **Scalp Sinyalleri:** Destek/Direnç yakınlığına göre otomatik üretilir | Geçmiş sinyaller kaydedilir | Grafik üzerinde etiket olarak görünür")
