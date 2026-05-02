"""
Rug Muncher — Multi-Channel Intelligence Network
================================================
Specialized channel outputs for different audiences.

Channels:
  🏘️ Community Scans    — Daily rankings, trending tokens
  🚨 Crypto Alerts      — Hacks, rugs, scams (free)
  🐋 Crypto Alpha       — Whale moves, big money ($5/mo)
  💎 Safe Gems          — High-score SAFE tokens (alpha buys)
  🕵️ Dev Watch         — Serial ruggers, deployer alerts
  🍯 Honeypot Traps     — Real-time honeypot detections
  💧 Liquidity Alerts   — LP drains, unlocks, migrations
  🚀 Launch Radar       — Brand new contracts scanned
  👛 Wallet Tracker     — Whale/insider wallet movements
  📊 Sentiment Feed     — Social news correlation

All channels support:
  • Auto-post on trigger conditions
  • Formatted cards with proof
  • Subscriber-only gating
  • Daily/weekly digest modes
"""

import os
from typing import Dict, List, Optional
from dataclasses import dataclass
from datetime import datetime

from telegram import Bot


# ── Channel Registry ──

@dataclass
class Channel:
    key: str
    name: str
    emoji: str
    description: str
    price_monthly: float
    price_yearly: float
    access: str  # "free", "premium", "alpha"
    trigger_events: List[str]
    format_style: str


CHANNELS = {
    "main_channel": Channel(
        key="main_channel",
        name="Crypto Rug Muncher",
        emoji="🔍",
        description="Main brand channel — posts from website, Twitter, and alerts.",
        price_monthly=0,
        price_yearly=0,
        access="free",
        trigger_events=["high_risk", "new_contract", "web_post"],
        format_style="alert",
    ),
    "community_scans": Channel(
        key="community_scans",
        name="Community Scan Feed",
        emoji="🏘️",
        description="Daily scan rankings + trending tokens from the community.",
        price_monthly=0,
        price_yearly=0,
        access="free",
        trigger_events=["daily_digest", "trending"],
        format_style="leaderboard",
    ),
    "crypto_alerts": Channel(
        key="crypto_alerts",
        name="Crypto Alerts",
        emoji="🚨",
        description="Critical alerts: hacks, incoming rugs, scams, exploits.",
        price_monthly=0,
        price_yearly=0,
        access="free",
        trigger_events=["high_risk", "honeypot", "exploit"],
        format_style="alert",
    ),
    "crypto_alpha": Channel(
        key="crypto_alpha",
        name="Crypto Alpha",
        emoji="🐋",
        description="Whale movements, big money placements, insider accumulation.",
        price_monthly=5.0,
        price_yearly=49.0,
        access="premium",
        trigger_events=["whale_move", "big_buy", "insider"],
        format_style="alpha",
    ),
    "safe_gems": Channel(
        key="safe_gems",
        name="Safe Gems",
        emoji="💎",
        description="High-scoring SAFE tokens spotted before they pump.",
        price_monthly=0,
        price_yearly=0,
        access="free",
        trigger_events=["safe_score"],
        format_style="gem",
    ),
    "dev_watch": Channel(
        key="dev_watch",
        name="Dev Watch",
        emoji="🕵️",
        description="Serial ruggers, deployer history, blacklisted devs.",
        price_monthly=0,
        price_yearly=0,
        access="free",
        trigger_events=["serial_rugger", "blacklisted_dev"],
        format_style="alert",
    ),
    "honeypot_traps": Channel(
        key="honeypot_traps",
        name="Honeypot Traps",
        emoji="🍯",
        description="Real-time honeypot and trap contract detections.",
        price_monthly=0,
        price_yearly=0,
        access="free",
        trigger_events=["honeypot"],
        format_style="trap",
    ),
    "liquidity_alerts": Channel(
        key="liquidity_alerts",
        name="Liquidity Alerts",
        emoji="💧",
        description="LP drains, unlocks, migrations, sudden liquidity changes.",
        price_monthly=2.99,
        price_yearly=29.0,
        access="premium",
        trigger_events=["lp_drain", "unlock", "migration"],
        format_style="alert",
    ),
    "launch_radar": Channel(
        key="launch_radar",
        name="Launch Radar",
        emoji="🚀",
        description="Brand new contracts being scanned in real-time.",
        price_monthly=0,
        price_yearly=0,
        access="free",
        trigger_events=["new_contract"],
        format_style="launch",
    ),
    "wallet_tracker": Channel(
        key="wallet_tracker",
        name="Wallet Tracker",
        emoji="👛",
        description="Whale and insider wallet movement alerts.",
        price_monthly=9.99,
        price_yearly=99.0,
        access="alpha",
        trigger_events=["whale_wallet", "insider_move"],
        format_style="wallet",
    ),
    "sentiment_feed": Channel(
        key="sentiment_feed",
        name="Sentiment Feed",
        emoji="📊",
        description="Social sentiment spikes correlated with on-chain data.",
        price_monthly=0,
        price_yearly=0,
        access="free",
        trigger_events=["sentiment_spike"],
        format_style="sentiment",
    ),
}


# ── Formatters ──

def format_alert_card(address: str, chain: str, risk_score: int,
                      risk_level: str, findings: List[str],
                      channel: Channel, extra: Dict = None) -> str:
    """Format a channel-specific alert card."""
    extra = extra or {}
    now = datetime.utcnow().strftime("%H:%M UTC")

    bars = "█" * (risk_score // 10) + "░" * (10 - risk_score // 10)
    short_addr = f"{address[:6]}...{address[-4:]}"

    if channel.format_style == "alert":
        return (
            f"<b>{channel.emoji} {channel.name.upper()}</b>\n"
            f"<b>╔══════════════════════════════════════╗</b>\n"
            f"<b>║  🚨 {risk_level.upper()} DETECTED</b>\n"
            f"<b>╚══════════════════════════════════════╝</b>\n\n"
            f"<b>📍 Target:</b> <code>{short_addr}</code>\n"
            f"<b>⛓ Chain:</b> {chain.upper()}\n"
            f"<b>💀 Risk:</b> {risk_score}/100 <code>[{bars}]</code>\n"
            f"<b>🕐 Time:</b> {now}\n\n"
            f"<b>⚠️ Findings:</b>\n" +
            "\n".join([f"  • {f}" for f in findings[:5]]) +
            f"\n\n<i>Scan with @rugmuncherbot for full dossier</i>"
        )

    elif channel.format_style == "alpha":
        whale_size = extra.get("whale_size", "Unknown")
        return (
            f"<b>{channel.emoji} {channel.name.upper()}</b>\n"
            f"<b>╔══════════════════════════════════════╗</b>\n"
            f"<b>║  🐋 BIG MONEY MOVEMENT</b>\n"
            f"<b>╚══════════════════════════════════════╝</b>\n\n"
            f"<b>📍 Target:</b> <code>{short_addr}</code>\n"
            f"<b>⛓ Chain:</b> {chain.upper()}\n"
            f"<b>💰 Size:</b> <b>{whale_size}</b>\n"
            f"<b>💀 Risk:</b> {risk_score}/100 <code>[{bars}]</code>\n"
            f"<b>🕐 Time:</b> {now}\n\n"
            f"<i>Alpha for subscribers only. DYOR.</i>"
        )

    elif channel.format_style == "gem":
        return (
            f"<b>{channel.emoji} {channel.name.upper()}</b>\n"
            f"<b>╔══════════════════════════════════════╗</b>\n"
            f"<b>║  💎 SAFE GEM SPOTTED</b>\n"
            f"<b>╚══════════════════════════════════════╝</b>\n\n"
            f"<b>📍 Contract:</b> <code>{short_addr}</code>\n"
            f"<b>⛓ Chain:</b> {chain.upper()}\n"
            f"<b>🛡️ Safety:</b> {risk_score}/100 <code>[{bars}]</code>\n"
            f"<b>🕐 Time:</b> {now}\n\n"
            f"<i>Clean contract spotted by the community. NFA.</i>"
        )

    elif channel.format_style == "trap":
        return (
            f"<b>{channel.emoji} {channel.name.upper()}</b>\n"
            f"<b>╔══════════════════════════════════════╗</b>\n"
            f"<b>║  🍯 HONEYPOT CONFIRMED</b>\n"
            f"<b>╚══════════════════════════════════════╝</b>\n\n"
            f"<b>📍 Target:</b> <code>{short_addr}</code>\n"
            f"<b>⛓ Chain:</b> {chain.upper()}\n"
            f"<b>💀 Risk:</b> {risk_score}/100\n"
            f"<b>🕐 Time:</b> {now}\n\n"
            f"<b>❌ DO NOT BUY THIS TOKEN</b>\n"
            f"<i>Verified honeypot. Funds will be locked.</i>"
        )

    elif channel.format_style == "launch":
        return (
            f"<b>{channel.emoji} {channel.name.upper()}</b>\n"
            f"<b>╔══════════════════════════════════════╗</b>\n"
            f"<b>║  🚀 NEW CONTRACT DETECTED</b>\n"
            f"<b>╚══════════════════════════════════════╝</b>\n\n"
            f"<b>📍 Contract:</b> <code>{short_addr}</code>\n"
            f"<b>⛓ Chain:</b> {chain.upper()}\n"
            f"<b>💀 Risk:</b> {risk_score}/100 <code>[{bars}]</code>\n"
            f"<b>🕐 Time:</b> {now}\n\n"
            f"<i>Fresh off the blockchain. Scan before you ape.</i>"
        )

    elif channel.format_style == "wallet":
        wallet = extra.get("wallet", "Unknown")
        action = extra.get("action", "movement")
        return (
            f"<b>{channel.emoji} {channel.name.upper()}</b>\n"
            f"<b>╔══════════════════════════════════════╗</b>\n"
            f"<b>║  👛 WALLET ALERT</b>\n"
            f"<b>╚══════════════════════════════════════╝</b>\n\n"
            f"<b>👤 Wallet:</b> <code>{wallet[:8]}...{wallet[-4:]}</code>\n"
            f"<b>📍 Target:</b> <code>{short_addr}</code>\n"
            f"<b>⛓ Chain:</b> {chain.upper()}\n"
            f"<b>⚡ Action:</b> <b>{action.upper()}</b>\n"
            f"<b>🕐 Time:</b> {now}\n\n"
            f"<i>Whale/insider activity detected.</i>"
        )

    elif channel.format_style == "sentiment":
        sentiment = extra.get("sentiment", "neutral")
        spike = extra.get("spike_metric", "0%")
        return (
            f"<b>{channel.emoji} {channel.name.upper()}</b>\n"
            f"<b>╔══════════════════════════════════════╗</b>\n"
            f"<b>║  📊 SENTIMENT SPIKE</b>\n"
            f"<b>╚══════════════════════════════════════╝</b>\n\n"
            f"<b>📍 Target:</b> <code>{short_addr}</code>\n"
            f"<b>⛓ Chain:</b> {chain.upper()}\n"
            f"<b>📈 Sentiment:</b> <b>{sentiment.upper()}</b> (+{spike})\n"
            f"<b>💀 Risk:</b> {risk_score}/100\n"
            f"<b>🕐 Time:</b> {now}\n\n"
            f"<i>Social buzz correlated with on-chain data.</i>"
        )

    elif channel.format_style == "leaderboard":
        return (
            f"<b>{channel.emoji} {channel.name.upper()}</b>\n"
            f"<b>╔══════════════════════════════════════╗</b>\n"
            f"<b>║  📊 COMMUNITY SCAN RANKINGS</b>\n"
            f"<b>╚══════════════════════════════════════╝</b>\n\n"
            f"<i>Daily digest of what the community scanned...</i>\n\n"
            f"{extra.get('rankings_text', 'No data yet')}\n\n"
            f"<i>Join the hunt: @rugmuncherbot</i>"
        )

    # Fallback
    return f"<b>{channel.emoji} {channel.name}</b>\n<code>{short_addr}</code> on {chain.upper()} — Risk: {risk_score}/100"


# ── Channel Manager ──

class ChannelManager:
    """Manage multi-channel alerts and subscriptions."""

    def __init__(self, bot: Bot):
        self.bot = bot
        self.channel_ids = self._load_channel_ids()
        # Dedup tracker: {content_hash: message_id} for main channel
        self._main_channel_hashes: Dict[str, int] = {}
        self._main_channel_id = self.channel_ids.get("main_channel")

    def _content_hash(self, text: str) -> str:
        """Hash content for dedup detection (ignores timestamp)."""
        import hashlib
        # Strip timestamps, URLs with IDs to normalize
        normalized = text
        for pattern in [r"\d{2}:\d{2} UTC", r"message_id=\d+", r"id=\d+"]:
            normalized = __import__("re").sub(pattern, "", normalized)
        return hashlib.md5(normalized.encode()).hexdigest()[:16]

    async def _delete_old_duplicate(self, chat_id: str, new_hash: str):
        """Delete old messages with same content hash, keep newest."""
        if chat_id not in self._main_channel_hashes:
            self._main_channel_hashes = {}
            # Scan existing messages once
            try:
                async for msg in self.bot.get_chat_history(chat_id, limit=100):
                    if msg.text:
                        h = self._content_hash(msg.text)
                        self._main_channel_hashes[h] = msg.id
            except Exception:
                pass

        for h, msg_id in list(self._main_channel_hashes.items()):
            if h == new_hash:
                try:
                    await self.bot.delete_message(chat_id=chat_id, message_id=msg_id)
                    del self._main_channel_hashes[h]
                except Exception:
                    pass

    def _load_channel_ids(self) -> Dict[str, str]:
        """Load channel IDs from environment."""
        ids = {}
        for key in CHANNELS.keys():
            env_var = f"CHANNEL_{key.upper()}"
            val = os.getenv(env_var, "")
            if val:
                ids[key] = val
        return ids

    def is_configured(self, channel_key: str) -> bool:
        return channel_key in self.channel_ids

    async def post(self, channel_key: str, text: str, photo_bytes: bytes = None):
        """Post a message to a channel with dedup protection for main channel."""
        if channel_key not in self.channel_ids:
            return False
        chat_id = self.channel_ids[channel_key]
        try:
            # Dedup for main channel: delete old version before posting new
            if channel_key == "main_channel":
                content_hash = self._content_hash(text)
                await self._delete_old_duplicate(chat_id, content_hash)
                self._main_channel_hashes[content_hash] = None  # placeholder

            if photo_bytes:
                msg = await self.bot.send_photo(
                    chat_id=chat_id,
                    photo=photo_bytes,
                    caption=text,
                    parse_mode="HTML",
                )
            else:
                msg = await self.bot.send_message(
                    chat_id=chat_id,
                    text=text,
                    parse_mode="HTML",
                    disable_web_page_preview=True,
                )
            # Track message ID for future dedup
            if channel_key == "main_channel" and msg:
                self._main_channel_hashes[self._content_hash(text)] = msg.id
            return True
        except Exception as e:
            print(f"Channel post failed for {channel_key}: {e}")
            return False

    async def maybe_post_scan(self, address: str, chain: str, risk_score: int,
                              risk_level: str, findings: List[str],
                              scan_type: str = "contract", extra: Dict = None):
        """Auto-route scan results to appropriate channels based on triggers."""
        extra = extra or {}

        for key, channel in CHANNELS.items():
            if not self.is_configured(key):
                continue

            should_post = False

            # Route by risk score / event type
            if "high_risk" in channel.trigger_events and risk_score >= 80:
                should_post = True
            if "honeypot" in channel.trigger_events and any("honeypot" in f.lower() for f in findings):
                should_post = True
            if "safe_score" in channel.trigger_events and risk_score <= 20:
                should_post = True
            if "new_contract" in channel.trigger_events:
                should_post = True
            if "serial_rugger" in channel.trigger_events and any("serial" in f.lower() or "rugger" in f.lower() for f in findings):
                should_post = True
            if "lp_drain" in channel.trigger_events and any("drain" in f.lower() or "liquidity" in f.lower() for f in findings):
                should_post = True

            if should_post:
                text = format_alert_card(address, chain, risk_score, risk_level,
                                         findings, channel, extra)
                await self.post(key, text)


def build_channel_list_text() -> str:
    """Build formatted channel list for /channels command."""
    lines = [f"<b>📡 RUG MUNCHER INTELLIGENCE NETWORK</b>\n"]
    for key, ch in CHANNELS.items():
        price = "FREE" if ch.price_monthly == 0 else f"${ch.price_monthly:.0f}/mo"
        lines.append(
            f"{ch.emoji} <b>{ch.name}</b> — {price}\n"
            f"   <i>{ch.description}</i>\n"
        )
    return "\n".join(lines)
