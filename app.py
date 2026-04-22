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
    "UNI/USDT", "AAVE/USDT", "MATIC/USDT", "ARB/USDT", "OP/USDT"
]

# ==================== 4 BORSA ====================
BORSALAR = {
    'Binance': ccxt.binance(),
    'Bybit': ccxt.bybit(),
    'Bitget': ccxt.bitget(),
    'OKX': ccxt.okx()
}

# ==================== BAŞLIK ====================
st.title("📈 TRADINGVIEW TARZI DASHBOARD")
st.caption("Binance + Bybit + Bitget + OKX | Sadece Güçlü Dirençler")

# ==================== KENAR ÇUBUĞU ====================
with st.sidebar:
    st.header("⚙️ AYARLAR")
    
    secilen_coin = st.selectbox("Coin seç:", coin_listesi, index=0)
    coin_adi = secilen_coin.split("/")[0]
    
    st.markdown("---")
    
    zaman_dilimleri = {
        "1 Dakika": "1m", "5 Dakika": "5m", "15 Dakika": "15m",
        "30 Dakika": "30m", "1 Saat": "1h", "4 Saat": "4h",
        "1 Gün": "1d", "1 Hafta": "1w"
    }
    
    secili_zaman = st.selectbox("Zaman dilimi:", list(zaman_dilimleri.keys()), index=4)
    tf_kodu = zaman_dilimleri[secili_zaman]
    
    st.markdown("---")
    
    # Sadece direnç seçeneği
    st.subheader("📊 Gösterge")
    sadece_direnc = st.checkbox("🔴 Sadece Güçlü Dirençleri Göster", value=True)
    
    if sadece_direnc:
        st.info("3 veya 4 borsada ortak olan dirençler gösterilir")
    
    st.markdown("---")
    
    yenileme_araligi = st.select_slider("Yenileme sıklığı:", options=[10, 15, 30, 60], value=15)
    
    if st.button("🔄 Yenile", use_container_width=True):
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

def direnc_bul(df, order=10, yuvarla=50):
    """Sadece direnç seviyelerini bulur (tepe noktaları)"""
    if df is None or len(df) < 20:
        return []
    
    # Fiyata göre yuvarlama
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
    direncler = [round(df['yuksek'].iloc[t] / yuvarla) * yuvarla for t in tepeler]
    return list(set(direncler))

def ortak_direnc_bul(tum_direncler, min_guc=3):
    """En az min_guc borsada görülen dirençleri bul"""
    direnc_sayac = Counter()
    for alt_liste in tum_direncler:
        for item in alt_liste:
            direnc_sayac[item] += 1
    
    # Sadece min_guc (3) ve üzeri
    ortak_direnc = [(seviye, sayi) for seviye, sayi in direnc_sayac.items() if sayi >= min_guc]
    ortak_direnc.sort(key=lambda x: x[1], reverse=True)
    
    return ortak_direnc

def grafik_ciz_tradingview(df, baslik, direncler, guncel_fiyat):
    """TradingView tarzı grafik çizer"""
    if df is None or len(df) == 0:
        fig = go.Figure()
        fig.add_annotation(text="Veri alınamadı", showarrow=False)
        return fig
    
    fig = go.Figure()
    
    # Mum grafiği (TradingView tarzı)
    fig.add_trace(go.Candlestick(
        x=df.index,
        open=df['acilis'],
        high=df['yuksek'],
        low=df['dusuk'],
        close=df['kapanis'],
        name='Fiyat',
        line=dict(width=1),
        opacity=1
    ))
    
    # Direnç çizgileri (sadece güçlü olanlar)
    for seviye, guc in direncler:
        if guc == 4:
            renk = '#FF0000'  # Koyu kırmızı
            kalinlik = 3
            etiket = f'🔴 ÇOK GÜÇLÜ DİRENÇ {seviye:.2f}'
        else:
            renk = '#FF6666'  # Açık kırmızı
            kalinlik = 2
            etiket = f'🟠 GÜÇLÜ DİRENÇ {seviye:.2f}'
        
        fig.add_hline(
            y=seviye, 
            line_dash="solid", 
            line_color=renk, 
            line_width=kalinlik,
            annotation_text=etiket, 
            annotation_position="top right",
            annotation_font_size=10
        )
    
    # Güncel fiyat çizgisi
    fig.add_hline(
        y=guncel_fiyat, 
        line_dash="dot", 
        line_color="white", 
        line_width=1.5,
        annotation_text=f"📍 GÜNCEL {guncel_fiyat:.2f}", 
        annotation_position="top left"
    )
    
    # TradingView tarzı layout
    fig.update_layout(
        height=650,
        title=dict(
            text=f"<b>{baslik}</b><br><sub style='font-size:12px'>🔴 Koyu kırmızı = 4/4 borsa | 🟠 Açık kırmızı = 3/4 borsa</sub>",
            x=0.5,
            xanchor='center'
        ),
        template="plotly_dark",
        xaxis=dict(
            title="Zaman",
            showgrid=True,
            gridcolor='#2a2a2a',
            showline=True,
            linecolor='#444',
            mirror=True
        ),
        yaxis=dict(
            title="Fiyat (USDT)",
            showgrid=True,
            gridcolor='#2a2a2a',
            showline=True,
            linecolor='#444',
            mirror=True,
            side='right'
        ),
        paper_bgcolor='#131722',
        plot_bgcolor='#131722',
        xaxis_rangeslider_visible=False,
        dragmode='zoom',
        hovermode='x unified',
        font=dict(family='Arial', size=12),
        legend=dict(
            orientation='h',
            yanchor='bottom',
            y=1.02,
            xanchor='right',
            x=1
        )
    )
    
    # Grid ayarları
    fig.update_xaxes(showspikes=True, spikecolor='white', spikethickness=1)
    fig.update_yaxes(showspikes=True, spikecolor='white', spikethickness=1)
    
    return fig

# ==================== ANA İŞLEM ====================
with st.spinner(f"📊 {coin_adi} verileri yükleniyor..."):
    
    # Canlı fiyatlar
    st.subheader(f"💰 {coin_adi} Canlı Fiyat")
    
    fiyat_cols = st.columns(4)
    anlik_fiyatlar = []
    for idx, (borsa_adi, borsa) in enumerate(BORSALAR.items()):
        fiyat, degisim = anlik_fiyat_al(borsa, secilen_coin)
        if fiyat:
            anlik_fiyatlar.append(fiyat)
            with fiyat_cols[idx]:
                st.metric(
                    label=f"{borsa_adi}", 
                    value=f"${fiyat:,.2f}" if fiyat > 1 else f"${fiyat:,.4f}",
                    delta=f"{degisim:.2f}%" if degisim else None,
                    delta_color="normal"
                )
    
    ortalama_fiyat = sum(anlik_fiyatlar) / len(anlik_fiyatlar) if anlik_fiyatlar else 0
    
    # Bilgi kartları
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("📊 Ortalama Fiyat", f"${ortalama_fiyat:,.2f}" if ortalama_fiyat > 1 else f"${ortalama_fiyat:,.4f}")
    with col2:
        st.metric("⏱️ Zaman", secili_zaman)
    with col3:
        st.metric("🏛️ Borsa", "4 (Binance, Bybit, Bitget, OKX)")
    with col4:
        st.metric("🔄 Yenileme", f"{yenileme_araligi} sn")
    
    st.markdown("---")
    
    # Veri çekme
    tum_direncler = []
    ana_df = None
    
    for borsa_adi, borsa in BORSALAR.items():
        df = veri_cek(borsa, secilen_coin, tf_kodu, limit=500)
        if df is not None:
            if ana_df is None:
                ana_df = df
            
            # Zaman dilimine göre order değeri
            if tf_kodu in ['1m', '5m']:
                order_val = 8
            elif tf_kodu in ['15m', '30m']:
                order_val = 10
            elif tf_kodu in ['1h']:
                order_val = 12
            elif tf_kodu in ['4h']:
                order_val = 14
            else:
                order_val = 16
            
            direncler = direnc_bul(df, order=order_val)
            tum_direncler.append(direncler)
    
    # Ortak dirençleri bul (en az 3 borsa)
    ortak_direncler = ortak_direnc_bul(tum_direncler, min_guc=3)
    
    if ana_df is not None:
        # Grafik başlığı
        grafik_baslik = f"{coin_adi}/USDT - {secili_zaman}"
        
        # Grafik çiz
        fig = grafik_ciz_tradingview(ana_df, grafik_baslik, ortak_direncler, ortalama_fiyat)
        
        config = {
            'scrollZoom': True,
            'doubleClick': 'reset',
            'displayModeBar': True,
            'modeBarButtonsToRemove': ['lasso2d', 'select2d', 'zoomIn2d', 'zoomOut2d'],
            'displaylogo': False,
            'responsive': True
        }
        
        st.plotly_chart(fig, use_container_width=True, config=config)
        
        # ==================== DİRENÇ LİSTESİ ====================
        if ortak_direncler:
            st.markdown("---")
            st.subheader("🔴 GÜÇLÜ DİRENÇ SEVİYELERİ (3+ Borsa)")
            st.caption("Bu seviyelerde fiyatın takılma veya dönme ihtimali YÜKSEK")
            
            for seviye, guc in ortak_direncler[:10]:
                if guc == 4:
                    renk = '#FF0000'
                    emoji = '🔥'
                    aciklama = 'ÇOK GÜÇLÜ - 4/4 Borsa'
                else:
                    renk = '#FF6666'
                    emoji = '✅'
                    aciklama = 'GÜÇLÜ - 3/4 Borsa'
                
                fiyat_gosterim = f"{seviye:,.2f}" if seviye > 1 else f"{seviye:,.4f}"
                st.markdown(
                    f"<div style='border-left: 4px solid {renk}; padding-left: 10px; margin: 8px 0;'>"
                    f"<b style='color:{renk}'>{emoji} ${fiyat_gosterim}</b><br>"
                    f"<span style='font-size:12px'>{aciklama}</span>"
                    f"</div>", 
                    unsafe_allow_html=True
                )
        else:
            st.info("🔍 Henüz 3+ borsada ortak direnç seviyesi bulunamadı")
    else:
        st.error("❌ Veri alınamadı. Lütfen farklı zaman dilimi seçin.")

# ==================== OTOMATİK YENİLEME ====================
if 'son_yenileme' not in st.session_state:
    st.session_state.son_yenileme = time.time()

gecen_sure = time.time() - st.session_state.son_yenileme
if gecen_sure > yenileme_araligi:
    st.session_state.son_yenileme = time.time()
    st.rerun()
else:
    st.info(f"🔄 {int(yenileme_araligi - gecen_sure)} saniye içinde otomatik yenilenecek...")

st.caption("💡 **TradingView Özellikleri:** Fare ile yakınlaştırma/kaydırma | Çift tıkla sıfırla | Sadece güçlü dirençler (3+ borsa)")
