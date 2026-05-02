"""
Rug Muncher — Smart Money Tracker
==================================
Tracks whale movements, insider accumulation, and big-money
signals for the Crypto Alpha channel.

Signals:
  • Whale wallet buys (> $10k)
  • Insider accumulation (same dev, multiple tokens)
  • Smart money clustering (multiple whales same token)
  • Exchange inflows/outflows
  • Fresh wallet funding patterns
"""

import os
import json
from typing import Dict, List, Optional
from dataclasses import dataclass
from datetime import datetime, timedelta


@dataclass
class SmartMoneySignal:
    signal_type: str          # whale_buy, insider, cluster, exchange, fresh_wallet
    address: str
    chain: str
    wallet: str
    amount_usd: float
    confidence: int           # 0-100
    details: str
    timestamp: str


class SmartMoneyTracker:
    """Analyze transactions for smart money patterns."""

    WHALE_THRESHOLD = 10000.0    # $10k USD
    CLUSTER_MIN_WALLETS = 3
    FRESH_WALLET_MAX_AGE_HOURS = 24

    def __init__(self):
        self.recent_signals: List[SmartMoneySignal] = []
        self.wallet_history: Dict[str, List[Dict]] = {}

    def analyze_transaction(self, tx: Dict) -> Optional[SmartMoneySignal]:
        """Analyze a single transaction for smart money signals."""
        wallet = tx.get("from", "")
        to = tx.get("to", "")
        value_usd = tx.get("value_usd", 0)
        token = tx.get("token_address", "")
        chain = tx.get("chain", "ethereum")

        # Whale buy
        if value_usd >= self.WHALE_THRESHOLD:
            return SmartMoneySignal(
                signal_type="whale_buy",
                address=token,
                chain=chain,
                wallet=wallet,
                amount_usd=value_usd,
                confidence=min(100, int(value_usd / 1000)),
                details=f"Whale bought ${value_usd:,.0f} worth",
                timestamp=datetime.utcnow().isoformat(),
            )

        # Fresh wallet
        wallet_age_hours = tx.get("wallet_age_hours", 999)
        if wallet_age_hours <= self.FRESH_WALLET_MAX_AGE_HOURS and value_usd >= 1000:
            return SmartMoneySignal(
                signal_type="fresh_wallet",
                address=token,
                chain=chain,
                wallet=wallet,
                amount_usd=value_usd,
                confidence=70,
                details=f"Fresh wallet ({wallet_age_hours}h old) bought ${value_usd:,.0f}",
                timestamp=datetime.utcnow().isoformat(),
            )

        return None

    def detect_cluster(self, token: str, chain: str, window_hours: int = 6) -> Optional[SmartMoneySignal]:
        """Detect if multiple whales bought same token in window."""
        cutoff = datetime.utcnow() - timedelta(hours=window_hours)
        wallets = set()
        total_usd = 0.0

        for sig in self.recent_signals:
            if sig.address.lower() != token.lower():
                continue
            if sig.chain != chain:
                continue
            sig_time = datetime.fromisoformat(sig.timestamp)
            if sig_time < cutoff:
                continue
            if sig.signal_type == "whale_buy":
                wallets.add(sig.wallet)
                total_usd += sig.amount_usd

        if len(wallets) >= self.CLUSTER_MIN_WALLETS:
            return SmartMoneySignal(
                signal_type="cluster",
                address=token,
                chain=chain,
                wallet=",".join(list(wallets)[:3]),
                amount_usd=total_usd,
                confidence=min(100, 50 + len(wallets) * 10),
                details=f"{len(wallets)} whales clustered ${total_usd:,.0f}",
                timestamp=datetime.utcnow().isoformat(),
            )
        return None

    def format_signal(self, signal: SmartMoneySignal) -> str:
        """Format signal for channel posting."""
        emojis = {
            "whale_buy": "🐋",
            "insider": "🕵️",
            "cluster": "🎯",
            "exchange": "🏦",
            "fresh_wallet": "👶",
        }
        emoji = emojis.get(signal.signal_type, "💰")
        short_wallet = f"{signal.wallet[:6]}...{signal.wallet[-4:]}" if len(signal.wallet) > 12 else signal.wallet

        return (
            f"<b>{emoji} SMART MONEY SIGNAL</b>\n"
            f"<b>╔══════════════════════════════════════╗</b>\n"
            f"<b>║  {signal.signal_type.replace('_', ' ').upper()}</b>\n"
            f"<b>╚══════════════════════════════════════╝</b>\n\n"
            f"<b>📍 Token:</b> <code>{signal.address[:10]}...</code>\n"
            f"<b>⛓ Chain:</b> {signal.chain.upper()}\n"
            f"<b>👤 Wallet:</b> <code>{short_wallet}</code>\n"
            f"<b>💰 Amount:</b> <b>${signal.amount_usd:,.0f}</b>\n"
            f"<b>🎯 Confidence:</b> {signal.confidence}%\n"
            f"<b>🕐 Time:</b> {signal.timestamp[:16]}\n\n"
            f"<i>{signal.details}</i>\n\n"
            f"<i>Alpha for subscribers only. DYOR.</i>"
        )

    def add_signal(self, signal: SmartMoneySignal):
        """Store signal for cluster detection."""
        self.recent_signals.append(signal)
        # Prune old signals
        cutoff = datetime.utcnow() - timedelta(hours=24)
        self.recent_signals = [
            s for s in self.recent_signals
            if datetime.fromisoformat(s.timestamp) > cutoff
        ]


# Singleton
smart_money = SmartMoneyTracker()
