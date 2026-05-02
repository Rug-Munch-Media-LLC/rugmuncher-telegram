"""
⚡ Enrichment Engine — Lazy Async Deep-Dive Pattern
===================================================
Inspired by lazy-loading visual dashboards: send instant feedback,
then asynchronously enrich with deeper data.

This prevents Telegram UI blocking and gives users immediate
g ratification while heavy APIs churn in the background.

Pattern:
  1. Instantly return a "preview" card with basic metadata
  2. Spawn background tasks for: Helius, Birdeye, RugCheck, etc.
  3. Edit the original message when enrichment completes
  4. Cache results to avoid re-fetching

Integrates with:
  • URLScamDetector
  • TokenStatisticsEngine
  • ClusterMonitor
  • SentimentRadar
  • WalletPersonaProfiler
"""

import asyncio
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Callable, Any
from functools import lru_cache


@dataclass
class EnrichmentJob:
    job_id: str
    token_address: str
    chain: str
    preview: Dict
    status: str = "pending"       # pending | enriching | complete | failed
    results: Dict = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)
    started_at: float = 0.0
    completed_at: float = 0.0


class EnrichmentEngine:
    """
    Orchestrates multi-source async enrichment with lazy-edit pattern.
    """

    def __init__(self, max_concurrent: int = 5):
        self.semaphore = asyncio.Semaphore(max_concurrent)
        self.cache: Dict[str, Dict] = {}
        self.jobs: Dict[str, EnrichmentJob] = {}
        self.providers: Dict[str, Callable] = {}

    def register_provider(self, name: str, func: Callable):
        """Register an async enrichment function: func(address, chain) -> dict."""
        self.providers[name] = func

    async def enrich(self, job_id: str, token_address: str, chain: str,
                     preview: Dict, edit_callback: Optional[Callable] = None) -> EnrichmentJob:
        """
        Main entry: kick off enrichment, return job handle immediately.
        If edit_callback provided, it will be called with (job, updated_text)
        as each provider completes.
        """
        job = EnrichmentJob(
            job_id=job_id,
            token_address=token_address,
            chain=chain,
            preview=preview,
            status="enriching",
            started_at=time.time(),
        )
        self.jobs[job_id] = job

        cache_key = f"{chain}:{token_address}"
        if cache_key in self.cache:
            job.results = self.cache[cache_key]
            job.status = "complete"
            job.completed_at = time.time()
            if edit_callback:
                edit_callback(job, self._build_final_text(job))
            return job

        # Run providers concurrently with semaphore
        tasks = []
        for name, func in self.providers.items():
            tasks.append(self._run_provider(job, name, func))

        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

        job.status = "complete" if not job.errors else "partial"
        job.completed_at = time.time()
        self.cache[cache_key] = job.results

        if edit_callback:
            edit_callback(job, self._build_final_text(job))
        return job

    async def _run_provider(self, job: EnrichmentJob, name: str, func: Callable):
        async with self.semaphore:
            try:
                result = await func(job.token_address, job.chain)
                job.results[name] = result
            except Exception as e:
                job.errors.append(f"{name}: {e}")

    def _build_final_text(self, job: EnrichmentJob) -> str:
        """Build enriched Telegram text from job results."""
        lines = [
            f"🔍 <b>DEEP SCAN COMPLETE</b>",
            f"",
            f"<b>Token:</b> <code>{job.token_address}</code>",
            f"<b>Chain:</b> {job.chain.upper()}",
        ]

        # URL check
        url_res = job.results.get("url_check")
        if url_res and url_res.get("risk_score", 0) > 20:
            lines.append(f"🌐 <b>Website Risk:</b> {url_res.get('risk_class', 'unknown')} ({url_res.get('risk_score')}/100)")

        # Stats
        stats = job.results.get("token_stats")
        if stats:
            if stats.get("hhi"):
                lines.append(f"📊 <b>HHI:</b> {stats['hhi']:.3f} | <b>Gini:</b> {stats['gini']:.3f}")
            if stats.get("effective_holders"):
                lines.append(f"👥 <b>Effective holders:</b> {stats['effective_holders']:.0f}")

        # Cluster
        cluster = job.results.get("cluster")
        if cluster and cluster.get("coordination_score", 0) > 0.3:
            lines.append(f"📦 <b>Cluster alert:</b> {cluster.get('cluster_type')} (score {cluster['coordination_score']})")

        # Sentiment
        sent = job.results.get("sentiment")
        if sent and sent.get("negative_pct", 0) > 40:
            lines.append(f"📰 <b>Sentiment:</b> {sent['negative_pct']:.0f}% negative")

        # Persona
        persona = job.results.get("persona")
        if persona and persona.get("persona") not in ("unknown", "ordinary"):
            lines.append(f"👤 <b>Creator persona:</b> {persona['persona'].upper()} ({persona['persona_score']})")

        if job.errors:
            lines.append(f"\n⚠️ Some checks failed: {', '.join(e.split(':')[0] for e in job.errors[:2])}")

        return "\n".join(lines)

    def get_cached(self, token_address: str, chain: str) -> Optional[Dict]:
        return self.cache.get(f"{chain}:{token_address}")

    def invalidate(self, token_address: str, chain: str):
        self.cache.pop(f"{chain}:{token_address}", None)


# Singleton
enrichment_engine = EnrichmentEngine()
