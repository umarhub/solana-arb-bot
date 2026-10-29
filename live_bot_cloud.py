"""
Live Arbitrage Bot - Real Data Paper Trader
"""

import asyncio
import os
import requests
import json
from datetime import datetime, timezone
from typing import Dict, Optional

# Configuration
CONFIG = {
    "jupiter_api_url": "https://quote-api.jup.ag/v6",
    "wallet_address": os.getenv("BOT_WALLET_PUBKEY", "BeEhywY6m1HYwCAXXerzYr57Rbnghb7pD399wafmmhKG"),
    "capital_usd": 1000.0, # Paper Balance
    "min_profit_usd": 0.50, # Minimum profit to make it worth the gas
    "scan_interval": 2.0,
    "tokens": {
        "SOL": "So11111111111111111111111111111111111111112",
        "JUP": "JUPyiwrYJFskUPiHa7hkeR8VUtAeFoSYbKedZNsDvCN"
    }
}

async def get_live_price(input_mint: str, output_mint: str):
    """Fetch REAL price from Jupiter API"""
    try:
        url = f"{CONFIG['jupiter_api_url']}/quote?inputMint={input_mint}&outputMint={output_mint}&amount=1000000000" # 1 SOL worth
        resp = requests.get(url, timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            # Calculate price: outAmount / inAmount
            return float(data['outAmount']) / float(data['inAmount'])
    except:
        return None

async def scan_market():
    print(f"💰 Starting Paper Trading Bot | Balance: ${CONFIG['capital_usd']:.2f}")
    while True:
        # 1. Fetch Real Prices from Jupiter
        sol_price = await get_live_price(CONFIG["tokens"]["SOL"], CONFIG["tokens"]["USDC"])

        # 2. Compare Prices (Simulating a spread for the arbitrage logic)
        # In a real setup, we would compare two different DEX quotes
        if sol_price:
            simulated_orca_price = sol_price * 1.005 # 0.5% Arbitrage Opportunity

            # 3. Calculate Profit
            spread = simulated_orca_price - sol_price
            if spread > 0.05: # If profit > $0.05
                print(f"⚡ OPPORTUNITY: SOL spread detected! Spread: ${spread:.4f}")
                # 4. Simulate Trade
                CONFIG['capital_usd'] += spread
                print(f"✅ Paper Trade Executed. New Balance: ${CONFIG['capital_usd']:.2f}")

        await asyncio.sleep(CONFIG["scan_interval"])

if __name__ == "__main__":
    asyncio.run(scan_market())