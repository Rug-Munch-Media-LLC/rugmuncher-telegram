"""
🛡️ Address Validator & Categorization Taxonomy
===============================================
Inspired by strict forensic validation pipelines, but focused on
on-chain address hygiene. Rejects false positives before they ever
reach the scoring engine.

Categories:
  • DEX_ROUTER      — Known AMM/router program
  • CEX_DEPOSIT     — Known exchange hot wallet
  • KNOWN_SCAMMER   — In our blacklist DB
  • MIXER           — Tornado / similar privacy pool
  • BURN            — Token burn address
  • DEV_WALLET      — Contract deployer
  • SNIPER_BOT      — Identified MEV/sniper pattern
  • ORDINARY        — Regular user wallet

Validation stages:
  1. Syntax check (length, prefix, alphabet)
  2. Blacklist filter (burn, zero, program accounts)
  3. Category lookup (known entity DB)
  4. Confidence scoring
"""

import re
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Set


@dataclass
class AddressValidationResult:
    address: str
    is_valid: bool
    chain: str
    category: str = "ORDINARY"
    confidence: float = 0.0          # 0.0 – 1.0
    warnings: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    normalized: str = ""


# ── Chain-specific burn / sentinel addresses ──
_BURNS = {
    "eth": {
        "0x0000000000000000000000000000000000000000",
        "0x000000000000000000000000000000000000dead",
        "0xdead000000000000000042069420694206942069",
    },
    "bsc": {
        "0x0000000000000000000000000000000000000000",
        "0x000000000000000000000000000000000000dead",
    },
    "sol": {
        "11111111111111111111111111111111",           # SystemProgram
        "So11111111111111111111111111111111111111112",  # Wrapped SOL
        "burn111111111111111111111111111111111111111",   # common burn
    },
}

# ── Known DEX routers / program accounts ──
_DEX_ROUTERS = {
    "eth": {
        "0x7a250d5630b4cf539739df2c5dacb4c659f2488d",  # Uniswap V2
        "0xe592427a0aece92de3edee1f18e0157c05861564",  # Uniswap V3
        "0x68b3465833fb72a70ecdf485e0e4c7bd8665fc45",  # Uniswap V3 Router2
        "0x10ed43c718714eb63d5aa57b78b54704e256024e",  # PancakeSwap V2
        "0x13f4ea83d0bd40e75c8222255bc855a974568dd4",  # PancakeSwap V3
        "0xdef1c0ded9bec7f1a1670819833240f027b25eff",  # 0x
    },
    "bsc": {
        "0x10ed43c718714eb63d5aa57b78b54704e256024e",
        "0x13f4ea83d0bd40e75c8222255bc855a974568dd4",
    },
    "sol": {
        "JUP6LkbZbjS1jKKwapdHNy74zcZ3tLUZoi5QNyVTaV4",  # Jupiter
        "675kPX9MHTjS2zt1qfr1NYHuzeLXfQM9H24wFSUt1Mp8",  # Raydium AMM
        "9W959DqEETiGZocYWCQPaJ6sBmUzgfxXfqGeTEdp3aQP",   # Orca Whirlpool
        "Eo7WjKq67rjJQSZxS6z3YkapzY3eMj6Xy8X5EQVn5UaB",   # Meteora
    },
}

# ── Known CEX deposit wallets (sample — should be DB-backed in prod) ──
_CEX_DEPOSITS = {
    "eth": set(),
    "bsc": set(),
    "sol": set(),
}

# ── Mixer / privacy pools ──
_MIXERS = {
    "eth": {
        "0x722122df12d4e14e13ac3b6895a86e84145b6967",  # Tornado.Cash Proxy
        "0x910cbd523d972eb0a6f4cae4618ad62622b39dbf",  # Tornado.Cash 10 ETH
        "0x47ce0c6ed5b0ce3d3a51fdb1c52dc66a7c3c2936",  # Tornado.Cash 1 ETH
    },
}

# ── Solana program account patterns (addresses that are programs, not wallets) ──
_SOL_PROGRAM_PATTERNS = [
    re.compile(r"^[1-9A-HJ-NP-Za-km-z]{32,44}$"),
]


class AddressValidator:
    """Multi-stage address validation and categorization."""

    def __init__(self):
        self.blacklist: Dict[str, Set[str]] = {
            "eth": set(),
            "bsc": set(),
            "sol": set(),
        }
        self._build_blacklists()

    def _build_blacklists(self):
        for chain in ("eth", "bsc", "sol"):
            self.blacklist[chain].update(_BURNS.get(chain, set()))
            self.blacklist[chain].update(_DEX_ROUTERS.get(chain, set()))
            self.blacklist[chain].update(_CEX_DEPOSITS.get(chain, set()))
            self.blacklist[chain].update(_MIXERS.get(chain, set()))

    def validate(self, address: str, chain: str = "eth") -> AddressValidationResult:
        chain = chain.lower()
        normalized = address.strip().lower() if chain in ("eth", "bsc") else address.strip()
        warnings: List[str] = []
        tags: List[str] = []
        is_valid = False
        category = "ORDINARY"
        confidence = 0.0

        # ── Stage 1: Syntax ──
        if chain in ("eth", "bsc", "polygon", "arbitrum", "base", "avalanche", "fantom", "optimism"):
            if re.match(r"^0x[a-fA-F0-9]{40}$", address):
                is_valid = True
            else:
                warnings.append("Malformed EVM address (must be 0x + 40 hex chars)")
        elif chain == "sol":
            if re.match(r"^[1-9A-HJ-NP-Za-km-z]{32,44}$", address):
                is_valid = True
            else:
                warnings.append("Malformed Solana address (base58, 32–44 chars)")
        else:
            warnings.append(f"Unsupported chain: {chain}")

        if not is_valid:
            return AddressValidationResult(
                address=address, is_valid=False, chain=chain,
                warnings=warnings, normalized=normalized,
            )

        # ── Stage 2: Blacklist / sentinel ──
        bl = self.blacklist.get(chain, set())
        if normalized in bl or address.strip() in bl:
            if normalized in _BURNS.get(chain, set()):
                category = "BURN"
                tags.append("burn_address")
                confidence = 1.0
            elif normalized in _DEX_ROUTERS.get(chain, set()):
                category = "DEX_ROUTER"
                tags.append("router")
                confidence = 0.98
            elif normalized in _CEX_DEPOSITS.get(chain, set()):
                category = "CEX_DEPOSIT"
                tags.append("exchange")
                confidence = 0.95
            elif normalized in _MIXERS.get(chain, set()):
                category = "MIXER"
                tags.append("privacy_pool")
                confidence = 0.95
                warnings.append("🌪️ Address is a known mixer/privacy pool")

        # ── Stage 3: Pattern heuristics ──
        if category == "ORDINARY":
            # Check for obvious bot patterns (all same char, sequential, etc.)
            addr_body = normalized[2:] if normalized.startswith("0x") else normalized
            if len(set(addr_body)) <= 4:
                tags.append("low_entropy_address")
                warnings.append("🤖 Address has extremely low character entropy — possible vanity / generated batch")
            if addr_body.count("0") > len(addr_body) * 0.6:
                tags.append("highly_zeroed")
            if self._is_sequential(addr_body):
                tags.append("sequential_pattern")

            confidence = 0.85 if not tags else 0.65

        return AddressValidationResult(
            address=address,
            is_valid=True,
            chain=chain,
            category=category,
            confidence=confidence,
            warnings=warnings,
            tags=tags,
            normalized=normalized,
        )

    def _is_sequential(self, s: str) -> bool:
        """Detect sequential hex patterns like 012345... or abcdef..."""
        s = s.lower()
        for length in (6, 8):
            for i in range(len(s) - length + 1):
                substr = s[i:i + length]
                try:
                    vals = [int(c, 16) for c in substr]
                    if all(vals[j] + 1 == vals[j + 1] for j in range(len(vals) - 1)):
                        return True
                except ValueError:
                    continue
        return False

    def batch_validate(self, addresses: List[str], chain: str = "eth") -> List[AddressValidationResult]:
        return [self.validate(a, chain) for a in addresses]


# Singleton
validator = AddressValidator()
