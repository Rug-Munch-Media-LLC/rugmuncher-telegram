"""
Crosspost Hub API
FastAPI backend for crossposting + x402 gateway integration.
"""
import os
import json
import logging
from contextlib import asynccontextmanager
from typing import List, Optional

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from bot.x402_integrations.client import x402_client, X402Response
from bot.x402_integrations.crosspost_manager import crosspost_manager, CrosspostResult

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("crosspost_api")


# ── Models ──

class CrosspostRequest(BaseModel):
    text: str
    platforms: List[str] = ["twitter", "telegram"]
    gateway: str = "solana"  # base | solana | agent
    payment_header: Optional[str] = None
    telegram_chat_id: Optional[str] = None
    discord_webhook: Optional[str] = None


class GatewayStatus(BaseModel):
    name: str
    url: str
    healthy: bool
    latency_ms: float
    details: dict


# ── Lifecycle ──

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("🚀 Crosspost Hub started")
    yield
    logger.info("Crosspost Hub shutting down")


app = FastAPI(
    title="Rug Muncher Crosspost Hub",
    description="Crosspost to X, Telegram, Discord with x402 monetization",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Health & Status ──

@app.get("/health")
async def health():
    return {"status": "ok", "service": "crosspost-hub"}


@app.get("/gateways/status")
async def gateways_status():
    """Check all 3 x402 gateways."""
    import time
    results = []

    for name, url, check_fn in [
        ("Base x402 Gateway", x402_client.base_url, x402_client.base_models),
        ("Solana x402 Gateway", x402_client.solana_url, x402_client.solana_models),
        ("Solana Profit Agent", x402_client.agent_url, x402_client.agent_dashboard),
    ]:
        start = time.time()
        try:
            resp = check_fn()
            latency = (time.time() - start) * 1000
            results.append({
                "name": name,
                "url": url,
                "healthy": resp.ok or resp.status_code == 402,
                "latency_ms": round(latency, 1),
                "details": resp.data if resp.ok else {"error": resp.error},
            })
        except Exception as e:
            results.append({
                "name": name,
                "url": url,
                "healthy": False,
                "latency_ms": round((time.time() - start) * 1000, 1),
                "details": {"error": str(e)},
            })

    return {"gateways": results, "timestamp": time.time()}


# ── Crosspost Endpoints ──

@app.post("/crosspost")
async def crosspost(req: CrosspostRequest):
    """Crosspost to selected platforms. Requires payment header for monetized posts."""
    if not req.text or len(req.text) > 2000:
        raise HTTPException(400, "Text required, max 2000 chars")

    # If no payment header, return 402 requirements from chosen gateway
    if not req.payment_header:
        if req.gateway == "base":
            resp = x402_client.base_chat("deepseek-v3.2", [{"role": "user", "content": req.text}])
        elif req.gateway == "solana":
            resp = x402_client.solana_chat([{"role": "user", "content": req.text}])
        else:
            resp = x402_client.agent_submit_task(req.text)

        if resp.status_code == 402 and resp.payment_required:
            pr = resp.payment_required
            return JSONResponse(
                status_code=402,
                content={
                    "error": "Payment required",
                    "type": "payment_required",
                    "code": "402",
                    "paymentRequired": {
                        "version": pr.version,
                        "scheme": pr.scheme,
                        "network": pr.network,
                        "payTo": pr.pay_to,
                        "price": pr.price,
                        "amountAtomic": pr.amount_atomic,
                        "asset": pr.asset,
                        "assetDecimals": pr.asset_decimals,
                        "instructions": pr.instructions,
                    },
                    "gateway": req.gateway,
                },
                headers={"X-Payment-Required": "true"},
            )
        # Gateway didn't 402 — still require payment for crossposting
        return JSONResponse(
            status_code=402,
            content={
                "error": "Payment required",
                "type": "payment_required",
                "code": "402",
                "message": f"Pay via {req.gateway} gateway to unlock crossposting",
                "gateway": req.gateway,
            },
        )

    # Payment provided — execute crosspost
    results = crosspost_manager.crosspost(
        text=req.text,
        platforms=req.platforms,
        telegram_chat_id=req.telegram_chat_id,
        discord_webhook=req.discord_webhook,
    )

    return {
        "status": "posted",
        "gateway": req.gateway,
        "platforms": req.platforms,
        "results": {
            k: {
                "success": v.success,
                "post_id": v.post_id,
                "url": v.url,
                "error": v.error,
                "timestamp": v.timestamp,
            }
            for k, v in results.items()
        },
    }


@app.get("/gateways/pricing")
async def gateways_pricing():
    """Get pricing from all gateways."""
    pricing = {}

    base = x402_client.base_models()
    if base.ok and base.data:
        pricing["base"] = {
            "models": [
                {"id": m.get("id"), "price": m.get("price_per_request_usd")}
                for m in base.data.get("data", [])
            ]
        }

    sol = x402_client.solana_models()
    if sol.ok and sol.data:
        pricing["solana"] = {
            "models": [
                {"id": m.get("id"), "price": m.get("price_per_request_usd")}
                for m in sol.data.get("data", [])
            ]
        }

    agent = x402_client.agent_pricing()
    if agent.ok and agent.data:
        pricing["agent"] = agent.data

    return pricing


# ── Run ──

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("CROSSPOST_PORT", "8010"))
    uvicorn.run("bot.x402_integrations.api:app", host="0.0.0.0", port=port, reload=False)
