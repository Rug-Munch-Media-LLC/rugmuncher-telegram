"""
x402 Unified Client
Talks to all 3 gateways: Base, Solana, Solana Agent.
Handles 402 responses, payment creation, and retries.
"""
import os
import json
import base64
import logging
from typing import Optional, Dict, Any
from dataclasses import dataclass

import requests

logger = logging.getLogger("x402_client")

# Gateway endpoints
BASE_GATEWAY = os.getenv("X402_BASE_GATEWAY", "http://localhost:8004")
SOLANA_GATEWAY = os.getenv("X402_SOLANA_GATEWAY", "http://localhost:8002")
SOLANA_AGENT = os.getenv("X402_SOLANA_AGENT", "http://localhost:8003")


@dataclass
class PaymentRequirement:
    version: int
    scheme: str
    network: str
    pay_to: str
    price: str
    amount_atomic: str
    asset: str
    asset_decimals: int
    instructions: list


@dataclass
class X402Response:
    ok: bool
    status_code: int
    data: Any
    payment_required: Optional[PaymentRequirement] = None
    error: Optional[str] = None


class X402Client:
    """Client for x402 pay-per-request gateways."""

    def __init__(self):
        self.base_url = BASE_GATEWAY
        self.solana_url = SOLANA_GATEWAY
        self.agent_url = SOLANA_AGENT

    # ── Base Gateway (EVM / Sepolia) ──

    def base_models(self) -> X402Response:
        """List available models on Base gateway."""
        return self._get(f"{self.base_url}/v1/models")

    def base_chat(self, model: str, messages: list, payment_header: Optional[str] = None) -> X402Response:
        """Chat via Base gateway. Returns 402 if no payment."""
        headers = {"Content-Type": "application/json"}
        if payment_header:
            headers["X-Payment"] = payment_header
        return self._post(f"{self.base_url}/v1/chat/completions", headers=headers, json={
            "model": model,
            "messages": messages,
        })

    # ── Solana Gateway ──

    def solana_models(self) -> X402Response:
        """List models on Solana gateway."""
        return self._get(f"{self.solana_url}/v1/models")

    def solana_chat(self, messages: list, payment_header: Optional[str] = None) -> X402Response:
        """Chat via Solana gateway."""
        headers = {"Content-Type": "application/json"}
        if payment_header:
            headers["X-Payment"] = payment_header
        return self._post(f"{self.solana_url}/v1/chat/completions", headers=headers, json={
            "messages": messages,
        })

    # ── Solana Profit Agent ──

    def agent_pricing(self) -> X402Response:
        """Get current agent pricing."""
        return self._get(f"{self.agent_url}/pricing")

    def agent_submit_task(self, prompt: str, complexity: str = "standard",
                          payment_header: Optional[str] = None) -> X402Response:
        """Submit a task to the profit agent."""
        headers = {"Content-Type": "application/json"}
        if payment_header:
            headers["X-Payment"] = payment_header
        return self._post(f"{self.agent_url}/v1/tasks", headers=headers, json={
            "prompt": prompt,
            "complexity": complexity,
        })

    def agent_get_task(self, task_id: int) -> X402Response:
        """Get task result."""
        return self._get(f"{self.agent_url}/v1/tasks/{task_id}")

    def agent_dashboard(self) -> X402Response:
        """Get profit dashboard."""
        return self._get(f"{self.agent_url}/dashboard")

    # ── Internal HTTP ──

    def _get(self, url: str) -> X402Response:
        try:
            r = requests.get(url, timeout=15)
            return self._parse(r)
        except Exception as e:
            return X402Response(ok=False, status_code=0, data=None, error=str(e))

    def _post(self, url: str, headers: dict, json: dict) -> X402Response:
        try:
            r = requests.post(url, headers=headers, json=json, timeout=60)
            return self._parse(r)
        except Exception as e:
            return X402Response(ok=False, status_code=0, data=None, error=str(e))

    def _parse(self, r: requests.Response) -> X402Response:
        if r.status_code == 402:
            body = r.json()
            pr = body.get("paymentRequired", {})
            return X402Response(
                ok=False,
                status_code=402,
                data=body,
                payment_required=PaymentRequirement(
                    version=pr.get("version", 2),
                    scheme=pr.get("scheme", ""),
                    network=pr.get("network", ""),
                    pay_to=pr.get("payTo", ""),
                    price=pr.get("price", ""),
                    amount_atomic=str(pr.get("amountAtomic", "")),
                    asset=pr.get("asset", ""),
                    asset_decimals=pr.get("assetDecimals", 6),
                    instructions=pr.get("instructions", []),
                ),
            )
        if r.status_code >= 400:
            return X402Response(ok=False, status_code=r.status_code, data=r.text[:500],
                                error=f"HTTP {r.status_code}")
        return X402Response(ok=True, status_code=r.status_code, data=r.json() if r.text else None)


# Singleton
x402_client = X402Client()
