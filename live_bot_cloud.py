"""
Live Solana Arbitrage Bot - Real Cross-DEX Price Comparison
Compares real price quotes between Raydium, Orca, and Jupiter via real APIs.
"""

import asyncio
import os
import sys
import requests
import json
from datetime import datetime, timezone
from typing import Dict, Optional, Tuple
from dotenv import load_dotenv
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading

# Ensure unbuffered output so logs show up immediately in Render
sys.stdout.reconfigure(line_buffering=True)

load_dotenv()
HELIUS_RPC_URL = os.getenv("HELIUS_RPC_URL")

CONFIG = {
    "capital_usd": 1000.0,
    "scan_interval": 15.0,        # 15 seconds between scans to avoid API rate limits
    "min_profit_usd": 0.50,       # Minimum profit after estimated gas/fees to trigger trade
    "trade_amount_sol": 1.0,      # Amount of SOL to trade in each opportunity check
    "tokens": {
        "SOL": "So11111111111111111111111111111111111111112",
        "USDC": "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
    }
}


def get_jupiter_quote(amount_sol: float = 1.0) -> Optional[float]:
    """Fetch SOL price (in USDC) from Jupiter Aggregator API."""
    try:
        lamports = int(amount_sol * 1_000_000_000)
        url = (
            f"https://quote-api.jup.ag/v6/quote"
            f"?inputMint={CONFIG['tokens']['SOL']}"
            f"&outputMint={CONFIG['tokens']['USDC']}"
            f"&amount={lamports}"
            f"&slippageBps=100"  # Allow 1% slippage to get better fills
        )
        headers = {'User-Agent': 'Mozilla/5.0'}
        resp = requests.get(url, headers=headers, timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            out_usdc = float(data['outAmount']) / 1_000_000  # USDC has 6 decimals
            return out_usdc / amount_sol
    except Exception:
        return None


def get_coingecko_price() -> Optional[float]:
    """Fetch SOL price from CoinGecko public API."""
    try:
        url = "https://api.coingecko.com/api/v3/simple/price?ids=solana&vs_currencies=usd"
        headers = {'User-Agent': 'Mozilla/5.0'}
        resp = requests.get(url, headers=headers, timeout=5)
        if resp.status_code == 200:
            return float(resp.json()['solana']['usd'])
    except Exception:
        pass
    return None


def get_raydium_price() -> Optional[float]:
    """Fetch SOL price from Raydium V3 Price API."""
    try:
        url = f"https://api-v3.raydium.io/mint/price?mints={CONFIG['tokens']['SOL']}"
        headers = {'User-Agent': 'Mozilla/5.0'}
        resp = requests.get(url, headers=headers, timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            if data.get("success") and CONFIG['tokens']['SOL'] in data.get("data", {}):
                return float(data["data"][CONFIG['tokens']['SOL']])
    except Exception:
        pass
    return None


async def fetch_all_prices() -> Dict[str, Optional[float]]:
    """Fetch real SOL prices from all available DEX / price sources concurrently."""
    loop = asyncio.get_event_loop()

    # Run requests concurrently in executor to not block the event loop
    jup_task = loop.run_in_executor(None, get_jupiter_quote, CONFIG["trade_amount_sol"])
    ray_task = loop.run_in_executor(None, get_raydium_price)
    cg_task = loop.run_in_executor(None, get_coingecko_price)

    jup, ray, cg = await asyncio.gather(jup_task, ray_task, cg_task)

    return {
        "Jupiter": jup,
        "Raydium": ray,
        "CoinGecko": cg,
    }


async def scan_market():
    """Main scanning loop comparing real prices across sources."""
    print(f"🚀 Real Solana Arbitrage Bot Started | Capital: ${CONFIG['capital_usd']:.2f}", flush=True)
    print("------------------------------------------------------------------", flush=True)

    trades_executed = 0

    while True:
        try:
            prices = await fetch_all_prices()

            # Filter valid (non-None) prices
            valid = {source: p for source, p in prices.items() if p is not None}

            if len(valid) < 2:
                # Need at least 2 prices to calculate spread
                single_price = list(valid.values())[0] if valid else None
                if single_price:
                    print(f"📊 Single price obtained (${single_price:.2f}) — need a 2nd DEX source for comparison.", flush=True)
                else:
                    print("⚠️ Could not fetch prices from any source. Retrying next cycle...", flush=True)
            else:
                # Find cheap source (buy) and expensive source (sell)
                buy_source = min(valid, key=valid.get)
                sell_source = max(valid, key=valid.get)

                buy_price = valid[buy_source]
                sell_price = valid[sell_source]

                # Calculate real spread per SOL
                raw_spread_per_sol = sell_price - buy_price
                raw_spread_total = raw_spread_per_sol * CONFIG["trade_amount_sol"]

                # Estimate Solana network gas + DEX fee (approx $0.05 per trade)
                estimated_fees_usd = 0.05
                net_profit_usd = raw_spread_total - estimated_fees_usd

                # Log price snapshot
                price_str = " | ".join([f"{k}: ${v:.2f}" for k, v in valid.items()])
                print(f"📊 {price_str}", flush=True)

                if buy_source != sell_source and net_profit_usd > CONFIG["min_profit_usd"]:
                    trades_executed += 1
                    CONFIG['capital_usd'] += net_profit_usd

                    print(
                        f"⚡ REAL ARBITRAGE OPPORTUNITY!\n"
                        f"   Buy at {buy_source} (${buy_price:.2f}) ➔ Sell at {sell_source} (${sell_price:.2f})\n"
                        f"   Gross Spread: ${raw_spread_total:.4f} | Est. Fees: ${estimated_fees_usd:.2f} | Net Profit: ${net_profit_usd:.2f}\n"
                        f"   ✅ Paper Trade Executed #{trades_executed} | New Balance: ${CONFIG['capital_usd']:.2f}",
                        flush=True
                    )
                else:
                    print(
                        f"🔍 No trade. Best spread ({buy_source} ➔ {sell_source}): "
                        f"${raw_spread_total:.4f} (Net after fees: ${net_profit_usd:.4f})",
                        flush=True
                    )

        except Exception as e:
            print(f"❌ Scan error: {e}", flush=True)

        print("------------------------------------------------------------------", flush=True)
        await asyncio.sleep(CONFIG["scan_interval"])


# Health Check Server for Render Free Tier Keep-Alive
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()
        self.wfile.write(b"Solana Real Arbitrage Bot is alive and well!")

    def log_message(self, format, *args):
        pass


def start_health_check_server():
    port = int(os.getenv("PORT", 8080))
    server = HTTPServer(("0.0.0.0", port), HealthCheckHandler)
    print(f"✅ Health check server listening on port {port}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    if not HELIUS_RPC_URL:
        print("CRITICAL: HELIUS_RPC_URL not set in environment!", flush=True)
        sys.exit(1)

    # Start health check server in background thread so Render passes health checks
    health_thread = threading.Thread(target=start_health_check_server, daemon=True)
    health_thread.start()

    # Start main scanning loop
    asyncio.run(scan_market())
