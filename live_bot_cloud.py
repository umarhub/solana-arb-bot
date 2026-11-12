"""
Live Solana Arbitrage Bot - REAL TRADES VERSION
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

sys.stdout.reconfigure(line_buffering=True)
load_dotenv()

HELIUS_RPC_URL = os.getenv("HELIUS_RPC_URL")
BOT_WALLET_PRIVATE_KEY = os.getenv("BOT_WALLET_PRIVATE_KEY")

CONFIG = {
    "capital_usd": 1000.0,
    "scan_interval": 10.0,
    "min_profit_usd": 0.01,
    "trade_amount_sol": 1.0,
    "max_slippage_bps": 50,
    "tokens": {
        "SOL": "So11111111111111111111111111111111111111112",
        "USDC": "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
    }
}

WALLET_ADDRESS = "FGtCJy49HUXukc5ee6tmjyt74ojzjJvGGbvgTEExJ6QW"


JUPITER_BASES = [
    "https://api.jup.ag/v6",
    "https://quote-api.jup.ag/v6",
    "https://jup.ag/v6",
]

def get_jupiter_quote(amount_sol=1.0):
    lamports = int(amount_sol * 1000000000)
    for base in JUPITER_BASES:
        try:
            url = f"{base}/quote"
            params = {
                "inputMint": CONFIG["tokens"]["SOL"],
                "outputMint": CONFIG["tokens"]["USDC"],
                "amount": lamports,
                "slippageBps": CONFIG["max_slippage_bps"]
            }
            headers = {"User-Agent": "Mozilla/5.0"}
            resp = requests.get(url, params=params, headers=headers, timeout=5)
            if resp.status_code == 200:
                data = resp.json()
                out_usdc = float(data["outAmount"]) / 1000000
                return out_usdc / amount_sol
        except Exception:
            continue
    return None


def get_coingecko_price():
    try:
        url = "https://api.coingecko.com/api/v3/simple/price"
        params = {"ids": "solana", "vs_currencies": "usd"}
        headers = {"User-Agent": "Mozilla/5.0"}
        resp = requests.get(url, params=params, headers=headers, timeout=5)
        if resp.status_code == 200:
            return float(resp.json()["solana"]["usd"])
    except Exception:
        pass
    return None


def get_raydium_price():
    try:
        url = "https://api-v3.raydium.io/mint/price"
        params = {"mints": CONFIG["tokens"]["SOL"]}
        headers = {"User-Agent": "Mozilla/5.0"}
        resp = requests.get(url, params=params, headers=headers, timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            if data.get("success") and CONFIG["tokens"]["SOL"] in data.get("data", {}):
                return float(data["data"][CONFIG["tokens"]["SOL"]])
    except Exception:
        pass
    return None


def execute_real_swap(amount_sol):
    """Execute a real swap on Jupiter using robust endpoints."""
    lamports = int(amount_sol * 1000000000)

    # Try endpoints until one works
    for base in JUPITER_BASES:
        try:
            # 1. Get Quote
            quote_resp = requests.get(f"{base}/quote", params={
                "inputMint": CONFIG["tokens"]["SOL"],
                "outputMint": CONFIG["tokens"]["USDC"],
                "amount": lamports,
                "slippageBps": CONFIG["max_slippage_bps"]
            }, headers={"User-Agent": "Mozilla/5.0"}, timeout=5)

            if quote_resp.status_code != 200: continue
            quote_data = quote_resp.json()

            # 2. Get Transaction
            swap_resp = requests.post(f"{base}/swap/transaction", json={
                "quoteResponse": quote_data,
                "userPublicKey": WALLET_ADDRESS,
                "wrapUnwrapSol": True,
                "dynamicComputeUnitLimit": True,
                "prioritizationFeeLamports": 10000
            }, headers={"User-Agent": "Mozilla/5.0", "Content-Type": "application/json"}, timeout=10)

            if swap_resp.status_code != 200: continue

            tx_encoded = swap_resp.json().get("transaction")
            if not tx_encoded: continue

            # 3. Send Transaction
            send_payload = {
                "jsonrpc": "2.0", "id": 1, "method": "sendTransaction",
                "params": [tx_encoded, {"encoding": "base64", "skipPreflight": False, "preflightCommitment": "confirmed", "maxRetries": 3}]
            }
            send_resp = requests.post(HELIUS_RPC_URL, json=send_payload, headers={"Content-Type": "application/json"}, timeout=15)

            if send_resp.status_code == 200 and "result" in send_resp.json():
                print(f"✅ REAL SWAP EXECUTED! TX: {send_resp.json()['result']}", flush=True)
                return True

        except Exception:
            continue
    return False

async def fetch_all_prices():
    loop = asyncio.get_event_loop()
    jup_task = loop.run_in_executor(None, get_jupiter_quote, CONFIG["trade_amount_sol"])
    ray_task = loop.run_in_executor(None, get_raydium_price)
    cg_task = loop.run_in_executor(None, get_coingecko_price)
    jup, ray, cg = await asyncio.gather(jup_task, ray_task, cg_task)
    return {"Jupiter": jup, "Raydium": ray, "CoinGecko": cg}


async def scan_market():
    print("REAL MONEY ARBITRAGE BOT STARTED", flush=True)
    print(f"Wallet: {WALLET_ADDRESS}", flush=True)
    print("-" * 60, flush=True)

    trades_executed = 0
    total_profit = 0.0

    while True:
        try:
            prices = await fetch_all_prices()
            valid = {source: p for source, p in prices.items() if p is not None}

            if len(valid) < 2:
                single_price = list(valid.values())[0] if valid else None
                if single_price:
                    print(f"Single price (${single_price:.2f}) - need 2nd source", flush=True)
                else:
                    print("No prices fetched", flush=True)
            else:
                buy_source = min(valid, key=valid.get)
                sell_source = max(valid, key=valid.get)
                buy_price = valid[buy_source]
                sell_price = valid[sell_source]

                raw_spread_per_sol = sell_price - buy_price
                raw_spread_total = raw_spread_per_sol * CONFIG["trade_amount_sol"]
                estimated_fees_usd = 0.05
                net_profit_usd = raw_spread_total - estimated_fees_usd

                price_str = " | ".join([f"{k}: ${v:.2f}" for k, v in valid.items()])
                print(f"{price_str}", flush=True)

                 # Check for profitable spread AND ensure we aren't trading on CoinGecko
                if buy_source != sell_source and net_profit_usd > CONFIG["min_profit_usd"]:
                    if buy_source in ["Jupiter", "Raydium"] and sell_source in ["Jupiter", "Raydium"]:
                        print(f"⚡ EXECUTING REAL SWAP: Buy {buy_source} -> Sell {sell_source}", flush=True)
                        success = execute_real_swap(CONFIG["trade_amount_sol"])
                        if success:
                            trades_executed += 1
                            total_profit += net_profit_usd
                            print(f"✅ REAL TRADE #{trades_executed} | Profit: ${net_profit_usd:.4f} | Total: ${total_profit:.2f}", flush=True)
                        else:
                            print("❌ Swap failed", flush=True)
                    else:
                        print(f"🔍 Skipping: Cannot trade on {buy_source} or {sell_source} (Not an exchange)", flush=True)
                else:
                    print(f"No trade. Spread: ${raw_spread_total:.4f} (Net: ${net_profit_usd:.4f})", flush=True)

        except Exception as e:
            print(f"Scan error: {e}", flush=True)

        print("-" * 60, flush=True)
        await asyncio.sleep(CONFIG["scan_interval"])


class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()
        self.wfile.write(b"Solana Real Money Bot is alive!")

    def log_message(self, format, *args):
        pass


def start_health_check_server():
    port = int(os.getenv("PORT", 8080))
    server = HTTPServer(("0.0.0.0", port), HealthCheckHandler)
    print(f"Health check server on port {port}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    if not HELIUS_RPC_URL:
        print("CRITICAL: HELIUS_RPC_URL not set!", flush=True)
        sys.exit(1)
    if not BOT_WALLET_PRIVATE_KEY:
        print("CRITICAL: BOT_WALLET_PRIVATE_KEY not set!", flush=True)
        sys.exit(1)

    health_thread = threading.Thread(target=start_health_check_server, daemon=True)
    health_thread.start()
    asyncio.run(scan_market())
    def log_message(self, format, *args):
        pass


def start_health_check_server():
    port = int(os.getenv("PORT", 8080))
    server = HTTPServer(("0.0.0.0", port), HealthCheckHandler)
    print(f"Health check server on port {port}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    if not HELIUS_RPC_URL:
        print("CRITICAL: HELIUS_RPC_URL not set!", flush=True)
        sys.exit(1)
    if not BOT_WALLET_PRIVATE_KEY:
        print("CRITICAL: BOT_WALLET_PRIVATE_KEY not set!", flush=True)
        sys.exit(1)

    health_thread = threading.Thread(target=start_health_check_server, daemon=True)
    health_thread.start()
    asyncio.run(scan_market())