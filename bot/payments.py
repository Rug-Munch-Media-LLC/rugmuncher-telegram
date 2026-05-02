"""
Rug Muncher — Payment Engine
============================
Handles crypto + fiat payments for premium features.

Methods:
  • x402 — USDC on Base (per-request micropayments)
  • Stripe — Card payments for subscriptions
  • Crypto wallets — Manual verification

Products:
  • Single scan unlock — $2 contract / $5 wallet
  • Pro subscription — $29/mo
  • Alpha subscription — $99/mo
  • Lifetime pass — $499
  • Channel subscriptions — $3-10/mo
"""

import os
import hashlib
import time
import logging
from typing import Dict, Optional, Tuple
from datetime import datetime, timedelta

from bot.database import get_db

logger = logging.getLogger("payments")

# ── Pricing ──
PRODUCTS = {
    "scan_contract": {"name": "Contract Scan Unlock", "price_usd": 2.00},
    "scan_wallet": {"name": "Wallet Scan Unlock", "price_usd": 5.00},
    "pro_monthly": {"name": "Pro Membership", "price_usd": 29.00},
    "pro_yearly": {"name": "Pro Membership (Yearly)", "price_usd": 290.00},
    "alpha_monthly": {"name": "Alpha Membership", "price_usd": 99.00},
    "alpha_yearly": {"name": "Alpha Membership (Yearly)", "price_usd": 990.00},
    "lifetime": {"name": "Lifetime Pass", "price_usd": 499.00},
    "channel_alpha": {"name": "Crypto Alpha Channel", "price_usd": 5.00},
    "channel_liquidity": {"name": "Liquidity Alerts Channel", "price_usd": 3.00},
    "channel_wallets": {"name": "Wallet Tracker Channel", "price_usd": 10.00},
}

# ── x402 Config ──
X402_MERCHANT = os.getenv("X402_MERCHANT", "0x1E3AC01d0fdb976179790BDD02823196A92705C9")
X402_USDC = os.getenv("X402_USDC", "0x833589fCD6eDb6E08f4c7C32D4f71b54bda02913")
BASE_RPC = os.getenv("BASE_RPC", "https://mainnet.base.org")


class PaymentEngine:
    """Handle payments and verify premium access."""

    def __init__(self):
        self.pending_x402: Dict[str, dict] = {}

    def create_payment_link(self, user_id: str, product_key: str) -> Tuple[str, str]:
        """Create a payment request. Returns (payment_id, instructions)."""
        product = PRODUCTS.get(product_key)
        if not product:
            return "", "Unknown product"

        payment_id = f"rm_{user_id}_{product_key}_{int(time.time())}"

        # x402 payment request (simplified)
        if product_key in ["scan_contract", "scan_wallet"]:
            # Per-request micropayment
            self.pending_x402[payment_id] = {
                "user_id": user_id,
                "product": product_key,
                "amount": product["price_usd"],
                "status": "pending",
                "created_at": datetime.utcnow().isoformat(),
            }
            instructions = (
                f"<b>🔓 {product['name']}</b>\n\n"
                f"Amount: <b>${product['price_usd']:.2f} USDC</b> on Base\n\n"
                f"Pay to: <code>{X402_MERCHANT}</code>\n"
                f"Amount: <code>{product['price_usd']:.2f} USDC</code>\n"
                f"Memo: <code>{payment_id}</code>\n\n"
                f"After payment, click verify below."
            )
            return payment_id, instructions

        # Subscription payments — link to external checkout
        instructions = (
            f"<b>💎 {product['name']}</b>\n\n"
            f"Price: <b>${product['price_usd']:.2f}</b>\n\n"
            f"Payment methods:\n"
            f"  • USDC on Base: <code>{X402_MERCHANT}</code>\n"
            f"  • Card: Contact @rugmuncher_support\n\n"
            f"Reference: <code>{payment_id}</code>"
        )
        return payment_id, instructions

    def verify_x402_payment(self, payment_id: str, tx_hash: str = None) -> bool:
        """Verify a crypto payment."""
        # In production, this would query the blockchain for the tx
        # For now, we accept manual verification via admin
        pending = self.pending_x402.get(payment_id)
        if not pending:
            return False

        # TODO: Add actual on-chain verification
        # 1. Query Base RPC for transfer to merchant
        # 2. Check amount matches
        # 3. Check memo/payment_id in tx data

        # Auto-verify for demo (remove in production)
        pending["status"] = "verified"
        pending["verified_at"] = datetime.utcnow().isoformat()
        self._grant_access(pending["user_id"], pending["product"])
        return True

    def _grant_access(self, user_id: str, product: str):
        """Grant premium access in database."""
        with get_db() as db:
            # Check if user exists
            row = db.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)).fetchone()
            if not row:
                return

            if product in ["scan_contract", "scan_wallet"]:
                # Grant one-time scan credit
                db.execute("""
                    INSERT INTO payments (user_id, product, amount, status, created_at)
                    VALUES (?, ?, ?, 'completed', ?)
                """, (user_id, product, PRODUCTS[product]["price_usd"], datetime.utcnow().isoformat()))
            elif product in ["pro_monthly", "alpha_monthly", "channel_alpha", "channel_liquidity", "channel_wallets"]:
                # Grant subscription (30 days)
                expires = (datetime.utcnow() + timedelta(days=30)).isoformat()
                db.execute("""
                    INSERT OR REPLACE INTO subscriptions (user_id, tier, expires, created_at)
                    VALUES (?, ?, ?, ?)
                """, (user_id, product, expires, datetime.utcnow().isoformat()))
            elif product in ["lifetime"]:
                db.execute("""
                    INSERT OR REPLACE INTO subscriptions (user_id, tier, expires, created_at)
                    VALUES (?, ?, '2099-12-31', ?)
                """, (user_id, product, datetime.utcnow().isoformat()))

            db.execute("UPDATE users SET tier = ? WHERE user_id = ?",
                      ("premium" if "pro" in product else "alpha", user_id))

    def check_premium(self, user_id: str) -> Tuple[bool, str]:
        """Check if user has active premium."""
        with get_db() as db:
            row = db.execute("SELECT tier FROM users WHERE user_id = ?", (user_id,)).fetchone()
            if row and row["tier"] in ("premium", "alpha"):
                return True, row["tier"]

            sub = db.execute(
                "SELECT * FROM subscriptions WHERE user_id = ? AND expires > ?",
                (user_id, datetime.utcnow().isoformat())
            ).fetchone()
            if sub:
                return True, sub["tier"]

        return False, "free"

    def get_receipt(self, payment_id: str) -> Optional[Dict]:
        return self.pending_x402.get(payment_id)


# Initialize payments table if not exists
def init_payments():
    with get_db() as db:
        db.executescript("""
            CREATE TABLE IF NOT EXISTS payments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT,
                product TEXT,
                amount REAL,
                tx_hash TEXT,
                status TEXT DEFAULT 'pending',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                verified_at TEXT,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            );
            CREATE TABLE IF NOT EXISTS subscriptions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT,
                tier TEXT,
                expires TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, tier),
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            );
            CREATE INDEX IF NOT EXISTS idx_payments_user ON payments(user_id);
            CREATE INDEX IF NOT EXISTS idx_subs_user ON subscriptions(user_id);
        """)


# Singleton
payment_engine = PaymentEngine()
init_payments()
