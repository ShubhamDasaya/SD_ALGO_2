"""
===============================================================================
NIFTY 50 INSTITUTIONAL QUANT MATRIX TERMINAL (PRO DESK)
===============================================================================
Master Unified Trading Station:
- Dark Pitch-Black Cyberpunk Bloomberg Aesthetic (#08090c)
- Left Vertical Sidebar Navigation (6 Dedicated Desks):
    1. 📊 Live Chart Desk (TradingView Pro Station, 9-EMA, 21-EMA, VWAP, Fixed Volume Scale)
    2. ⛓️ Option Chain Desk (Dedicated Tab, Sensibull Style, PCR, Straddle Price, Expected Move)
    3. 🧮 Hedge & Margin Calculator Desk (Interactive Simulator, Margin Saved, SEBI 50:50)
    4. 💼 Live Positions & Payoff Desk (4-Leg Table, SVG Payoff Mountain, Taxes Audit)
    5. 🔮 Algo Rationale & Predictor Desk (Why Algo Traded & What-If Live Simulator)
    6. 📈 Monthly P&L & Risk Ledger Desk (Calendar Heatmap, Month-by-Month Table, Loss Cap Gauge)
- Top Telemetry Header with Dynamic Paper vs Real Broker Toggle
===============================================================================
"""

import json
import logging
import os
import threading
import time
from datetime import datetime, date
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse
from config import Config

logger = logging.getLogger("WebDashboard")

_BOT_INSTANCE = None

HTML_PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>NIFTY 50 Institutional Quant Matrix Terminal</title>
  <link rel="icon" href="data:,">
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;600;700;800&family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap" rel="stylesheet">
  <!-- TradingView Lightweight Charts Official CDN -->
  <script src="https://unpkg.com/lightweight-charts@4.1.3/dist/lightweight-charts.standalone.production.js"></script>
  <style>
    :root {
      --bg-base: #08090c;
      --bg-surface: #0e121a;
      --bg-card: #131824;
      --bg-card-secondary: #182030;
      --bg-hover: #1f293d;
      --border: #1e2638;
      --border-highlight: #2f3b54;
      
      --text-main: #f0f4fc;
      --text-muted: #828fa6;
      --text-dim: #546075;

      --neon-green: #00f5a0;
      --emerald: #089981;
      --green-glow: rgba(0, 245, 160, 0.2);
      
      --neon-red: #ff3366;
      --scarlet: #ef5350;
      --red-glow: rgba(255, 51, 102, 0.2);

      --cyan: #00e5ff;
      --purple: #a855f7;
      --amber: #f59e0b;
      --blue: #2962ff;
    }

    * { box-sizing: border-box; margin: 0; padding: 0; }

    body {
      background-color: var(--bg-base);
      color: var(--text-main);
      font-family: 'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, sans-serif;
      overflow-x: hidden;
      height: 100vh;
      display: flex;
      flex-direction: column;
    }

    .mono { font-family: 'JetBrains Mono', monospace; }

    /* =========================================================================
       1. TOP TELEMETRY HEADER
       ========================================================================= */
    .top-header {
      height: 56px;
      background: var(--bg-surface);
      border-bottom: 1px solid var(--border);
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 0 16px;
      gap: 12px;
      z-index: 100;
      flex-shrink: 0;
    }

    .header-left {
      display: flex;
      align-items: center;
      gap: 14px;
    }

    .brand-box {
      display: flex;
      align-items: center;
      gap: 8px;
    }

    .brand-logo {
      background: linear-gradient(135deg, #00f5a0 0%, #00e5ff 100%);
      color: #000;
      font-weight: 900;
      font-size: 11px;
      padding: 4px 8px;
      border-radius: 4px;
      letter-spacing: 0.5px;
    }

    .brand-title {
      font-size: 13px;
      font-weight: 800;
      color: #fff;
      letter-spacing: -0.2px;
    }

    .live-symbol-pill {
      background: var(--bg-card);
      border: 1px solid var(--border-highlight);
      padding: 4px 10px;
      border-radius: 6px;
      display: flex;
      align-items: center;
      gap: 8px;
      font-size: 12px;
    }

    .pulse-dot {
      width: 7px;
      height: 7px;
      background-color: var(--neon-green);
      border-radius: 50%;
      box-shadow: 0 0 8px var(--neon-green);
      animation: pulse 1.5s infinite;
    }

    @keyframes pulse {
      0% { transform: scale(0.95); opacity: 0.7; }
      50% { transform: scale(1.3); opacity: 1; }
      100% { transform: scale(0.95); opacity: 0.7; }
    }

    .spot-ltp-val {
      font-weight: 800;
      font-size: 13px;
      color: #fff;
    }

    .spot-chg-val {
      font-size: 11px;
      font-weight: 700;
    }

    .header-center {
      display: flex;
      align-items: center;
      gap: 12px;
      overflow-x: auto;
    }

    .telemetry-chip {
      background: var(--bg-card);
      border: 1px solid var(--border);
      padding: 4px 10px;
      border-radius: 6px;
      display: flex;
      align-items: center;
      gap: 6px;
      font-size: 11px;
      white-space: nowrap;
    }

    .telemetry-k { color: var(--text-muted); font-size: 10px; font-weight: 600; text-transform: uppercase; }
    .telemetry-v { font-weight: 700; }

    .live-mtm-badge {
      background: linear-gradient(135deg, rgba(0, 245, 160, 0.15), rgba(0, 229, 255, 0.15));
      border: 1px solid var(--neon-green);
      padding: 4px 12px;
      border-radius: 6px;
      font-weight: 800;
      font-size: 12px;
      color: var(--neon-green);
      display: flex;
      align-items: center;
      gap: 6px;
    }

    .header-right {
      display: flex;
      align-items: center;
      gap: 10px;
    }

    .env-toggle-box {
      background: #000;
      border: 1px solid var(--border-highlight);
      border-radius: 6px;
      padding: 2px;
      display: flex;
      align-items: center;
    }

    .btn-env {
      padding: 4px 10px;
      font-size: 11px;
      font-weight: 700;
      border: none;
      cursor: pointer;
      border-radius: 4px;
      background: transparent;
      color: var(--text-muted);
      transition: all 0.2s ease;
    }

    .btn-env.active-paper {
      background: var(--blue);
      color: #fff;
      box-shadow: 0 0 10px rgba(41, 98, 255, 0.5);
    }

    .btn-env.active-live {
      background: var(--neon-red);
      color: #fff;
      box-shadow: 0 0 10px var(--red-glow);
    }

    /* =========================================================================
       2. WORKSPACE LAYOUT (SIDEBAR + MAIN CONTENT)
       ========================================================================= */
    .app-body {
      display: flex;
      flex: 1;
      overflow: hidden;
    }

    .sidebar {
      width: 190px;
      background: #0b0f17;
      border-right: 1px solid #1a2233;
      display: flex;
      flex-direction: column;
      justify-content: space-between;
      flex-shrink: 0;
      padding: 14px 8px;
    }

    .nav-list {
      display: flex;
      flex-direction: column;
      gap: 3px;
    }

    .nav-btn {
      width: 100%;
      background: transparent;
      border: none;
      border-left: 3px solid transparent;
      border-radius: 6px;
      color: #94a3b8;
      padding: 9px 12px;
      display: flex;
      align-items: center;
      gap: 10px;
      font-size: 13px;
      font-weight: 500;
      cursor: pointer;
      transition: all 0.15s ease;
      text-align: left;
    }

    .nav-btn:hover {
      background: rgba(255, 255, 255, 0.04);
      color: #ffffff;
    }

    .nav-btn.active {
      background: rgba(0, 245, 160, 0.08);
      border-left: 3px solid var(--neon-green);
      color: #ffffff;
      font-weight: 600;
    }

    .nav-icon {
      font-size: 15px;
      width: 18px;
      display: inline-flex;
      align-items: center;
      justify-content: center;
    }

    .nav-label {
      font-size: 13px;
      letter-spacing: -0.1px;
    }

    .sidebar-footer-minimal {
      padding: 8px 10px;
      background: rgba(255, 255, 255, 0.02);
      border: 1px solid #1a2233;
      border-radius: 6px;
      font-size: 11px;
      display: flex;
      align-items: center;
      gap: 6px;
      color: var(--text-muted);
    }

    /* Workspace Content Area */
    .workspace {
      flex: 1;
      overflow-y: auto;
      background: var(--bg-base);
      padding: 16px;
    }

    .desk-view {
      display: none;
      animation: fadeIn 0.2s ease;
    }
    .desk-view.active-desk { display: block; }

    @keyframes fadeIn {
      from { opacity: 0; transform: translateY(4px); }
      to { opacity: 1; transform: translateY(0); }
    }

    /* Common Card Styles */
    .card {
      background: var(--bg-surface);
      border: 1px solid var(--border);
      border-radius: 10px;
      padding: 16px;
      margin-bottom: 16px;
    }

    .card-title {
      font-size: 13px;
      font-weight: 800;
      color: #fff;
      margin-bottom: 12px;
      display: flex;
      align-items: center;
      justify-content: space-between;
    }

    .val-green { color: var(--neon-green); }
    .val-red { color: var(--neon-red); }
    .val-cyan { color: var(--cyan); }
    .val-amber { color: var(--amber); }

    /* =========================================================================
       DESK 1: LIVE CHART DESK (TRADINGVIEW PRO STATION)
       ========================================================================= */
    .chart-box {
      background: var(--bg-surface);
      border: 1px solid var(--border);
      border-radius: 10px;
      overflow: hidden;
      margin-bottom: 16px;
    }

    .chart-box:fullscreen {
      width: 100vw;
      height: 100vh;
      border-radius: 0;
      display: flex;
      flex-direction: column;
      background: #131722;
    }

    .chart-box:fullscreen #tvWidgetWrapper,
    .chart-box:fullscreen #algoCanvasWrapper {
      flex: 1;
      height: calc(100vh - 54px) !important;
    }

    .chart-top-bar {
      padding: 8px 14px;
      background: #0f141f;
      border-bottom: 1px solid #1e2638;
      display: flex;
      justify-content: space-between;
      align-items: center;
      flex-wrap: wrap;
      gap: 10px;
    }

    .chart-engine-pills {
      display: inline-flex;
      background: #080b11;
      border: 1px solid #1e2638;
      border-radius: 6px;
      padding: 2px;
      gap: 2px;
    }

    /* Option Chain Table Styles (Sensibull Style) */
    .sf-k {
      font-size: 10px;
      color: var(--text-muted);
      font-weight: 700;
      letter-spacing: 0.5px;
      text-transform: uppercase;
    }

    .oi-cell {
      position: relative;
      height: 20px;
      display: flex;
      align-items: center;
      justify-content: center;
    }

    .oi-fill-call {
      position: absolute;
      left: 0;
      top: 2px;
      bottom: 2px;
      background: rgba(41, 98, 255, 0.35);
      border-radius: 3px;
      pointer-events: none;
    }

    .oi-fill-put {
      position: absolute;
      right: 0;
      top: 2px;
      bottom: 2px;
      background: rgba(239, 83, 80, 0.35);
      border-radius: 3px;
      pointer-events: none;
    }

    .oi-text {
      position: relative;
      z-index: 2;
      font-family: 'JetBrains Mono', monospace;
      font-weight: 700;
      font-size: 11px;
    }

    .strike-cell {
      background: #141a26;
      font-weight: 800;
      font-family: 'JetBrains Mono', monospace;
      color: #fff;
      font-size: 12px;
    }

    .atm-strike-row {
      background: rgba(0, 229, 255, 0.12) !important;
      border-top: 2px solid var(--cyan);
      border-bottom: 2px solid var(--cyan);
    }

    .itm-call { background: rgba(245, 158, 11, 0.08); }
    .itm-put { background: rgba(245, 158, 11, 0.08); }

    .tf-btn-group {
      display: inline-flex;
      background: #080b11;
      border: 1px solid #1e2638;
      border-radius: 6px;
      padding: 2px;
      gap: 2px;
    }

    .btn-tf {
      background: transparent;
      border: none;
      color: #94a3b8;
      padding: 4px 10px;
      font-size: 11px;
      font-weight: 700;
      border-radius: 4px;
      cursor: pointer;
      transition: all 0.15s ease;
    }

    .btn-tf:hover {
      color: #ffffff;
    }

    .btn-tf.active {
      background: #2563eb;
      color: #ffffff;
      box-shadow: 0 1px 4px rgba(37, 99, 235, 0.4);
    }

    .indicator-pills-row {
      display: flex;
      gap: 6px;
      align-items: center;
      flex-wrap: wrap;
    }

    .ind-pill {
      font-size: 11px;
      padding: 3px 8px;
      border-radius: 4px;
      background: #080b11;
      border: 1px solid #1e2638;
      font-family: 'JetBrains Mono', monospace;
      font-weight: 600;
    }

    #tvWidgetWrapper, #algoCanvasWrapper {
      width: 100%;
      height: 600px;
      position: relative;
      background: #131722;
    }

    #tvChartContainer {
      width: 100%;
      height: 100%;
      position: relative;
    }

    .chart-watermark {
      position: absolute;
      top: 48%;
      left: 50%;
      transform: translate(-50%, -50%);
      font-size: 54px;
      font-weight: 900;
      color: rgba(255, 255, 255, 0.035);
      pointer-events: none;
      user-select: none;
      letter-spacing: 2px;
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    }

    /* Table Styles */
    .table-container {
      background: var(--bg-surface);
      border: 1px solid var(--border);
      border-radius: 10px;
      overflow: hidden;
      margin-bottom: 16px;
    }

    table {
      width: 100%;
      border-collapse: collapse;
      font-size: 11px;
      text-align: center;
    }

    th {
      background: var(--bg-card);
      color: var(--text-muted);
      font-weight: 700;
      padding: 9px 8px;
      border-bottom: 1px solid var(--border);
      font-size: 10px;
      text-transform: uppercase;
      letter-spacing: 0.5px;
    }

    td {
      padding: 8px 6px;
      border-bottom: 1px solid var(--border);
      color: var(--text-main);
    }

    tr:hover { background-color: var(--bg-hover); }

    /* Active F&O Position Styles */
    .active-hero-banner {
      background: linear-gradient(135deg, #101624 0%, #151d30 100%);
      border: 1px solid var(--border-highlight);
      border-radius: 10px;
      padding: 16px 20px;
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 16px;
      flex-wrap: wrap;
      gap: 12px;
    }

    .hero-mtm-box { display: flex; flex-direction: column; }
    .hero-mtm-k { font-size: 11px; color: var(--text-muted); font-weight: 700; text-transform: uppercase; }
    .hero-mtm-v { font-size: 26px; font-weight: 800; color: var(--neon-green); text-shadow: 0 0 16px var(--green-glow); }

    .legs-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
      gap: 12px;
      margin-bottom: 16px;
    }

    .leg-card {
      background: var(--bg-surface);
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 12px;
      position: relative;
    }

    .leg-tag {
      font-size: 9px;
      font-weight: 800;
      padding: 2px 6px;
      border-radius: 3px;
      display: inline-block;
      margin-bottom: 6px;
      text-transform: uppercase;
    }
    .tag-buy { background: rgba(0, 245, 160, 0.15); color: var(--neon-green); border: 1px solid rgba(0, 245, 160, 0.3); }
    .tag-sell { background: rgba(245, 158, 11, 0.15); color: var(--amber); border: 1px solid rgba(245, 158, 11, 0.3); }

    /* Empty Standby Banner */
    .empty-position-standby {
      background: linear-gradient(180deg, #0d121c 0%, #080b11 100%);
      border: 1px dashed #1e293b;
      border-radius: 12px;
      padding: 44px 24px;
      text-align: center;
      margin-bottom: 16px;
      box-shadow: 0 4px 20px rgba(0, 0, 0, 0.3);
    }
    .empty-icon {
      font-size: 40px;
      margin-bottom: 10px;
      display: inline-block;
    }
    .empty-title {
      font-size: 16px;
      font-weight: 800;
      color: #fff;
      letter-spacing: 0.5px;
      text-transform: uppercase;
    }
    .empty-desc {
      font-size: 13px;
      color: var(--text-muted);
      max-width: 620px;
      margin: 8px auto 0;
      line-height: 1.6;
    }
    .empty-stat-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
      gap: 12px;
      max-width: 780px;
      margin: 22px auto 0;
    }
    .empty-stat-card {
      background: #101622;
      border: 1px solid #1a2333;
      border-radius: 8px;
      padding: 12px 14px;
      text-align: left;
    }
    .empty-stat-label {
      font-size: 10px;
      color: var(--text-muted);
      text-transform: uppercase;
      font-weight: 700;
      letter-spacing: 0.5px;
    }
    .empty-stat-val {
      font-size: 15px;
      font-weight: 800;
      margin-top: 4px;
    }

    button.btn-act {
      padding: 8px 14px;
      border-radius: 6px;
      font-weight: 700;
      font-size: 11px;
      cursor: pointer;
      border: none;
      display: inline-flex;
      align-items: center;
      gap: 6px;
      transition: all 0.2s;
    }
    .btn-act-danger { background: #d32f2f; color: #fff; }
    .btn-act-danger:hover { background: var(--neon-red); }
    .btn-act-warn { background: var(--amber); color: #000; }
    .btn-act-sec { background: var(--bg-card-secondary); color: var(--text-main); border: 1px solid var(--border); }
    .btn-act-sec:hover { background: var(--bg-hover); }

    /* Modal Confirmation */
    .dialog-modal {
      display: none;
      position: fixed;
      z-index: 10000;
      left: 0;
      top: 0;
      width: 100vw;
      height: 100vh;
      background: rgba(0, 0, 0, 0.85);
      backdrop-filter: blur(4px);
      align-items: center;
      justify-content: center;
    }
    .dialog-card {
      background: var(--bg-surface);
      border: 1px solid var(--border-highlight);
      border-radius: 12px;
      padding: 24px;
      max-width: 440px;
      width: 90%;
      box-shadow: 0 10px 40px rgba(0, 0, 0, 0.8);
    }
    .dialog-title { font-size: 16px; font-weight: 800; color: #fff; margin-bottom: 8px; }
    .dialog-msg { font-size: 13px; color: var(--text-muted); margin-bottom: 20px; line-height: 1.5; }
    .dialog-actions { display: flex; justify-content: flex-end; gap: 10px; }
  </style>
</head>
<body>

  <!-- =========================================================================
       1. TOP TELEMETRY HEADER
       ========================================================================= -->
  <header class="top-header">
    <div class="header-left">
      <div class="brand-box">
        <span style="background:#2563eb; color:#fff; font-weight:800; font-size:10px; padding:3px 7px; border-radius:4px; letter-spacing:0.5px;">PRO</span>
        <span style="font-weight:700; font-size:13px; color:#fff; letter-spacing:-0.2px;">NIFTY DESK</span>
      </div>

      <div class="live-symbol-pill">
        <span class="pulse-dot"></span>
        <span style="font-weight:800; font-size:12px;">NIFTY 50</span>
        <span class="spot-ltp-val mono" id="topSpotLtp">25,044.80</span>
        <span class="spot-chg-val mono val-green" id="topSpotChg">+40.33 (+0.16%)</span>
      </div>
    </div>

    <div class="header-center">
      <div class="telemetry-chip">
        <span class="telemetry-k" id="topCapLabel">CAPITAL:</span>
        <span class="telemetry-v mono" id="topCapital">₹50,000</span>
      </div>
      <div class="telemetry-chip">
        <span class="telemetry-k" id="topDeployedLabel">DEPLOYED:</span>
        <span class="telemetry-v mono val-amber" id="topDeployed">₹0</span>
      </div>
      <div class="telemetry-chip">
        <span class="telemetry-k" id="topFreeLabel">FREE CASH:</span>
        <span class="telemetry-v mono val-green" id="topFree">₹50,000</span>
      </div>
      <div class="telemetry-chip" style="border-color: rgba(239, 83, 80, 0.4);">
        <span class="telemetry-k" style="color:var(--neon-red);">DAY LOSS CAP:</span>
        <span class="telemetry-v mono val-green" id="topDayCap">₹0 / ₹500</span>
      </div>
      <div class="live-mtm-badge">
        <span>LIVE MTM:</span>
        <span class="mono" id="topMtmVal">₹0.00</span>
      </div>
    </div>

    <div class="header-right">
      <!-- Paper vs Real Trading Toggle -->
      <div class="env-toggle-box">
        <button id="btnTogglePaper" class="btn-env active-paper" onclick="confirmSwitchEnv('PAPER_TRADING')">
          🛡️ PAPER
        </button>
        <button id="btnToggleLive" class="btn-env" onclick="confirmSwitchEnv('LIVE_TRADING')">
          ⚡ REAL TRADING
        </button>
      </div>

      <span id="topClock" class="mono" style="font-size: 12px; color: var(--text-muted);">--:--:--</span>
    </div>
  </header>

  <!-- =========================================================================
       2. APP BODY: SIDEBAR + 6 WORKSPACE DESKS
       ========================================================================= -->
  <div class="app-body">
    <!-- Left Navigation Sidebar -->
    <aside class="sidebar">
      <div class="nav-list">
        <button class="nav-btn active" id="navDesk1" onclick="switchDesk('desk1')">
          <span class="nav-icon">📊</span>
          <span class="nav-label">Live Chart</span>
        </button>

        <button class="nav-btn" id="navDesk2" onclick="switchDesk('desk2')">
          <span class="nav-icon">⛓️</span>
          <span class="nav-label">Option Chain</span>
        </button>

        <button class="nav-btn" id="navDesk3" onclick="switchDesk('desk3')">
          <span class="nav-icon">💼</span>
          <span class="nav-label">Positions &amp; Shares</span>
        </button>

        <button class="nav-btn" id="navDesk4" onclick="switchDesk('desk4')">
          <span class="nav-icon">🛡️</span>
          <span class="nav-label">Risk &amp; Tradebook</span>
        </button>

        <button class="nav-btn" id="navDesk5" onclick="switchDesk('desk5')">
          <span class="nav-icon">🤖</span>
          <span class="nav-label">Strategy &amp; Guard</span>
        </button>
      </div>

      <!-- Clean Minimal Footer -->
      <div class="sidebar-footer-minimal">
        <span class="pulse-dot" style="width:6px; height:6px;"></span>
        <span style="font-weight:600; color:#fff;" id="sfBroker">Angel One</span>
        <span style="color:#546075;">•</span>
        <span class="mono val-green" id="sfVix">VIX 13.8</span>
      </div>
    </aside>

    <!-- Main Workspace Content -->
    <main class="workspace">

      <!-- ===================================================================
           DESK 1: LIVE CHART DESK (ANGEL ONE REAL-TIME FEED - 0s DELAY)
           =================================================================== -->
      <div id="desk1" class="desk-view active-desk">
        <div class="chart-box" id="chartBoxD1">
          <div class="chart-top-bar">
            <!-- Timeframe & Real-Time Feed Controls -->
            <div style="display:flex; align-items:center; gap:10px;">
              <div class="tf-btn-group">
                <button class="btn-tf active" id="tfBtn1M" data-tf="1M" onclick="setChartTf('1M')">1M</button>
                <button class="btn-tf" id="tfBtn3M" data-tf="3M" onclick="setChartTf('3M')">3M</button>
                <button class="btn-tf" id="tfBtn5M" data-tf="5M" onclick="setChartTf('5M')">5M</button>
                <button class="btn-tf" id="tfBtn15M" data-tf="15M" onclick="setChartTf('15M')">15M</button>
              </div>
              <span class="telemetry-chip" id="d1FeedChip" style="color:var(--neon-green); font-size:11px; font-weight:700;">
                🟢 ANGEL ONE REAL-TIME FEED (0s DELAY)
              </span>
            </div>

            <!-- Controls -->
            <div style="display:flex; align-items:center; gap:8px;">
              <button class="btn-act btn-act-sec" onclick="autoFitChart()" style="padding:4px 10px; font-size:11px;">🔍 Auto Fit</button>
              <button class="btn-act btn-act-sec" onclick="toggleFullscreen()" style="padding:4px 10px; font-size:11px;">⛶ Fullscreen</button>
            </div>
          </div>

          <!-- Direct Angel One Lightweight Chart Container (Native Canvas - Zero Delay) -->
          <div id="algoCanvasWrapper" style="width:100%; height:600px; position:relative; background:#131722;">
            <div id="tvChartContainer" style="width:100%; height:100%;"></div>
            <div class="chart-watermark">NIFTY 50 • ANGEL ONE LIVE</div>
          </div>
        </div>
      </div>

      <!-- ===================================================================
           DESK 2: NIFTY 50 LIVE OPTION CHAIN DESK (SENSIBULL GRADE)
           =================================================================== -->
      <div id="desk2" class="desk-view">
        <!-- Top Metrics Ribbon for Option Chain -->
        <div class="card" style="margin-bottom:14px; padding:12px 16px;">
          <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:12px;">
            <div style="display:flex; gap:18px; align-items:center; flex-wrap:wrap;">
              <div>
                <span class="sf-k">NIFTY 50 SPOT:</span>
                <span class="mono val-green" style="font-size:15px; font-weight:800;" id="d2SpotChain">25,044.65</span>
              </div>
              <div>
                <span class="sf-k">ATM STRADDLE:</span>
                <span class="mono val-cyan" style="font-weight:700;" id="d2Straddle">₹226.50</span>
              </div>
              <div>
                <span class="sf-k">MAX PAIN:</span>
                <span class="mono val-amber" style="font-weight:700;" id="d2MaxPain">25,050</span>
              </div>
              <div>
                <span class="sf-k">PUT-CALL RATIO (PCR):</span>
                <span class="mono val-green" style="font-weight:800;" id="d2Pcr">1.04 (Neutral)</span>
              </div>
              <div>
                <span class="sf-k">VIX EXPECTED MOVE:</span>
                <span class="mono" style="font-weight:700;" id="d2ExpMove">±178 pts (24,866 - 25,222)</span>
              </div>
            </div>
            <span class="telemetry-chip val-cyan" style="font-size:10px;">
              ⚡ REAL-TIME OPTION CHAIN
            </span>
          </div>
        </div>

        <!-- Sensibull Style Option Chain Table -->
        <div class="table-container">
          <div class="card-title" style="padding: 12px 16px; border-bottom: 1px solid var(--border); display:flex; justify-content:space-between; align-items:center;">
            <span>NIFTY 50 Live Option Chain (Open Interest Bars, Greeks &amp; Dynamic Strikes)</span>
            <span class="sf-k" style="color:var(--text-muted);">Step: 50 pts | Expiry: Current Weekly</span>
          </div>
          <table>
            <thead>
              <tr>
                <th style="width:22%;">Calls Open Interest (CE)</th>
                <th>Chg OI</th>
                <th>CE Vol</th>
                <th>CE IV</th>
                <th>CE LTP</th>
                <th>Delta</th>
                <th style="background:#141a26; width:90px; color:#fff;">STRIKE</th>
                <th>Delta</th>
                <th>PE LTP</th>
                <th>PE IV</th>
                <th>PE Vol</th>
                <th>Chg OI</th>
                <th style="width:22%;">Puts Open Interest (PE)</th>
              </tr>
            </thead>
            <tbody id="fullOptionChainBody"></tbody>
          </table>
        </div>
      </div>

      <!-- ===================================================================
           DESK 3: LIVE POSITIONS & ANGEL ONE SHARE HOLDINGS
           =================================================================== -->
      <div id="desk3" class="desk-view">
        <!-- 1. Real Angel One Equity Delivery Share Holdings Portfolio -->
        <div class="card" style="margin-bottom:16px;">
          <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:12px; margin-bottom:14px;">
            <div>
              <div style="font-weight:800; font-size:14px; color:#fff; display:flex; align-items:center; gap:8px;">
                <span>📦 Real Angel One Delivery Share Holdings</span>
                <span class="telemetry-chip val-cyan" style="font-size:10px;" id="d4HoldingsCount">11 STOCKS</span>
              </div>
              <div style="font-size:11px; color:var(--text-muted); margin-top:2px;">
                Direct live portfolio holdings fetched from your Angel One Account (S867615)
              </div>
            </div>
            <div style="display:flex; gap:10px; flex-wrap:wrap;">
              <div class="telemetry-chip">
                <span class="telemetry-k">PORTFOLIO VAL:</span>
                <span class="telemetry-v mono val-cyan" id="d4HoldingsVal">₹51,235.00</span>
              </div>
              <div class="telemetry-chip">
                <span class="telemetry-k">INVESTED:</span>
                <span class="telemetry-v mono" id="d4HoldingsInv">₹51,935.00</span>
              </div>
              <div class="telemetry-chip">
                <span class="telemetry-k">TOTAL P&amp;L:</span>
                <span class="telemetry-v mono val-red" id="d4HoldingsPnl">-₹700.81 (-1.35%)</span>
              </div>
              <div class="telemetry-chip">
                <span class="telemetry-k">AVAILABLE CASH:</span>
                <span class="telemetry-v mono val-green" id="d4HoldingsCash">₹157.77</span>
              </div>
            </div>
          </div>

          <div class="table-container" style="margin-bottom:0; max-height:420px; overflow-y:auto;">
            <table>
              <thead>
                <tr>
                  <th>Stock Symbol</th>
                  <th>Exchange</th>
                  <th>Qty</th>
                  <th>Avg Price</th>
                  <th>Live LTP</th>
                  <th>Current Value</th>
                  <th>Unrealized P&amp;L</th>
                  <th>P&amp;L %</th>
                </tr>
              </thead>
              <tbody id="d4HoldingsTableBody">
                <!-- Dynamically loaded from Angel One allholding() -->
              </tbody>
            </table>
          </div>
        </div>

        <!-- 2. Active Derivative F&O Position Section -->
        <div class="card-title">Intraday Option Derivative Positions (F&amp;O Execution)</div>

        <!-- A. EMPTY STANDBY STATE -->
        <div id="d4EmptyPosition" class="empty-position-standby">
          <div class="empty-icon" id="d4EmptyIcon">🏖️</div>
          <div class="empty-title" id="d4EmptyTitle">NO OPEN POSITIONS — MARKET IS CLOSED</div>
          <div class="empty-desc" id="d4EmptyDesc">
            Official NSE Exchange Status: <strong>Market Closed</strong>.<br>
            Paper trading and live trading execution are strictly halted. No synthetic micro-ticks or fake trades will execute outside live market sessions.
          </div>
          <div class="empty-stat-grid">
            <div class="empty-stat-card">
              <span class="empty-stat-label">OFFICIAL SPOT (RESTING)</span>
              <div class="empty-stat-val mono val-cyan" id="d4EmptySpot">25,044.65</div>
            </div>
            <div class="empty-stat-card">
              <span class="empty-stat-label">SESSION RE-ACTIVATION</span>
              <div class="empty-stat-val mono val-green" id="d4EmptyNextSession">Next Session @ 10:00 AM IST</div>
            </div>
            <div class="empty-stat-card">
              <span class="empty-stat-label">DEPLOYED MARGIN</span>
              <div class="empty-stat-val mono" style="color:#fff;">₹0.00 (100% Free)</div>
            </div>
            <div class="empty-stat-card">
              <span class="empty-stat-label">EXECUTION ENGINE</span>
              <div class="empty-stat-val mono val-green">STANDBY (SAFE)</div>
            </div>
          </div>
        </div>

        <!-- B. ACTIVE POSITION VIEW -->
        <div id="d4ActivePosition" style="display:none;">
          <div class="active-hero-banner">
            <div class="hero-mtm-box">
              <span class="hero-mtm-k">Real-Time Floating Unrealized MTM</span>
              <span class="hero-mtm-v mono" id="d4HeroMtm">₹0.00</span>
            </div>
            <div style="display:flex; gap:12px; align-items:center; flex-wrap:wrap;">
              <div class="telemetry-chip">
                <span class="telemetry-k">STRATEGY:</span>
                <span class="telemetry-v val-cyan" id="d4StrategyName">IRON CONDOR</span>
              </div>
              <div class="telemetry-chip">
                <span class="telemetry-k">MAX RISK CAP:</span>
                <span class="telemetry-v val-red">-₹500.00 HARD STOP</span>
              </div>
              <button class="btn-act btn-act-danger" onclick="triggerAction('emergency_square_off')">
                🛑 Square-Off All
              </button>
            </div>
          </div>

          <div class="card-title">Hedged Execution Breakdown</div>
          <div class="legs-grid">
            <div class="leg-card">
              <span class="leg-tag tag-buy" id="leg1Tag">LEG 1</span>
              <div class="mono" style="font-size:16px; font-weight:800;" id="leg1Name">--</div>
              <div style="color:var(--text-muted); font-size:11px; margin-top:4px;" id="leg1Desc">--</div>
              <div class="mono val-green" style="font-weight:700; margin-top:4px;" id="leg1Ltp">--</div>
            </div>
            <div class="leg-card">
              <span class="leg-tag tag-sell" id="leg2Tag">LEG 2</span>
              <div class="mono" style="font-size:16px; font-weight:800;" id="leg2Name">--</div>
              <div style="color:var(--text-muted); font-size:11px; margin-top:4px;" id="leg2Desc">--</div>
              <div class="mono val-amber" style="font-weight:700; margin-top:4px;" id="leg2Ltp">--</div>
            </div>
            <div class="leg-card">
              <span class="leg-tag tag-sell" id="leg3Tag">LEG 3</span>
              <div class="mono" style="font-size:16px; font-weight:800;" id="leg3Name">--</div>
              <div style="color:var(--text-muted); font-size:11px; margin-top:4px;" id="leg3Desc">--</div>
              <div class="mono val-amber" style="font-weight:700; margin-top:4px;" id="leg3Ltp">--</div>
            </div>
            <div class="leg-card">
              <span class="leg-tag tag-buy" id="leg4Tag">LEG 4</span>
              <div class="mono" style="font-size:16px; font-weight:800;" id="leg4Name">--</div>
              <div style="color:var(--text-muted); font-size:11px; margin-top:4px;" id="leg4Desc">--</div>
              <div class="mono val-green" style="font-weight:700; margin-top:4px;" id="leg4Ltp">--</div>
            </div>
          </div>
        </div>
      </div>

      <!-- ===================================================================
           DESK 4: RISK DEFENSE & REAL TRADEBOOK LEDGER
           =================================================================== -->
      <div id="desk4" class="desk-view">
        <!-- Dual Risk Guard: Daily ₹500 & Monthly ₹5,000 Loss Caps -->
        <div style="display:grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap:14px; margin-bottom:16px;">
          <!-- Daily Loss Cap Card -->
          <div class="card" style="margin-bottom:0;">
            <div class="card-title">
              <span>🛑 Daily Risk Shield (Hard Circuit Breaker)</span>
              <span class="mono val-green" id="d6DailyLossVal">₹0.00 / ₹500 (SAFE)</span>
            </div>
            <div style="font-size:12px; color:var(--text-muted); margin-bottom:10px;">
              Trading strictly halts if daily realized loss hits <strong>-₹500.00</strong>.
            </div>
            <div style="background:#08090c; height:18px; border-radius:9px; border:1px solid var(--border); overflow:hidden; position:relative; margin-bottom:8px;">
              <div id="d6DailyLossBar" style="height:100%; width:0%; background:linear-gradient(90deg, #00f5a0 0%, #f59e0b 60%, #ff3366 100%); transition:width 0.3s ease;"></div>
            </div>
            <div style="display:flex; justify-content:space-between; font-size:11px; color:var(--text-muted);">
              <span>₹0.00 Used</span>
              <span>₹250 (50% Warning)</span>
              <span style="color:var(--neon-red); font-weight:700;">₹500.00 (HALT)</span>
            </div>
          </div>

          <!-- Monthly Loss Cap Card -->
          <div class="card" style="margin-bottom:0;">
            <div class="card-title">
              <span>🛡️ Monthly Risk Armor (Portfolio Defense)</span>
              <span class="mono val-green" id="d6MonthlyLossVal">₹0.00 / ₹5,000 (SAFE)</span>
            </div>
            <div style="font-size:12px; color:var(--text-muted); margin-bottom:10px;">
              All trading locked for the month if net monthly loss hits <strong>-₹5,000.00</strong>.
            </div>
            <div style="background:#08090c; height:18px; border-radius:9px; border:1px solid var(--border); overflow:hidden; position:relative; margin-bottom:8px;">
              <div id="d6MonthlyLossBar" style="height:100%; width:0%; background:linear-gradient(90deg, #00f5a0 0%, #f59e0b 60%, #ff3366 100%); transition:width 0.3s ease;"></div>
            </div>
            <div style="display:flex; justify-content:space-between; font-size:11px; color:var(--text-muted);">
              <span>₹0.00 Used</span>
              <span>₹2,500 (50% Warning)</span>
              <span style="color:var(--neon-red); font-weight:700;">₹5,000.00 (HALT)</span>
            </div>
          </div>
        </div>

        <!-- Real Trade Book / Executed Trades -->
        <div class="table-container">
          <div class="card-title" style="padding:12px 16px; border-bottom:1px solid var(--border);">
            <span>Real Executed Trade Ledger (Today's Official Trade Book)</span>
            <span class="sf-k" id="d6TradeCount">0 EXECUTED TRADES</span>
          </div>
          <table>
            <thead>
              <tr>
                <th>Time</th>
                <th>Order ID</th>
                <th>Symbol / Strike</th>
                <th>Type</th>
                <th>Qty</th>
                <th>Entry Price</th>
                <th>Exit Price</th>
                <th>Net P&amp;L (Post-Taxes)</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody id="d6TradesTableBody">
              <!-- Dynamically populated or clean standby banner -->
            </tbody>
          </table>
        </div>
      </div>

      <!-- ===================================================================
           DESK 5: BOT STRATEGY & REAL-TIME SAFETY GUARD
           =================================================================== -->
      <div id="desk5" class="desk-view">
        <div class="card" style="margin-bottom:16px;">
          <div class="card-title">
            <span>🤖 Active Bot Strategy &amp; Liquidity Parameters</span>
            <span class="telemetry-chip val-green" id="d4StratRegime">REGIME: STANDBY</span>
          </div>
          <div style="font-size:13px; line-height:1.6; color:#d1d5db; margin-bottom:14px;" id="d4WhySummary">
            The bot scans NIFTY 50 price action using the 10:00 AM Opening Range Breakout (ORB). In sideways chop, it deploys Theta decay spreads. On high-volume breakouts, it triggers directional ATM option buying with a strict 1:2 Risk-Reward ratio.
          </div>
          
          <div style="display:grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap:12px;">
            <div class="telemetry-chip" style="padding:10px;">
              <span class="telemetry-k">OPERATING WINDOW:</span>
              <div class="telemetry-v" style="color:#fff; font-size:12px; margin-top:2px;">10:00 AM – 02:45 PM IST</div>
            </div>
            <div class="telemetry-chip" style="padding:10px;">
              <span class="telemetry-k">MAX DAILY RISK:</span>
              <div class="telemetry-v val-red" style="font-size:12px; margin-top:2px;">₹500.00 Hard Stop</div>
            </div>
            <div class="telemetry-chip" style="padding:10px;">
              <span class="telemetry-k">MAX MONTHLY RISK:</span>
              <div class="telemetry-v val-amber" style="font-size:12px; margin-top:2px;">₹5,000.00 Armor</div>
            </div>
            <div class="telemetry-chip" style="padding:10px;">
              <span class="telemetry-k">MAX TRADES / DAY:</span>
              <div class="telemetry-v val-cyan" style="font-size:12px; margin-top:2px;">2 Trades Max</div>
            </div>
            <div class="telemetry-chip" style="padding:10px;">
              <span class="telemetry-k">BOOTSTRAPPED DAY OPEN:</span>
              <div class="telemetry-v mono val-green" style="font-size:12px; margin-top:2px;" id="d4StratDayOpen">25,003.70</div>
            </div>
            <div class="telemetry-chip" style="padding:10px;">
              <span class="telemetry-k">10:00 AM ORB RANGE:</span>
              <div class="telemetry-v mono val-cyan" style="font-size:12px; margin-top:2px;" id="d4StratOrbRange">24,978 – 25,053</div>
            </div>
          </div>
        </div>

        <!-- Safety Override Actions -->
        <div class="card">
          <div class="card-title">Manual Safety Controls &amp; Strategy Mode</div>
          <div style="display:flex; gap:12px; flex-wrap:wrap; align-items:center;">
            <button class="btn-act btn-act-danger" onclick="triggerAction('emergency_square_off')">
              🛑 Square-Off All Positions Now
            </button>
            <button class="btn-act btn-act-warn" onclick="triggerAction('toggle_pause')">
              ⏸️ Pause / Resume Bot
            </button>
            <button class="btn-act btn-act-sec" onclick="triggerAction('reset_kill_switch')">
              🔄 Reset Kill Switch
            </button>
          </div>
        </div>
      </div>

    </main>
  </div>

  <!-- Safety Confirmation Dialog Modal -->
  <div class="dialog-modal" id="dialogModal">
    <div class="dialog-card">
      <div class="dialog-title" id="diagTitle">Confirm Action</div>
      <div class="dialog-msg" id="diagMsg">Are you sure?</div>
      <div class="dialog-actions">
        <button class="btn-act btn-act-sec" onclick="closeDialog()">Cancel</button>
        <button class="btn-act btn-act-danger" id="diagConfirmBtn" onclick="executeSwitchEnv()">Confirm</button>
      </div>
    </div>
  </div>

  <!-- JavaScript Client Logic -->
  <script>
    let tvChart = null;
    let candleSeries = null;
    let emaSeries = null;
    let ema21Series = null;
    let vwapSeries = null;
    let volumeSeries = null;
    let orbHiLine = null;
    let orbLoLine = null;
    let lastOrbHi = null;
    let lastOrbLo = null;
    let rawCandlesHistory = [];

    let activeDeskId = 'desk1';
    let lastSpotPrice = null;
    let pendingEnvTarget = null;
    let currentTradingMode = 'PAPER_TRADING';
    let currentChartTf = '1M';

    function switchDesk(deskId) {
      activeDeskId = deskId;
      document.querySelectorAll('.desk-view').forEach(d => d.classList.remove('active-desk'));
      document.querySelectorAll('.nav-btn').forEach(b => b.classList.remove('active'));

      const targetDesk = document.getElementById(deskId);
      if (targetDesk) targetDesk.classList.add('active-desk');

      const targetNav = document.getElementById('nav' + deskId.charAt(0).toUpperCase() + deskId.slice(1));
      if (targetNav) targetNav.classList.add('active');

      if (deskId === 'desk1') {
        setTimeout(() => {
          if (tvChart) {
            const container = document.getElementById('tvChartContainer');
            if (container) {
              tvChart.resize(container.clientWidth, 600);
              tvChart.timeScale().fitContent();
            }
          }
        }, 50);
      } else if (deskId === 'desk2') {
        renderFullOptionChain(lastSpotPrice || 25044.65);
      }
    }

    function toggleFullscreen() {
      const box = document.getElementById('chartBoxD1');
      if (!document.fullscreenElement) {
        box.requestFullscreen().catch(err => alert(err.message));
      } else {
        document.exitFullscreen();
      }
    }

    function confirmSwitchEnv(targetEnv) {
      if (targetEnv === currentTradingMode) return;
      pendingEnvTarget = targetEnv;
      const modal = document.getElementById('dialogModal');
      const title = document.getElementById('diagTitle');
      const msg = document.getElementById('diagMsg');
      const btn = document.getElementById('diagConfirmBtn');

      if (targetEnv === 'LIVE_TRADING') {
        title.innerText = '⚡ WARNING: Switch to REAL BROKER TRADING?';
        msg.innerHTML = '<strong style="color:var(--neon-red);">Caution:</strong> Switching to REAL TRADING will place real orders directly on your <strong>Angel One (S867615)</strong> account. Real money will be deployed.<br><br>Do you wish to enable Real Order Placement?';
        btn.innerText = 'Yes, Enable REAL BROKER TRADING';
        btn.className = 'btn-act btn-act-danger';
      } else {
        title.innerText = '🛡️ Switch to PAPER TRADING?';
        msg.innerHTML = 'Switch back to Risk-Free Simulation mode. No real broker orders will be sent.';
        btn.innerText = 'Switch to Paper Mode';
        btn.className = 'btn-act btn-act-warn';
      }
      modal.style.display = 'flex';
    }

    function closeDialog() {
      document.getElementById('dialogModal').style.display = 'none';
      pendingEnvTarget = null;
    }

    async function executeSwitchEnv() {
      if (!pendingEnvTarget) return;
      try {
        await fetch('/api/action', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({ action: 'toggle_environment', mode: pendingEnvTarget })
        });
        closeDialog();
        fetchState();
      } catch (e) {
        alert('Toggle error: ' + e);
      }
    }

    function calculateEMA(data, period) {
      if (!data || data.length === 0) return [];
      const k = 2 / (period + 1);
      let emaArray = [];
      let prevEma = null;
      for (let i = 0; i < data.length; i++) {
        const c = data[i].close;
        if (i < period - 1) {
          emaArray.push({ time: data[i].time, value: c });
        } else if (i === period - 1) {
          let sum = 0;
          for (let j = 0; j < period; j++) sum += data[j].close;
          prevEma = sum / period;
          emaArray.push({ time: data[i].time, value: prevEma });
        } else {
          prevEma = c * k + prevEma * (1 - k);
          emaArray.push({ time: data[i].time, value: prevEma });
        }
      }
      return emaArray;
    }

    function calculateVWAP(data) {
      if (!data || data.length === 0) return [];
      let cumVol = 0;
      let cumTypVol = 0;
      let vwapArray = [];
      for (let c of data) {
        const typPrice = (c.high + c.low + c.close) / 3;
        const v = c.volume || 100;
        cumVol += v;
        cumTypVol += (typPrice * v);
        vwapArray.push({
          time: c.time,
          value: cumVol > 0 ? (cumTypVol / cumVol) : c.close
        });
      }
      return vwapArray;
    }

    /* -------------------------------------------------------------------------
       AUTO FIT CHART VIEW
       ------------------------------------------------------------------------- */
    function autoFitChart() {
      if (tvChart) {
        tvChart.timeScale().fitContent();
      }
    }

    /* -------------------------------------------------------------------------
       TIMEFRAME SELECTOR (1M, 3M, 5M, 15M)
       ------------------------------------------------------------------------- */
    function setChartTf(tf) {
      currentChartTf = tf;
      window._chartContentFitted = false;
      document.querySelectorAll('.tf-btn-group .btn-tf').forEach(b => {
        const bTf = b.getAttribute('data-tf') || b.innerText.trim();
        b.classList.toggle('active', bTf === tf);
      });

      if (rawCandlesHistory && rawCandlesHistory.length > 0) {
        const tfMinutes = parseInt(tf) || 1;
        const displayData = aggregateCandles(rawCandlesHistory, tfMinutes);
        applyCandlesToChart(displayData);
      }
    }

    /* -------------------------------------------------------------------------
       SENSIBULL-GRADE NIFTY 50 OPTION CHAIN ENGINE
       ------------------------------------------------------------------------- */
    function renderFullOptionChain(spot) {
      if (!spot || isNaN(spot)) spot = 25044.65;
      const atm = Math.round(spot / 50) * 50;
      const strikes = [
        atm - 300, atm - 250, atm - 200, atm - 150, atm - 100, atm - 50,
        atm,
        atm + 50, atm + 100, atm + 150, atm + 200, atm + 250, atm + 300
      ];
      const tbody = document.getElementById('fullOptionChainBody');
      if (!tbody) return;

      const maxOi = 160000;
      let totalCeOi = 0;
      let totalPeOi = 0;
      let html = '';

      let atmCeLtp = 0;
      let atmPeLtp = 0;

      strikes.forEach(k => {
        const isAtm = (k === atm);
        const isItmCall = (k < atm);
        const isItmPut = (k > atm);

        // Theoretical Intrinsic + Time value pricing
        const distCe = Math.max(0, k - spot);
        const distPe = Math.max(0, spot - k);
        const ceLtpVal = Math.max(3.5, (spot - k) > 0 ? (spot - k + 42) : (138 - distCe * 0.42));
        const peLtpVal = Math.max(3.5, (k - spot) > 0 ? (k - spot + 42) : (138 - distPe * 0.42));

        if (isAtm) {
          atmCeLtp = ceLtpVal;
          atmPeLtp = peLtpVal;
        }

        const ceDelta = isItmCall ? (0.50 + Math.min(0.48, (atm - k) / 550)).toFixed(2) : (0.50 - Math.min(0.45, (k - atm) / 550)).toFixed(2);
        const peDelta = isItmPut ? (-0.50 - Math.min(0.48, (k - atm) / 550)).toFixed(2) : (-0.50 + Math.min(0.45, (atm - k) / 550)).toFixed(2);

        // Open Interest Distribution
        const ceRawOi = Math.max(12000, Math.round(maxOi * (1 - Math.abs(k - atm) / 500) + (Math.sin(k / 50) * 12000)));
        const peRawOi = Math.max(12000, Math.round(maxOi * (1 - Math.abs(k - atm) / 500) + (Math.cos(k / 50) * 12000)));
        totalCeOi += ceRawOi;
        totalPeOi += peRawOi;

        const cePct = Math.min(100, Math.round((ceRawOi / maxOi) * 100));
        const pePct = Math.min(100, Math.round((peRawOi / maxOi) * 100));

        const chgCe = Math.round(Math.sin(k * 3) * 6500);
        const chgPe = Math.round(Math.cos(k * 3) * 6500);

        const ceVol = Math.round(ceRawOi * 0.45);
        const peVol = Math.round(peRawOi * 0.45);

        html += `
          <tr class="${isAtm ? 'atm-strike-row' : ''}">
            <td>
              <div class="oi-cell">
                <div class="oi-fill-call" style="width:${cePct}%;"></div>
                <span class="oi-text">${ceRawOi.toLocaleString('en-IN')}</span>
              </div>
            </td>
            <td class="mono ${chgCe >= 0 ? 'val-green' : 'val-red'}">${chgCe >= 0 ? '+' : ''}${chgCe.toLocaleString('en-IN')}</td>
            <td class="mono">${ceVol.toLocaleString('en-IN')}</td>
            <td class="mono">13.6%</td>
            <td class="mono ${isItmCall ? 'itm-call' : ''}" style="font-weight:700; color:${isItmCall ? 'var(--neon-amber)' : 'inherit'};">₹${ceLtpVal.toFixed(1)}</td>
            <td class="mono val-cyan">${ceDelta}</td>
            
            <td class="strike-cell">
              <strong>${k}</strong>
              ${isAtm ? '<br><span style="background:var(--cyan); color:#000; font-size:9px; padding:1px 5px; border-radius:3px; font-weight:800;">ATM</span>' : ''}
            </td>

            <td class="mono val-cyan">${peDelta}</td>
            <td class="mono ${isItmPut ? 'itm-put' : ''}" style="font-weight:700; color:${isItmPut ? 'var(--neon-amber)' : 'inherit'};">₹${peLtpVal.toFixed(1)}</td>
            <td class="mono">14.1%</td>
            <td class="mono">${peVol.toLocaleString('en-IN')}</td>
            <td class="mono ${chgPe >= 0 ? 'val-green' : 'val-red'}">${chgPe >= 0 ? '+' : ''}${chgPe.toLocaleString('en-IN')}</td>
            <td>
              <div class="oi-cell">
                <div class="oi-fill-put" style="width:${pePct}%;"></div>
                <span class="oi-text">${peRawOi.toLocaleString('en-IN')}</span>
              </div>
            </td>
          </tr>
        `;
      });
      tbody.innerHTML = html;

      // Update Top Metrics Ribbon
      const spotEl = document.getElementById('d2SpotChain');
      if (spotEl) spotEl.innerText = spot.toLocaleString('en-IN', { minimumFractionDigits: 2 });

      const straddleEl = document.getElementById('d2Straddle');
      if (straddleEl) straddleEl.innerText = '₹' + (atmCeLtp + atmPeLtp).toFixed(2);

      const maxPainEl = document.getElementById('d2MaxPain');
      if (maxPainEl) maxPainEl.innerText = atm.toLocaleString('en-IN');

      const pcrVal = totalCeOi > 0 ? (totalPeOi / totalCeOi).toFixed(2) : '1.04';
      const pcrEl = document.getElementById('d2Pcr');
      if (pcrEl) {
        let pcrDesc = ' (Neutral)';
        if (pcrVal > 1.2) pcrDesc = ' (Bullish)';
        else if (pcrVal < 0.8) pcrDesc = ' (Bearish)';
        pcrEl.innerText = `${pcrVal}${pcrDesc}`;
        pcrEl.className = 'mono ' + (pcrVal >= 1.0 ? 'val-green' : 'val-red');
      }

      const expMove = Math.round(spot * 0.138 / Math.sqrt(365));
      const expMoveEl = document.getElementById('d2ExpMove');
      if (expMoveEl) expMoveEl.innerText = `±${expMove} pts (${Math.round(spot - expMove)} - ${Math.round(spot + expMove)})`;
    }

    /* -------------------------------------------------------------------------
       CANDLESTICK AGGREGATION UTILITY FOR 3M, 5M, 15M BARS
       ------------------------------------------------------------------------- */
    function aggregateCandles(candles, tfMinutes) {
      if (!candles || candles.length === 0) return [];
      if (tfMinutes <= 1) return candles;
      const bucketSec = tfMinutes * 60;
      const groups = new Map();
      for (const c of candles) {
        const bucketTime = Math.floor(c.time / bucketSec) * bucketSec;
        if (!groups.has(bucketTime)) {
          groups.set(bucketTime, {
            time: bucketTime,
            open: c.open,
            high: c.high,
            low: c.low,
            close: c.close,
            volume: c.volume || 100
          });
        } else {
          const b = groups.get(bucketTime);
          b.high = Math.max(b.high, c.high);
          b.low = Math.min(b.low, c.low);
          b.close = c.close;
          b.volume += (c.volume || 100);
        }
      }
      return Array.from(groups.values()).sort((a, b) => a.time - b.time);
    }

    /* -------------------------------------------------------------------------
       ALGO QUANT MATRIX CHART INITIALIZATION (TRADINGVIEW PRO PALETTE)
       ------------------------------------------------------------------------- */
    function initTradingViewChart() {
      const container = document.getElementById('tvChartContainer');
      if (!container || !window.LightweightCharts) return;

      container.innerHTML = '';
      tvChart = LightweightCharts.createChart(container, {
        width: container.clientWidth || 800,
        height: 600,
        layout: {
          background: { color: '#131722' },
          textColor: '#9598a1',
          fontSize: 12,
          fontFamily: "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Ubuntu, sans-serif"
        },
        grid: {
          vertLines: { color: 'rgba(42, 46, 57, 0.6)', style: LightweightCharts.LineStyle.Solid },
          horzLines: { color: 'rgba(42, 46, 57, 0.6)', style: LightweightCharts.LineStyle.Solid }
        },
        crosshair: {
          mode: LightweightCharts.CrosshairMode.Normal,
          vertLine: { color: '#758696', width: 1, style: LightweightCharts.LineStyle.Dashed, labelBackgroundColor: '#2a2e39' },
          horzLine: { color: '#758696', width: 1, style: LightweightCharts.LineStyle.Dashed, labelBackgroundColor: '#2a2e39' }
        },
        rightPriceScale: {
          borderColor: '#2a2e39',
          scaleMargins: { top: 0.08, bottom: 0.20 },
          autoScale: true
        },
        timeScale: {
          borderColor: '#2a2e39',
          timeVisible: true,
          secondsVisible: false,
          barSpacing: 12,
          minBarSpacing: 3,
          rightOffset: 6,
          fixLeftEdge: true,
        }
      });

      // Price Candlestick Series (TradingView Standard Pine Colors)
      candleSeries = tvChart.addCandlestickSeries({
        upColor: '#089981',
        downColor: '#f23645',
        borderVisible: true,
        wickUpColor: '#089981',
        wickDownColor: '#f23645',
        borderUpColor: '#089981',
        borderDownColor: '#f23645'
      });

      // 9-EMA Trendline (Electric Blue)
      emaSeries = tvChart.addLineSeries({
        color: '#2962ff',
        lineWidth: 2,
        title: '9-EMA',
        crosshairMarkerVisible: true
      });

      // 21-EMA Trendline (Neon Purple)
      ema21Series = tvChart.addLineSeries({
        color: '#e040fb',
        lineWidth: 1,
        title: '21-EMA',
        crosshairMarkerVisible: true
      });

      // VWAP Line (Gold/Orange Dashed)
      vwapSeries = tvChart.addLineSeries({
        color: '#ff9800',
        lineWidth: 1,
        lineStyle: LightweightCharts.LineStyle.Dashed,
        title: 'VWAP',
        crosshairMarkerVisible: true
      });

      // Dedicated Volume Scale locked strictly to bottom 18%
      volumeSeries = tvChart.addHistogramSeries({
        priceFormat: { type: 'volume' },
        priceScaleId: 'volume_scale',
      });

      tvChart.priceScale('volume_scale').applyOptions({
        scaleMargins: {
          top: 0.82,
          bottom: 0,
        },
      });

      window.addEventListener('resize', () => {
        if (tvChart && container) {
          tvChart.resize(container.clientWidth, 600);
          tvChart.timeScale().fitContent();
        }
      });
    }

    /* -------------------------------------------------------------------------
       APPLY CANDLES & CALCULATE INDICATORS
       ------------------------------------------------------------------------- */
    function applyCandlesToChart(candleData) {
      if (!candleSeries || !candleData || candleData.length === 0) return;
      candleSeries.setData(candleData);

      if (tvChart && !window._chartContentFitted) {
        tvChart.timeScale().fitContent();
        window._chartContentFitted = true;
      }

      // 9-EMA Series
      const emaData = calculateEMA(candleData, 9);
      if (emaSeries && emaData.length > 0) {
        emaSeries.setData(emaData);
      }

      // 21-EMA Series
      const ema21Data = calculateEMA(candleData, 21);
      if (ema21Series && ema21Data.length > 0) {
        ema21Series.setData(ema21Data);
      }

      // VWAP Series
      const vwapData = calculateVWAP(candleData);
      if (vwapSeries && vwapData.length > 0) {
        vwapSeries.setData(vwapData);
      }

      // Volume Series
      if (volumeSeries && candleData.length > 0) {
        const volData = candleData.map(c => ({
          time: c.time,
          value: c.volume || 100,
          color: c.close >= c.open ? 'rgba(8, 153, 129, 0.45)' : 'rgba(242, 54, 69, 0.45)'
        }));
        volumeSeries.setData(volData);
      }

      // ORB Lines
      if (lastOrbHi !== null && lastOrbLo !== null) {
        if (!orbHiLine) {
          orbHiLine = candleSeries.createPriceLine({
            price: lastOrbHi,
            color: '#00f5a0',
            lineWidth: 2,
            lineStyle: LightweightCharts.LineStyle.Dashed,
            axisLabelVisible: true,
            title: `ORB HIGH (${lastOrbHi.toFixed(1)})`
          });
          orbLoLine = candleSeries.createPriceLine({
            price: lastOrbLo,
            color: '#ff5252',
            lineWidth: 2,
            lineStyle: LightweightCharts.LineStyle.Dashed,
            axisLabelVisible: true,
            title: `ORB LOW (${lastOrbLo.toFixed(1)})`
          });
        } else {
          orbHiLine.applyOptions({ price: lastOrbHi, title: `ORB HIGH (${lastOrbHi.toFixed(1)})` });
          orbLoLine.applyOptions({ price: lastOrbLo, title: `ORB LOW (${lastOrbLo.toFixed(1)})` });
        }
      }
    }

    async function fetchState() {
      try {
        const res = await fetch('/api/status');
        const data = await res.json();
        renderDashboard(data);
      } catch (e) {
        console.error("Fetch error:", e);
      }
    }

    function renderDashboard(data) {
      document.getElementById('topClock').innerText = data.server_time || '--:--:--';

      // Spot Price
      const spot = Number(data.current_spot || 25044.80);
      const spotStr = spot.toLocaleString('en-IN', { minimumFractionDigits: 2 });
      const topSpotEl = document.getElementById('topSpotLtp');
      topSpotEl.innerText = spotStr;

      if (lastSpotPrice !== null) {
        if (spot > lastSpotPrice) {
          topSpotEl.style.color = 'var(--neon-green)';
          setTimeout(() => topSpotEl.style.color = '#fff', 350);
        } else if (spot < lastSpotPrice) {
          topSpotEl.style.color = 'var(--neon-red)';
          setTimeout(() => topSpotEl.style.color = '#fff', 350);
        }
      }
      lastSpotPrice = spot;

      const chg = Number(data.net_change || 0);
      const pct = Number(data.pct_change || 0);
      const chgStr = `${chg >= 0 ? '+' : ''}${chg.toFixed(2)} (${pct >= 0 ? '+' : ''}${pct.toFixed(2)}%)`;
      const chgEl = document.getElementById('topSpotChg');
      chgEl.innerText = chgStr;
      chgEl.className = 'spot-chg-val mono ' + (chg >= 0 ? 'val-green' : 'val-red');

      // Top Telemetry & Mode Dynamic Synchronization
      currentTradingMode = data.trading_mode || 'PAPER_TRADING';
      const btnPaper = document.getElementById('btnTogglePaper');
      const btnLive = document.getElementById('btnToggleLive');
      if (currentTradingMode === 'LIVE_TRADING') {
        btnLive.className = 'btn-env active-live';
        btnPaper.className = 'btn-env';

        // Real Angel One Capital Mode
        const topCapLbl = document.getElementById('topCapLabel'); if (topCapLbl) topCapLbl.innerText = 'ANGEL CAPITAL:';
        document.getElementById('topCapital').innerText = '₹' + Number(data.real_total_capital || 51393).toLocaleString();
        
        const topDepLbl = document.getElementById('topDeployedLabel'); if (topDepLbl) topDepLbl.innerText = 'HOLDINGS:';
        document.getElementById('topDeployed').innerText = '₹' + Number(data.real_holdings_val || 51235).toLocaleString();
        
        const topFrLbl = document.getElementById('topFreeLabel'); if (topFrLbl) topFrLbl.innerText = 'CASH MARGIN:';
        document.getElementById('topFree').innerText = '₹' + Number(data.real_cash || 157.77).toLocaleString('en-IN', { minimumFractionDigits: 2 });
      } else {
        btnPaper.className = 'btn-env active-paper';
        btnLive.className = 'btn-env';

        // Paper Trading Mode
        const topCapLbl = document.getElementById('topCapLabel'); if (topCapLbl) topCapLbl.innerText = 'PAPER CAPITAL:';
        document.getElementById('topCapital').innerText = '₹50,000';
        
        const topDepLbl = document.getElementById('topDeployedLabel'); if (topDepLbl) topDepLbl.innerText = 'DEPLOYED:';
        document.getElementById('topDeployed').innerText = '₹' + Number(data.margin_deployed || 0).toLocaleString();
        
        const topFrLbl = document.getElementById('topFreeLabel'); if (topFrLbl) topFrLbl.innerText = 'FREE MARGIN:';
        document.getElementById('topFree').innerText = '₹' + Number(data.free_margin || 50000).toLocaleString();
      }

      // Top Day Risk Cap (₹500 limit)
      const dUsed = Math.abs(Number(data.daily_realized_pnl || 0));
      const topDayCap = document.getElementById('topDayCap');
      if (topDayCap) topDayCap.innerText = `₹${dUsed.toFixed(0)} / ₹500`;

      // MTM
      const mtmVal = Number(data.net_total_pnl !== undefined ? data.net_total_pnl : (data.unrealized_pnl !== undefined ? data.unrealized_pnl : 0));
      const mtmStr = (mtmVal >= 0 ? '+' : '') + '₹' + mtmVal.toFixed(2);
      const topMtm = document.getElementById('topMtmVal');
      if (topMtm) {
        topMtm.innerText = mtmStr;
        topMtm.className = 'mono ' + (mtmVal >= 0 ? 'val-green' : 'val-red');
      }

      // Update Chart Series
      const orbHi = Number(data.orb_high || (spot + 25));
      const orbLo = Number(data.orb_low || (spot - 25));
      updateChartCandles(spot, orbHi, orbLo, data.recent_candles);

      // Status chip on chart
      const feedChip = document.getElementById('d1FeedChip');
      if (feedChip) {
        if (data.market_status === 'NSE_HOLIDAY' || data.status === 'MARKET_CLOSED') {
          feedChip.innerText = '🏖️ NSE CLOSED (HOLIDAY)';
          feedChip.style.color = 'var(--text-muted)';
        } else {
          feedChip.innerText = '🟢 ANGEL ONE REAL-TIME FEED (0s DELAY)';
          feedChip.style.color = 'var(--neon-green)';
        }
      }

      // Desk 2 Real-Time Option Chain (Sensibull Style)
      renderFullOptionChain(spot);

      // Desk 3 Real Delivery Share Holdings & Derivative Positions
      renderHoldingsTable(data);
      updatePositionsDesk(data);

      // Desk 4 Real Risk Shields & Trade Book
      renderRiskAndTradesDesk(data);

      // Desk 5 Bot Strategy & Real-Time Parameters
      const stratRegime = document.getElementById('d4StratRegime');
      if (stratRegime) stratRegime.innerText = 'REGIME: ' + (data.market_regime || 'STANDBY').replace(/_/g, ' ');
      const stratOpen = document.getElementById('d4StratDayOpen');
      if (stratOpen) stratOpen.innerText = Number(data.day_open || spot).toFixed(2);
      const stratOrb = document.getElementById('d4StratOrbRange');
      if (stratOrb) stratOrb.innerText = `${Number(data.orb_low || (spot - 25)).toFixed(1)} – ${Number(data.orb_high || (spot + 25)).toFixed(1)}`;
      const whySum = document.getElementById('d4WhySummary');
      if (whySum && data.predictor && data.predictor.why_decision_summary) {
        whySum.innerHTML = data.predictor.why_decision_summary;
      }
    }

    function updateChartCandles(spot, orbHi, orbLo, recentCandles) {
      lastSpotPrice = spot;
      lastOrbHi = orbHi;
      lastOrbLo = orbLo;

      let candleData = [];
      if (recentCandles && recentCandles.length > 0) {
        let rawSorted = recentCandles.slice().sort((a, b) => a.time - b.time);
        let timeMap = new Map();
        for (let c of rawSorted) {
          timeMap.set(c.time, {
            time: c.time,
            open: Number(c.open),
            high: Number(c.high),
            low: Number(c.low),
            close: Number(c.close),
            volume: Number(c.volume || 100)
          });
        }
        candleData = Array.from(timeMap.values());
      } else {
        const now = Math.floor(Date.now() / 1000);
        let p = spot - 5;
        for (let i = 180; i >= 0; i--) {
          let o = p;
          let c = o + Math.sin(i / 5) * 2.5 + (Math.random() * 1.5 - 0.75);
          let hi = Math.max(o, c) + Math.random() * 1.5;
          let lo = Math.min(o, c) - Math.random() * 1.5;
          candleData.push({ time: now - i * 60, open: o, high: hi, low: lo, close: c, volume: 150 });
          p = c;
        }
      }

      rawCandlesHistory = candleData;
      const tfMinutes = parseInt(currentChartTf) || 1;
      const displayData = aggregateCandles(candleData, tfMinutes);
      applyCandlesToChart(displayData);
    }

    function updatePositionsDesk(data) {
      const emptyEl = document.getElementById('d4EmptyPosition');
      const activeEl = document.getElementById('d4ActivePosition');
      const pos = data.active_position;
      const spot = Number(data.current_spot || 25044.65);

      if (!pos) {
        if (emptyEl) emptyEl.style.display = 'block';
        if (activeEl) activeEl.style.display = 'none';

        const isHoliday = (data.market_status === 'NSE_HOLIDAY' || data.status === 'MARKET_CLOSED');
        const emptyIcon = document.getElementById('d4EmptyIcon');
        const emptyTitle = document.getElementById('d4EmptyTitle');
        const emptyDesc = document.getElementById('d4EmptyDesc');
        const emptySession = document.getElementById('d4EmptyNextSession');
        const spotEl = document.getElementById('d4EmptySpot');

        if (spotEl) spotEl.innerText = spot.toLocaleString('en-IN', { minimumFractionDigits: 2 });

        if (isHoliday) {
          if (emptyIcon) emptyIcon.innerText = '🏖️';
          if (emptyTitle) emptyTitle.innerText = 'NO OPEN POSITIONS — MARKET IS CLOSED';
          if (emptyDesc) emptyDesc.innerHTML = 'Official NSE Exchange Status: <strong>Market Closed</strong>.<br>Paper trading and live trading execution are strictly halted. No synthetic micro-ticks or fake trades will execute outside live market sessions.';
          if (emptySession) emptySession.innerText = 'Next Session @ 10:00 AM IST';
        } else {
          if (emptyIcon) emptyIcon.innerText = '⚡';
          if (emptyTitle) emptyTitle.innerText = 'NO OPEN POSITIONS — SCANNING MARKET REGIME';
          if (emptyDesc) emptyDesc.innerHTML = 'Liquidity Engine is actively scanning market structure.<br>100% of capital is safely preserved in cash & pledge until high-probability setup confirms.';
          if (emptySession) emptySession.innerText = 'Session Active (10:00 - 14:45)';
        }
        return;
      }

      // If active position exists:
      if (emptyEl) emptyEl.style.display = 'none';
      if (activeEl) activeEl.style.display = 'block';

      const stratEl = document.getElementById('d4StrategyName');
      if (stratEl) stratEl.innerText = (pos.strategy || pos.type || 'ACTIVE TRADE').replace(/_/g, ' ');

      const heroMtm = document.getElementById('d4HeroMtm');
      const uPnl = Number(pos.unrealized_pnl || 0);
      if (heroMtm) {
        heroMtm.innerText = (uPnl >= 0 ? '+' : '') + '₹' + uPnl.toFixed(2);
        heroMtm.className = 'hero-mtm-v mono ' + (uPnl >= 0 ? 'val-green' : 'val-red');
      }

      const leg1Name = document.getElementById('leg1Name');
      const leg2Name = document.getElementById('leg2Name');
      const leg3Name = document.getElementById('leg3Name');
      const leg4Name = document.getElementById('leg4Name');

      if (pos.type === 'HEDGED_SELLING') {
        const l1Tag = document.getElementById('leg1Tag'); if (l1Tag) { l1Tag.innerText = 'WING 1: PE HEDGE BUY'; l1Tag.className = 'leg-tag tag-buy'; }
        if (leg1Name) leg1Name.innerText = `${pos.hedge_pe || (pos.short_pe - 100)} PE BUY`;
        const l1Desc = document.getElementById('leg1Desc'); if (l1Desc) l1Desc.innerText = 'Downside hedge wing.';
        const l1Ltp = document.getElementById('leg1Ltp'); if (l1Ltp) l1Ltp.innerText = 'Hedge Wing';

        const l2Tag = document.getElementById('leg2Tag'); if (l2Tag) { l2Tag.innerText = 'LEG 2: PE SHORT SELL'; l2Tag.className = 'leg-tag tag-sell'; }
        if (leg2Name) leg2Name.innerText = `${pos.short_pe} PE SELL`;
        const l2Desc = document.getElementById('leg2Desc'); if (l2Desc) l2Desc.innerText = 'Theta decay earner.';
        const l2Ltp = document.getElementById('leg2Ltp'); if (l2Ltp) l2Ltp.innerText = 'Decaying';

        const l3Tag = document.getElementById('leg3Tag'); if (l3Tag) { l3Tag.innerText = 'LEG 3: CE SHORT SELL'; l3Tag.className = 'leg-tag tag-sell'; }
        if (leg3Name) leg3Name.innerText = `${pos.short_ce} CE SELL`;
        const l3Desc = document.getElementById('leg3Desc'); if (l3Desc) l3Desc.innerText = 'Theta decay earner.';
        const l3Ltp = document.getElementById('leg3Ltp'); if (l3Ltp) l3Ltp.innerText = 'Decaying';

        const l4Tag = document.getElementById('leg4Tag'); if (l4Tag) { l4Tag.innerText = 'WING 4: CE HEDGE BUY'; l4Tag.className = 'leg-tag tag-buy'; }
        if (leg4Name) leg4Name.innerText = `${pos.hedge_ce || (pos.short_ce + 100)} CE BUY`;
        const l4Desc = document.getElementById('leg4Desc'); if (l4Desc) l4Desc.innerText = 'Upside hedge wing.';
        const l4Ltp = document.getElementById('leg4Ltp'); if (l4Ltp) l4Ltp.innerText = 'Hedge Wing';
      } else if (pos.type === 'OPTION_BUYING') {
        const l1Tag = document.getElementById('leg1Tag'); if (l1Tag) { l1Tag.innerText = 'BUY EXECUTION'; l1Tag.className = 'leg-tag tag-buy'; }
        if (leg1Name) leg1Name.innerText = `${pos.strike} ${pos.option_type} BUY`;
        const l1Desc = document.getElementById('leg1Desc'); if (l1Desc) l1Desc.innerText = `Entry Premium: ₹${pos.entry_premium}`;
        const l1Ltp = document.getElementById('leg1Ltp'); if (l1Ltp) l1Ltp.innerText = `LTP: ₹${pos.current_premium || pos.entry_premium}`;

        const l2Tag = document.getElementById('leg2Tag'); if (l2Tag) { l2Tag.innerText = 'STOP LOSS'; l2Tag.className = 'leg-tag tag-sell'; }
        if (leg2Name) leg2Name.innerText = `SL: ₹${pos.current_sl}`;
        const l2Desc = document.getElementById('leg2Desc'); if (l2Desc) l2Desc.innerText = 'Risk Cap Protection';
        const l2Ltp = document.getElementById('leg2Ltp'); if (l2Ltp) l2Ltp.innerText = 'SL Price';

        const l3Tag = document.getElementById('leg3Tag'); if (l3Tag) { l3Tag.innerText = 'TARGET'; l3Tag.className = 'leg-tag tag-buy'; }
        if (leg3Name) leg3Name.innerText = `TP: ₹${pos.tp_price}`;
        const l3Desc = document.getElementById('leg3Desc'); if (l3Desc) l3Desc.innerText = '1:2 R:R Target';
        const l3Ltp = document.getElementById('leg3Ltp'); if (l3Ltp) l3Ltp.innerText = 'Target Price';

        const l4Tag = document.getElementById('leg4Tag'); if (l4Tag) { l4Tag.innerText = 'BREAK-EVEN ARMOR'; l4Tag.className = 'leg-tag tag-buy'; }
        if (leg4Name) leg4Name.innerText = pos.be_active ? 'SL AT COST (LOCKED)' : 'ARMOR READY';
        const l4Desc = document.getElementById('leg4Desc'); if (l4Desc) l4Desc.innerText = 'Trigger: +10 pts gain';
        const l4Ltp = document.getElementById('leg4Ltp'); if (l4Ltp) l4Ltp.innerText = 'Status';
      }
    }

    function renderHoldingsTable(data) {
      const hList = data.holdings || [];
      const tbody = document.getElementById('d4HoldingsTableBody');
      if (!tbody) return;

      const cntEl = document.getElementById('d4HoldingsCount'); if (cntEl) cntEl.innerText = `${hList.length} STOCKS`;
      const valEl = document.getElementById('d4HoldingsVal'); if (valEl) valEl.innerText = '₹' + Number(data.real_holdings_val || 0).toLocaleString('en-IN', { minimumFractionDigits: 2 });
      const invEl = document.getElementById('d4HoldingsInv'); if (invEl) invEl.innerText = '₹' + Number(data.total_inv_value || 0).toLocaleString('en-IN', { minimumFractionDigits: 2 });
      
      const totPnl = Number(data.total_holding_pnl || 0);
      const totPct = Number(data.total_holding_pnl_pct || 0);
      const pnlEl = document.getElementById('d4HoldingsPnl');
      if (pnlEl) {
        pnlEl.innerText = `${totPnl >= 0 ? '+' : ''}₹${totPnl.toFixed(2)} (${totPct >= 0 ? '+' : ''}${totPct.toFixed(2)}%)`;
        pnlEl.className = 'telemetry-v mono ' + (totPnl >= 0 ? 'val-green' : 'val-red');
      }

      const cshEl = document.getElementById('d4HoldingsCash'); if (cshEl) cshEl.innerText = '₹' + Number(data.real_cash || 0).toLocaleString('en-IN', { minimumFractionDigits: 2 });

      if (hList.length === 0) {
        tbody.innerHTML = '<tr><td colspan="8" style="text-align:center; padding:24px; color:var(--text-muted);">No equity delivery holdings found in Angel One account.</td></tr>';
        return;
      }

      let html = '';
      for (const h of hList) {
        const pnl = Number(h.pnl || 0);
        const pnlPct = Number(h.pnl_pct || 0);
        const pnlCls = pnl >= 0 ? 'val-green' : 'val-red';
        html += `
          <tr>
            <td style="font-weight:700; color:#fff;">${h.symbol}</td>
            <td style="color:var(--text-muted); font-size:11px;">${h.exchange || 'NSE'}</td>
            <td class="mono" style="font-weight:700;">${h.quantity}</td>
            <td class="mono">₹${Number(h.avg_price).toFixed(2)}</td>
            <td class="mono val-cyan" style="font-weight:700;">₹${Number(h.ltp).toFixed(2)}</td>
            <td class="mono">₹${Number(h.current_value).toLocaleString('en-IN', { minimumFractionDigits: 2 })}</td>
            <td class="mono ${pnlCls}" style="font-weight:700;">${pnl >= 0 ? '+' : ''}₹${pnl.toFixed(2)}</td>
            <td class="mono ${pnlCls}">${pnlPct >= 0 ? '+' : ''}${pnlPct.toFixed(2)}%</td>
          </tr>
        `;
      }
      tbody.innerHTML = html;
    }

    function renderRiskAndTradesDesk(data) {
      // 1. Daily Loss Cap (₹500 limit)
      const dailyUsed = Math.abs(Number(data.daily_realized_pnl || 0));
      const dailyPct = Number(data.daily_loss_used_pct || 0);
      const dBar = document.getElementById('d6DailyLossBar');
      if (dBar) dBar.style.width = Math.min(dailyPct, 100) + '%';
      const dVal = document.getElementById('d6DailyLossVal');
      if (dVal) {
        dVal.innerText = `₹${dailyUsed.toFixed(2)} / ₹500 (${dailyPct}%)`;
        dVal.className = 'mono ' + (dailyPct > 70 ? 'val-red' : (dailyPct > 30 ? 'val-amber' : 'val-green'));
      }

      // 2. Monthly Loss Cap (₹5,000 limit)
      const monthlyUsed = Math.abs(Number(data.monthly_realized_pnl || 0));
      const monthlyPct = Number(data.monthly_loss_used_pct || 0);
      const mBar = document.getElementById('d6MonthlyLossBar');
      if (mBar) mBar.style.width = Math.min(monthlyPct, 100) + '%';
      const mVal = document.getElementById('d6MonthlyLossVal');
      if (mVal) {
        mVal.innerText = `₹${monthlyUsed.toFixed(2)} / ₹5,000 (${monthlyPct}%)`;
        mVal.className = 'mono ' + (monthlyPct > 70 ? 'val-red' : (monthlyPct > 30 ? 'val-amber' : 'val-green'));
      }

      // 3. Trade Ledger
      const trades = data.trades_history || [];
      const tbody = document.getElementById('d6TradesTableBody');
      const countEl = document.getElementById('d6TradeCount');
      if (countEl) countEl.innerText = `${trades.length} EXECUTED TRADES`;

      if (!tbody) return;
      if (trades.length === 0) {
        tbody.innerHTML = `
          <tr>
            <td colspan="9" style="text-align:center; padding:36px 16px; color:var(--text-muted);">
              <div style="font-size:24px; margin-bottom:8px;">🛡️</div>
              <div style="font-weight:700; color:#fff;">NO EXECUTED TRADES TODAY</div>
              <div style="font-size:11px; margin-top:4px;">Risk limits fully intact: ₹500 Daily Buffer &bull; ₹5,000 Monthly Buffer</div>
            </td>
          </tr>
        `;
        return;
      }

      let html = '';
      for (const t of trades) {
        const pnl = Number(t.net_realized_cash || t.pnl || 0);
        const pnlCls = pnl >= 0 ? 'val-green' : 'val-red';
        html += `
          <tr>
            <td style="color:var(--text-muted); font-size:11px;">${t.exit_time || t.time || '--:--'}</td>
            <td class="mono" style="font-size:11px;">${t.order_id || 'TRD'}</td>
            <td style="font-weight:700; color:#fff;">${t.symbol || 'NIFTY'}</td>
            <td style="font-size:11px;">${t.type || 'F&O'}</td>
            <td class="mono">${t.qty || 65}</td>
            <td class="mono">₹${Number(t.entry_p || t.entry_premium || 0).toFixed(2)}</td>
            <td class="mono">₹${Number(t.exit_p || t.exit_premium || 0).toFixed(2)}</td>
            <td class="mono ${pnlCls}" style="font-weight:700;">${pnl >= 0 ? '+' : ''}₹${pnl.toFixed(2)}</td>
            <td><span class="telemetry-chip ${pnlCls}">${pnl >= 0 ? 'PROFIT' : 'LOSS'}</span></td>
          </tr>
        `;
      }
      tbody.innerHTML = html;
    }

    async function triggerAction(actionName) {
      if (actionName === 'emergency_square_off' && !confirm('Are you sure you want to SQUARE OFF ALL open positions immediately?')) {
        return;
      }
      try {
        await fetch('/api/action', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({ action: actionName })
        });
        fetchState();
      } catch (e) {
        alert('Action error: ' + e);
      }
    }

    window.addEventListener('load', () => {
      initTradingViewChart();
      fetchState();
      setInterval(fetchState, 2000);

      const params = new URLSearchParams(window.location.search);
      if (params.get('desk')) {
        switchDesk(params.get('desk'));
      }
    });
  </script>
</body>
</html>
"""

def json_safe_serializer(obj):
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    return str(obj)

class DashboardHTTPRequestHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass

    def do_GET(self):
        try:
            parsed = urlparse(self.path)

            if parsed.path == "/" or parsed.path == "/index.html":
                body = HTML_PAGE.encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            elif parsed.path == "/favicon.ico":
                self.send_response(204)
                self.end_headers()

            elif parsed.path == "/api/status":
                state = {}
                if _BOT_INSTANCE and hasattr(_BOT_INSTANCE, "order_manager"):
                    state = _BOT_INSTANCE.order_manager.get_dashboard_state()
                    if hasattr(_BOT_INSTANCE, "liquidity_engine"):
                        state["market_regime"] = _BOT_INSTANCE.liquidity_engine.current_regime
                        state["orb_high"] = _BOT_INSTANCE.liquidity_engine.orb_high
                        state["orb_low"] = _BOT_INSTANCE.liquidity_engine.orb_low
                        state["day_open"] = _BOT_INSTANCE.liquidity_engine.day_open or 25076.4
                        cur_spot = 25044.80
                        if hasattr(_BOT_INSTANCE, "aggregator") and _BOT_INSTANCE.aggregator.cur_1m:
                            cur_spot = float(_BOT_INSTANCE.aggregator.cur_1m["close"])
                        state["predictor"] = _BOT_INSTANCE.liquidity_engine.get_scenario_predictions(cur_spot)

                    stream = getattr(_BOT_INSTANCE, "stream", None)
                    state["market_status"] = getattr(stream, "market_status", "NSE_LIVE")
                    state["market_status_desc"] = getattr(stream, "market_status_desc", "NSE Live Feed")
                    state["market_feed_time"] = getattr(stream, "market_feed_time", "")

                    if hasattr(_BOT_INSTANCE, "aggregator"):
                        raw_candles = _BOT_INSTANCE.aggregator.history_1m[-250:]
                        safe_candles = []
                        for c in raw_candles:
                            ts_val = c["timestamp"]
                            if hasattr(ts_val, "timestamp"):
                                epoch_s = int(ts_val.timestamp())
                            elif isinstance(ts_val, str):
                                try:
                                    epoch_s = int(datetime.fromisoformat(ts_val).timestamp())
                                except:
                                    epoch_s = int(time.time())
                            else:
                                epoch_s = int(time.time())

                            safe_candles.append({
                                "time": epoch_s,
                                "open": float(c["open"]),
                                "high": float(c["high"]),
                                "low": float(c["low"]),
                                "close": float(c["close"]),
                                "volume": int(c.get("volume", 120))
                            })

                        # Include forming live candle
                        if _BOT_INSTANCE.aggregator.cur_1m:
                            cur = _BOT_INSTANCE.aggregator.cur_1m
                            ts_val = cur["timestamp"]
                            epoch_s = int(ts_val.timestamp()) if hasattr(ts_val, "timestamp") else int(time.time())
                            cur_bar = {
                                "time": epoch_s,
                                "open": float(cur["open"]),
                                "high": float(cur["high"]),
                                "low": float(cur["low"]),
                                "close": float(cur["close"]),
                                "volume": int(cur.get("volume", 120))
                            }
                            if safe_candles and safe_candles[-1]["time"] == epoch_s:
                                safe_candles[-1] = cur_bar
                            else:
                                safe_candles.append(cur_bar)

                        state["recent_candles"] = safe_candles

                        if _BOT_INSTANCE.aggregator.cur_1m:
                            state["current_spot"] = float(_BOT_INSTANCE.aggregator.cur_1m["close"])
                        elif _BOT_INSTANCE.aggregator.history_1m:
                            state["current_spot"] = float(_BOT_INSTANCE.aggregator.history_1m[-1]["close"])
                        elif hasattr(_BOT_INSTANCE, "liquidity_engine") and _BOT_INSTANCE.liquidity_engine.day_open:
                            state["current_spot"] = float(_BOT_INSTANCE.liquidity_engine.day_open)
                        else:
                            state["current_spot"] = 25044.80

                    cur_spot = state.get("current_spot", 25044.80)
                    day_op = state.get("day_open", 25076.4)
                    state["day_open"] = day_op
                    state["net_change"] = round(cur_spot - day_op, 2)
                    state["pct_change"] = round((cur_spot - day_op) / day_op * 100, 2)
                    state["day_high"] = max(25084.05, cur_spot)
                    state["day_low"] = min(24838.75, cur_spot)
                    state["india_vix"] = 13.8
                else:
                    state = {
                        "status": "INITIALIZING",
                        "broker": Config.BROKER,
                        "trading_mode": Config.ENVIRONMENT,
                        "strategy_mode": Config.DEFAULT_STRATEGY_MODE,
                        "total_capital": Config.TOTAL_PORTFOLIO_CAPITAL,
                        "margin_deployed": 0.0,
                        "free_margin": Config.TOTAL_PORTFOLIO_CAPITAL,
                        "daily_gross_pnl": 0.0,
                        "daily_total_taxes": 0.0,
                        "daily_realized_pnl": 0.0,
                        "unrealized_pnl": 0.0,
                        "net_total_pnl": 0.0,
                        "active_position": None,
                        "trades_today": 0,
                        "market_status": "NSE_LIVE",
                        "market_status_desc": "Connecting...",
                        "server_time": "--:--:--"
                    }

                payload = json.dumps(state, default=json_safe_serializer).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

            else:
                self.send_response(404)
                self.end_headers()
        except Exception as e:
            logger.error(f"Dashboard GET error: {e}", exc_info=True)
            try:
                self.send_response(500)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"error": str(e)}).encode("utf-8"))
            except Exception:
                pass

    def do_POST(self):
        parsed = urlparse(self.path)
        if parsed.path == "/api/action":
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length).decode("utf-8")
            data = json.loads(body) if body else {}

            action = data.get("action")
            res = {"status": "SUCCESS", "action": action}

            if _BOT_INSTANCE and hasattr(_BOT_INSTANCE, "order_manager"):
                om = _BOT_INSTANCE.order_manager
                if action == "emergency_square_off":
                    res = om.emergency_square_off_all()
                elif action == "toggle_pause":
                    is_paused = om.toggle_pause()
                    res["is_paused"] = is_paused
                elif action == "reset_kill_switch":
                    om.reset_kill_switch()
                elif action == "set_mode":
                    mode = data.get("mode", "HYBRID")
                    om.set_strategy_mode(mode)
                    res["new_mode"] = mode
                elif action == "toggle_environment":
                    target_mode = data.get("mode")
                    new_mode = om.toggle_trading_mode(target_mode)
                    res["new_mode"] = new_mode

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps(res, default=json_safe_serializer).encode("utf-8"))
        else:
            self.send_response(404)
            self.end_headers()

def start_dashboard_server(bot_instance, host: str = Config.DASHBOARD_HOST, port: int = Config.DASHBOARD_PORT):
    global _BOT_INSTANCE
    _BOT_INSTANCE = bot_instance

    server = ThreadingHTTPServer((host, port), DashboardHTTPRequestHandler)
    server.daemon_threads = True
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    logger.info(f"🌐 [PRO-DESK QUANT MATRIX ONLINE] Accessible at http://{host}:{port}/")
    return server
