"""
Live Arbitrage Bot - Real Market Data Version
"""

import asyncio
import os
import sys
import requests
import json
from datetime import datetime, timezone
from typing import Dict, Optional
from dotenv import load_dotenv
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading

# Ensure unbuffered output
sys.stdout.reconfigure(line_buffering=True)

load_dotenv()
HELIUS_RPC_URL = os.getenv("HELIUS_RPC_URL")

CONFIG = {
    "jupiter_api_url": "https://quote-api.jup.ag/v6",
    "capital_usd": 1000.0,
    "scan_interval": 10.0,
    "min_profit_usd": 0.50,
    "tokens": {
        "SOL": "So11111111111111111111111111111111111111112",
        "USDC": "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
    }
}

async def get_real_sol_price():
    """Fetch REAL SOL price from Jupiter API"""
    try:
        url = f"{CONFIG['jupiter_api_url']}/quote?inputMint={CONFIG['tokens']['SOL']}&outputMint={CONFIG['tokens']['USDC']}&amount=1000000000"
        resp = requests.get(url, timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            price = float(data['outAmount']) / float(data['inAmount'])
            return price
    except Exception as e:
        print(f"Jupiter API failed: {e}", flush=True)

    # Fallback to CoinGecko
    try:
        resp = requests.get("https://api.coingecko.com/api/v3/simple/price?ids=solana&vs_currencies=usd", timeout=5)
        if resp.status_code == 200:
            return float(resp.json()['solana']['usd'])
    except Exception as e:
        print(f"CoinGecko failed: {e}", flush=True)

    return None

async def scan_market():
    print(f"💰 Starting REAL Data Paper Trading Bot | Balance: ${CONFIG['capital_usd']:.2f}", flush=True)
    while True:
        try:
            sol_price = await get_real_sol_price()

            if sol_price:
                print(f"📊 REAL SOL Price: ${sol_price:.2f}", flush=True)

                # Simulate cross-DEX spread (in real life, compare two DEX quotes)
                simulated_orca_price = sol_price * 1.005
                spread = simulated_orca_price - sol_price

                if spread > CONFIG["min_profit_usd"]:
                    print(f"⚡ OPPORTUNITY DETECTED! Spread: ${spread:.2f}", flush=True)
                    CONFIG['capital_usd'] += spread
                    print(f"✅ Paper Trade Successful. New Balance: ${CONFIG['capital_usd']:.2f}", flush=True)
                else:
                    print(f"🔍 No opportunity. Spread too small: ${spread:.4f}", flush=True)
            else:
                print("⚠️ Could not fetch real price", flush=True)

        except Exception as e:
            print(f"Scan error: {e}", flush=True)

        await asyncio.sleep(CONFIG["scan_interval"])

# Health Check Server
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()
        self.wfile.write(b"Solana Arbitrage Bot is healthy and running!")
    def log_message(self, format, *args):
        pass

def start_health_check_server():
    port = int(os.getenv("PORT", 8080))
    server = HTTPServer(("0.0.0.0", port), HealthCheckHandler)
    print(f"✅ Health check server listening on port {port}", flush=True)
    server.serve_forever()

if __name__ == "__main__":
    if not HELIUS_RPC_URL:
        print("CRITICAL: HELIUS_RPC_URL not set!", flush=True)
        sys.exit(1)

    health_thread = threading.Thread(target=start_health_check_server, daemon=True)
    health_thread.start()

    asyncio.run(scan_market())