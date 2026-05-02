"""
Rug Muncher — Central Configuration
====================================
"""

import os
from pathlib import Path
from dataclasses import dataclass

PROJECT_ROOT = Path(__file__).parent
DATA_DIR = Path("/root/data/rug_muncher")
DATA_DIR.mkdir(parents=True, exist_ok=True)

# ── Branding ──
BRAND_NAME = "Rug Muncher"
BRAND_TAGLINE = "Don't get rekt. Scan first."
BRAND_COLOR = "#FF4444"  # Red for danger
SAFE_COLOR = "#00C853"   # Green for safe
WARNING_COLOR = "#FFB300" # Amber for caution

# ── Free Tier Limits ──
FREE_DAILY_SCANS = 3
FREE_DAILY_WALLET_SCANS = 3

# ── Pricing ──
@dataclass
class PricingTier:
    name: str
    contract_scan: float
    wallet_scan: float
    pack_10_discount: float = 0.25  # 25% off
    pack_50_discount: float = 0.40  # 40% off

PREMIUM_PRICING = PricingTier(
    name="Premium",
    contract_scan=2.00,
    wallet_scan=5.00,
)

@dataclass
class SubscriptionTier:
    name: str
    monthly: float
    yearly: float
    features: list

SUBSCRIPTIONS = [
    SubscriptionTier(
        name="Pro",
        monthly=29.0,
        yearly=290.0,
        features=[
            "Unlimited contract scans",
            "Unlimited wallet scans",
            "PDF reports",
            "JSON exports",
            "Priority queue",
        ],
    ),
    SubscriptionTier(
        name="Alpha",
        monthly=99.0,
        yearly=990.0,
        features=[
            "Everything in Pro",
            "Real-time wallet alerts",
            "API access",
            "Webhook notifications",
            "Dedicated support",
            "Custom integrations",
        ],
    ),
]

LIFETIME_PRICE = 499.0

# ── Risk Score Thresholds ──
RISK_LEVELS = {
    "SAFE": (0, 20),
    "LOW": (20, 40),
    "MEDIUM": (40, 60),
    "HIGH": (60, 80),
    "CRITICAL": (80, 100),
}

# ── Affiliate Partners ──
PARTNERS = {
    "gmgn": {
        "name": "🎯 GMGN",
        "desc": "Find memecoins early. Real-time trending + new token alerts.",
        "url": "https://gmgn.ai/?ref=RugMuncher",
        "cta": "Find Gems on GMGN",
    },
    "axiom": {
        "name": "⚡ Axiom",
        "desc": "Fastest Solana trading bot. Snipe launches, auto-sell, MEV protection.",
        "url": "https://axiom.trade?ref=RugMuncher",
        "cta": "Trade on Axiom",
    },
    "bullx": {
        "name": "🐂 BullX",
        "desc": "Cross-chain DEX aggregator. Best prices, lowest slippage.",
        "url": "https://bullx.io/?ref=RugMuncher",
        "cta": "Swap on BullX",
    },
    "photon": {
        "name": "🔦 Photon",
        "desc": "Trojan-powered trading on Solana. Anti-rug + profit-taking bots.",
        "url": "https://photon.trojan.trade?ref=RugMuncher",
        "cta": "Trade on Photon",
    },
    "banana": {
        "name": "🍌 Banana Gun",
        "desc": "Multi-chain sniper bot. ETH, SOL, BASE. Anti-MEV.",
        "url": "https://bananagun.io?ref=RugMuncher",
        "cta": "Snipe with Banana",
    },
    "maestro": {
        "name": "🎼 Maestro",
        "desc": "Telegram trading bot. Copy trades, limit orders, wallet tracker.",
        "url": "https://maestrobots.com?ref=RugMuncher",
        "cta": "Trade with Maestro",
    },
}

# ── API Keys ──
STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY", "")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET", "")

# ── x402 Merchant ──
X402_MERCHANT = os.getenv("X402_MERCHANT", "0x1E3AC01d0fdb976179790BDD02823196A92705C9")
X402_USDC = os.getenv("X402_USDC", "0x833589fCD6eDb6E08f4c7C32D4f71b54bda02913")

# ── Channel IDs (set via env vars: CHANNEL_CRYPTO_ALERTS, etc.) ──
CHANNEL_IDS = {
    "main_channel": os.getenv("CHANNEL_CRYPTO_RUGMUNCHER", ""),
    "community_scans": os.getenv("CHANNEL_COMMUNITY_SCANS", ""),
    "crypto_alerts": os.getenv("CHANNEL_CRYPTO_ALERTS", ""),
    "crypto_alpha": os.getenv("CHANNEL_CRYPTO_ALPHA", ""),
    "safe_gems": os.getenv("CHANNEL_SAFE_GEMS", ""),
    "dev_watch": os.getenv("CHANNEL_DEV_WATCH", ""),
    "honeypot_traps": os.getenv("CHANNEL_HONEYPOT_TRAPS", ""),
    "liquidity_alerts": os.getenv("CHANNEL_LIQUIDITY_ALERTS", ""),
    "launch_radar": os.getenv("CHANNEL_LAUNCH_RADAR", ""),
    "wallet_tracker": os.getenv("CHANNEL_WALLET_TRACKER", ""),
    "sentiment_feed": os.getenv("CHANNEL_SENTIMENT_FEED", ""),
}
