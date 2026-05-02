"""
🏗️ Contract Maturity Engine — Security Posture Scoring
========================================================
Inspired by the Nascent Simple Security Toolkit's audit readiness
and pre-launch checklists, rebuilt for automated token scanning.

Instead of looking for active malicious signals (honeypot, tax traps),
this engine scores the *absence of security maturity* — a leading
indicator that a contract was slapped together by amateurs or scammers.

A contract with:
  • Old Solidity version      → higher risk
  • No source verification    → higher risk
  • No audit trail            → higher risk
  • No security contact       → higher risk
  • No bug bounty             → higher risk
  • Compiler warnings         → higher risk
  • Missing NatSpec           → higher risk
  • Unchecked blocks undocumented → higher risk

Score: 0–100 maturity points.
Low maturity = elevated rug probability.

This complements the existing 100-point forensic risk engine by
adding a "professionalism" dimension.
"""

import re
from dataclasses import dataclass, field
from typing import List, Dict, Optional
from datetime import datetime


@dataclass
class MaturityResult:
    address: str
    chain: str
    maturity_score: int       # 0–100 (higher = more professional/secure)
    maturity_level: str       # EXCELLENT | GOOD | ADEQUATE | POOR | DANGEROUS
    checklist: Dict[str, bool] = field(default_factory=dict)
    findings: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)


# ── Solidity version risk tiers ──
# Higher penalty = older, riskier versions
_SOLIDITY_RISKS = {
    "0.4": 25, "0.5": 20, "0.6": 15, "0.7": 8, "0.8": 0,
}

# ── Known audit firms (triggers positive signal if found) ──
_AUDIT_FIRMS = [
    "trail of bits", "openzeppelin", "certik", "hacken", "quantstamp",
    "peckshield", "slowmist", "consensys diligence", "chainsecurity",
    "sigmaprime", "runtime verification", "certora", "immunefi",
    "code4rena", "sherlock", "spearbit",
]

# ── Security contact signals ──
_SECURITY_CONTACT_SIGNALS = [
    "security@", "bugbounty@", "responsible disclosure",
    "security contact", "bug bounty", "hackerone", "immunefi",
]


class ContractMaturityEngine:
    """
    Score a token contract's development maturity based on signals
    we can extract from source code, GitHub, explorers, and public docs.
    """

    def analyze(self, address: str, chain: str = "eth",
                source_code: Optional[str] = None,
                metadata: Optional[Dict] = None) -> MaturityResult:
        """
        metadata expected keys:
          - solidity_version: str (e.g. "0.8.19")
          - is_verified: bool
          - compiler_warnings: int
          - has_natspec: bool
          - has_audit: bool
          - audit_firms: List[str]
          - github_url: Optional[str]
          - has_bug_bounty: bool
          - security_contact: Optional[str]
          - uses_openzeppelin: bool
          - uses_solmate: bool
          - uses_custom_libs: bool
          - has_deploy_script: bool
          - has_test_suite: bool
          - has_ci: bool
          - license: Optional[str]
          - is_proxy: bool
          - has_timelock: bool
          - has_multisig: bool
        """
        if metadata is None:
            metadata = {}

        score = 0
        checklist: Dict[str, bool] = {}
        findings: List[str] = []
        recommendations: List[str] = []

        # ── 1. Source Verification (25 pts) ──
        if metadata.get("is_verified"):
            score += 25
            checklist["source_verified"] = True
        else:
            checklist["source_verified"] = False
            findings.append("📄 Contract source NOT verified — could be anything")
            recommendations.append("Verify contract on Etherscan/BscScan/Explorer")

        # ── 2. Solidity Version (15 pts) ──
        sol_ver = metadata.get("solidity_version", "")
        if sol_ver:
            major_minor = ".".join(sol_ver.split(".")[:2])
            penalty = _SOLIDITY_RISKS.get(major_minor, 10)
            earned = max(0, 15 - penalty)
            score += earned
            checklist["modern_solidity"] = earned >= 10
            if penalty >= 15:
                findings.append(f"⚠️ Ancient Solidity {sol_ver} — known vulnerabilities exist")
                recommendations.append("Upgrade to Solidity 0.8.x")
            elif penalty >= 8:
                findings.append(f"⚠️ Dated Solidity {sol_ver} — missing recent safety features")
        else:
            checklist["modern_solidity"] = False
            findings.append("❓ Solidity version unknown")

        # ── 3. Code Quality & Documentation (15 pts) ──
        doc_score = 0
        if metadata.get("has_natspec"):
            doc_score += 8
            checklist["has_natspec"] = True
        else:
            checklist["has_natspec"] = False
            if source_code:
                # Heuristic: count @notice / @param / @return
                natspec_lines = len(re.findall(r"@(?:notice|param|return|dev|title)", source_code or ""))
                if natspec_lines >= 5:
                    doc_score += 8
                    checklist["has_natspec"] = True
                else:
                    findings.append("📝 Missing NatSpec documentation")
                    recommendations.append("Add NatSpec to all public/external functions")

        if metadata.get("compiler_warnings", 0) == 0:
            doc_score += 4
            checklist["no_warnings"] = True
        else:
            checklist["no_warnings"] = False
            findings.append(f"⚠️ {metadata['compiler_warnings']} compiler warnings")
            recommendations.append("Fix all compiler warnings before launch")

        if metadata.get("license"):
            doc_score += 3
            checklist["has_license"] = True
        else:
            checklist["has_license"] = False
            if source_code and "SPDX-License-Identifier" in source_code:
                doc_score += 3
                checklist["has_license"] = True
            else:
                findings.append("📜 No SPDX license identifier")

        score += min(15, doc_score)

        # ── 4. Library Maturity (10 pts) ──
        lib_score = 0
        if metadata.get("uses_openzeppelin"):
            lib_score += 8
            checklist["uses_openzeppelin"] = True
        elif source_code and "openzeppelin" in source_code.lower():
            lib_score += 8
            checklist["uses_openzeppelin"] = True
        else:
            checklist["uses_openzeppelin"] = False

        if metadata.get("uses_solmate"):
            lib_score += 6
            checklist["uses_solmate"] = True
        elif source_code and "solmate" in source_code.lower():
            lib_score += 6
            checklist["uses_solmate"] = True

        # Penalty for unknown/custom libraries
        if metadata.get("uses_custom_libs") and lib_score == 0:
            findings.append("🧩 Uses unverified custom libraries — no battle-tested foundation")
            recommendations.append("Prefer OpenZeppelin or Solmate for core logic")

        score += min(10, lib_score)

        # ── 5. Audit History (15 pts) ──
        if metadata.get("has_audit"):
            score += 15
            checklist["has_audit"] = True
            audit_firms = metadata.get("audit_firms", [])
            if audit_firms:
                findings.append(f"✅ Audited by: {', '.join(audit_firms)}")
        else:
            checklist["has_audit"] = False
            # Heuristic from source comments
            if source_code:
                lowered = source_code.lower()
                found_audits = [f for f in _AUDIT_FIRMS if f in lowered]
                if found_audits:
                    score += 15
                    checklist["has_audit"] = True
                    findings.append(f"✅ Audit references found in source: {', '.join(found_audits)}")
                else:
                    findings.append("🔍 No security audit found")
                    recommendations.append("Commission an audit before launch (Trail of Bits, OpenZeppelin, Spearbit)")
            else:
                findings.append("🔍 No security audit found")
                recommendations.append("Commission an audit before launch")

        # ── 6. Bug Bounty & Security Contact (10 pts) ──
        bounty_score = 0
        if metadata.get("has_bug_bounty"):
            bounty_score += 6
            checklist["has_bug_bounty"] = True
            findings.append("🛡️ Bug bounty program active")
        else:
            checklist["has_bug_bounty"] = False

        sec_contact = metadata.get("security_contact", "")
        if sec_contact:
            bounty_score += 4
            checklist["has_security_contact"] = True
            findings.append(f"📧 Security contact: {sec_contact}")
        elif source_code:
            lowered = source_code.lower()
            if any(s in lowered for s in _SECURITY_CONTACT_SIGNALS):
                bounty_score += 4
                checklist["has_security_contact"] = True
            else:
                findings.append("📭 No security contact or bug bounty program")
                recommendations.append("Set up security@ email and list on Immunefi")
        else:
            findings.append("📭 No security contact or bug bounty program")
            recommendations.append("Set up security@ email and list on Immunefi")

        score += min(10, bounty_score)

        # ── 7. Deployment Hygiene (10 pts) ──
        deploy_score = 0
        if metadata.get("has_deploy_script"):
            deploy_score += 4
            checklist["has_deploy_script"] = True
        if metadata.get("has_test_suite"):
            deploy_score += 3
            checklist["has_test_suite"] = True
        else:
            findings.append("🧪 No test suite referenced")
        if metadata.get("has_ci"):
            deploy_score += 3
            checklist["has_ci"] = True
        else:
            findings.append("🔧 No CI/CD pipeline detected")

        score += min(10, deploy_score)

        # ── 8. Governance & Upgrade Safety ──
        if metadata.get("has_timelock"):
            score += 3
            checklist["has_timelock"] = True
            findings.append("⏳ Timelock detected — good governance practice")
        else:
            checklist["has_timelock"] = False
            if not metadata.get("is_proxy"):
                findings.append("⏳ No timelock — admin actions can be instant")
                recommendations.append("Add a timelock for sensitive operations")

        if metadata.get("has_multisig"):
            score += 2
            checklist["has_multisig"] = True
            findings.append("🔑 Multisig ownership — no single point of failure")
        else:
            checklist["has_multisig"] = False
            if not metadata.get("ownership_renounced", False):
                findings.append("🔑 Single-owner contract — consider multisig")

        # ── Determine level ──
        if score >= 85:
            level = "EXCELLENT"
            rec = "✅ Professional-grade security posture"
        elif score >= 65:
            level = "GOOD"
            rec = "🟢 Solid development practices with minor gaps"
        elif score >= 45:
            level = "ADEQUATE"
            rec = "🟡 Acceptable for early-stage, but gaps exist"
        elif score >= 25:
            level = "POOR"
            rec = "🟠 Concerning lack of security maturity"
        else:
            level = "DANGEROUS"
            rec = "❌ Amateur-hour deployment — extreme caution advised"

        if level in ("POOR", "DANGEROUS"):
            findings.insert(0, f"⚠️ MATURITY ALERT: {level} ({score}/100) — {rec}")

        return MaturityResult(
            address=address,
            chain=chain,
            maturity_score=min(100, score),
            maturity_level=level,
            checklist=checklist,
            findings=findings,
            recommendations=recommendations,
        )

    def quick_maturity(self, address: str, chain: str = "eth",
                       is_verified: bool = False,
                       solidity_version: str = "",
                       has_audit: bool = False) -> MaturityResult:
        """Convenience one-liner with minimal inputs."""
        return self.analyze(address, chain, metadata={
            "is_verified": is_verified,
            "solidity_version": solidity_version,
            "has_audit": has_audit,
        })


# Singleton
maturity_engine = ContractMaturityEngine()
