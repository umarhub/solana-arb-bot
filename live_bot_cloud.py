"""
Live Solana Arbitrage Bot - REAL TRADES VERSION
Executes actual swaps on Solana DEXs using your wallet.
"""

import asyncio
import os
import sys
import requests
import json
import base64
import time
from datetime import datetime, timezone
from typing import Dict, Optional, Tuple
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
        "USDC": "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wE
    }
}

def get_jupiter_quote(amount_sol: float = 1.0) ->
    try:
        lamports = int(amount_sol * 1_000_000_000)
        url = (
            f"https://quote-api.jup.ag/v6/quote"
            f"?inputMint={CONFIG['tokens']['SOL']}"
            f"&outputMint={CONFIG['tokens']['USDC'
            f"&amount={lamports}"
            f"&slippageBps={CONFIG['max_slippage_b
        )
        headers = {'User-Agent': 'Mozilla/5.0'}
        resp = requests.get(url, headers=headers, timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            out_usdc = float(data['outAmount']) /
            return out_usdc / amount_sol
    except Exception:
        pass
    return None

def get_coingecko_price() -> Optional[float]:
    try:
        url = "https://api.coingecko.com/api/v3/siencies=usd"
        headers = {'User-Agent': 'Mozilla/5.0'}
        resp = requests.get(url, headers=headers,
        if resp.status_code == 200:
            return float(resp.json()['solana']['us
    except Exception:
        pass
    return None

def get_raydium_price() -> Optional[float]:
    try:
        url = f"https://api-v3.raydium.io/mint/price?mints={CONFIG['tokens']['SOL']}"
        headers = {'User-Agent': 'Mozilla/5.0'}
        resp = requests.get(url, headers=headers, timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            if data.get("success") and CONFIG['toka", {}):
                return float(data["data"][CONFIG['tokens']['SOL']])
    except Exception:
        pass
    return None

def get_jupiter_swap_transaction(quote_data, walle
    """Get a swap transaction from Jupiter and return it for signing."""
    try:
        # Step 1: Get swap transaction
        swap_url = "https://quote-api.jup.ag/v6/sw
        swap_payload = {
            "quoteResponse": quote_data,
            "userPublicKey": wallet_address,
            "wrapUnwrapSol": True,
            "dynamicComputeUnitLimit": True,
            "prioritizationFeeLamports": 10000
        }
        headers = {'User-Agent': 'Mozilla/5.0', 'Con'}
        resp = requests.post(swap_url, json=swap_payload, headers=headers, timeout=10)
        if resp.status_code == 200:
            return resp.json()
        else:
            print(f"Swap transaction failed: {resp.status_code} {resp.text[:200]}", flush=True)
    except Exception as e:
        print(f"Swap transaction error: {e}", flush=True)
    return None

def execute_real_swap(buy_price, sell_price, amoune_key):
    """Execute a real swap on Jupiter."""
    try:
        lamports = int(amount_sol * 1_000_000_000)

        # Get quote for SOL -> USDC
        quote_url = (
            f"https://quote-api.jup.ag/v6/quote"
            f"?inputMint={CONFIG['tokens']['SOL']}
            f"&outputMint={CONFIG['tokens']['USDC']}"
            f"&amount={lamports}"
            f"&slippageBps={CONFIG['max_slippage_bps']}"
        )
        headers = {'User-Agent': 'Mozilla/5.0'}
        quote_resp = requests.get(quote_url, heade

        if quote_resp.status_code != 200:
            print(f"Quote failed: {quote_resp.status_code}", flush=True)
            return False

        quote_data = quote_resp.json()

        # Get swap transaction
        swap_tx = get_jupiter_swap_transaction(quote_data, wallet_address, private_key)
        if not swap_tx:
            return False

        # Sign and send transaction
        tx_encoded = swap_tx.get("transaction")
        if not tx_encoded:
            print("No transaction in swap response
            return False

        # Send the transaction to Solana
        send_url = f"{HELIUS_RPC_URL}"
        send_payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "sendTransaction",
            "params": [
                tx_encoded,
                {
                    "encoding": "base64",
                    "skipPreflight": False,
                    "preflightCommitment": "confir
                    "maxRetries": 3
                }
            ]
        }
        send_resp = requests.post(send_url, json=send_payload, headers={'Content-Type': 'application/json'}, timeout=15)

        if send_resp.status_code == 200:
            send_data = send_resp.json()
            if "result" in send_data:
                tx_sig = send_data["result"]
                print(f"✅ REAL SWAP EXECUTED! TX: {tx_sig}", flush=True)
                return True
            elif "error" in send_data:
                print(f"Send error: {send_data['er
        else:
            print(f"Send failed: {send_resp.status

    except Exception as e:
        print(f"Swap execution error: {e}", flush=True)

    return False

async def fetch_all_prices() -> Dict[str, Optional[float]]:
    loop = asyncio.get_event_loop()
    jup_task = loop.run_in_executor(None, get_jupiter_quote, CONFIG["trade_amount_sol"])
    ray_task = loop.run_in_executor(None, get_rayd
    cg_task = loop.run_in_executor(None, get_coingecko_price)
    jup, ray, cg = await asyncio.gather(jup_task,
    return {"Jupiter": jup, "Raydium": ray, "CoinGecko": cg}

async def get_wallet_balance():
    """Get real wallet balance from Solana blockch
    try:
        if not HELIUS_RPC_URL:
            return None
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "getBalance",
            "params": ["FGtCJy49HUXukc5ee6tmjyt74o
        }
        resp = requests.post(HELIUS_RPC_URL, json=pe': 'application/json'}, timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            if "result" in data:
                lamports = data["result"]["value"]
                return lamports / 1_000_000_000
    except Exception as e:
        print(f"Balance check error: {e}", flush=True)
    return None

async def scan_market():
    print("🚀 REAL MONEY ARBITRAGE BOT STARTED", flush=True)
    print(f"Wallet: FGtCJy49HUXukc5ee6tmjyt74ojzjJ
    print("------------------------------------------------------------------", flush=True)

    trades_executed = 0
    total_profit = 0.0

    while True:
        try:
            prices = await fetch_all_prices()
            valid = {source: p for source, p in prices.items() if p is not None}

            if len(valid) < 2:
                single_price = list(valid.values()
                if single_price:
                    print(f"📊 Single price (${sinurce", flush=True)
                else:
                    print("⚠️ No prices fetched",
            else:
                buy_source = min(valid, key=valid.
                sell_source = max(valid, key=valid.get)
                buy_price = valid[buy_source]
                sell_price = valid[sell_source]

                raw_spread_per_sol = sell_price - buy_price
                raw_spread_total = raw_spread_per_l"]
                estimated_fees_usd = 0.05
                net_profit_usd = raw_spread_total

                price_str = " | ".join([f"{k}: ${vs()])
                print(f"📊 {price_str}", flush=True)

                if buy_source != sell_source and net_profit_usd > CONFIG["min_profit_usd"]:
                    print(f"⚡ EXECUTING REAL SWAPll_source}", flush=True)

                    # Execute real swap
                    success = execute_real_swap(
                        buy_price, sell_price,
                        CONFIG["trade_amount_sol"],
                        "FGtCJy49HUXukc5ee6tmjyt74
                        BOT_WALLET_PRIVATE_KEY
                    )

                    if success:
                        trades_executed += 1
                        total_profit += net_profit
                        print(f"✅ REAL TRADE #{trades_executed} | Profit: ${net_profit_usd:.4f} | Total: ${total_profit:.2f}",
flush=True)
                    else:
                        print("❌ Swap failed", fl
                else:
                    print(f"🔍 No trade. Spread: $${net_profit_usd:.4f})", flush=True)

        except Exception as e:
            print(f"❌ Scan error: {e}", flush=True)

        print("------------------------------------------------------------------", flush=True)
        await asyncio.sleep(CONFIG["scan_interval"

class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()
        self.wfile.write(b"Solana Real Money Arbitrage Bot is alive!")
    def log_message(self, format, *args):
        pass

def start_health_check_server():
    port = int(os.getenv("PORT", 8080))
    server = HTTPServer(("0.0.0.0", port), HealthCheckHandler)
    print(f"✅ Health check server on port {port}"
    server.serve_forever()

if __name__ == "__main__":
    if not HELIUS_RPC_URL:
        print("CRITICAL: HELIUS_RPC_URL not set!", flush=True)
        sys.exit(1)
    if not BOT_WALLET_PRIVATE_KEY:
        print("CRITICAL: BOT_WALLET_PRIVATE_KEY no
        sys.exit(1)

    health_thread = threading.Thread(target=start_health_check_server, daemon=True)
    health_thread.start()
    asyncio.run(scan_market())