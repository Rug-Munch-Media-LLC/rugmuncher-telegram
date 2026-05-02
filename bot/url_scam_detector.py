"""
🔗 URL Scam Detector — Lexical Forensics for Crypto Links
=========================================================
Inspired by structural URL analysis concepts, but rebuilt for the
crypto scam landscape. Detects suspicious links in Telegram bios,
Discord announcements, Twitter profiles, and "official" token sites.

No blacklists needed — we score from the URL string itself using
lexical features + Shannon entropy, so zero-day scam domains are
caught instantly.

Risk classes:
  • safe           — Clean structural profile
  • potential_phishing — Mimics known brands, excessive subdomains
  • known_scam_pattern — Matches common rug-pull naming patterns
  • honeypot_site  — URL entropy + path patterns typical of trap sites
  • copycat_domain — Levenshtein-like proximity to major exchanges/TGEs
"""

import re
import math
from dataclasses import dataclass, field
from typing import List, Dict, Optional
from urllib.parse import urlparse


@dataclass
class URLRiskResult:
    url: str
    risk_class: str           # safe | potential_phishing | known_scam_pattern | honeypot_site | copycat_domain
    risk_score: float         # 0.0 – 100.0
    features: Dict = field(default_factory=dict)
    findings: List[str] = field(default_factory=list)
    recommendation: str = ""


# ── Known brand roots we see impersonated in crypto ──
_BRAND_ROOTS = [
    "pancakeswap", "uniswap", "sushiswap", "1inch", "curve", "aave",
    "compound", "binance", "coinbase", "kraken", "ftx", "bybit",
    "okx", "kucoin", "gemini", "metamask", "phantom", "solflare",
    "trustwallet", "ledger", "trezor", "opensea", "magiceden",
    "pump", "dexscreener", "birdeye", "jupiter", "raydium", "orca",
    "alchemy", "infura", "quicknode", "helius", "moralis",
]

# ── Common crypto scam TLD preferences ──
_SUSPICIOUS_TLDS = {".tk", ".ml", ".ga", ".cf", ".gq", ".top", ".xyz", ".click", ".link"}

# ── Regex patterns that scream scam ──
_SCAM_PATH_PATTERNS = [
    re.compile(r"/(claim|airdrop|free|bonus|gift|reward|mint)\b", re.I),
    re.compile(r"/(connect|verify|validate|sync|restore|import)\b", re.I),
    re.compile(r"/(wallet|seed|phrase|private.?key|backup)\b", re.I),
    re.compile(r"\.(php|html)\?[^&]*=(claim|airdrop|wallet|seed)", re.I),
]

# ── Homoglyph / leet-speak swaps used in copycat domains ──
_HOMOGLYPHS = str.maketrans("0o1il5s", "ooiissS")


def _shannon_entropy(s: str) -> float:
    """Shannon entropy in bits per character."""
    if not s:
        return 0.0
    length = len(s)
    counts = {}
    for ch in s:
        counts[ch] = counts.get(ch, 0) + 1
    entropy = 0.0
    for count in counts.values():
        p = count / length
        entropy -= p * math.log2(p)
    return entropy


def _domain_similarity(domain: str, brand: str) -> float:
    """Rough similarity 0–1 between domain and a known brand."""
    d = domain.lower().translate(_HOMOGLYPHS)
    b = brand.lower()
    if b in d and d != b:
        return 0.75
    # Simple prefix / suffix overlap
    overlap = sum(1 for i in range(min(len(d), len(b))) if d[i] == b[i])
    return overlap / max(len(d), len(b))


class URLScamDetector:
    """Lightweight, zero-API URL forensic scorer."""

    def analyze(self, raw_url: str) -> URLRiskResult:
        # Normalize
        url = raw_url.strip()
        if not url.startswith(("http://", "https://")):
            url = "https://" + url

        parsed = urlparse(url)
        domain = parsed.netloc.lower()
        path = parsed.path.lower()
        query = parsed.query.lower()

        # ── Feature extraction ──
        features = {
            "url_length": len(url),
            "domain_length": len(domain),
            "path_length": len(path),
            "subdomain_count": domain.count("."),
            "has_ip": bool(re.match(r"^\d+\.\d+\.\d+\.\d+", domain)),
            "has_at_symbol": "@" in url,
            "has_double_slash": "//" in path,
            "has_hex_blob": bool(re.search(r"[0-9a-f]{16,}", domain + path)),
            "url_entropy": _shannon_entropy(url),
            "domain_entropy": _shannon_entropy(domain),
            "path_entropy": _shannon_entropy(path),
            "digit_ratio": sum(c.isdigit() for c in domain) / max(len(domain), 1),
            "special_char_ratio": sum(not c.isalnum() for c in domain) / max(len(domain), 1),
            "suspicious_tld": any(domain.endswith(tld) for tld in _SUSPICIOUS_TLDS),
            "path_scam_keyword_matches": 0,
            "brand_copycat_score": 0.0,
            "excessive_subdomains": domain.count(".") >= 3,
        }

        # Path scam keyword scan
        for pat in _SCAM_PATH_PATTERNS:
            if pat.search(path) or pat.search(query):
                features["path_scam_keyword_matches"] += 1

        # Brand copycat scan
        best_sim = 0.0
        for brand in _BRAND_ROOTS:
            sim = _domain_similarity(domain, brand)
            if sim > best_sim:
                best_sim = sim
        features["brand_copycat_score"] = best_sim

        # ── Scoring ──
        score = 0.0
        findings: List[str] = []

        # Entropy signals
        if features["domain_entropy"] > 4.2:
            score += 18
            findings.append(f"🔐 High domain entropy ({features['domain_entropy']:.2f}) — randomized / obfuscated domain")
        elif features["domain_entropy"] > 3.5:
            score += 8
            findings.append(f"🔐 Elevated domain entropy ({features['domain_entropy']:.2f})")

        if features["url_entropy"] > 5.0:
            score += 10
            findings.append("🔐 Very high overall URL entropy — possible encoded payload")

        # Copycat brand
        if best_sim >= 0.75:
            score += 25
            findings.append(f"🎭 Copycat domain mimics known brand (similarity {best_sim:.2f})")
        elif best_sim >= 0.5:
            score += 12
            findings.append(f"🎭 Possible brand impersonation (similarity {best_sim:.2f})")

        # Structural red flags
        if features["has_ip"]:
            score += 15
            findings.append("🌐 Raw IP address used as host — common in phishing")
        if features["has_at_symbol"]:
            score += 12
            findings.append("📧 '@' symbol in URL — credential-harvesting trick")
        if features["has_double_slash"]:
            score += 8
            findings.append("⛔ Double-slash redirect pattern detected")
        if features["excessive_subdomains"]:
            score += 8
            findings.append("📂 Excessive subdomains — URL confusion tactic")
        if features["suspicious_tld"]:
            score += 7
            findings.append("🚩 Suspicious TLD associated with scam infrastructure")
        if features["has_hex_blob"]:
            score += 6
            findings.append("🧬 Hex blob in domain/path — obfuscation attempt")

        # Path keywords
        kw = features["path_scam_keyword_matches"]
        if kw >= 2:
            score += 18
            findings.append(f"🪤 Multiple scam-path keywords detected ({kw})")
        elif kw == 1:
            score += 9
            findings.append("🪤 Scam-path keyword detected")

        # Digit ratio
        if features["digit_ratio"] > 0.3:
            score += 8
            findings.append("🔢 Domain is heavily numeric — algorithm-generated")

        score = min(100.0, score)

        # ── Risk class ──
        if score >= 60:
            risk_class = "honeypot_site"
            rec = "❌ DO NOT CLICK — High probability of credential theft or malware"
        elif score >= 40:
            if best_sim >= 0.5:
                risk_class = "copycat_domain"
            elif kw > 0:
                risk_class = "known_scam_pattern"
            else:
                risk_class = "potential_phishing"
            rec = "⚠️ Highly suspicious — Verify through official channels before interacting"
        elif score >= 20:
            risk_class = "potential_phishing"
            rec = "🟡 Some structural risk markers — Proceed with caution"
        else:
            risk_class = "safe"
            rec = "✅ No structural scam signals detected (but this does NOT guarantee safety)"

        return URLRiskResult(
            url=raw_url,
            risk_class=risk_class,
            risk_score=round(score, 1),
            features=features,
            findings=findings,
            recommendation=rec,
        )


# Singleton
detector = URLScamDetector()


def quick_check(url: str) -> URLRiskResult:
    """Convenience one-liner."""
    return detector.analyze(url)
