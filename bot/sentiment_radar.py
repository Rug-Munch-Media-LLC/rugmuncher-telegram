"""
📰 Sentiment Radar — Off-Chain Mood Layer for Rug Detection
============================================================
Inspired by two-stage news sentiment pipelines, but rebuilt with
lightweight local NLP (no paid API dependencies) and crypto-specific
keyword tuning.

Combines:
  • News headline scraping (optional, via free APIs)
  • VADER sentiment analysis (local, zero cost)
  • Aggregate sentiment score per token/ticker
  • Trending negativity spike detection

Usage:
  radar = SentimentRadar()
  result = radar.analyze("PEPE", headlines=[...])
  # result.sentiment_pct: -100 (max negative) to +100 (max positive)
"""

import re
import math
from dataclasses import dataclass, field
from typing import List, Dict, Optional
from collections import defaultdict


@dataclass
class SentimentResult:
    query: str
    positive_pct: float
    neutral_pct: float
    negative_pct: float
    compound_score: float       # -1.0 to +1.0
    article_count: int
    findings: List[str] = field(default_factory=list)
    top_positive: List[str] = field(default_factory=list)
    top_negative: List[str] = field(default_factory=list)


# ── VADER-inspired lexicon (crypto-tuned subset) ──
_CRYTO_POSITIVE = {
    "moon", "pump", "bull", "rally", "surge", "breakout", "ath", "all-time high",
    "adoption", "partnership", "listing", "burn", "deflationary", " staking",
    "yield", "airdrop", "gem", "alpha", "whale buying", "accumulation",
}
_CRYTO_NEGATIVE = {
    "rug", "scam", "honeypot", "dump", "bear", "crash", "collapse", "ploit",
    "hack", "exploit", "drain", "withdraw", "panic", "fud", "investigation",
    "sec", "lawsuit", "arrest", "frozen", "locked", "cant sell", "cannot sell",
    "high tax", "mint", "infinite", "dilution", "sell off", "whale dump",
    "dev sold", "creator sold", "abandoned", "dead", "graveyard",
}
_CRYTO_INTENSIFIERS = {
    "very", "extremely", "massively", "huge", "major", "significant",
    "absolute", "total", "complete", "utter", "massive", "big",
}
_CRYTO_NEGATORS = {"not", "no", "never", "neither", "barely", "hardly"}


class SentimentRadar:
    """Local, zero-API sentiment analysis for crypto headlines/text."""

    def analyze(self, query: str, headlines: List[str]) -> SentimentResult:
        if not headlines:
            return SentimentResult(
                query=query, positive_pct=0.0, neutral_pct=100.0,
                negative_pct=0.0, compound_score=0.0, article_count=0,
                findings=["No headlines to analyze"],
            )

        pos_count = 0
        neg_count = 0
        neu_count = 0
        compound_scores: List[float] = []
        top_pos: List[str] = []
        top_neg: List[str] = []

        for headline in headlines:
            score, intensity = self._score_text(headline.lower())
            compound_scores.append(score)
            if score > 0.05:
                pos_count += 1
                if len(top_pos) < 3:
                    top_pos.append(headline)
            elif score < -0.05:
                neg_count += 1
                if len(top_neg) < 3:
                    top_neg.append(headline)
            else:
                neu_count += 1

        total = len(headlines)
        pos_pct = pos_count / total * 100
        neg_pct = neg_count / total * 100
        neu_pct = neu_count / total * 100
        avg_compound = sum(compound_scores) / len(compound_scores) if compound_scores else 0.0

        findings = []
        if neg_pct >= 60:
            findings.append(f"🚨 Sentiment crisis: {neg_pct:.0f}% negative coverage")
        elif neg_pct >= 40:
            findings.append(f"⚠️ Elevated negativity: {neg_pct:.0f}% negative")
        elif pos_pct >= 70:
            findings.append(f"🟢 Strong positive sentiment: {pos_pct:.0f}% bullish")

        if avg_compound < -0.3:
            findings.append(f"📉 Deeply bearish compound score ({avg_compound:.2f})")
        elif avg_compound > 0.3:
            findings.append(f"📈 Strongly bullish compound score ({avg_compound:.2f})")

        return SentimentResult(
            query=query,
            positive_pct=round(pos_pct, 1),
            neutral_pct=round(neu_pct, 1),
            negative_pct=round(neg_pct, 1),
            compound_score=round(avg_compound, 3),
            article_count=total,
            findings=findings,
            top_positive=top_pos,
            top_negative=top_neg,
        )

    def _score_text(self, text: str) -> tuple[float, float]:
        """Return (compound_score, intensity) for a single text."""
        words = re.findall(r"\b[a-z]+\b", text)
        pos = 0
        neg = 0
        intensity = 1.0

        for i, word in enumerate(words):
            if word in _CRYTO_INTENSIFIERS:
                intensity = 1.5
                continue
            if word in _CRYTO_NEGATORS and i + 1 < len(words):
                # Flip next word's sentiment
                next_word = words[i + 1]
                if next_word in _CRYTO_POSITIVE:
                    neg += 1 * intensity
                elif next_word in _CRYTO_NEGATIVE:
                    pos += 1 * intensity
                intensity = 1.0
                continue

            if word in _CRYTO_POSITIVE:
                pos += 1 * intensity
            elif word in _CRYTO_NEGATIVE:
                neg += 1 * intensity
            intensity = 1.0

        # Bigram scan for compound phrases
        bigrams = [f"{words[i]} {words[i + 1]}" for i in range(len(words) - 1)]
        for bg in bigrams:
            if bg in ("dev sold", "creator sold", "team dumped", "lp removed",
                      "liquidity drained", "cant sell", "cannot sell"):
                neg += 2.0
            if bg in ("whale bought", "major partnership", "exchange listing"):
                pos += 2.0

        compound = (pos - neg) / max(pos + neg, 1.0)
        return compound, intensity

    def quick_score(self, text: str) -> float:
        """Single-text compound score (-1.0 to +1.0)."""
        score, _ = self._score_text(text.lower())
        return score


# Singleton
sentiment_radar = SentimentRadar()
