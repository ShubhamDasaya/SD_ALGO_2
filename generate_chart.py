import matplotlib.pyplot as plt
import matplotlib.patches as patches
import numpy as np
import os

# Set dark theme style
plt.style.use('dark_background')
fig, ax = plt.subplots(figsize=(15, 8.5), dpi=150)
fig.patch.set_facecolor('#0d1117')
ax.set_facecolor('#161b22')

# Generate simulated candle timestamps (from 09:15 to 15:15 in 5-min intervals)
times = [
    "09:15", "09:20", "09:25", "09:30", "09:35", "09:40", "09:45",
    "09:50", "09:55", "10:00", "10:05", "10:10", "10:15", "10:20",
    "10:25", "10:30", "10:35", "10:40", "10:45", "11:00", "11:15", "11:30",
    "12:00", "12:30", "13:00", "13:15", "13:45", "14:15", "14:45", "15:15"
]
x_indices = list(range(len(times)))

# Simulated Spot Prices for Nifty (around 24,300)
# 09:15-09:45 Range: High 24,340, Low 24,280, Open 24,300
np.random.seed(42)

# Specific points:
# ORB: 0 to 6 (09:15 to 09:45)
# Breakout Candle at index 10 (10:05) or 11 (10:10)
candles = [
    # Open, High, Low, Close
    (24300, 24325, 24290, 24310), # 09:15
    (24310, 24335, 24300, 24320), # 09:20
    (24320, 24340, 24310, 24315), # 09:25 (ORB High = 24340)
    (24315, 24320, 24280, 24285), # 09:30 (ORB Low = 24280)
    (24285, 24310, 24280, 24300), # 09:35
    (24300, 24315, 24290, 24305), # 09:40
    (24305, 24320, 24295, 24310), # 09:45 (ORB Ends)
    (24310, 24325, 24305, 24320), # 09:50
    (24320, 24335, 24315, 24330), # 09:55
    (24330, 24342, 24325, 24338), # 10:00 (Tests High)
    (24338, 24370, 24335, 24365), # 10:05 [BREAKOUT CANDLE!] Close = 24365
    (24365, 24385, 24360, 24380), # 10:10
    (24380, 24405, 24375, 24398), # 10:15 [BE Trigger]
    (24398, 24415, 24390, 24410), # 10:20 [Target Zone 24410-24420]
    (24410, 24425, 24400, 24420), # 10:25 [TARGET HIT!]
    (24420, 24425, 24395, 24400), # 10:30
    (24400, 24410, 24385, 24390), # 10:35
    (24390, 24405, 24380, 24395), # 10:40
    (24395, 24400, 24380, 24385), # 10:45
    (24385, 24395, 24370, 24375), # 11:00
    (24375, 24385, 24365, 24370), # 11:15
    (24370, 24375, 24355, 24360), # 11:30 [Lunch Chop starts]
    (24360, 24370, 24350, 24365), # 12:00
    (24365, 24375, 24355, 24360), # 12:30
    (24360, 24370, 24350, 24355), # 13:00
    (24355, 24380, 24350, 24375), # 13:15 [Lunch Chop ends]
    (24375, 24400, 24370, 24390), # 13:45
    (24390, 24410, 24385, 24405), # 14:15
    (24405, 24415, 24395, 24400), # 14:45
    (24400, 24405, 24380, 24390)  # 15:15
]

# Draw Candlesticks
width = 0.55
width2 = 0.1

for i, (op, hi, lo, cl) in enumerate(candles):
    color = '#26a69a' if cl >= op else '#ef5350'
    # High-Low Wick
    ax.plot([i, i], [lo, hi], color=color, linewidth=1.5)
    # Body
    rect = patches.Rectangle((i - width/2, min(op, cl)), width, abs(cl - op),
                             facecolor=color, edgecolor=color, alpha=0.95)
    ax.add_patch(rect)

# Draw Moving Averages (EMA 20 & EMA 50)
closes = [c[3] for c in candles]
ema20 = []
ema50 = []
e20 = closes[0]
e50 = closes[0] - 15
for c in closes:
    e20 = c * (2/21) + e20 * (1 - 2/21)
    e50 = c * (2/51) + e50 * (1 - 2/51)
    ema20.append(e20)
    ema50.append(e50)

ax.plot(x_indices, ema20, color='#00d2ff', label='20 EMA (Short-term Momentum)', linewidth=2.2, alpha=0.9)
ax.plot(x_indices, ema50, color='#ff9800', label='50 EMA (Trend Direction)', linewidth=2.0, alpha=0.85)

# 1. Opening Range Box (09:15 to 09:45)
orb_high = 24340
orb_low = 24280
rect_orb = patches.Rectangle((-0.5, orb_low), 6.9, orb_high - orb_low,
                             facecolor='#3b82f6', alpha=0.15, edgecolor='#60a5fa', linestyle='--', linewidth=1.2)
ax.add_patch(rect_orb)

ax.axhline(orb_high, color='#60a5fa', linestyle='--', linewidth=1.5, alpha=0.7)
ax.text(6.8, orb_high + 2, 'ORB High: 24,340', color='#93c5fd', fontsize=10, fontweight='bold')

ax.axhline(orb_low, color='#60a5fa', linestyle='--', linewidth=1.5, alpha=0.7)
ax.text(6.8, orb_low - 7, 'ORB Low: 24,280', color='#93c5fd', fontsize=10, fontweight='bold')

# 2. Lunch Chop Zone Shade (11:30 to 13:15, idx 21 to 25)
rect_lunch = patches.Rectangle((20.5, 24260), 4.9, 180,
                               facecolor='#475569', alpha=0.25, edgecolor='#94a3b8', linestyle=':')
ax.add_patch(rect_lunch)
ax.text(22.8, 24275, 'NO TRADING ZONE\n(Lunch Chop 11:30 - 13:15)', color='#cbd5e1', fontsize=9,
        fontweight='bold', ha='center', bbox=dict(boxstyle='round,pad=0.4', facecolor='#1e293b', edgecolor='#475569'))

# 3. Setup Annotations at Breakout (idx 10: 10:05)
entry_x = 10
entry_spot = 24365

# Breakout Arrow
ax.annotate('BULLISH BREAKOUT ENTRY\n(1) Close > ORB High\n(2) 20 EMA > 50 EMA\n(3) Strong Green Body',
            xy=(entry_x, entry_spot),
            xytext=(entry_x - 3.5, entry_spot + 35),
            arrowprops=dict(facecolor='#22c55e', edgecolor='#16a34a', width=2, headwidth=9),
            fontsize=9.5, fontweight='bold', color='#4ade80',
            bbox=dict(boxstyle='round,pad=0.5', facecolor='#064e3b', edgecolor='#22c55e', alpha=0.9))

# Trade Levels Lines
# Entry Level (24,365) -> Buy ATM 24350 CE @ ₹110
ax.hlines(entry_spot, entry_x, 15, colors='#38bdf8', linestyles='-', linewidth=2)
ax.text(15.2, entry_spot, '➔ ENTRY: Buy ATM 24350 CE @ ₹110 (1 Lot)', color='#38bdf8', fontsize=10, fontweight='bold', va='center')

# Stop Loss (Spot equiv ~24,345, -10 pts on premium ~ ₹100, Net Loss ₹770)
sl_spot = 24345
ax.hlines(sl_spot, entry_x, 15, colors='#ef4444', linestyles='--', linewidth=1.8)
ax.text(15.2, sl_spot, '🛑 STOP LOSS: Prem ₹100 (-10 pts | Max Loss -₹770)', color='#f87171', fontsize=9.5, fontweight='bold', va='center')

# Break-Even Trigger (+10 pts gain ~ Spot 24,385, Prem ₹120)
be_spot = 24385
ax.hlines(be_spot, 12, 15, colors='#a855f7', linestyles=':', linewidth=1.8)
ax.text(15.2, be_spot, '🛡️ BREAK-EVEN ACTIVATED (SL moved to ₹111 Cost)', color='#c084fc', fontsize=9.5, fontweight='bold', va='center')

# Target Level (Spot 24,420, +18 pts on premium ~ ₹128, Net Profit +₹1050)
tp_spot = 24420
ax.hlines(tp_spot, entry_x, 15, colors='#22c55e', linestyles='-', linewidth=2)
ax.text(15.2, tp_spot, '🎯 TARGET HIT: Prem ₹128 (+18 pts | Net +₹1,050)', color='#4ade80', fontsize=10, fontweight='bold', va='center')

# Format Grid & Axes
ax.set_xticks(x_indices[::2])
ax.set_xticklabels([times[i] for i in x_indices[::2]], fontsize=10, color='#94a3b8')
ax.set_yticks(np.arange(24260, 24440, 20))
ax.set_yticklabels([f"{y:,}" for y in np.arange(24260, 24440, 20)], fontsize=10, color='#94a3b8')
ax.grid(True, linestyle='--', color='#21262d', alpha=0.8)

# Title & Subtitle Banner
plt.title("NIFTY 50 (5-MIN) - INSTITUTIONAL SMC OPTION SCALPING STRATEGY SETUP",
          fontsize=14, fontweight='bold', pad=22, color='#f1f5f9', loc='left')
plt.suptitle("Opening Range Breakout (ORB) + 20/50 EMA Trend + ATM 1-Lot Scalp (+18 Target / -10 SL)",
             fontsize=10.5, color='#94a3b8', x=0.125, y=0.93, ha='left')

ax.legend(loc='lower left', facecolor='#1e293b', edgecolor='#334155', fontsize=9.5)
plt.tight_layout()

output_path = r"C:\shubham\trading\Indian_Option_Bot\nifty_strategy_chart_setup.png"
plt.savefig(output_path, dpi=180, bbox_inches='tight')
print(f"[OK] Chart saved successfully to: {output_path}")

