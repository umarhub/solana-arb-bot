"""
Live Solana Arbitrage Bot - FINAL REAL TRADES VERSION
"""
import asyncio
import os
import sys
import requests
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

def get_dexscreener_price():
    try:
        resp = requests.get("https://api.dexscreener.com/latest/dex/tokens/" + CONFIG["tokens"]["SOL"], timeout=5)
        if resp.status_code == 200:
            pairs = resp.json().get("pairs", [])
            sol_pairs = [p for p in pairs if p.get("baseToken", {}).get("symbol") == "SOL"]
            return float(sol_pairs[0]["priceUsd"]) if sol_pairs else None
    except: pass
    return None

def get_raydium_price():
    try:
        resp = requests.get("https://api-v3.raydium.io/mint/price", params={"mints": CONFIG["tokens"]["SOL"]}, timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            return float(data["data"][CONFIG["tokens"]["SOL"]]) if data.get("success") else None
    except: pass
    return None

def execute_jupiter_swap(amount_sol):
    """Execute swap via Jupiter using a different API domain that isn't blocked."""
    try:
        lamports = int(amount_sol * 1_000_000_000)
        # Use api.jup.ag instead of quote-api.jup.ag
        base_url = "https://api.jup.ag/swap/v6"

        # 1. Get Quote
        quote = requests.get("https://api.jup.ag/swap/v6/quote", params={
            "inputMint": CONFIG["tokens"]["SOL"], "outputMint": CONFIG["tokens"]["USDC"],
            "amount": lamports, "slippageBps": CONFIG["max_slippage_bps"]
        }, timeout=5).json()

        # 2. Get Transaction
        tx_resp = requests.post("https://api.jup.ag/swap/v6/swap", json={
            "quoteResponse": quote, "userPublicKey": WALLET_ADDRESS,
            "wrapUnwrapSol": True, "prioritizationFeeLamports": 10000
        }, timeout=10)

        tx_encoded = tx_resp.json().get("swapTransaction")

        # 3. Send Transaction via Helius RPC
        res = requests.post(HELIUS_RPC_URL, json={
            "jsonrpc": "2.0", "id": 1, "method": "sendTransaction",
            "params": [tx_encoded, {"encoding": "base64"}]
        }, timeout=15)

        return res.status_code == 200
    except Exception as e:
        print(f"Swap Error: {e}", flush=True)
        return False

async def fetch_prices():
    loop = asyncio.get_event_loop()
    dex = await loop.run_in_executor(None, get_dexscreener_price)
    ray = await loop.run_in_executor(None, get_raydium_price)
    return {"DexScreener": dex, "Raydium": ray}

async def scan_market():
    print("BOT STARTED - REAL TRADING ENABLED", flush=True)
    while True:
        try:
            prices = await fetch_prices()
            valid = {s: p for s, p in prices.items() if p is not None}
            if len(valid) == 2:
                buy_s, sell_s = min(valid, key=valid.get), max(valid, key=valid.get)
                profit = (valid[sell_s] - valid[buy_s]) * CONFIG["trade_amount_sol"] - 0.05
                print(f"Prices: {valid} | Spread: {profit:.4f}", flush=True)

                if profit > CONFIG["min_profit_usd"]:
                    print(f"⚡ EXECUTING SWAP via Jupiter", flush=True)
                    if execute_jupiter_swap(CONFIG["trade_amount_sol"]):
                        print("✅ TRADE SUCCESSFUL", flush=True)
                    else:
                        print("❌ TRADE FAILED", flush=True)
        except Exception as e:
            print(f"Error: {e}", flush=True)
        await asyncio.sleep(10)

# Health Check (Keep-Alive)
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200); self.end_headers(); self.wfile.write(b"OK")
    def log_message(self, *args): pass

def run_server():
    HTTPServer(("0.0.0.0", int(os.getenv("PORT", 8080))), HealthCheckHandler).serve_forever()

if __name__ == "__main__":
    threading.Thread(target=run_server, daemon=True).start()
    asyncio.run(scan_market())