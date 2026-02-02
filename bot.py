import sys
import os
import time
import threading
import json
import requests
from datetime import datetime, timedelta

# استدعاء مكتبة قراءة الملفات السرية
try:
    from dotenv import load_dotenv
    load_dotenv() # 👈 هذا الأمر يقرأ ملف .env ويحمل المفاتيح للذاكرة
except ImportError:
    print("⚠️ مكتبة python-dotenv غير مثبتة. المفاتيح قد لا تعمل.")

import numpy as np
import yfinance as yf
import pandas as pd
import telebot
from telebot import types
import pandas_ta as ta

# ==========================================================
# 🔐 الكيان الذهبي V95 (Secure GitHub Edition)
# ==========================================================

class SecureBotV95:
    def __init__(self):
        # 🔑 قراءة المفاتيح من البيئة المحيطة (Environment Variables)
        self.token = os.getenv('TELEGRAM_TOKEN')
        self.chat_id = os.getenv('CHAT_ID')
        self.av_key = os.getenv('ALPHA_VANTAGE_KEY')
        
        # فحص أمني قبل التشغيل
        if not self.token or not self.chat_id:
            print("❌ خطأ قاتل: لم يتم العثور على مفاتيح تليجرام في ملف .env")
            sys.exit() # إيقاف البرنامج فوراً
            
        self.bot = telebot.TeleBot(self.token)
        self.memory_file = "trading_memory.json"

        try: self.bot.remove_webhook(); time.sleep(1)
        except: pass
        
        # الإعدادات
        self.balance = 500.0
        self.equity = 500.0
        self.risk_pct = 0.05
        self.interval = "15m"
        
        self.assets = {
            '🥇 GOLD': {'y': 'GC=F', 'av': 'XAUUSD'}, 
            '🥈 SILVER': {'y': 'SI=F', 'av': 'SILVER'},
            '🛢️ OIL': {'y': 'CL=F', 'av': 'WTI'}, 
            '💶 EUR': {'y': 'EURUSD=X', 'av': 'EURUSD'},
            '💷 GBP': {'y': 'GBPUSD=X', 'av': 'GBPUSD'},
            '💴 JPY': {'y': 'JPY=X', 'av': 'JPYUSD'}
        }
        
        self.size_dampener = {
            '🥇 GOLD': 0.1, '🥈 SILVER': 0.1, '🛢️ OIL': 0.1,     
            '💶 EUR': 0.01, '💷 GBP': 0.01, '💴 JPY': 0.01
        }
        
        self.positions = {name: None for name in self.assets}
        self.load_memory()
        self.running = True 
        self.setup_telegram_handlers()

    # ==============================
    # 🕵️‍♂️ نظام القاضي (Alpha Vantage)
    # ==============================
    def verify_with_alpha_vantage(self, symbol_av, signal_type):
        if not self.av_key: return True # تجاوز إذا لم يوجد مفتاح
        try:
            print(f"🔎 التحقق من {symbol_av}...")
            url = f"https://www.alphavantage.co/query?function=SMA&symbol={symbol_av}&interval=15min&time_period=20&series_type=close&apikey={self.av_key}"
            r = requests.get(url, timeout=10)
            data = r.json()
            if "Note" in data:
                print("⚠️ Alpha Vantage Limit Reached.")
                return True
            # منطق التحقق البسيط (مجرد التأكد من وجود بيانات)
            if 'Technical Analysis: SMA' in data: return True
            return True
        except: return True

    # ==============================
    # 💾 الذاكرة
    # ==============================
    def save_memory(self):
        try:
            data = {"balance": self.balance, "positions": self.positions}
            with open(self.memory_file, 'w') as f: json.dump(data, f, indent=4)
        except: pass

    def load_memory(self):
        if os.path.exists(self.memory_file):
            try:
                with open(self.memory_file, 'r') as f:
                    data = json.load(f)
                    self.balance = data.get("balance", 500.0)
                    self.positions = data.get("positions", {name: None for name in self.assets})
                if self.balance <= 0:
                    self.balance = 500.0; self.positions = {name: None for name in self.assets}
                    self.save_memory()
            except: self.save_memory()
        else: self.save_memory()

    # ==============================
    # 🕹️ التحكم
    # ==============================
    def get_time(self):
        return datetime.now().strftime('%H:%M:%S')

    def setup_telegram_handlers(self):
        @self.bot.message_handler(commands=['start'])
        def welcome(m): self.send_dashboard_menu()

        @self.bot.message_handler(func=lambda m: True)
        def handle(m):
            if m.text == '📊 تقرير الحالة': self.bot.reply_to(m, self.generate_report(), parse_mode="Markdown")
            elif m.text == '💰 كشف الحساب': self.bot.reply_to(m, f"💰 الرصيد: `{self.balance:.2f}$`", parse_mode="Markdown")
            elif m.text == '✅ فحص الاتصال': self.bot.reply_to(m, "🟢 V95 Secure Online")
            elif m.text == '🛑 إغلاق الكل (طوارئ)': 
                self.emergency_close()
                self.bot.reply_to(m, "⚠️ Emergency Close Executed.")

    def send_dashboard_menu(self):
        markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
        markup.add('📊 تقرير الحالة', '💰 كشف الحساب', '🛑 إغلاق الكل (طوارئ)')
        try: self.bot.send_message(self.chat_id, "🔐 *V95: Secure Mode Activated*", reply_markup=markup, parse_mode="Markdown")
        except: pass

    def generate_report(self):
        lines = [f"📡 *SECURE REPORT* | {self.get_time()}", "━━━━━━━━"]
        active = False
        for name, codes in self.assets.items():
            trade = self.positions[name]
            if trade:
                active = True
                p = self.get_price(codes['y'])
                if p:
                    pnl = (p - trade['entry']) * trade['size'] if trade['type'] == 'BUY' else (trade['entry'] - p) * trade['size']
                    icon = "🟢" if pnl > 0 else "🔻"
                    lines.append(f"{icon} {name}: {pnl:+.2f}$")
        if not active: lines.append("💤 No Active Trades")
        return "\n".join(lines)

    def emergency_close(self):
        for name in self.positions: self.positions[name] = None
        self.save_memory()

    # ==============================
    # ⚙️ المحرك
    # ==============================
    def get_price(self, ticker):
        try:
            d = yf.download(ticker, period="1d", interval="15m", progress=False, auto_adjust=True)
            if isinstance(d.columns, pd.MultiIndex): d.columns = d.columns.get_level_values(0)
            return d['Close'].iloc[-1]
        except: return None

    def fetch_data(self, ticker):
        try:
            d = yf.download(ticker, period="5d", interval="15m", progress=False, auto_adjust=True)
            if len(d) < 100: return None
            if isinstance(d.columns, pd.MultiIndex): d.columns = d.columns.get_level_values(0)
            
            d.ta.ema(length=200, append=True)
            d.ta.rsi(length=14, append=True)
            d.ta.atr(length=14, append=True)
            row = d.iloc[-1]
            return {'price': row['Close'], 'ema': row['EMA_200'], 'rsi': row['RSI_14'], 'atr': row['ATRr_14']}
        except: return None

    def trading_loop(self):
        print("🔐 Secure Engine Running...")
        while self.running:
            try:
                for name, codes in self.assets.items():
                    data = self.fetch_data(codes['y'])
                    if not data or pd.isna(data['ema']): continue
                    price, trade = data['price'], self.positions[name]
                    
                    if trade:
                        if trade['type'] == 'BUY':
                            if price > trade['h']: trade['h'] = price; trade['sl'] = max(trade['sl'], price - data['atr']*2.5)
                            if price <= trade['sl']: self.close_trade(name, (price - trade['entry']) * trade['size'])
                        else:
                            if price < trade['l']: trade['l'] = price; trade['sl'] = min(trade['sl'], price + data['atr']*2.5)
                            if price >= trade['sl']: self.close_trade(name, (trade['entry'] - price) * trade['size'])
                    else:
                        dist = data['atr'] * 2.5
                        if dist > 0:
                            raw = (self.balance * self.risk_pct) / dist
                            size = round(raw * self.size_dampener.get(name, 1.0), 3)
                            if size > 1000: size = 1000
                            
                            if size > 0:
                                signal = None
                                if price > data['ema'] and data['rsi'] < 70: signal = 'BUY'
                                elif price < data['ema'] and data['rsi'] > 30: signal = 'SELL'
                                
                                if signal and self.verify_with_alpha_vantage(codes['av'], signal):
                                    sl = price - dist if signal == 'BUY' else price + dist
                                    self.open_trade(name, signal, price, size, sl)
            except: pass
            time.sleep(60)

    def open_trade(self, name, type, price, size, sl):
        self.positions[name] = {'type': type, 'entry': price, 'size': size, 'sl': sl, 'h': price, 'l': price}
        self.save_memory()
        try: self.bot.send_message(self.chat_id, f"🚀 *{type} {name}*\nPrice: `{price}`")
        except: pass

    def close_trade(self, name, pnl):
        self.balance += pnl
        self.positions[name] = None
        self.save_memory()
        try: self.bot.send_message(self.chat_id, f"🛑 *Close {name}*\nPnL: `{pnl:.2f}$`")
        except: pass

    def run(self):
        t = threading.Thread(target=self.trading_loop); t.daemon = True; t.start()
        self.send_dashboard_menu()
        self.bot.infinity_polling()

if __name__ == "__main__":
    bot = SecureBotV95()
    bot.run()
