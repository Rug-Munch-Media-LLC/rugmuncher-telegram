"""
Rug Muncher — Real Data Scanner Wrapper
========================================
Wraps ServicePackScanner with our multi-source API sourcer
for maximum data coverage and accuracy.

Now integrates:
  • URL Scam Detector
  • Token Statistics (HHI, Gini, volatility)
  • Address Validator & Taxonomy
  • Wallet Persona Profiler
  • Cluster Monitor
  • Sentiment Radar
  • Launch Detector
  • Lazy Enrichment Engine

Falls back gracefully if any source fails.
"""

import asyncio
import logging
from typing import Optional, Dict, Any
from dataclasses import dataclass, field
from datetime import datetime

try:
    from service_pack import ServicePackScanner, TokenScanResult
except ImportError:
    ServicePackScanner = None
    TokenScanResult = None

from bot.api_sourcer import api_sourcer, ContractData
from bot.risk_engine import risk_engine, RiskReport, HeuristicResult, CategoryResult

# New intelligence modules
from bot.url_scam_detector import detector as url_detector, URLRiskResult
from bot.token_statistics import stats_engine, Holder, TokenStatsResult
from bot.address_validator import validator, AddressValidationResult
from bot.wallet_persona import profiler, SwapEvent, WalletPersonaResult
from bot.cluster_monitor import cluster_monitor, FundingEvent, ClusterResult
from bot.sentiment_radar import sentiment_radar, SentimentResult
from bot.launch_detector import launch_detector, LaunchEvent, EnrichedLaunch
from bot.enrichment_engine import enrichment_engine, EnrichmentJob

logger = logging.getLogger("scanner_wrapper")


@dataclass
class EnhancedScanResult:
    """Enhanced result with real on-chain data."""
    address: str
    chain: str
    risk_score: int
    risk_level: str
    findings: list
    sources: dict = field(default_factory=dict)
    contract_data: Optional[ContractData] = None
    recommendation: str = ""
    # New enrichment fields
    url_check: Optional[URLRiskResult] = None
    token_stats: Optional[TokenStatsResult] = None
    address_validation: Optional[AddressValidationResult] = None
    persona: Optional[WalletPersonaResult] = None
    clusters: list = field(default_factory=list)
    sentiment: Optional[SentimentResult] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "address": self.address,
            "chain": self.chain,
            "risk_score": self.risk_score,
            "risk_level": self.risk_level,
            "findings": self.findings,
            "sources": self.sources,
            "recommendation": self.recommendation,
        }


class RealScanner:
    """Production scanner with real API integrations + new intelligence layer."""

    def __init__(self):
        if ServicePackScanner:
            self.base_scanner = ServicePackScanner()
        else:
            self.base_scanner = None
            logger.warning("ServicePackScanner not available — running in API-only mode")
        logger.info("✅ RealScanner initialized with multi-source API + intelligence layer")

    def _calculate_risk(self, contract: ContractData, extras: Dict[str, Any]) -> RiskReport:
        """Run deep 100-point forensic risk analysis with new signals."""
        report = risk_engine.analyze(contract)

        # ── Inject new statistical signals ──
        token_stats = extras.get("token_stats")
        if token_stats:
            cat = self._find_or_create_category(report, "Holder Distribution")
            if token_stats.hhi > 0.5:
                cat.heuristics.append(HeuristicResult(
                    name="hhi_monopoly", weight=15, score=15,
                    finding=f"🐋 Supply monopoly: HHI = {token_stats.hhi:.3f}",
                    raw_value=token_stats.hhi,
                ))
            elif token_stats.hhi > 0.25:
                cat.heuristics.append(HeuristicResult(
                    name="hhi_high", weight=15, score=8,
                    finding=f"⚠️ High supply concentration: HHI = {token_stats.hhi:.3f}",
                    raw_value=token_stats.hhi,
                ))
            if token_stats.gini > 0.8:
                cat.heuristics.append(HeuristicResult(
                    name="gini_extreme", weight=12, score=12,
                    finding=f"📊 Extreme inequality: Gini = {token_stats.gini:.3f}",
                    raw_value=token_stats.gini,
                ))

        # Cluster signals
        clusters = extras.get("clusters", [])
        if clusters:
            cat = self._find_or_create_category(report, "Market Behavior")
            best = max(clusters, key=lambda c: c.coordination_score)
            if best.coordination_score >= 0.7:
                cat.heuristics.append(HeuristicResult(
                    name="coordinated_cluster", weight=15, score=15,
                    finding=f"🚨 Coordinated wallet ring detected: {best.cluster_type} (score {best.coordination_score})",
                    raw_value=best.coordination_score,
                ))

        # Sentiment
        sentiment = extras.get("sentiment")
        if sentiment and sentiment.negative_pct >= 60:
            cat = self._find_or_create_category(report, "Market Behavior")
            cat.heuristics.append(HeuristicResult(
                name="negative_sentiment", weight=8, score=8,
                finding=f"📰 Sentiment crisis: {sentiment.negative_pct:.0f}% negative coverage",
                raw_value=sentiment.negative_pct,
            ))

        # URL check
        url_check = extras.get("url_check")
        if url_check and url_check.risk_score >= 40:
            cat = self._find_or_create_category(report, "Contract Security")
            cat.heuristics.append(HeuristicResult(
                name="suspicious_website", weight=10, score=min(10, int(url_check.risk_score / 4)),
                finding=f"🌐 Suspicious project URL: {url_check.risk_class} ({url_check.risk_score}/100)",
                raw_value=url_check.risk_score,
            ))

        # Recalculate total with new heuristics
        report.total_score = sum(cat.score for cat in report.categories)
        for min_s, max_s, lvl, r in risk_engine.LEVELS:
            if min_s <= report.total_score <= max_s:
                report.level = lvl
                report.recommendation = r
                break

        return report

    def _find_or_create_category(self, report: RiskReport, name: str) -> CategoryResult:
        for cat in report.categories:
            if cat.name == name:
                return cat
        new_cat = CategoryResult(name=name, max_points=20, heuristics=[])
        report.categories.append(new_cat)
        return new_cat

    async def scan(self, address: str, chain: str = "solana", deep: bool = False,
                   project_url: Optional[str] = None,
                   headlines: Optional[list] = None,
                   holder_balances: Optional[list] = None) -> Dict[str, Any]:
        """Run enhanced scan with real data + new intelligence layer."""
        logger.info(f"🔍 RealScan: {address} on {chain}")

        extras: Dict[str, Any] = {}

        # ── Parallel enrichment of new signals ──
        tasks = []

        # URL check
        if project_url:
            tasks.append(("url_check", asyncio.to_thread(url_detector.analyze, project_url)))

        # Token stats (if holder balances provided)
        if holder_balances:
            holders = [Holder(address=f"h_{i}", balance=b) for i, b in enumerate(holder_balances)]
            tasks.append(("token_stats", asyncio.to_thread(stats_engine.analyze, holders)))

        # Address validation
        tasks.append(("address_validation", asyncio.to_thread(validator.validate, address, chain)))

        # Sentiment
        if headlines:
            tasks.append(("sentiment", asyncio.to_thread(sentiment_radar.analyze, address[:8], headlines)))

        # Run all enrichment tasks
        if tasks:
            results = await asyncio.gather(*[t[1] for t in tasks], return_exceptions=True)
            for (key, _), res in zip(tasks, results):
                if isinstance(res, Exception):
                    logger.warning(f"Enrichment {key} failed: {res}")
                else:
                    extras[key] = res

        # ── Core API sourcer ──
        try:
            contract_data = await api_sourcer.analyze_contract(address, chain)
        except Exception as e:
            logger.error(f"API sourcer failed: {e}")
            contract_data = ContractData(address=address, chain=chain)

        # ── Risk analysis with enriched signals ──
        report = self._calculate_risk(contract_data, extras)

        # Build sources dict
        sources = {
            "api_sourcer": {
                "is_verified": contract_data.is_verified,
                "has_honeypot": contract_data.has_honeypot,
                "buy_tax": contract_data.buy_tax,
                "sell_tax": contract_data.sell_tax,
                "holders": contract_data.holders,
                "liquidity_usd": contract_data.liquidity_usd,
                "market_cap": contract_data.market_cap,
                "price_usd": contract_data.price_usd,
                "top_holder_pct": contract_data.top_holder_pct,
            },
            "risk_breakdown": report.category_breakdown,
        }

        for key in ("url_check", "token_stats", "sentiment", "address_validation"):
            if key in extras:
                val = extras[key]
                sources[key] = val.__dict__ if hasattr(val, "__dataclass_fields__") else val

        return EnhancedScanResult(
            address=address,
            chain=chain,
            risk_score=report.total_score,
            risk_level=report.level,
            findings=report.findings,
            sources=sources,
            contract_data=contract_data,
            recommendation=report.recommendation,
            url_check=extras.get("url_check"),
            token_stats=extras.get("token_stats"),
            address_validation=extras.get("address_validation"),
            sentiment=extras.get("sentiment"),
        ).to_dict()

    async def scan_wallet(self, address: str, chain: str = "ethereum",
                          swap_history: Optional[list] = None) -> Dict[str, Any]:
        """Wallet scan with persona profiling."""
        result = {
            "address": address,
            "chain": chain,
            "validation": validator.validate(address, chain).__dict__,
        }
        if swap_history:
            swaps = [SwapEvent(
                timestamp=s.get("timestamp", datetime.utcnow()),
                token_in=s.get("token_in", ""),
                token_out=s.get("token_out", ""),
                amount_in_usd=s.get("amount_in_usd", 0),
                amount_out_usd=s.get("amount_out_usd", 0),
                tx_hash=s.get("tx_hash", ""),
            ) for s in swap_history]
            persona = profiler.analyze(address, swaps)
            result["persona"] = persona.__dict__
        return result

    async def detect_clusters(self, parent: str, funding_events: list) -> list:
        """Run cluster monitor on a parent's funding history."""
        events = [FundingEvent(
            timestamp=e.get("timestamp", datetime.utcnow()),
            parent=e.get("parent", parent),
            child=e.get("child", ""),
            amount=e.get("amount", 0),
            token=e.get("token", "SOL"),
            tx_hash=e.get("tx_hash", ""),
        ) for e in funding_events]
        clusters = cluster_monitor.detect(parent, events)
        return [c.__dict__ for c in clusters]


# Singleton
real_scanner = RealScanner()

