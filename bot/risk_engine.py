#!/usr/bin/env python3
"""
🛡️ Deep Risk Engine — 100-Point Forensic Scoring
=================================================
Granular heuristics across 5 categories. Every point is earned.

Categories (100 pts total):
  1. Contract Security     (25 pts)
  2. Liquidity Health      (20 pts)
  3. Holder Distribution   (20 pts)
  4. Creator / Dev Profile (20 pts)
  5. Market Behavior       (15 pts)

Returns full breakdown + human-readable findings.
"""

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from bot.api_sourcer import ContractData


@dataclass
class HeuristicResult:
    name: str
    weight: int          # max points this heuristic can add
    score: int           # actual points added (0 to weight)
    finding: str         # human-readable explanation
    raw_value: any = None


@dataclass
class CategoryResult:
    name: str
    max_points: int
    heuristics: List[HeuristicResult]

    @property
    def score(self) -> int:
        return min(self.max_points, sum(h.score for h in self.heuristics))

    @property
    def findings(self) -> List[str]:
        return [h.finding for h in self.heuristics if h.score > 0]


@dataclass
class RiskReport:
    address: str
    chain: str
    total_score: int
    max_score: int = 100
    level: str = "SAFE"
    categories: List[CategoryResult] = field(default_factory=list)
    recommendation: str = ""
    executive_summary: str = ""

    @property
    def findings(self) -> List[str]:
        f = []
        for cat in self.categories:
            f.extend(cat.findings)
        return f

    @property
    def category_breakdown(self) -> Dict[str, int]:
        return {cat.name: cat.score for cat in self.categories}


class DeepRiskEngine:
    """100-point forensic scoring with granular heuristics."""

    # ── Level Thresholds ────────────────────────────────────────
    LEVELS = [
        (0, 19, "SAFE", "✅ Clean scan — But always verify independently"),
        (20, 39, "LOW", "🟢 Looks decent — Still DYOR before investing"),
        (40, 59, "MEDIUM", "🟡 Proceed with caution — Verify further before aping"),
        (60, 79, "HIGH", "⚠️ Extreme risk — Only with money you can afford to lose"),
        (80, 100, "CRITICAL", "❌ DO NOT INTERACT — High probability of fund loss"),
    ]

    def __init__(self):
        pass

    # ═════════════════════════════════════════════════════════════
    #  CATEGORY 1: CONTRACT SECURITY (25 pts)
    # ═════════════════════════════════════════════════════════════
    def _contract_security(self, cd: ContractData) -> CategoryResult:
        h: List[HeuristicResult] = []

        # 1.1 Honeypot (max 25, but capped at category max)
        if cd.has_honeypot:
            h.append(HeuristicResult(
                name="honeypot",
                weight=25, score=25,
                finding=f"🍯 HONEYPOT CONFIRMED: {cd.honeypot_reason or 'Simulated buy/sell failed'}",
                raw_value=True,
            ))

        # 1.2 Extreme taxes
        max_tax = max(cd.buy_tax, cd.sell_tax)
        if max_tax >= 15:
            h.append(HeuristicResult(
                name="extreme_tax", weight=15, score=15,
                finding=f"💸 EXTREME taxes: Buy {cd.buy_tax:.1f}% / Sell {cd.sell_tax:.1f}%",
                raw_value=max_tax,
            ))
        elif max_tax >= 10:
            h.append(HeuristicResult(
                name="high_tax", weight=15, score=10,
                finding=f"💸 High taxes: Buy {cd.buy_tax:.1f}% / Sell {cd.sell_tax:.1f}%",
                raw_value=max_tax,
            ))
        elif max_tax >= 5:
            h.append(HeuristicResult(
                name="moderate_tax", weight=15, score=5,
                finding=f"💸 Moderate taxes: Buy {cd.buy_tax:.1f}% / Sell {cd.sell_tax:.1f}%",
                raw_value=max_tax,
            ))

        # 1.3 Transfer tax (separate from buy/sell)
        transfer_tax = cd.extra.get("transfer_tax", 0)
        if transfer_tax >= 5:
            h.append(HeuristicResult(
                name="transfer_tax", weight=5, score=5,
                finding=f"💸 Transfer tax {transfer_tax:.1f}% — You pay even moving between wallets",
                raw_value=transfer_tax,
            ))
        elif transfer_tax > 0:
            h.append(HeuristicResult(
                name="transfer_tax", weight=5, score=2,
                finding=f"💸 Transfer tax {transfer_tax:.1f}% detected",
                raw_value=transfer_tax,
            ))

        # 1.4 Unverified source
        if not cd.is_verified and cd.is_contract:
            h.append(HeuristicResult(
                name="unverified", weight=10, score=10,
                finding="📄 Contract source code NOT verified — Could be anything",
                raw_value=False,
            ))

        # 1.5 Mint function
        if cd.has_mint:
            h.append(HeuristicResult(
                name="mint", weight=12, score=12,
                finding="🖨️ Mint function detected — Supply can be inflated at will",
                raw_value=True,
            ))

        # 1.6 Blacklist
        if cd.has_blacklist:
            h.append(HeuristicResult(
                name="blacklist", weight=15, score=15,
                finding="🚫 Blacklist function — You could be blocked from selling",
                raw_value=True,
            ))

        # 1.7 Pause
        if cd.has_pause:
            h.append(HeuristicResult(
                name="pause", weight=8, score=8,
                finding="⏸️ Pause function — Trading can be frozen",
                raw_value=True,
            ))

        # 1.8 Proxy / upgradeable
        if cd.is_proxy:
            h.append(HeuristicResult(
                name="proxy", weight=8, score=8,
                finding=f"🔀 Proxy contract — Logic can be swapped. Implementation: {cd.implementation[:20] if cd.implementation else 'unknown'}",
                raw_value=True,
            ))

        # 1.9 Dangerous patterns in source code
        src = (cd.source_code or "").lower()
        dangerous = []
        if "selfdestruct" in src or "suicide" in src:
            dangerous.append("self-destruct")
        if "delegatecall" in src:
            dangerous.append("delegatecall")
        if re.search(r'\bdestroy\b', src):
            dangerous.append("destroy")
        if dangerous:
            h.append(HeuristicResult(
                name="dangerous_code", weight=15, score=min(15, len(dangerous) * 8),
                finding=f"💣 Dangerous code patterns: {', '.join(dangerous)}",
                raw_value=dangerous,
            ))

        # 1.10 Hidden ownership (renounced flag but creator still has admin functions)
        if "renounced" in src and (cd.has_mint or cd.has_blacklist or cd.has_pause):
            h.append(HeuristicResult(
                name="hidden_owner", weight=10, score=10,
                finding="🎭 Ownership claims to be renounced but admin functions still present",
                raw_value=True,
            ))

        return CategoryResult(name="Contract Security", max_points=25, heuristics=h)

    # ═════════════════════════════════════════════════════════════
    #  CATEGORY 2: LIQUIDITY HEALTH (20 pts)
    # ═════════════════════════════════════════════════════════════
    def _liquidity_health(self, cd: ContractData) -> CategoryResult:
        h: List[HeuristicResult] = []
        liq = cd.liquidity_usd

        # 2.1 Liquidity amount
        if liq > 0:
            if liq < 5_000:
                h.append(HeuristicResult(
                    name="extreme_low_liq", weight=15, score=15,
                    finding=f"💧 CATASTROPHIC liquidity: ${liq:,.0f} — Slippage will eat you alive",
                    raw_value=liq,
                ))
            elif liq < 20_000:
                h.append(HeuristicResult(
                    name="very_low_liq", weight=15, score=12,
                    finding=f"💧 Very low liquidity: ${liq:,.0f}",
                    raw_value=liq,
                ))
            elif liq < 50_000:
                h.append(HeuristicResult(
                    name="low_liq", weight=15, score=8,
                    finding=f"💧 Low liquidity: ${liq:,.0f}",
                    raw_value=liq,
                ))
            elif liq < 100_000:
                h.append(HeuristicResult(
                    name="moderate_liq", weight=15, score=4,
                    finding=f"💧 Moderate liquidity: ${liq:,.0f}",
                    raw_value=liq,
                ))
            else:
                # Good liquidity — bonus (reduces score, but we only add positive)
                pass
        else:
            h.append(HeuristicResult(
                name="no_liq", weight=15, score=15,
                finding="💧 NO LIQUIDITY DETECTED — Token may be untradeable",
                raw_value=0,
            ))

        # 2.2 LP ownership / lock status (from extra data if available)
        lp_owner = cd.extra.get("lp_owner", "")
        lp_locked = cd.extra.get("lp_locked", False)
        if lp_owner and lp_owner.lower() == cd.creator.lower() and not lp_locked:
            h.append(HeuristicResult(
                name="lp_unsafe", weight=10, score=10,
                finding=f"🔓 LP tokens held by creator and NOT locked — Can rug liquidity instantly",
                raw_value=lp_owner,
            ))
        elif lp_locked:
            # LP locked is good — no points added
            pass

        # 2.3 Single-sided liquidity (dev-only pool)
        if cd.extra.get("single_sided_liquidity", False):
            h.append(HeuristicResult(
                name="single_sided", weight=10, score=10,
                finding="⚠️ Single-sided liquidity pool — Dev controls entire market",
                raw_value=True,
            ))

        # 2.4 Liquidity drain (sudden drop > 50%)
        liq_drop = cd.extra.get("liquidity_drop_pct", 0)
        if liq_drop >= 70:
            h.append(HeuristicResult(
                name="liq_drain_severe", weight=12, score=12,
                finding=f"🚨 Liquidity DRAINED {liq_drop:.0f}% — Active rug in progress",
                raw_value=liq_drop,
            ))
        elif liq_drop >= 30:
            h.append(HeuristicResult(
                name="liq_drain", weight=12, score=8,
                finding=f"⚠️ Liquidity dropped {liq_drop:.0f}% recently",
                raw_value=liq_drop,
            ))

        # 2.5 Volume vs market cap ratio (illiquid high mcap = manipulation)
        if cd.market_cap > 0 and cd.volume_24h > 0:
            vol_mcap_ratio = cd.volume_24h / cd.market_cap
            if vol_mcap_ratio < 0.01:
                h.append(HeuristicResult(
                    name="illiquid_mcap", weight=5, score=5,
                    finding=f"📉 Illiquid token: 24h volume only ${cd.volume_24h:,.0f} vs ${cd.market_cap:,.0f} mcap",
                    raw_value=vol_mcap_ratio,
                ))

        return CategoryResult(name="Liquidity Health", max_points=20, heuristics=h)

    # ═════════════════════════════════════════════════════════════
    #  CATEGORY 3: HOLDER DISTRIBUTION (20 pts)
    # ═════════════════════════════════════════════════════════════
    def _holder_distribution(self, cd: ContractData) -> CategoryResult:
        h: List[HeuristicResult] = []

        # 3.1 Top holder concentration
        top = cd.top_holder_pct
        if top >= 60:
            h.append(HeuristicResult(
                name="whale_danger", weight=15, score=15,
                finding=f"🐋 WHALE DANGER: Top holder owns {top:.1f}% — One dump kills the chart",
                raw_value=top,
            ))
        elif top >= 40:
            h.append(HeuristicResult(
                name="high_concentration", weight=15, score=12,
                finding=f"⚠️ High concentration: Top holder owns {top:.1f}%",
                raw_value=top,
            ))
        elif top >= 20:
            h.append(HeuristicResult(
                name="moderate_concentration", weight=15, score=6,
                finding=f"⚠️ Moderate concentration: Top holder owns {top:.1f}%",
                raw_value=top,
            ))

        # 3.2 Top 10 holders
        top10 = cd.extra.get("top10_holder_pct", 0)
        if top10 >= 90:
            h.append(HeuristicResult(
                name="top10_extreme", weight=12, score=12,
                finding=f"🔒 Top 10 holders control {top10:.1f}% — No decentralization",
                raw_value=top10,
            ))
        elif top10 >= 70:
            h.append(HeuristicResult(
                name="top10_high", weight=12, score=8,
                finding=f"🔒 Top 10 holders control {top10:.1f}%",
                raw_value=top10,
            ))
        elif top10 >= 50:
            h.append(HeuristicResult(
                name="top10_moderate", weight=12, score=4,
                finding=f"🔒 Top 10 holders control {top10:.1f}%",
                raw_value=top10,
            ))

        # 3.3 Total holders
        holders = cd.holders
        if holders > 0:
            if holders < 50:
                h.append(HeuristicResult(
                    name="very_few_holders", weight=10, score=10,
                    finding=f"👶 Only {holders} holders — Extremely early / possible private sale scam",
                    raw_value=holders,
                ))
            elif holders < 200:
                h.append(HeuristicResult(
                    name="few_holders", weight=10, score=6,
                    finding=f"👶 Only {holders} holders — Very low distribution",
                    raw_value=holders,
                ))
            elif holders < 500:
                h.append(HeuristicResult(
                    name="low_holders", weight=10, score=3,
                    finding=f"👶 Low holder count: {holders}",
                    raw_value=holders,
                ))

        # 3.4 Fresh wallet concentration
        fresh_pct = cd.extra.get("fresh_wallet_pct", 0)
        if fresh_pct >= 70:
            h.append(HeuristicResult(
                name="fresh_wallets_extreme", weight=10, score=10,
                finding=f"🆕 {fresh_pct:.0f}% of wallets are < 24h old — Bot farm / airdrop scam",
                raw_value=fresh_pct,
            ))
        elif fresh_pct >= 40:
            h.append(HeuristicResult(
                name="fresh_wallets_high", weight=10, score=6,
                finding=f"🆕 {fresh_pct:.0f}% of wallets are < 24h old",
                raw_value=fresh_pct,
            ))

        # 3.5 Sniper dominance
        sniper_pct = cd.extra.get("sniper_supply_pct", 0)
        if sniper_pct >= 40:
            h.append(HeuristicResult(
                name="sniper_dominance", weight=8, score=8,
                finding=f"🎯 Snipers own {sniper_pct:.1f}% of supply — Expect massive dumps",
                raw_value=sniper_pct,
            ))
        elif sniper_pct >= 20:
            h.append(HeuristicResult(
                name="sniper_presence", weight=8, score=4,
                finding=f"🎯 Significant sniper presence: {sniper_pct:.1f}% of supply",
                raw_value=sniper_pct,
            ))

        # 3.6 Bundler detection
        bundler_rate = cd.extra.get("bundler_rate", 0)
        if bundler_rate >= 0.3:
            h.append(HeuristicResult(
                name="bundlers", weight=8, score=8,
                finding=f"📦 High bundler rate ({bundler_rate:.0%}) — Coordinated buy walls",
                raw_value=bundler_rate,
            ))
        elif bundler_rate >= 0.1:
            h.append(HeuristicResult(
                name="bundlers", weight=8, score=4,
                finding=f"📦 Bundler activity detected ({bundler_rate:.0%})",
                raw_value=bundler_rate,
            ))

        return CategoryResult(name="Holder Distribution", max_points=20, heuristics=h)

    # ═════════════════════════════════════════════════════════════
    #  CATEGORY 4: CREATOR / DEV PROFILE (20 pts)
    # ═════════════════════════════════════════════════════════════
    def _creator_profile(self, cd: ContractData) -> CategoryResult:
        h: List[HeuristicResult] = []

        # 4.1 Creator wallet age
        creator_age_days = cd.extra.get("creator_age_days", -1)
        if creator_age_days >= 0:
            if creator_age_days < 1:
                h.append(HeuristicResult(
                    name="creator_fresh", weight=12, score=12,
                    finding=f"👶 Creator wallet is BRAND NEW (< 1 day old)",
                    raw_value=creator_age_days,
                ))
            elif creator_age_days < 7:
                h.append(HeuristicResult(
                    name="creator_young", weight=12, score=8,
                    finding=f"👶 Creator wallet is only {creator_age_days:.0f} days old",
                    raw_value=creator_age_days,
                ))
            elif creator_age_days < 30:
                h.append(HeuristicResult(
                    name="creator_newish", weight=12, score=4,
                    finding=f"👶 Creator wallet is {creator_age_days:.0f} days old",
                    raw_value=creator_age_days,
                ))

        # 4.2 Previous rug history
        prev_rugs = cd.extra.get("creator_previous_rugs", 0)
        if prev_rugs >= 3:
            h.append(HeuristicResult(
                name="serial_rugger", weight=20, score=20,
                finding=f"🎭 SERIAL RUGGER: Creator has {prev_rugs} previous rug pulls",
                raw_value=prev_rugs,
            ))
        elif prev_rugs >= 1:
            h.append(HeuristicResult(
                name="known_rugger", weight=20, score=15,
                finding=f"🎭 Known rugger: Creator has {prev_rugs} previous rug pull(s)",
                raw_value=prev_rugs,
            ))

        # 4.3 Funded from mixer / suspicious source
        if cd.extra.get("creator_funded_from_mixer", False):
            h.append(HeuristicResult(
                name="mixer_funds", weight=15, score=15,
                finding="🌪️ Creator funded from mixer/Tornado — Attempting to hide identity",
                raw_value=True,
            ))
        elif cd.extra.get("creator_funded_from_exchange", False):
            pass  # Neutral

        # 4.4 Creator still holds significant supply
        creator_hold = cd.extra.get("creator_hold_pct", 0)
        if creator_hold >= 20:
            h.append(HeuristicResult(
                name="creator_hoarding", weight=8, score=8,
                finding=f"💰 Creator still holds {creator_hold:.1f}% of supply — Massive dump risk",
                raw_value=creator_hold,
            ))
        elif creator_hold >= 10:
            h.append(HeuristicResult(
                name="creator_holding", weight=8, score=4,
                finding=f"💰 Creator holds {creator_hold:.1f}% of supply",
                raw_value=creator_hold,
            ))

        # 4.5 Creator already dumped
        creator_sold = cd.extra.get("creator_sold_pct", 0)
        if creator_sold >= 80:
            h.append(HeuristicResult(
                name="creator_dumped", weight=10, score=10,
                finding=f"💨 Creator has sold {creator_sold:.1f}% of their allocation — Abandoned project",
                raw_value=creator_sold,
            ))
        elif creator_sold >= 50:
            h.append(HeuristicResult(
                name="creator_dumping", weight=10, score=6,
                finding=f"💨 Creator has sold {creator_sold:.1f}% of their allocation",
                raw_value=creator_sold,
            ))

        # 4.6 Ownership not renounced (for contracts that should be)
        if not cd.extra.get("ownership_renounced", True) and not cd.is_proxy:
            h.append(HeuristicResult(
                name="ownership_kept", weight=8, score=8,
                finding="🔑 Ownership NOT renounced — Dev retains full control",
                raw_value=False,
            ))

        # 4.7 Contract factory / batch deployment
        if cd.extra.get("deployed_by_factory", False):
            h.append(HeuristicResult(
                name="factory_deploy", weight=10, score=10,
                finding="🏭 Deployed by contract factory — Likely one of many copy-paste scams",
                raw_value=True,
            ))

        # 4.8 Creator token status (from sniper data)
        cts = cd.extra.get("creator_token_status", "")
        if cts == "creator_sold":
            h.append(HeuristicResult(
                name="creator_status_sold", weight=8, score=8,
                finding="💨 Creator has completely sold out — Project has no leader",
                raw_value=cts,
            ))
        elif cts == "creator_hold":
            pass  # Neutral — already scored by creator_hold_pct

        return CategoryResult(name="Creator / Dev Profile", max_points=20, heuristics=h)

    # ═════════════════════════════════════════════════════════════
    #  CATEGORY 5: MARKET BEHAVIOR (15 pts)
    # ═════════════════════════════════════════════════════════════
    def _market_behavior(self, cd: ContractData) -> CategoryResult:
        h: List[HeuristicResult] = []

        # 5.1 Volume vs market cap ratio (wash trading)
        if cd.market_cap > 0 and cd.volume_24h > 0:
            ratio = cd.volume_24h / cd.market_cap
            if ratio > 10:
                h.append(HeuristicResult(
                    name="wash_trading", weight=10, score=10,
                    finding=f"🔄 Suspicious volume: ${cd.volume_24h:,.0f} volume vs ${cd.market_cap:,.0f} mcap — Possible wash trading",
                    raw_value=ratio,
                ))
            elif ratio > 3:
                h.append(HeuristicResult(
                    name="high_volume", weight=10, score=5,
                    finding=f"🔄 Very high volume relative to market cap ({ratio:.1f}x)",
                    raw_value=ratio,
                ))

        # 5.2 Price change
        price_change = cd.extra.get("price_change_24h", 0)
        if price_change <= -80:
            h.append(HeuristicResult(
                name="massive_dump", weight=15, score=15,
                finding=f"🔻 MASSIVE DUMP: Price down {price_change:.1f}% in 24h — Likely rug executed",
                raw_value=price_change,
            ))
        elif price_change <= -50:
            h.append(HeuristicResult(
                name="heavy_dump", weight=15, score=10,
                finding=f"🔻 Heavy dump: Price down {price_change:.1f}% in 24h",
                raw_value=price_change,
            ))
        elif price_change <= -30:
            h.append(HeuristicResult(
                name="significant_drop", weight=15, score=5,
                finding=f"🔻 Price down {price_change:.1f}% in 24h",
                raw_value=price_change,
            ))

        # 5.3 Buy/sell ratio
        buy_sell = cd.extra.get("buy_sell_ratio", 1.0)
        if buy_sell < 0.2:
            h.append(HeuristicResult(
                name="heavy_selling", weight=8, score=8,
                finding=f"📉 Heavy selling pressure: Buy/sell ratio {buy_sell:.2f}",
                raw_value=buy_sell,
            ))
        elif buy_sell < 0.5:
            h.append(HeuristicResult(
                name="more_selling", weight=8, score=4,
                finding=f"📉 More sellers than buyers: Buy/sell ratio {buy_sell:.2f}",
                raw_value=buy_sell,
            ))

        # 5.4 No organic volume
        if cd.volume_24h > 0 and cd.volume_24h < 1_000:
            h.append(HeuristicResult(
                name="no_volume", weight=8, score=8,
                finding=f"📉 Dead token: Only ${cd.volume_24h:,.0f} volume in 24h",
                raw_value=cd.volume_24h,
            ))
        elif cd.volume_24h == 0 and cd.market_cap > 0:
            h.append(HeuristicResult(
                name="zero_volume", weight=8, score=8,
                finding="📉 ZERO volume despite having market cap — Artificially inflated",
                raw_value=0,
            ))

        # 5.5 Token Sniffer flag
        if cd.extra.get("token_sniffer_scam", False):
            score = cd.extra.get("token_sniffer_score", 0)
            h.append(HeuristicResult(
                name="token_sniffer", weight=12, score=12,
                finding=f"🚨 Token Sniffer flagged as SCAM (score: {score}/100)",
                raw_value=score,
            ))

        # 5.6 Bubblemaps decentralization
        bm = cd.extra.get("bubblemap_score")
        if bm is not None and bm < 20:
            h.append(HeuristicResult(
                name="bubblemap_critical", weight=8, score=8,
                finding=f"🔗 Critical decentralization: Bubblemaps score {bm}/100",
                raw_value=bm,
            ))
        elif bm is not None and bm < 40:
            h.append(HeuristicResult(
                name="bubblemap_low", weight=8, score=4,
                finding=f"🔗 Low decentralization: Bubblemaps score {bm}/100",
                raw_value=bm,
            ))

        # 5.7 Arkham intelligence labels
        ark_labels = cd.extra.get("arkham_labels", [])
        if any("scam" in str(l).lower() or "hack" in str(l).lower() for l in ark_labels):
            h.append(HeuristicResult(
                name="arkham_flag", weight=10, score=10,
                finding=f"🕵️ Arkham Intelligence flagged this entity: {ark_labels}",
                raw_value=ark_labels,
            ))

        return CategoryResult(name="Market Behavior", max_points=15, heuristics=h)

    # ═════════════════════════════════════════════════════════════
    #  MAIN ENTRY
    # ═════════════════════════════════════════════════════════════
    def analyze(self, cd: ContractData) -> RiskReport:
        """Run full 100-point forensic analysis."""

        categories = [
            self._contract_security(cd),
            self._liquidity_health(cd),
            self._holder_distribution(cd),
            self._creator_profile(cd),
            self._market_behavior(cd),
        ]

        total = sum(cat.score for cat in categories)

        # Determine level
        level = "SAFE"
        rec = "✅ Clean scan — But always verify independently"
        for min_s, max_s, lvl, r in self.LEVELS:
            if min_s <= total <= max_s:
                level = lvl
                rec = r
                break

        # Executive summary
        summary_parts = [f"Score {total}/100 ({level})"]
        if total >= 80:
            summary_parts.append("CRITICAL RISK — Multiple severe findings. Do not interact.")
        elif total >= 60:
            summary_parts.append("HIGH RISK — Several dangerous signals present.")
        elif total >= 40:
            summary_parts.append("MODERATE RISK — Some concerning patterns. Verify before investing.")
        elif total >= 20:
            summary_parts.append("LOW RISK — Looks reasonable but not perfect.")
        else:
            summary_parts.append("SAFE — No major red flags detected.")

        worst = []
        for cat in categories:
            for heu in cat.heuristics:
                if heu.score >= heu.weight * 0.8:
                    worst.append(heu.finding)
        if worst:
            summary_parts.append(f"Top threats: {worst[0]}")
            if len(worst) > 1:
                summary_parts.append(f"Also: {worst[1]}")

        return RiskReport(
            address=cd.address,
            chain=cd.chain,
            total_score=total,
            max_score=100,
            level=level,
            categories=categories,
            recommendation=rec,
            executive_summary=" | ".join(summary_parts),
        )


# Singleton
risk_engine = DeepRiskEngine()
