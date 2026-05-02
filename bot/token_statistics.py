"""
📊 Token Statistics Engine — Rigorous On-Chain Concentration Metrics
=====================================================================
Inspired by traditional finance market-concentration analysis and
institutional forensic indices, rebuilt for crypto token holder data.

Computes academically rigorous signals:
  • Herfindahl-Hirschman Index (HHI) — holder monopoly power
  • Gini Coefficient — supply distribution inequality
  • Rolling Volatility — price-action anomaly detection
  • Concentration Ratios — top-N holder dominance
  • Beta-like Whale Sensitivity — token price correlation to whale moves

All formulas are transparent and auditable — no black-box ML.
"""

import math
from dataclasses import dataclass, field
from typing import List, Dict, Optional
from collections import defaultdict


@dataclass
class Holder:
    address: str
    balance: float          # raw token balance
    pct_supply: float = 0.0  # 0.0–1.0


@dataclass
class TokenStatsResult:
    hhi: float                       # 0.0 – 1.0  (1.0 = total monopoly)
    gini: float                      # 0.0 – 1.0  (1.0 = max inequality)
    cr_top5: float                   # top 5 concentration ratio
    cr_top10: float                  # top 10 concentration ratio
    cr_top20: float                  # top 20 concentration ratio
    effective_holders: float         # 1/HHI  (intuitive "how many equal holders")
    volatility_24h: Optional[float] = None
    volatility_7d: Optional[float] = None
    whale_beta: Optional[float] = None
    findings: List[str] = field(default_factory=list)
    raw: Dict = field(default_factory=dict)


class TokenStatisticsEngine:
    """Compute concentration and volatility statistics from holder data."""

    def analyze(self, holders: List[Holder], price_series: Optional[List[float]] = None,
                whale_price_changes: Optional[List[float]] = None) -> TokenStatsResult:
        """
        holders: list of Holder objects (sorted or unsorted)
        price_series: chronological list of price observations (e.g., hourly)
        whale_price_changes: parallel list of % changes in a whale's holdings
        """
        if not holders:
            return TokenStatsResult(
                hhi=0.0, gini=0.0, cr_top5=0.0, cr_top10=0.0, cr_top20=0.0,
                effective_holders=0.0, findings=["No holder data available"]
            )

        # Normalize percentages
        total_balance = sum(h.balance for h in holders)
        if total_balance > 0:
            for h in holders:
                h.pct_supply = h.balance / total_balance

        sorted_h = sorted(holders, key=lambda x: x.pct_supply, reverse=True)
        shares = [h.pct_supply for h in sorted_h]

        # ── Herfindahl-Hirschman Index ──
        hhi = sum(s ** 2 for s in shares)
        effective_holders = 1.0 / hhi if hhi > 0 else 0.0

        # ── Concentration Ratios ──
        cr_top5 = sum(shares[:5])
        cr_top10 = sum(shares[:10])
        cr_top20 = sum(shares[:20])

        # ── Gini Coefficient (discrete formula) ──
        n = len(shares)
        if n <= 1:
            gini = 0.0
        else:
            # Sort ascending for standard Gini formula
            y = sorted(shares)
            cumsum = 0.0
            for i, val in enumerate(y, start=1):
                cumsum += (2 * i - n - 1) * val
            gini = cumsum / (n * sum(y)) if sum(y) > 0 else 0.0

        # ── Rolling Volatility (annualized) ──
        vol_24h = None
        vol_7d = None
        if price_series and len(price_series) >= 2:
            log_returns = []
            for i in range(1, len(price_series)):
                if price_series[i - 1] > 0 and price_series[i] > 0:
                    log_returns.append(math.log(price_series[i] / price_series[i - 1]))
            if log_returns:
                mean_lr = sum(log_returns) / len(log_returns)
                variance = sum((r - mean_lr) ** 2 for r in log_returns) / len(log_returns)
                std = math.sqrt(variance)
                # Annualize assuming hourly data -> 8760 hours/year
                # If 24h data -> 365 days/year
                # We'll compute both assumptions based on series length heuristic
                n_obs = len(log_returns)
                periods_per_year = 8760 if n_obs > 100 else 365 if n_obs > 20 else 52
                ann_vol = std * math.sqrt(periods_per_year)
                vol_7d = ann_vol
                if n_obs >= 24:
                    vol_24h = std * math.sqrt(365)  # daily granularity assumption

        # ── Whale Beta (simplified) ──
        whale_beta = None
        if whale_price_changes and len(whale_price_changes) == len(log_returns) and log_returns:
            # Correlation coefficient between token returns and whale activity %
            x = log_returns
            y = whale_price_changes[:len(x)]
            n = len(x)
            mean_x = sum(x) / n
            mean_y = sum(y) / n
            num = sum((xi - mean_x) * (yi - mean_y) for xi, yi in zip(x, y))
            den_x = sum((xi - mean_x) ** 2 for xi in x)
            den_y = sum((yi - mean_y) ** 2 for yi in y)
            if den_x > 0 and den_y > 0:
                whale_beta = num / math.sqrt(den_x * den_y)

        # ── Findings generation ──
        findings = []
        if hhi > 0.5:
            findings.append(f"🐋 MONOPOLY: HHI = {hhi:.3f} — One wallet effectively controls the supply")
        elif hhi > 0.25:
            findings.append(f"⚠️ High concentration: HHI = {hhi:.3f}")

        if gini > 0.8:
            findings.append(f"📊 Extreme inequality: Gini = {gini:.3f} — 'Fair launch' is a lie")
        elif gini > 0.6:
            findings.append(f"📊 Significant inequality: Gini = {gini:.3f}")

        if cr_top5 > 0.8:
            findings.append(f"🔒 Top 5 holders control {cr_top5:.1%} — No decentralization")
        elif cr_top5 > 0.5:
            findings.append(f"🔒 Top 5 holders control {cr_top5:.1%}")

        if effective_holders < 10:
            findings.append(f"👥 Effective holders ≈ {effective_holders:.1f} — Treat as oligopoly")

        if vol_7d and vol_7d > 5.0:
            findings.append(f"📈 Extreme volatility: {vol_7d:.1f}x annualized — Possible manipulation")
        elif vol_7d and vol_7d > 2.0:
            findings.append(f"📈 High volatility: {vol_7d:.1f}x annualized")

        if whale_beta and abs(whale_beta) > 0.7:
            direction = "positively" if whale_beta > 0 else "inversely"
            findings.append(f"🐋 Whale lock-step: β = {whale_beta:.2f} — Price moves {direction} with whale wallet")

        return TokenStatsResult(
            hhi=round(hhi, 4),
            gini=round(gini, 4),
            cr_top5=round(cr_top5, 4),
            cr_top10=round(cr_top10, 4),
            cr_top20=round(cr_top20, 4),
            effective_holders=round(effective_holders, 1),
            volatility_24h=round(vol_24h, 4) if vol_24h else None,
            volatility_7d=round(vol_7d, 4) if vol_7d else None,
            whale_beta=round(whale_beta, 4) if whale_beta else None,
            findings=findings,
            raw={
                "holder_count": len(holders),
                "total_supply": total_balance,
            }
        )

    def quick_from_balances(self, balances: List[float], **kwargs) -> TokenStatsResult:
        """Convenience: pass raw balances without constructing Holder objects."""
        holders = [Holder(address=f"holder_{i}", balance=b) for i, b in enumerate(balances)]
        return self.analyze(holders, **kwargs)


# Singleton
stats_engine = TokenStatisticsEngine()
