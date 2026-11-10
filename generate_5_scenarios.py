import matplotlib.pyplot as plt
import matplotlib.patches as patches
import numpy as np
import os

plt.style.use('dark_background')
output_dir = r"C:\shubham\trading\Indian_Option_Bot"

def draw_candle(ax, x, op, hi, lo, cl, width=0.55):
    color = '#26a69a' if cl >= op else '#ef5350'
    ax.plot([x, x], [lo, hi], color=color, linewidth=1.5, zorder=2)
    rect = patches.Rectangle((x - width/2, min(op, cl)), width, abs(cl - op),
                             facecolor=color, edgecolor=color, alpha=0.95, zorder=3)
    ax.add_patch(rect)

# =============================================================================
# SCENARIO 1: BULLISH LIQUIDITY SWEEP (BUY CE) -> TARGET HIT (+16 pts / +Rs 1,040)
# =============================================================================
fig, ax = plt.subplots(figsize=(14, 7), dpi=150)
fig.patch.set_facecolor('#0d1117'); ax.set_facecolor('#161b22')

# Nifty 5m Candles around 22,550
# Index 0 to 4: Pullback down to 15M Swing Low / Demand at 22,545
# Index 5: THE SWEEP CANDLE (Dips to 22,538, closes strong at 22,552)
# Index 6 to 10: Explosive rally to 22,590 (Target Hit)
candles1 = [
    (22570, 22575, 22560, 22562),
    (22562, 22568, 22555, 22556),
    (22556, 22560, 22548, 22550),
    (22550, 22554, 22544, 22546),
    (22546, 22548, 22542, 22544),
    (22544, 22556, 22538, 22553), # SWEEP! Low 22538 < 22545, Close 22553
    (22553, 22565, 22550, 22563), # Follow through
    (22563, 22574, 22560, 22572),
    (22572, 22584, 22570, 22582), # BE Trigger (+8 pts on option)
    (22582, 22595, 22580, 22592), # Target Hit!
    (22592, 22598, 22586, 22588)
]
times1 = ["09:50", "09:55", "10:00", "10:05", "10:10", "10:15", "10:20", "10:25", "10:30", "10:35", "10:40"]

for i, c in enumerate(candles1):
    draw_candle(ax, i, *c)

# Liquidity Line (15M Swing Low / Demand)
ax.axhline(22545, color='#f59e0b', linestyle='--', linewidth=1.8, label='15M Swing Low / Demand Liquidity (22,545)')
ax.text(0, 22546, '15M Swing Low (Liquidity Pool: 22,545)', color='#fbbf24', fontsize=9.5, fontweight='bold')

# Sweep Annotation
ax.annotate('LIQUIDITY SWEEP & PP REJECTION!\n• Low dipped to 22,538 (Trapping sellers)\n• Closed BACK ABOVE level @ 22,553\n• Rejection Wick + Bullish Displacement',
            xy=(5, 22538), xytext=(2.2, 22525),
            arrowprops=dict(facecolor='#38bdf8', edgecolor='#0284c7', width=1.8, headwidth=8),
            fontsize=9, fontweight='bold', color='#7dd3fc',
            bbox=dict(boxstyle='round,pad=0.4', facecolor='#0c4a6e', edgecolor='#38bdf8', alpha=0.9))

# Trade Levels
ax.hlines(22553, 5, 10, colors='#22c55e', linestyles='-', linewidth=2)
ax.text(10.2, 22553, '➔ ENTRY: Buy ATM 22550 CE @ ₹110', color='#4ade80', fontsize=9.5, fontweight='bold', va='center')

ax.hlines(22536, 5, 10, colors='#ef4444', linestyles='--', linewidth=1.5)
ax.text(10.2, 22536, '🛑 STOP LOSS: Premium ₹101 (-9 pts / -₹585 Risk)', color='#f87171', fontsize=9, fontweight='bold', va='center')

ax.hlines(22572, 7, 10, colors='#a855f7', linestyles=':', linewidth=1.5)
ax.text(10.2, 22572, '🛡️ AUTO BREAK-EVEN (+8 pts Option gain -> SL to ₹111 Cost)', color='#c084fc', fontsize=9, fontweight='bold', va='center')

ax.hlines(22592, 5, 10, colors='#10b981', linestyles='-', linewidth=2)
ax.text(10.2, 22592, '🎯 TARGET HIT: Prem ₹126 (+16 pts / Net +₹1,040 Profit)', color='#34d399', fontsize=9.5, fontweight='bold', va='center')

ax.set_xticks(range(len(times1))); ax.set_xticklabels(times1, color='#94a3b8')
ax.set_ylabel('Nifty 50 Spot Price', color='#94a3b8', fontsize=10)
ax.set_title("SCENARIO 1: BULLISH LIQUIDITY SWEEP (BUY CE) -> PERFECT TARGET HIT", fontsize=12, fontweight='bold', color='#f1f5f9', pad=15)
ax.legend(loc='upper left', facecolor='#1e293b', edgecolor='#334155')
ax.grid(True, linestyle='--', color='#21262d', alpha=0.7)
plt.tight_layout()
p1 = os.path.join(output_dir, "scenario_1_bullish_sweep_target.png")
plt.savefig(p1, dpi=160, bbox_inches='tight')
plt.close()

# =============================================================================
# SCENARIO 2: BEARISH LIQUIDITY SWEEP (BUY PE) -> TARGET HIT
# =============================================================================
fig, ax = plt.subplots(figsize=(14, 7), dpi=150)
fig.patch.set_facecolor('#0d1117'); ax.set_facecolor('#161b22')

candles2 = [
    (22680, 22690, 22675, 22688),
    (22688, 22698, 22684, 22695),
    (22695, 22704, 22692, 22700),
    (22700, 22705, 22696, 22702),
    (22702, 22718, 22694, 22696), # BEARISH SWEEP! High 22718 > 22705, Close 22696
    (22696, 22698, 22682, 22685),
    (22685, 22688, 22670, 22672), # BE Trigger
    (22672, 22675, 22658, 22660), # Target zone
    (22660, 22665, 22648, 22650), # Target Hit
    (22650, 22658, 22645, 22652)
]
times2 = ["13:20", "13:25", "13:30", "13:35", "13:40", "13:45", "13:50", "13:55", "14:00", "14:05"]

for i, c in enumerate(candles2):
    draw_candle(ax, i, *c)

ax.axhline(22705, color='#ec4899', linestyle='--', linewidth=1.8, label='Previous Day High / Supply Liquidity (22,705)')
ax.text(0, 22707, 'Previous Day High (PDH / Buy-Stop Liquidity: 22,705)', color='#f472b6', fontsize=9.5, fontweight='bold')

ax.annotate('BEARISH BUY-STOP SWEEP!\n• High spiked to 22,718 (Trapping breakout retail buyers)\n• Closed BACK BELOW 22,705 @ 22,696\n• Red Rejection Wick & Bearish Displacement',
            xy=(4, 22718), xytext=(1.2, 22722),
            arrowprops=dict(facecolor='#f43f5e', edgecolor='#e11d48', width=1.8, headwidth=8),
            fontsize=9, fontweight='bold', color='#fda4af',
            bbox=dict(boxstyle='round,pad=0.4', facecolor='#881337', edgecolor='#f43f5e', alpha=0.9))

# Trade Levels
ax.hlines(22696, 4, 9, colors='#f43f5e', linestyles='-', linewidth=2)
ax.text(9.2, 22696, '➔ ENTRY: Buy ATM 22700 PE @ ₹115', color='#fb7185', fontsize=9.5, fontweight='bold', va='center')

ax.hlines(22715, 4, 9, colors='#ef4444', linestyles='--', linewidth=1.5)
ax.text(9.2, 22715, '🛑 STOP LOSS: Prem ₹106 (-9 pts / -₹585 Risk)', color='#f87171', fontsize=9, fontweight='bold', va='center')

ax.hlines(22672, 6, 9, colors='#a855f7', linestyles=':', linewidth=1.5)
ax.text(9.2, 22672, '🛡️ BREAK-EVEN ACTIVE (+8 pts gain -> SL to Cost)', color='#c084fc', fontsize=9, fontweight='bold', va='center')

ax.hlines(22650, 4, 9, colors='#10b981', linestyles='-', linewidth=2)
ax.text(9.2, 22650, '🎯 TARGET HIT: Prem ₹131 (+16 pts / Net +₹1,040 Profit)', color='#34d399', fontsize=9.5, fontweight='bold', va='center')

ax.set_xticks(range(len(times2))); ax.set_xticklabels(times2, color='#94a3b8')
ax.set_ylabel('Nifty 50 Spot Price', color='#94a3b8', fontsize=10)
ax.set_title("SCENARIO 2: BEARISH LIQUIDITY SWEEP (BUY PE) -> TARGET HIT", fontsize=12, fontweight='bold', color='#f1f5f9', pad=15)
ax.legend(loc='upper left', facecolor='#1e293b', edgecolor='#334155')
ax.grid(True, linestyle='--', color='#21262d', alpha=0.7)
plt.tight_layout()
p2 = os.path.join(output_dir, "scenario_2_bearish_sweep_target.png")
plt.savefig(p2, dpi=160, bbox_inches='tight')
plt.close()

# =============================================================================
# SCENARIO 3: AUTO BREAK-EVEN PROTECTION (ZERO LOSS CAPITAL SHIELD)
# =============================================================================
fig, ax = plt.subplots(figsize=(14, 7), dpi=150)
fig.patch.set_facecolor('#0d1117'); ax.set_facecolor('#161b22')

candles3 = [
    (22610, 22615, 22602, 22605),
    (22605, 22618, 22594, 22612), # Sweep low 22594 < 22600, Close 22612
    (22612, 22625, 22610, 22622),
    (22622, 22634, 22620, 22630), # Profit reaches +8.5 pts! BE Activated
    (22630, 22632, 22615, 22618), # Market suddenly stalls and reverses
    (22618, 22620, 22608, 22610), # Hits Cost (Break Even Exit!)
    (22610, 22612, 22585, 22588), # Huge dump afterwards (Retail accounts get wiped)
    (22588, 22592, 22570, 22575)
]
times3 = ["10:15", "10:20", "10:25", "10:30", "10:35", "10:40", "10:45", "10:50"]

for i, c in enumerate(candles3):
    draw_candle(ax, i, *c)

ax.axhline(22600, color='#38bdf8', linestyle='--', linewidth=1.8, label='15M Swing Low (22,600)')

ax.annotate('1. ENTRY: CE Buy @ 22,612\n(Swept 22,600)', xy=(1, 22612), xytext=(0.2, 22625),
            arrowprops=dict(facecolor='#22c55e', width=1.5, headwidth=6), color='#4ade80', fontsize=9, fontweight='bold',
            bbox=dict(boxstyle='round,pad=0.3', facecolor='#064e3b', edgecolor='#22c55e'))

ax.annotate('2. BREAK-EVEN ARMED (+8 pts Profit)!\nSL automatically shifted to Cost Price (₹111)',
            xy=(3, 22630), xytext=(2.2, 22642),
            arrowprops=dict(facecolor='#a855f7', width=1.5, headwidth=6), color='#c084fc', fontsize=9, fontweight='bold',
            bbox=dict(boxstyle='round,pad=0.3', facecolor='#3b0764', edgecolor='#a855f7'))

ax.annotate('3. BREAK-EVEN EXIT @ COST!\nBot squares off @ Rs 0.00 Loss\n(Protected from sudden 50-pt crash!)',
            xy=(5, 22610), xytext=(4.2, 22626),
            arrowprops=dict(facecolor='#facc15', width=1.8, headwidth=7), color='#fde047', fontsize=9, fontweight='bold',
            bbox=dict(boxstyle='round,pad=0.4', facecolor='#713f12', edgecolor='#facc15'))

ax.set_xticks(range(len(times3))); ax.set_xticklabels(times3, color='#94a3b8')
ax.set_ylabel('Nifty 50 Spot Price', color='#94a3b8', fontsize=10)
ax.set_title("SCENARIO 3: AUTO BREAK-EVEN CAPITAL SHIELD (SAVES FROM BIG REVERSALS)", fontsize=12, fontweight='bold', color='#f1f5f9', pad=15)
ax.legend(loc='lower left', facecolor='#1e293b', edgecolor='#334155')
ax.grid(True, linestyle='--', color='#21262d', alpha=0.7)
plt.tight_layout()
p3 = os.path.join(output_dir, "scenario_3_breakeven_capital_shield.png")
plt.savefig(p3, dpi=160, bbox_inches='tight')
plt.close()

# =============================================================================
# SCENARIO 4: THETA SHIELD (TIME STOP EXITS SIDEWAYS TRAP)
# =============================================================================
fig, ax = plt.subplots(figsize=(14, 7), dpi=150)
fig.patch.set_facecolor('#0d1117'); ax.set_facecolor('#161b22')

# Entry after sweep, but market stays dead sideways for 4 bars (20 mins)
candles4 = [
    (22555, 22558, 22544, 22553), # Entry Bar (Swept 22548)
    (22553, 22556, 22550, 22552), # Bar 1 (5m elapsed)
    (22552, 22555, 22549, 22554), # Bar 2 (10m elapsed)
    (22554, 22557, 22551, 22553), # Bar 3 (15m elapsed)
    (22553, 22555, 22548, 22550), # Bar 4 (20m elapsed) -> TIME STOP!
    (22550, 22552, 22546, 22548), # Sideways continues
    (22548, 22551, 22545, 22547)
]
times4 = ["10:15", "10:20", "10:25", "10:30", "10:35 (Time Stop)", "10:40", "10:45"]

for i, c in enumerate(candles4):
    draw_candle(ax, i, *c)

rect_theta = patches.Rectangle((0.7, 22540), 3.6, 25, facecolor='#475569', alpha=0.2, edgecolor='#cbd5e1', linestyle=':')
ax.add_patch(rect_theta)

ax.annotate('ENTRY: CE Buy @ 22,553', xy=(0, 22553), xytext=(-0.3, 22560),
            arrowprops=dict(facecolor='#22c55e', width=1.5, headwidth=6), color='#4ade80', fontsize=9, fontweight='bold',
            bbox=dict(boxstyle='round,pad=0.3', facecolor='#064e3b', edgecolor='#22c55e'))

ax.annotate('⏱️ THETA SHIELD: 20-MIN TIME STOP TRIGGERED!\n• Market went dead sideways (Only 5 pts range)\n• Options Theta is decaying premium every minute\n• Bot forcefully closes position @ Minor PnL (+₹165)\n➔ Avoids holding into full premium burn!',
            xy=(4, 22550), xytext=(1.8, 22538),
            arrowprops=dict(facecolor='#38bdf8', width=1.8, headwidth=7), color='#7dd3fc', fontsize=9.5, fontweight='bold',
            bbox=dict(boxstyle='round,pad=0.4', facecolor='#075985', edgecolor='#38bdf8', alpha=0.9))

ax.set_xticks(range(len(times4))); ax.set_xticklabels(times4, color='#94a3b8')
ax.set_ylabel('Nifty 50 Spot Price', color='#94a3b8', fontsize=10)
ax.set_title("SCENARIO 4: THETA SHIELD (20-MIN TIME STOP EXITS DEAD CHOP BEFORE OPTIONS MELT)", fontsize=12, fontweight='bold', color='#f1f5f9', pad=15)
ax.grid(True, linestyle='--', color='#21262d', alpha=0.7)
plt.tight_layout()
p4 = os.path.join(output_dir, "scenario_4_theta_shield_timestop.png")
plt.savefig(p4, dpi=160, bbox_inches='tight')
plt.close()

# =============================================================================
# SCENARIO 5: HARD STOP LOSS & KILL SWITCH (CAPITAL DISCIPLINE)
# =============================================================================
fig, ax = plt.subplots(figsize=(14, 7), dpi=150)
fig.patch.set_facecolor('#0d1117'); ax.set_facecolor('#161b22')

candles5 = [
    (22555, 22562, 22544, 22558), # Sweep attempt
    (22558, 22560, 22535, 22536), # Severe breakdown (SL Hit!)
    (22536, 22538, 22510, 22512), # Freefall continues (-80 pts)
    (22512, 22515, 22485, 22488),
    (22488, 22490, 22460, 22465)
]
times5 = ["13:50 (Entry)", "13:55 (SL Hit)", "14:00 (Halted)", "14:05 (Halted)", "14:10 (Halted)"]

for i, c in enumerate(candles5):
    draw_candle(ax, i, *c)

ax.annotate('1. False Sweep Entry @ 22,558', xy=(0, 22558), xytext=(-0.3, 22568),
            arrowprops=dict(facecolor='#22c55e', width=1.5, headwidth=6), color='#4ade80', fontsize=9, fontweight='bold',
            bbox=dict(boxstyle='round,pad=0.3', facecolor='#064e3b', edgecolor='#22c55e'))

ax.annotate('2. 🛑 STOP LOSS HIT (-9 pts / -₹585 Loss)\nInstant exit without any emotional hesitation!',
            xy=(1, 22536), xytext=(1.2, 22550),
            arrowprops=dict(facecolor='#ef4444', width=1.8, headwidth=7), color='#f87171', fontsize=9.5, fontweight='bold',
            bbox=dict(boxstyle='round,pad=0.4', facecolor='#7f1d1d', edgecolor='#ef4444'))

ax.annotate('3. 🚨 KILL SWITCH ACTIVATED (Day Over!)\n• Bot completely shuts down for the day\n• Avoided -80 pts massive intraday crash\n• Protected ₹9,415 Capital to fight another day!',
            xy=(2, 22512), xytext=(2.2, 22530),
            arrowprops=dict(facecolor='#f97316', width=1.8, headwidth=7), color='#fdba74', fontsize=9.5, fontweight='bold',
            bbox=dict(boxstyle='round,pad=0.4', facecolor='#7c2d12', edgecolor='#f97316'))

ax.set_xticks(range(len(times5))); ax.set_xticklabels(times5, color='#94a3b8')
ax.set_ylabel('Nifty 50 Spot Price', color='#94a3b8', fontsize=10)
ax.set_title("SCENARIO 5: 1-LOSS HARD KILL SWITCH (SAVES 93% CAPITAL FROM CRASHES & OVERTRADING)", fontsize=12, fontweight='bold', color='#f1f5f9', pad=15)
ax.grid(True, linestyle='--', color='#21262d', alpha=0.7)
plt.tight_layout()
p5 = os.path.join(output_dir, "scenario_5_kill_switch_discipline.png")
plt.savefig(p5, dpi=160, bbox_inches='tight')
plt.close()

print("[OK] All 5 Scenario Charts generated successfully!")

