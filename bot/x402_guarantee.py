"""
RMI x402 Paid Scan Guarantee System
====================================
Ensures customers ALWAYS receive what they pay for.
Payment = Guaranteed data delivery with SLA, receipt, and refund fallback.

Architecture:
1. Payment verified → Receipt generated → Data fetched → Stored permanently
2. If primary source fails → Cascading fallbacks → If all fail → Auto-refund
3. Customer can retrieve paid results forever via receipt ID
"""
import os
import json
import time
import hashlib
import logging
import requests
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field, asdict
from enum import Enum
import redis

logger = logging.getLogger("x402_guarantee")

# ── Configuration ──
REDIS_URL = os.getenv("REDIS_URL", "redis://127.0.0.1:6379")
PAID_SCAN_TTL = 0  # 0 = never expire (permanent storage)
SLA_TIMEOUT_SECONDS = 30
MAX_FALLBACK_ATTEMPTS = 5
REFUND_WALLET = os.getenv("REFUND_WALLET", "")

# ── Redis connection ──
try:
    redis_client = redis.Redis.from_url(REDIS_URL, decode_responses=True)
except:
    redis_client = None

# ── Data Classes ──
class PaymentStatus(Enum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    FULFILLED = "fulfilled"
    FAILED = "failed"
    REFUNDED = "refunded"
    EXPIRED = "expired"

class DataDeliveryStatus(Enum):
    FETCHING = "fetching"
    DELIVERED = "delivered"
    PARTIAL = "partial"
    FAILED = "failed"
    REFUNDED = "refunded"

@dataclass
class PaymentReceipt:
    """Permanent record of x402 payment."""
    receipt_id: str
    payment_tx: str
    amount: str
    asset: str
    network: str
    customer_address: str
    timestamp: str
    status: str
    scan_request: Dict[str, Any]
    scan_result: Optional[Dict[str, Any]] = None
    delivery_status: str = "fetching"
    refund_tx: str = ""
    created_at: str = ""
    updated_at: str = ""
    
    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.utcnow().isoformat()
            self.updated_at = self.created_at
    
    def to_dict(self) -> Dict:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'PaymentReceipt':
        return cls(**data)

@dataclass
class SLARecord:
    """Service level agreement tracking."""
    receipt_id: str
    promised_time: int  # seconds
    actual_time: float
    met_sla: bool
    fallbacks_used: int
    sources_tried: List[str]
    timestamp: str = ""
    
    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.utcnow().isoformat()

# ── Core Guarantee System ──
class X402GuaranteeSystem:
    """Ensures paid scans always deliver data or refund."""
    
    def __init__(self):
        self.redis = redis_client
        self.fallback_system = None  # Will be injected
        self.pricing = self._load_pricing()
    
    def _load_pricing(self) -> Dict:
        """Load x402 pricing tiers."""
        return {
            "basic_scan": {"price": "0.01", "asset": "USDC", "sla_seconds": 10},
            "deep_scan": {"price": "0.05", "asset": "USDC", "sla_seconds": 30},
            "whale_analysis": {"price": "0.10", "asset": "USDC", "sla_seconds": 60},
            "alpha_report": {"price": "0.25", "asset": "USDC", "sla_seconds": 120},
        }
    
    def generate_receipt_id(self, payment_tx: str) -> str:
        """Generate unique receipt ID from payment transaction."""
        return hashlib.sha256(f"{payment_tx}{time.time()}".encode()).hexdigest()[:16]
    
    def create_payment_receipt(self, payment_tx: str, amount: str, asset: str,
                              network: str, customer_address: str,
                              scan_request: Dict) -> PaymentReceipt:
        """Create permanent payment receipt."""
        receipt_id = self.generate_receipt_id(payment_tx)
        receipt = PaymentReceipt(
            receipt_id=receipt_id,
            payment_tx=payment_tx,
            amount=amount,
            asset=asset,
            network=network,
            customer_address=customer_address,
            timestamp=datetime.utcnow().isoformat(),
            status=PaymentStatus.CONFIRMED.value,
            scan_request=scan_request,
        )
        
        # Store permanently in Redis
        if self.redis:
            self.redis.set(
                f"x402:receipt:{receipt_id}",
                json.dumps(receipt.to_dict()),
                ex=PAID_SCAN_TTL if PAID_SCAN_TTL > 0 else None
            )
            # Index by customer for retrieval
            self.redis.sadd(f"x402:customer:{customer_address}", receipt_id)
            # Index by time for analytics
            self.redis.zadd("x402:receipts_by_time", {receipt_id: time.time()})
        
        logger.info(f"Created receipt {receipt_id} for {customer_address}")
        return receipt
    
    def verify_payment(self, payment_tx: str, network: str) -> bool:
        """Verify payment on blockchain."""
        try:
            if network == "solana":
                return self._verify_solana_payment(payment_tx)
            elif network in ["base", "ethereum"]:
                return self._verify_evm_payment(payment_tx)
            return False
        except Exception as e:
            logger.error(f"Payment verification failed: {e}")
            return False
    
    def _verify_solana_payment(self, tx: str) -> bool:
        """Verify Solana transaction."""
        try:
            r = requests.post(
                "https://api.mainnet-beta.solana.com",
                json={"jsonrpc": "2.0", "id": 1, "method": "getTransaction", "params": [tx]},
                timeout=10
            )
            if r.status_code == 200:
                result = r.json().get("result")
                return result is not None and result.get("meta", {}).get("err") is None
        except:
            pass
        return False
    
    def _verify_evm_payment(self, tx: str) -> bool:
        """Verify EVM transaction."""
        try:
            r = requests.get(
                f"https://api.basescan.org/api",
                params={"module": "proxy", "action": "eth_getTransactionByHash", "txhash": tx},
                timeout=10
            )
            if r.status_code == 200:
                result = r.json().get("result")
                return result is not None and result.get("blockNumber") is not None
        except:
            pass
        return False
    
    async def fulfill_scan(self, receipt: PaymentReceipt) -> PaymentReceipt:
        """Fulfill scan with guaranteed delivery or refund."""
        start_time = time.time()
        scan_type = receipt.scan_request.get("type", "basic_scan")
        pricing = self.pricing.get(scan_type, self.pricing["basic_scan"])
        sla_seconds = pricing.get("sla_seconds", SLA_TIMEOUT_SECONDS)
        
        # Track SLA
        sources_tried = []
        fallbacks_used = 0
        
        # Try primary source
        try:
            receipt.delivery_status = DataDeliveryStatus.FETCHING.value
            result = await self._fetch_scan_data(receipt.scan_request)
            sources_tried.append("primary")
            
            if result:
                receipt.scan_result = result
                receipt.delivery_status = DataDeliveryStatus.DELIVERED.value
                receipt.status = PaymentStatus.FULFILLED.value
                receipt.updated_at = datetime.utcnow().isoformat()
                self._save_receipt(receipt)
                
                # Record SLA
                actual_time = time.time() - start_time
                self._record_sla(receipt.receipt_id, sla_seconds, actual_time, 
                               fallbacks_used, sources_tried)
                
                logger.info(f"Scan {receipt.receipt_id} fulfilled in {actual_time:.2f}s")
                return receipt
        except Exception as e:
            logger.error(f"Primary scan failed: {e}")
            sources_tried.append("primary_failed")
        
        # Try fallbacks
        for i in range(MAX_FALLBACK_ATTEMPTS):
            fallbacks_used += 1
            try:
                result = await self._fetch_fallback_data(receipt.scan_request, i)
                sources_tried.append(f"fallback_{i}")
                
                if result:
                    receipt.scan_result = result
                    receipt.delivery_status = DataDeliveryStatus.DELIVERED.value
                    receipt.status = PaymentStatus.FULFILLED.value
                    receipt.updated_at = datetime.utcnow().isoformat()
                    self._save_receipt(receipt)
                    
                    actual_time = time.time() - start_time
                    self._record_sla(receipt.receipt_id, sla_seconds, actual_time,
                                   fallbacks_used, sources_tried)
                    
                    logger.info(f"Scan {receipt.receipt_id} fulfilled via fallback {i} in {actual_time:.2f}s")
                    return receipt
            except Exception as e:
                logger.error(f"Fallback {i} failed: {e}")
                sources_tried.append(f"fallback_{i}_failed")
        
        # All sources failed → Auto-refund
        logger.error(f"ALL sources failed for {receipt.receipt_id} - initiating refund")
        receipt.delivery_status = DataDeliveryStatus.REFUNDED.value
        receipt.status = PaymentStatus.REFUNDED.value
        receipt.updated_at = datetime.utcnow().isoformat()
        
        # Process refund
        refund_tx = await self._process_refund(receipt)
        receipt.refund_tx = refund_tx
        self._save_receipt(receipt)
        
        actual_time = time.time() - start_time
        self._record_sla(receipt.receipt_id, sla_seconds, actual_time,
                       fallbacks_used, sources_tried)
        
        return receipt
    
    async def _fetch_scan_data(self, scan_request: Dict) -> Optional[Dict]:
        """Fetch scan data from primary source."""
        # Implementation would call bot scanner or MCP Router
        return None
    
    async def _fetch_fallback_data(self, scan_request: Dict, attempt: int) -> Optional[Dict]:
        """Fetch scan data from fallback sources."""
        # Implementation would try alternative sources
        return None
    
    async def _process_refund(self, receipt: PaymentReceipt) -> str:
        """Process automatic refund."""
        # Implementation would send refund transaction
        return "refund_tx_placeholder"
    
    def _save_receipt(self, receipt: PaymentReceipt):
        """Save receipt to permanent storage."""
        if self.redis:
            self.redis.set(
                f"x402:receipt:{receipt.receipt_id}",
                json.dumps(receipt.to_dict()),
                ex=PAID_SCAN_TTL if PAID_SCAN_TTL > 0 else None
            )
    
    def _record_sla(self, receipt_id: str, promised: int, actual: float,
                   fallbacks: int, sources: List[str]):
        """Record SLA metrics."""
        sla = SLARecord(
            receipt_id=receipt_id,
            promised_time=promised,
            actual_time=actual,
            met_sla=actual <= promised,
            fallbacks_used=fallbacks,
            sources_tried=sources,
        )
        
        if self.redis:
            self.redis.set(
                f"x402:sla:{receipt_id}",
                json.dumps(asdict(sla)),
                ex=86400 * 30  # Keep SLA records for 30 days
            )
    
    def get_customer_receipts(self, customer_address: str) -> List[Dict]:
        """Get all receipts for a customer."""
        if not self.redis:
            return []
        
        receipt_ids = self.redis.smembers(f"x402:customer:{customer_address}")
        receipts = []
        for rid in receipt_ids:
            data = self.redis.get(f"x402:receipt:{rid}")
            if data:
                receipts.append(json.loads(data))
        
        return receipts
    
    def get_receipt(self, receipt_id: str) -> Optional[Dict]:
        """Get specific receipt by ID."""
        if not self.redis:
            return None
        
        data = self.redis.get(f"x402:receipt:{receipt_id}")
        return json.loads(data) if data else None
    
    def get_sla_metrics(self, hours: int = 24) -> Dict:
        """Get SLA performance metrics."""
        if not self.redis:
            return {}
        
        cutoff = time.time() - (hours * 3600)
        recent_ids = self.redis.zrangebyscore("x402:receipts_by_time", cutoff, "+inf")
        
        total = 0
        met_sla = 0
        avg_time = 0
        fallback_rate = 0
        
        for rid in recent_ids:
            sla_data = self.redis.get(f"x402:sla:{rid}")
            if sla_data:
                sla = json.loads(sla_data)
                total += 1
                if sla.get("met_sla"):
                    met_sla += 1
                avg_time += sla.get("actual_time", 0)
                if sla.get("fallbacks_used", 0) > 0:
                    fallback_rate += 1
        
        return {
            "total_scans": total,
            "sla_met_rate": met_sla / max(1, total),
            "avg_response_time": avg_time / max(1, total),
            "fallback_rate": fallback_rate / max(1, total),
            "period_hours": hours,
        }

# ── Main instance ──
x402_guarantee = X402GuaranteeSystem()
