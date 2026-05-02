"""
🚀 Launch Detector — Real-Time Token Birth Monitor
==================================================
Inspired by program-log subscription patterns for Solana,
but architected as a chain-agnostic launch detection backbone.

For Solana:
  • Subscribe to Pump.fun / Raydium / Orca program logs
  • Filter by fee-account / program ID for minimal RPC load
  • Extract creator wallet, base token, LP amounts instantly

For EVM:
  • WebSocket filter on PairCreated events (Uniswap V2/V3, PancakeSwap)
  • Log parsing for token0/token1/factory/pair address

Two-stage pipeline:
  1. INSTANT: Emit "new token detected" with bare metadata
  2. ENRICHED: Async follow-up with risk report once APIs respond
"""

import asyncio
import json
import logging
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Callable, Any
from datetime import datetime

logger = logging.getLogger("launch_detector")


@dataclass
class LaunchEvent:
    chain: str
    token_address: str
    pair_address: Optional[str]
    creator_wallet: Optional[str]
    quote_token: str           # SOL, ETH, BNB, etc.
    timestamp: datetime
    lp_amount_quote: Optional[float] = None
    lp_amount_base: Optional[float] = None
    dex: str = "unknown"       # pumpfun, raydium, uniswap_v2, pancakeswap, etc.
    raw: Dict = field(default_factory=dict)


@dataclass
class EnrichedLaunch:
    launch: LaunchEvent
    risk_score: Optional[float] = None
    risk_level: str = "PENDING"
    rugcheck_url: Optional[str] = None
    first_findings: List[str] = field(default_factory=list)


class LaunchDetector:
    """Architecture for real-time launch detection.

    NOTE: This module contains the *detection logic and orchestration*.
    Actual WebSocket / RPC connections should be managed by the
    bot's scheduler or a dedicated async runner.
    """

    # ── Solana program accounts of interest ──
    SOLANA_PROGRAMS = {
        "pumpfun": {"program": "6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P", "fee": None},
        "raydium": {"program": "675kPX9MHTjS2zt1qfr1NYHuzeLXfQM9H24wFSUt1Mp8",
                    "fee": "7YttLkHDoNj9wyDur5pM1ejNaAvT9X4eqaYcHQqtj2G5"},
        "orca": {"program": "9W959DqEETiGZocYWCQPaJ6sBmUzgfxXfqGeTEdp3aQP", "fee": None},
    }

    # ── EVM event signatures ──
    EVM_EVENT_SIGS = {
        "uniswap_v2_paircreated": "0x0d3648bd0f6ba80134a33ba9275ac585d9d315f0ad8355cddefde31afa28d0e9",
        "uniswap_v3_poolcreated": "0x783cca1c0412dd0d695e784568c96da2e9c22ff989357a2e8b1d9b2b4e6b7118",
    }

    def __init__(self):
        self.subscribers: List[Callable[[LaunchEvent], Any]] = []
        self.enrichers: List[Callable[[LaunchEvent], Any]] = []
        self.seen_tokens: set = set()

    def subscribe(self, callback: Callable[[LaunchEvent], Any]):
        """Register a callback for raw launch events."""
        self.subscribers.append(callback)

    def on_enrich(self, callback: Callable[[EnrichedLaunch], Any]):
        """Register a callback for enriched launch events."""
        self.enrichers.append(callback)

    def _notify(self, event: LaunchEvent):
        for cb in self.subscribers:
            try:
                cb(event)
            except Exception as e:
                logger.error(f"Launch subscriber error: {e}")

    def _notify_enriched(self, enriched: EnrichedLaunch):
        for cb in self.enrichers:
            try:
                cb(enriched)
            except Exception as e:
                logger.error(f"Enrich subscriber error: {e}")

    # ═════════════════════════════════════════════════════════════
    #  SOLANA: Process a log from Helius / custom RPC
    # ═════════════════════════════════════════════════════════════
    def process_solana_log(self, log_data: Dict) -> Optional[LaunchEvent]:
        """
        Parse a Solana program log entry.
        log_data should contain at minimum: {program, logs[], signature, blockTime}
        """
        program = log_data.get("program", "")
        sig = log_data.get("signature", "")
        block_time = log_data.get("blockTime", 0)

        detected_dex = None
        for dex, info in self.SOLANA_PROGRAMS.items():
            if program == info["program"] or program == info.get("fee"):
                detected_dex = dex
                break

        if not detected_dex:
            return None

        # Extract token mint from log patterns (heuristic)
        mint = self._extract_sol_mint(log_data.get("logs", []))
        if not mint or mint in self.seen_tokens:
            return None
        self.seen_tokens.add(mint)

        event = LaunchEvent(
            chain="solana",
            token_address=mint,
            pair_address=log_data.get("accountKeys", [None])[0],
            creator_wallet=None,  # Requires getParsedTransaction follow-up
            quote_token="SOL",
            timestamp=datetime.utcfromtimestamp(block_time) if block_time else datetime.utcnow(),
            dex=detected_dex,
            raw=log_data,
        )
        self._notify(event)
        return event

    def _extract_sol_mint(self, logs: List[str]) -> Optional[str]:
        """Heuristic: find first 32–44 char base58 string that looks like a mint."""
        import re
        for line in logs:
            candidates = re.findall(r"[1-9A-HJ-NP-Za-km-z]{32,44}", line)
            for c in candidates:
                if c not in ("So11111111111111111111111111111111111111112",
                             "11111111111111111111111111111111"):
                    return c
        return None

    # ═════════════════════════════════════════════════════════════
    #  EVM: Process a logsSubscription event
    # ═════════════════════════════════════════════════════════════
    def process_evm_log(self, chain: str, log_entry: Dict) -> Optional[LaunchEvent]:
        """
        Parse an EVM log from WebSocket subscription.
        log_entry: {address, topics[], data, transactionHash, blockNumber}
        """
        topics = log_entry.get("topics", [])
        if not topics:
            return None

        topic0 = topics[0]
        if topic0 == self.EVM_EVENT_SIGS["uniswap_v2_paircreated"] and len(topics) >= 3:
            token0 = "0x" + topics[1][-40:]
            token1 = "0x" + topics[2][-40:]
            pair = "0x" + log_entry.get("data", "")[-40:]  # simplified
            # Determine which is the new token (non-ETH stable)
            new_token = token0 if token1 in ("0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2",
                                              "0xbb4cdb9cbd36b01bd1cbaebf2de08d9173bc095c",
                                              "0x4200000000000000000000000000000000000006") else token1
            if new_token in self.seen_tokens:
                return None
            self.seen_tokens.add(new_token)

            event = LaunchEvent(
                chain=chain,
                token_address=new_token,
                pair_address=pair,
                creator_wallet=None,
                quote_token="ETH" if chain in ("eth", "base", "arbitrum", "optimism") else "BNB",
                timestamp=datetime.utcnow(),
                dex="uniswap_v2",
                raw=log_entry,
            )
            self._notify(event)
            return event
        return None

    # ═════════════════════════════════════════════════════════════
    #  TWO-STAGE ENRICHMENT
    # ═════════════════════════════════════════════════════════════
    async def enrich_launch(self, launch: LaunchEvent,
                            risk_scorer_func=None,
                            creator_lookup_func=None) -> EnrichedLaunch:
        """
        Async enrichment pipeline:
          1. Look up creator wallet
          2. Run quick risk score
          3. Emit enriched event
        """
        enriched = EnrichedLaunch(launch=launch)

        if creator_lookup_func:
            try:
                launch.creator_wallet = await creator_lookup_func(launch)
            except Exception as e:
                logger.warning(f"Creator lookup failed: {e}")

        if risk_scorer_func:
            try:
                score_result = await risk_scorer_func(launch.token_address, launch.chain)
                if isinstance(score_result, dict):
                    enriched.risk_score = score_result.get("score")
                    enriched.risk_level = score_result.get("level", "PENDING")
                    enriched.first_findings = score_result.get("findings", [])
                else:
                    enriched.risk_score = score_result
            except Exception as e:
                logger.warning(f"Risk scoring failed: {e}")

        if launch.chain == "solana":
            enriched.rugcheck_url = f"https://rugcheck.xyz/tokens/{launch.token_address}"

        self._notify_enriched(enriched)
        return enriched

    def build_telegram_alert(self, enriched: EnrichedLaunch) -> str:
        """Generate a Telegram-friendly alert string."""
        l = enriched.launch
        emoji = "🟢" if enriched.risk_level == "SAFE" else "🟡" if enriched.risk_level == "LOW" else "🟠" if enriched.risk_level == "MEDIUM" else "🔴" if enriched.risk_level in ("HIGH", "CRITICAL") else "⏳"
        lines = [
            f"{emoji} <b>NEW TOKEN DETECTED</b>",
            f"",
            f"<b>Token:</b> <code>{l.token_address}</code>",
            f"<b>DEX:</b> {l.dex.upper()}",
            f"<b>Chain:</b> {l.chain.upper()}",
        ]
        if l.creator_wallet:
            lines.append(f"<b>Creator:</b> <code>{l.creator_wallet}</code>")
        if enriched.risk_score is not None:
            lines.append(f"<b>Risk:</b> {enriched.risk_level} ({enriched.risk_score:.0f}/100)")
        if enriched.first_findings:
            lines.append(f"<b>Flags:</b> {enriched.first_findings[0]}")
        if enriched.rugcheck_url:
            lines.append(f'<a href="{enriched.rugcheck_url}">🔍 RugCheck</a>')
        return "\n".join(lines)


# Singleton
launch_detector = LaunchDetector()
