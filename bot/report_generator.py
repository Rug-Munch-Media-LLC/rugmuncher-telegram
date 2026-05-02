"""
Rug Muncher — Report Generator
===============================
Generates:
  • PNG risk cards (viral shareable)
  • PDF detailed reports
  • Markdown for bots
  • JSON for API
"""

import json
from io import BytesIO
from typing import Dict, List, Optional
from pathlib import Path

try:
    from PIL import Image, ImageDraw, ImageFont
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

from config import BRAND_NAME, BRAND_TAGLINE, BRAND_COLOR, SAFE_COLOR, WARNING_COLOR


def _risk_color(score: int) -> str:
    if score >= 80:
        return "#FF1744"  # Red
    elif score >= 60:
        return "#FF5722"  # Deep Orange
    elif score >= 40:
        return "#FFB300"  # Amber
    elif score >= 20:
        return "#FFEB3B"  # Yellow
    else:
        return "#00C853"  # Green


def _risk_emoji(score: int) -> str:
    if score >= 80:
        return "🚨"
    elif score >= 60:
        return "⚠️"
    elif score >= 40:
        return "😐"
    elif score >= 20:
        return "🙂"
    else:
        return "✅"


def generate_png_card(
    address: str,
    risk_score: int,
    risk_level: str,
    findings: List[str],
    chain: str = "solana",
    tier: str = "free",
) -> Optional[bytes]:
    """
    Generate a viral shareable PNG risk card.
    Returns PNG bytes or None if PIL not available.
    """
    if not HAS_PIL:
        return None

    W, H = 800, 1000
    bg = "#0A0A0F"
    card_bg = "#14141F"
    text_light = "#FFFFFF"
    text_dim = "#8899AA"
    accent = _risk_color(risk_score)

    img = Image.new("RGB", (W, H), bg)
    draw = ImageDraw.Draw(img)

    # Try to load fonts, fallback to default
    try:
        font_title = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 36)
        font_sub = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 20)
        font_score = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 72)
        font_body = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 18)
        font_small = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 14)
    except Exception:
        font_title = font_sub = font_score = font_body = font_small = ImageFont.load_default()

    # Header bar
    draw.rectangle([0, 0, W, 8], fill=accent)

    # Brand
    draw.text((40, 30), f"🛡️ {BRAND_NAME}", fill=text_light, font=font_title)
    draw.text((40, 80), BRAND_TAGLINE, fill=text_dim, font=font_sub)

    # Divider
    draw.line([(40, 120), (W - 40, 120)], fill="#2A2A3A", width=2)

    # Chain badge
    draw.rounded_rectangle([40, 140, 180, 180], radius=8, fill="#1E1E2E", outline="#2A2A3A")
    draw.text((55, 148), f"🔗 {chain.upper()}", fill=text_dim, font=font_body)

    # Address (truncated)
    addr_display = address[:20] + "..." + address[-8:] if len(address) > 32 else address
    draw.text((40, 200), addr_display, fill=text_light, font=font_sub)

    # Risk Score Circle
    cx, cy = W // 2, 380
    radius = 80
    draw.ellipse([cx - radius, cy - radius, cx + radius, cy + radius], fill=card_bg, outline=accent, width=6)
    score_text = str(risk_score)
    bbox = draw.textbbox((0, 0), score_text, font=font_score)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    draw.text((cx - tw // 2, cy - th // 2 - 10), score_text, fill=accent, font=font_score)

    # Risk Level
    level_text = f"{_risk_emoji(risk_score)} {risk_level}"
    bbox = draw.textbbox((0, 0), level_text, font=font_sub)
    tw = bbox[2] - bbox[0]
    draw.text((cx - tw // 2, cy + radius + 20), level_text, fill=text_light, font=font_sub)

    # Findings section
    y = 520
    draw.text((40, y), "Key Findings:", fill=text_light, font=font_sub)
    y += 35

    max_findings = 5 if tier == "free" else 10
    display_findings = findings[:max_findings]

    for finding in display_findings:
        # Wrap text roughly
        words = finding.split()
        line = "• "
        for word in words:
            test = line + word + " "
            bbox = draw.textbbox((0, 0), test, font=font_body)
            if bbox[2] > W - 80:
                draw.text((40, y), line, fill=text_dim, font=font_body)
                y += 26
                line = "  " + word + " "
            else:
                line = test
        draw.text((40, y), line, fill=text_dim, font=font_body)
        y += 30

    # CTA for free tier
    if tier == "free":
        y += 20
        draw.rounded_rectangle([40, y, W - 40, y + 50], radius=8, fill=accent)
        cta = "🔓 Unlock full analysis at rugmuncher.ai"
        bbox = draw.textbbox((0, 0), cta, font=font_body)
        tw = bbox[2] - bbox[0]
        draw.text((cx - tw // 2, y + 12), cta, fill="#FFFFFF", font=font_body)

    # Footer
    draw.text((40, H - 40), "rugmuncher.ai  •  Don't get rekt", fill="#445566", font=font_small)

    buf = BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def generate_markdown_report(
    address: str,
    risk_score: int,
    risk_level: str,
    findings: List[str],
    chain: str = "solana",
    tier: str = "free",
) -> str:
    """Generate a Markdown report for Discord/Telegram."""
    emoji = _risk_emoji(risk_score)
    color = _risk_color(risk_score)

    lines = [
        f"## {emoji} {BRAND_NAME} Scan Result",
        f"",
        f"**Address:** `{address}`",
        f"**Chain:** {chain.upper()}",
        f"**Risk Score:** {risk_score}/100",
        f"**Risk Level:** {risk_level}",
        f"",
        f"### Key Findings:",
    ]

    max_findings = 5 if tier == "free" else len(findings)
    for f in findings[:max_findings]:
        lines.append(f"- {f}")

    if tier == "free" and len(findings) > max_findings:
        lines.append(f"")
        lines.append(f"🔓 *{len(findings) - max_findings} more findings hidden. Upgrade for full analysis.*")
        lines.append(f"👉 https://rugmuncher.ai")

    lines.append(f"")
    lines.append(f"---")
    lines.append(f"🛡️ {BRAND_NAME} — {BRAND_TAGLINE}")

    return "\n".join(lines)


def generate_json_report(
    address: str,
    risk_score: int,
    risk_level: str,
    findings: List[str],
    sources: Dict,
    novel_methods: Dict,
    chain: str = "solana",
    tier: str = "free",
) -> Dict:
    """Generate a structured JSON report for API consumers."""
    result = {
        "scanner": BRAND_NAME,
        "version": "1.0.0",
        "address": address,
        "chain": chain,
        "timestamp": str(datetime.utcnow().isoformat()),
        "tier": tier,
        "risk": {
            "score": risk_score,
            "level": risk_level,
            "max_score": 100,
        },
        "findings": findings[:5] if tier == "free" else findings,
        "sources_used": list(sources.keys()),
    }

    if tier == "premium":
        result["novel_methods"] = novel_methods
        result["raw_sources"] = sources

    return result


def generate_text_summary(
    address: str,
    risk_score: int,
    risk_level: str,
    findings: List[str],
    chain: str = "solana",
) -> str:
    """Generate a one-paragraph text summary."""
    emoji = _risk_emoji(risk_score)
    top_findings = [f for f in findings[:3] if not f.startswith("⚠️")]
    if not top_findings:
        top_findings = findings[:2]

    summary = (
        f"{emoji} {BRAND_NAME} scanned `{address}` on {chain.upper()}. "
        f"Risk Score: {risk_score}/100 ({risk_level}). "
    )

    if top_findings:
        summary += f"Key issues: {'; '.join(top_findings[:2])}. "

    if risk_score < 30:
        summary += "Looks relatively safe, but always DYOR."
    elif risk_score < 60:
        summary += "Moderate risk detected — proceed with caution."
    else:
        summary += "HIGH RISK — strong scam indicators present. Avoid."

    return summary


# Need datetime import for JSON report
from datetime import datetime
