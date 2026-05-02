"""
📦 Cluster Monitor — Coordinated Wallet Ring Detector
======================================================
Inspired by sliding-window burst detection concepts, rebuilt for
real-time Solana and EVM token launch forensics.

Detects:
  • Parent→child funding bursts within configurable time windows
  • BUY_CLUSTER vs SELL_CLUSTER classification
  • Swap coordination — did all children buy the SAME token?
  • Dev-wallet insider rings before/after launch

Algorithm:
  1. Stream or fetch transactions for a target wallet (parent/dev)
  2. Group OUT transfers by sliding time window
  3. If ≥N unique recipients in ≤W minutes → cluster trigger
  4. Correlation phase: check children for subsequent swaps into token X
  5. Score coordination confidence
"""

import asyncio
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Set
from datetime import datetime, timedelta
from collections import defaultdict


@dataclass
class FundingEvent:
    timestamp: datetime
    parent: str
    child: str
    amount: float           # normalized USD or native amount
    token: str              # "SOL", "ETH", "USDC", etc.
    tx_hash: str = ""


@dataclass
class ClusterResult:
    parent: str
    cluster_type: str       # BUY_CLUSTER | SELL_CLUSTER | FUNDING_BURST
    start_time: datetime
    end_time: datetime
    children: List[str]
    event_count: int
    coordination_score: float   # 0.0 – 1.0
    swap_correlation: Optional[float] = None
    common_target_token: Optional[str] = None
    findings: List[str] = field(default_factory=list)


# ── Noise filters — ignore these as "funding" ──
_NOISE_PROGRAMS = {"JUPITER", "SWAP", "MINT", "AIRDROP", "STAKE"}


class ClusterMonitor:
    """Detect coordinated wallet clusters via sliding-window analysis."""

    def __init__(self, min_children: int = 5, funding_window_minutes: int = 10):
        self.min_children = min_children
        self.window = timedelta(minutes=funding_window_minutes)

    def detect(self, parent: str, events: List[FundingEvent]) -> List[ClusterResult]:
        """
        Run sliding-window burst detection on a parent's funding events.
        Returns list of detected clusters.
        """
        if not events:
            return []

        # Filter noise and sort
        clean = [e for e in events if not self._is_noise(e)]
        clean.sort(key=lambda e: e.timestamp)

        clusters: List[ClusterResult] = []
        i = 0
        while i < len(clean):
            window_events = [clean[i]]
            window_children: Set[str] = {clean[i].child}
            j = i + 1
            while j < len(clean) and clean[j].timestamp - clean[i].timestamp <= self.window:
                window_events.append(clean[j])
                window_children.add(clean[j].child)
                j += 1

            if len(window_children) >= self.min_children:
                # Determine cluster type
                sol_eth_count = sum(1 for e in window_events if e.token in ("SOL", "ETH", "BNB", "MATIC", "AVAX"))
                stable_count = sum(1 for e in window_events if e.token in ("USDC", "USDT", "DAI", "BUSD"))
                other_count = len(window_events) - sol_eth_count - stable_count

                if other_count > sol_eth_count + stable_count:
                    ctype = "SELL_CLUSTER"      # funding with target token (distribution)
                else:
                    ctype = "BUY_CLUSTER"       # funding with buying power

                # Coordination scoring
                coord = min(1.0, len(window_children) / (self.min_children * 3))
                if len(window_events) / max(len(window_children), 1) > 1.5:
                    coord += 0.1  # Multiple transfers to same child = intentional

                clusters.append(ClusterResult(
                    parent=parent,
                    cluster_type=ctype,
                    start_time=clean[i].timestamp,
                    end_time=window_events[-1].timestamp,
                    children=list(window_children),
                    event_count=len(window_events),
                    coordination_score=round(min(1.0, coord), 3),
                    findings=[
                        f"📦 {ctype}: {len(window_children)} wallets funded in {(window_events[-1].timestamp - clean[i].timestamp).total_seconds() / 60:.0f} min",
                        f"🎯 Parent: {parent}",
                    ]
                ))
                i = j  # Skip past this cluster
            else:
                i += 1

        return clusters

    async def correlate_swaps(self, cluster: ClusterResult, swap_lookup_func) -> ClusterResult:
        """
        Async enrichment: for each child, look up recent swap transactions.
        swap_lookup_func: async callable(child_address) -> List[{token_out, timestamp}]
        """
        if not cluster.children:
            return cluster

        target_votes: Dict[str, int] = defaultdict(int)
        child_swap_count = 0

        tasks = [swap_lookup_func(child) for child in cluster.children]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        for swaps in results:
            if isinstance(swaps, Exception):
                continue
            if swaps:
                child_swap_count += 1
                for swap in swaps:
                    token = swap.get("token_out", "UNKNOWN")
                    target_votes[token] += 1

        if target_votes:
            top_token, top_votes = max(target_votes.items(), key=lambda x: x[1])
            cluster.swap_correlation = round(top_votes / len(cluster.children), 3)
            cluster.common_target_token = top_token
            if cluster.swap_correlation >= 0.6:
                cluster.findings.append(
                    f"🚨 HIGH COORDINATION: {cluster.swap_correlation:.0%} of children swapped into {top_token}"
                )
                cluster.coordination_score = min(1.0, cluster.coordination_score + 0.3)

        cluster.findings.append(
            f"📊 Swap follow-through: {child_swap_count}/{len(cluster.children)} children executed swaps"
        )
        return cluster

    def _is_noise(self, event: FundingEvent) -> bool:
        # In a real implementation this would check program IDs / method names
        return event.token.upper() in _NOISE_PROGRAMS

    def quick_burst_score(self, parent: str, events: List[FundingEvent]) -> float:
        """One-number burstiness score 0–100 for a parent wallet."""
        clusters = self.detect(parent, events)
        if not clusters:
            return 0.0
        best = max(clusters, key=lambda c: c.coordination_score)
        score = best.coordination_score * 100
        if best.cluster_type == "SELL_CLUSTER":
            score += 10
        return min(100.0, score)


# Singleton
cluster_monitor = ClusterMonitor()
