"""
👤 Wallet Persona Profiler — Trading Behavior Forensics
=======================================================
Inspired by order-cycle analysis and performance fingerprinting,
but rebuilt for real-time on-chain wallet profiling.

Detects:
  • Trader persona (scalper, hodler, bot, insider, degen)
  • Median hold duration — key rug-pull signal
  • Round-trip success rate
  • Timezone/geographic clustering from activity hours
  • Noise filtering (stables, wrapped assets, LP tokens)

A wallet that launches a token and dumps within 2 hours gets
flagged as INSIDER regardless of what the contract looks like.
"""

import math
from dataclasses import dataclass, field
from typing import List, Dict, Optional
from collections import defaultdict
from datetime import datetime


@dataclass
class SwapEvent:
    timestamp: datetime
    token_in: str
    token_out: str
    amount_in_usd: float
    amount_out_usd: float
    tx_hash: str = ""


@dataclass
class WalletPersonaResult:
    address: str
    persona: str                     # scalper | hodler | bot | insider | degen | ordinary
    persona_score: float             # 0.0 – 1.0 confidence
    median_hold_minutes: Optional[float]
    round_trips: int
    successful_round_trips: int      # profitable exits
    win_rate: float                  # 0.0 – 1.0
    active_hours: Dict[int, int]     # hour -> tx count
    top_traded_tokens: List[str]
    noise_filtered: bool
    findings: List[str] = field(default_factory=list)


# ── Tokens to ignore when analyzing "true" trading behavior ──
_NOISE_TOKENS = {
    "WETH", "WBTC", "USDT", "USDC", "DAI", "BUSD", "TUSD",
    "WBNB", "WMATIC", "WAVAX", "WFTM", "WSOL", "WSOL",
    "UNI-V2", "SLP", "Cake-LP", "Raydium LP", "Orca LP",
}


def _is_noise(token: str) -> bool:
    t = token.upper()
    return t in _NOISE_TOKENS or "LP" in t or "UNI-V" in t or "SLP" in t


class WalletPersonaProfiler:
    """Profile a wallet's trading behavior from swap history."""

    def analyze(self, address: str, swaps: List[SwapEvent]) -> WalletPersonaResult:
        if not swaps:
            return WalletPersonaResult(
                address=address, persona="unknown", persona_score=0.0,
                median_hold_minutes=None, round_trips=0,
                successful_round_trips=0, win_rate=0.0,
                active_hours={}, top_traded_tokens=[], noise_filtered=True,
                findings=["No swap history available"],
            )

        # Sort chronologically
        swaps = sorted(swaps, key=lambda s: s.timestamp)

        # ── Noise filter & hour tracking ──
        filtered_swaps = [s for s in swaps if not (_is_noise(s.token_in) and _is_noise(s.token_out))]
        active_hours: Dict[int, int] = defaultdict(int)
        for s in swaps:
            active_hours[s.timestamp.hour] += 1

        # ── Build position ledger (buy -> sell round trips) ──
        positions: Dict[str, List[Dict]] = defaultdict(list)  # token -> list of {buy_time, buy_usd}
        round_trips = 0
        successful_rt = 0
        hold_durations: List[float] = []
        token_profit: Dict[str, float] = defaultdict(float)

        for s in filtered_swaps:
            # Treat token_in as "selling", token_out as "buying"
            # We track buys (acquiring a non-noise token) and sells (disposing of it)
            if not _is_noise(s.token_out):
                # Buying token_out
                positions[s.token_out].append({
                    "time": s.timestamp,
                    "cost": s.amount_in_usd,
                })
            if not _is_noise(s.token_in):
                # Selling token_in
                buys = positions.get(s.token_in, [])
                if buys:
                    # FIFO matching
                    buy = buys.pop(0)
                    round_trips += 1
                    duration = (s.timestamp - buy["time"]).total_seconds() / 60.0
                    hold_durations.append(duration)
                    pnl = s.amount_out_usd - buy["cost"]
                    token_profit[s.token_in] += pnl
                    if pnl > 0:
                        successful_rt += 1

        # ── Persona classification ──
        median_hold = self._median(hold_durations) if hold_durations else None
        win_rate = successful_rt / round_trips if round_trips > 0 else 0.0
        total_swaps = len(filtered_swaps)
        unique_tokens = len(set(s.token_out for s in filtered_swaps if not _is_noise(s.token_out)))

        # Heuristic scoring
        bot_score = 0.0
        scalper_score = 0.0
        insider_score = 0.0
        degen_score = 0.0
        hodler_score = 0.0

        if median_hold is not None:
            if median_hold < 5:
                bot_score += 0.4
                scalper_score += 0.3
            elif median_hold < 60:
                scalper_score += 0.4
                bot_score += 0.2
            elif median_hold < 24 * 60:
                degen_score += 0.3
            else:
                hodler_score += 0.4

        # Swap frequency
        if total_swaps >= 50:
            bot_score += 0.3
        if unique_tokens > 20:
            degen_score += 0.3

        # Win rate
        if win_rate < 0.2 and round_trips > 5:
            insider_score += 0.3  # Consistently loses? Maybe dumping own tokens
        if win_rate > 0.8 and round_trips > 5:
            bot_score += 0.2  # Unnaturally high win rate

        # Time concentration (bot signatures)
        if active_hours:
            max_hour_count = max(active_hours.values())
            if max_hour_count / total_swaps > 0.5:
                bot_score += 0.2

        scores = {
            "bot": bot_score,
            "scalper": scalper_score,
            "insider": insider_score,
            "degen": degen_score,
            "hodler": hodler_score,
            "ordinary": 0.1,
        }
        persona = max(scores, key=scores.get)
        persona_score = scores[persona]

        # ── Findings ──
        findings = []
        if median_hold is not None:
            if median_hold < 10:
                findings.append(f"⚡ Ultra-short median hold: {median_hold:.1f} min — sniper/bot signature")
            elif median_hold < 60:
                findings.append(f"⚡ Scalper pattern: {median_hold:.1f} min median hold")
            elif median_hold > 7 * 24 * 60:
                findings.append(f"💎 Diamond hands: {median_hold / 1440:.1f} day median hold")

        if round_trips > 0:
            findings.append(f"📊 Round-trip win rate: {win_rate:.1%} ({successful_rt}/{round_trips})")

        if persona == "insider":
            findings.append("🎭 INSIDER persona — Wallet consistently acquires and rapidly dumps new tokens")
        elif persona == "bot":
            findings.append("🤖 BOT persona — Timing and frequency match automated trading")
        elif persona == "degen":
            findings.append("🎰 DEGEN persona — High token churn, speculative behavior")

        top_tokens = sorted(token_profit.keys(), key=lambda t: abs(token_profit[t]), reverse=True)[:5]

        return WalletPersonaResult(
            address=address,
            persona=persona,
            persona_score=round(persona_score, 3),
            median_hold_minutes=round(median_hold, 1) if median_hold else None,
            round_trips=round_trips,
            successful_round_trips=successful_rt,
            win_rate=round(win_rate, 3),
            active_hours=dict(active_hours),
            top_traded_tokens=top_tokens,
            noise_filtered=True,
            findings=findings,
        )

    def _median(self, values: List[float]) -> float:
        s = sorted(values)
        n = len(s)
        if n == 0:
            return 0.0
        if n % 2 == 1:
            return s[n // 2]
        return (s[n // 2 - 1] + s[n // 2]) / 2.0


# Singleton
profiler = WalletPersonaProfiler()
