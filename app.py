import asyncio
import ccxt.pro as ccxt_pro  # WebSocket destekli ccxt
import pandas as pd
import numpy as np
import time
import requests
import json
from collections import deque
from datetime import datetime
from scipy.signal import argrelextrema
import talib  # ekstra göstergeler için
import warnings
warnings.filterwarnings("ignore")

# ==================== TELEGRAM ====================
TELEGRAM_TOKEN = "8621122847:AAFvkF1gvqogowpt8UvkBTTRItUuGUVpd5g"
TELEGRAM_CHAT_ID = "6514368425"

def send_telegram(message):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "HTML"}
        requests.post(url, json=payload, timeout=3)
    except:
        pass

# ==================== COINGLASS (LİQUIDATION HEATMAP) ====================
# Ücretsiz API key alınacak: https://coinglass.com/api
COINGLASS_API_KEY = "YOUR_COINGLASS_API_KEY_HERE"

async def get_liquidation_heatmap(symbol="BTC"):
    url = f"https://open-api.coinglass.com/api/pro/v1/liquidationHeatMap?symbol={symbol}&timeType=1h"
    headers = {"coinglassSecret": COINGLASS_API_KEY}
    try:
        resp = requests.get(url, headers=headers, timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            # Dönen veri: long & short likidite seviyeleri ve miktarları
            return data.get("data", {})
    except:
        pass
    return {}

# ==================== BORSA VERİLERİ (WEBSOCKET) ====================
class ExchangeData:
    def __init__(self, exchange_name, symbol):
        self.exchange_name = exchange_name
        self.symbol = symbol
        if exchange_name == "binance":
            self.ex = ccxt_pro.binance()
        elif exchange_name == "bybit":
            self.ex = ccxt_pro.bybit()
        else:
            raise ValueError("Only binance and bybit supported")
        
        self.orderbook = None
        self.trades = deque(maxlen=1000)
        self.cvd = 0
        self.last_price = None
        self.oi = None
        self.funding_rate = None
        
    async def watch_orderbook(self):
        while True:
            try:
                ob = await self.ex.watch_order_book(self.symbol, limit=20)
                self.orderbook = ob
            except Exception as e:
                print(f"{self.exchange_name} orderbook error: {e}")
                await asyncio.sleep(1)
    
    async def watch_trades(self):
        while True:
            try:
                trades = await self.ex.watch_trades(self.symbol)
                for t in trades:
                    self.trades.append(t)
                    # Cumulative Volume Delta (CVD) hesapla
                    amount = t['amount']
                    if t['side'] == 'buy':
                        self.cvd += amount
                    else:
                        self.cvd -= amount
                    self.last_price = t['price']
            except Exception as e:
                print(f"{self.exchange_name} trades error: {e}")
                await asyncio.sleep(1)
    
    async def fetch_oi_funding(self):
        """Her dakika OI ve funding rate al"""
        while True:
            try:
                # Open Interest
                oi_data = await self.ex.fetch_open_interest(self.symbol)
                if oi_data:
                    self.oi = oi_data['openInterest']
                # Funding rate
                ticker = await self.ex.fetch_ticker(self.symbol)
                self.funding_rate = ticker.get('fundingRate', None)
                await asyncio.sleep(60)
            except:
                await asyncio.sleep(60)
    
    def get_orderbook_imbalance(self):
        if not self.orderbook:
            return 0
        bids_vol = sum([bid[1] for bid in self.orderbook['bids'][:10]])
        asks_vol = sum([ask[1] for ask in self.orderbook['asks'][:10]])
        if asks_vol == 0:
            return 1
        return bids_vol / asks_vol  # >1 alıcı baskın
    
    def get_cvd_trend(self, window=20):
        if len(self.trades) < window:
            return 0
        cvd_list = [self.trades[i]['price'] * self.trades[i]['amount'] for i in range(len(self.trades))]
        # basit: son 20 tick'in CVD eğimi
        return np.polyfit(range(window), cvd_list[-window:], 1)[0]

# ==================== OHLCV VE TEKNİK GÖSTERGELER ====================
async def fetch_ohlcv(exchange, symbol, timeframe='1h', limit=200):
    try:
        bars = await exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
        df = pd.DataFrame(bars, columns=['timestamp','open','high','low','close','volume'])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        df.set_index('timestamp', inplace=True)
        return df
    except:
        return None

def calculate_indicators(df):
    if df is None or len(df) < 50:
        return {}
    close = df['close'].values
    high = df['high'].values
    low = df['low'].values
    volume = df['volume'].values
    
    rsi = talib.RSI(close, timeperiod=14)
    macd, macd_signal, macd_hist = talib.MACD(close)
    adx = talib.ADX(high, low, close, timeperiod=14)
    ema9 = talib.EMA(close, timeperiod=9)
    ema21 = talib.EMA(close, timeperiod=21)
    bb_upper, bb_middle, bb_lower = talib.BBANDS(close, timeperiod=20, nbdevup=2, nbdevdn=2)
    atr = talib.ATR(high, low, close, timeperiod=14)
    
    # Trend gücü
    ema_cross = 1 if ema9[-1] > ema21[-1] else -1
    trend_strength = "UP" if ema_cross == 1 else "DOWN"
    adx_val = adx[-1] if not np.isnan(adx[-1]) else 20
    
    return {
        "rsi": rsi[-1],
        "macd_hist": macd_hist[-1],
        "adx": adx_val,
        "trend": trend_strength,
        "bb_position": (close[-1] - bb_lower[-1]) / (bb_upper[-1] - bb_lower[-1]) if (bb_upper[-1] - bb_lower[-1]) != 0 else 0.5,
        "atr": atr[-1],
        "volume_surge": volume[-1] > np.mean(volume[-20:]) * 1.5
    }

# ==================== KARAR VERİCİ (Sadece net sinyal) ====================
def decision(binance_data, bybit_data, liq_map, hourly_indicators):
    long_score = 0
    short_score = 0
    
    # 1. Order Book dengesi (ikisini de kullan)
    ob_imbalance = (binance_data.get_orderbook_imbalance() + bybit_data.get_orderbook_imbalance()) / 2
    if ob_imbalance > 1.2:
        long_score += 25
    elif ob_imbalance < 0.8:
        short_score += 25
    
    # 2. CVD trend
    cvd_trend = (binance_data.get_cvd_trend() + bybit_data.get_cvd_trend()) / 2
    if cvd_trend > 0:
        long_score += 20
    elif cvd_trend < 0:
        short_score += 20
    
    # 3. OI ve funding
    oi_binance = binance_data.oi if binance_data.oi else 0
    oi_bybit = bybit_data.oi if bybit_data.oi else 0
    oi_avg = (oi_binance + oi_bybit) / 2 if oi_binance and oi_bybit else None
    # OI artış eğilimi (bir önceki değere göre) - burada basitçe son 1 saat karşılaştırma yapılabilir, şimdilik pasif
    
    funding_avg = (binance_data.funding_rate if binance_data.funding_rate else 0) + (bybit_data.funding_rate if bybit_data.funding_rate else 0) / 2
    if funding_avg < -0.005:  # aşırı negatif = long sinyali
        long_score += 15
    elif funding_avg > 0.005:  # aşırı pozitif = short sinyali
        short_score += 15
    
    # 4. Liquidation heatmap (Coinglass)
    if liq_map:
        # long_liquidation seviyeleri (fiyatın altında) yoğunsa => aşağı çekilme riski yüksek (short sinyali)
        # short_liquidation seviyeleri (fiyatın üstünde) yoğunsa => yukarı çekilme (long sinyali)
        # Burada basitçe en yakın yoğun bölgeyi kullan, daha karmaşık yapılabilir
        # Şimdilik geçici: eğer harita varsa long_score ve short_score'a simetrik ekleme yapmayalım, ileride detaylandırırız
        long_score += 5
        short_score += 5
    
    # 5. Teknik göstergeler (hourly)
    if hourly_indicators:
        rsi = hourly_indicators.get('rsi', 50)
        if rsi < 35:
            long_score += 15
        elif rsi > 65:
            short_score += 15
        
        macd_hist = hourly_indicators.get('macd_hist', 0)
        if macd_hist > 0:
            long_score += 15
        elif macd_hist < 0:
            short_score += 15
        
        trend = hourly_indicators.get('trend', 'UP')
        if trend == 'UP':
            long_score += 20
        else:
            short_score += 20
        
        if hourly_indicators.get('volume_surge', False):
            if trend == 'UP':
                long_score += 10
            else:
                short_score += 10
    
    # 6. Fiyat pozisyonu (Bollinger bandı)
    bb_pos = hourly_indicators.get('bb_position', 0.5)
    if bb_pos < 0.2:
        long_score += 10
    elif bb_pos > 0.8:
        short_score += 10
    
    # Net karar: sadece bir yön net önde ise sinyal ver
    diff = long_score - short_score
    if diff > 30:
        return "LONG", long_score, short_score
    elif diff < -30:
        return "SHORT", long_score, short_score
    else:
        return None, long_score, short_score

# ==================== ANA DÖNGÜ ====================
async def main():
    symbol = "BTC/USDT"
    # Initialize exchange data objects
    binance = ExchangeData("binance", symbol)
    bybit = ExchangeData("bybit", symbol)
    
    # WebSocket tasks
    tasks = [
        asyncio.create_task(binance.watch_orderbook()),
        asyncio.create_task(binance.watch_trades()),
        asyncio.create_task(binance.fetch_oi_funding()),
        asyncio.create_task(bybit.watch_orderbook()),
        asyncio.create_task(bybit.watch_trades()),
        asyncio.create_task(bybit.fetch_oi_funding())
    ]
    
    # OHLCV için ayrı bir async döngü (1 saatlik mumları çek)
    async def update_ohlcv():
        binance_rest = ccxt_pro.binance()
        while True:
            df = await fetch_ohlcv(binance_rest, symbol, '1h', 200)
            if df is not None:
                globals()['ohlcv_df'] = df
            await asyncio.sleep(60)  # Her dakika güncelle
    
    tasks.append(asyncio.create_task(update_ohlcv()))
    
    # Liquidation heatmap güncelleme (her 5 dakika)
    async def update_liq():
        while True:
            globals()['liq_map'] = await get_liquidation_heatmap("BTC")
            await asyncio.sleep(300)
    tasks.append(asyncio.create_task(update_liq()))
    
    # Ana karar döngüsü (30 saniyede bir)
    sent_signals = set()
    while True:
        await asyncio.sleep(30)
        df = globals().get('ohlcv_df')
        if df is None:
            continue
        indicators = calculate_indicators(df)
        liq_map = globals().get('liq_map', {})
        signal, long_score, short_score = decision(binance, bybit, liq_map, indicators)
        if signal:
            signal_id = f"{signal}_{datetime.now().strftime('%Y%m%d%H%M')}"
            if signal_id not in sent_signals:
                sent_signals.add(signal_id)
                # Telegram mesajı
                msg = f"🚨 <b>NET SİNYAL</b> 🚨\n\n<b>{signal}</b> BTC\n📊 Long Score: {long_score}\n📊 Short Score: {short_score}\n⏰ {datetime.now().strftime('%H:%M:%S')}"
                send_telegram(msg)
                print(f"Sinyal gönderildi: {signal}")
        # sent_signals temizliği (çok büyümesin)
        if len(sent_signals) > 100:
            sent_signals.clear()
    
    await asyncio.gather(*tasks)

if __name__ == "__main__":
    asyncio.run(main())
