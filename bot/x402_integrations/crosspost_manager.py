"""
Unified Crosspost Manager
Posts content to X/Twitter, Telegram, Discord, and other platforms.
Integrates with x402 gateways for pay-per-post monetization.
"""
import os
import logging
from typing import Dict, List, Optional
from dataclasses import dataclass
from datetime import datetime

from bot.x402_integrations.client import x402_client, X402Response

logger = logging.getLogger("crosspost_manager")

# ── Platform configs ──
PLATFORM_EMOJIS = {
    "twitter": "🐦",
    "telegram": "📨",
    "discord": "💬",
    "web": "🌐",
}


@dataclass
class CrosspostResult:
    platform: str
    success: bool
    post_id: Optional[str] = None
    url: Optional[str] = None
    error: Optional[str] = None
    timestamp: str = ""


class CrosspostManager:
    """One interface to post everywhere."""

    def __init__(self):
        self.twitter = None
        self.telegram_bot_token = os.getenv("TELEGRAM_BOT_TOKEN", "")
        self.telegram_channel = os.getenv("CHANNEL_CRYPTO_ALERTS", "")
        self.telegram_main_channel = os.getenv("CHANNEL_CRYPTO_RUGMUNCHER", "")
        self._init_twitter()

    def _init_twitter(self):
        try:
            import tweepy
            bearer = os.getenv("TWITTER_BEARER_TOKEN", "")
            api_key = os.getenv("TWITTER_API_KEY", "")
            api_secret = os.getenv("TWITTER_API_SECRET", "")
            access_token = os.getenv("TWITTER_ACCESS_TOKEN", "")
            access_secret = os.getenv("TWITTER_ACCESS_SECRET", "")
            if all([api_key, api_secret, access_token, access_secret]):
                self.twitter = tweepy.Client(
                    bearer_token=bearer,
                    consumer_key=api_key,
                    consumer_secret=api_secret,
                    access_token=access_token,
                    access_token_secret=access_secret,
                )
                logger.info("✅ Twitter bridge ready")
        except Exception as e:
            logger.warning(f"Twitter init failed: {e}")

    # ── Core post methods ──

    def post_to_twitter(self, text: str, media_urls: Optional[List[str]] = None) -> CrosspostResult:
        if not self.twitter:
            return CrosspostResult(platform="twitter", success=False,
                                   error="Twitter not configured")
        try:
            resp = self.twitter.create_tweet(text=text)
            tweet_id = resp.data["id"]
            return CrosspostResult(
                platform="twitter",
                success=True,
                post_id=tweet_id,
                url=f"https://x.com/i/web/status/{tweet_id}",
                timestamp=datetime.utcnow().isoformat(),
            )
        except Exception as e:
            return CrosspostResult(platform="twitter", success=False, error=str(e))

    def post_to_telegram(self, text: str, chat_id: Optional[str] = None,
                         parse_mode: str = "HTML", broadcast: bool = False) -> CrosspostResult:
        token = self.telegram_bot_token
        if not token:
            return CrosspostResult(platform="telegram", success=False,
                                   error="TELEGRAM_BOT_TOKEN not set")
        import requests
        results = []
        targets = set()
        if chat_id:
            targets.add(chat_id)
        if broadcast:
            if self.telegram_main_channel:
                targets.add(self.telegram_main_channel)
            if self.telegram_channel:
                targets.add(self.telegram_channel)
        if not targets:
            targets.add(self.telegram_channel)
        for cid in targets:
            if not cid:
                continue
            try:
                r = requests.post(
                    f"https://api.telegram.org/bot{token}/sendMessage",
                    json={"chat_id": cid, "text": text, "parse_mode": parse_mode,
                          "disable_web_page_preview": False},
                    timeout=15,
                )
                data = r.json()
                if data.get("ok"):
                    msg_id = data["result"]["message_id"]
                    results.append(CrosspostResult(
                        platform="telegram",
                        success=True,
                        post_id=str(msg_id),
                        timestamp=datetime.utcnow().isoformat(),
                    ))
                else:
                    results.append(CrosspostResult(platform="telegram", success=False,
                                       error=data.get("description", "Unknown")))
            except Exception as e:
                results.append(CrosspostResult(platform="telegram", success=False, error=str(e)))
        # Return first result for compatibility
        return results[0] if results else CrosspostResult(platform="telegram", success=False, error="No targets")

    def post_to_discord(self, text: str, webhook_url: Optional[str] = None) -> CrosspostResult:
        url = webhook_url or os.getenv("DISCORD_WEBHOOK_URL", "")
        if not url:
            return CrosspostResult(platform="discord", success=False,
                                   error="DISCORD_WEBHOOK_URL not set")
        import requests
        try:
            r = requests.post(url, json={"content": text}, timeout=15)
            if r.status_code in (200, 204):
                return CrosspostResult(
                    platform="discord", success=True,
                    timestamp=datetime.utcnow().isoformat(),
                )
            return CrosspostResult(platform="discord", success=False,
                                   error=f"HTTP {r.status_code}")
        except Exception as e:
            return CrosspostResult(platform="discord", success=False, error=str(e))

    # ── Unified crosspost ──

    def crosspost(self, text: str, platforms: List[str],
                  telegram_chat_id: Optional[str] = None,
                  discord_webhook: Optional[str] = None) -> Dict[str, CrosspostResult]:
        """Post to multiple platforms at once."""
        results = {}
        for platform in platforms:
            if platform == "twitter":
                results[platform] = self.post_to_twitter(text)
            elif platform == "telegram":
                results[platform] = self.post_to_telegram(text, chat_id=telegram_chat_id)
            elif platform == "discord":
                results[platform] = self.post_to_discord(text, webhook_url=discord_webhook)
            else:
                results[platform] = CrosspostResult(
                    platform=platform, success=False, error="Unknown platform"
                )
        return results

    # ── x402 Monetized Post ──

    def monetized_crosspost(self, text: str, platforms: List[str],
                            gateway: str = "solana",
                            payment_header: Optional[str] = None) -> Dict[str, Any]:
        """
        Crosspost with x402 payment gate.
        If no payment_header → returns 402 requirements.
        If payment_header → executes posts.
        """
        if not payment_header:
            # Get payment requirement from chosen gateway
            if gateway == "base":
                resp = x402_client.base_chat("deepseek-v3.2", [{"role": "user", "content": text}])
            elif gateway == "solana":
                resp = x402_client.solana_chat([{"role": "user", "content": text}])
            else:
                resp = x402_client.agent_submit_task(text)

            if resp.status_code == 402:
                return {
                    "status": "payment_required",
                    "gateway": gateway,
                    "payment_required": resp.data,
                }
            # If gateway returned 200, we still haven't paid — use it as signal
            return {
                "status": "payment_required",
                "gateway": gateway,
                "payment_required": resp.data,
            }

        # Payment provided — execute posts
        results = self.crosspost(text, platforms)
        return {
            "status": "posted",
            "gateway": gateway,
            "results": {k: {
                "success": v.success,
                "post_id": v.post_id,
                "url": v.url,
                "error": v.error,
            } for k, v in results.items()},
        }


# Singleton
crosspost_manager = CrosspostManager()
