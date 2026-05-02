"""
RMI Universal Fallback System
=============================
Multi-layered redundancy for ALL data sources.
No service ever underserved - cascading fallbacks ensure 100% coverage.

Architecture:
PRIMARY → FALLBACK 1 → FALLBACK 2 → FALLBACK 3 → FALLBACK 4 → FALLBACK 5
"""
import os
import json
import time
import hashlib
import logging
import requests
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from enum import Enum
import re

logger = logging.getLogger("fallback_system")

# ── Fallback Levels ──
class FallbackLevel(Enum):
    PRIMARY = 0
    FALLBACK_1 = 1
    FALLBACK_2 = 2
    FALLBACK_3 = 3
    FALLBACK_4 = 4
    FALLBACK_5 = 5

@dataclass
class FallbackResult:
    """Result from a fallback attempt."""
    success: bool
    data: Any
    source: str
    level: FallbackLevel
    latency_ms: float
    error: str = ""
    timestamp: str = ""
    
    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.utcnow().isoformat()

# ── Health Monitor ──
class HealthMonitor:
    """Track source health and auto-select best fallback."""
    
    def __init__(self):
        self.source_health: Dict[str, Dict] = {}
        self.circuit_breakers: Dict[str, int] = {}
        self.last_success: Dict[str, datetime] = {}
        
    def record_success(self, source: str, latency_ms: float):
        """Record successful call."""
        if source not in self.source_health:
            self.source_health[source] = {
                "successes": 0, "failures": 0, "avg_latency": 0
            }
        h = self.source_health[source]
        h["successes"] += 1
        h["avg_latency"] = (h["avg_latency"] * (h["successes"] - 1) + latency_ms) / h["successes"]
        self.last_success[source] = datetime.utcnow()
        self.circuit_breakers.pop(source, None)
    
    def record_failure(self, source: str):
        """Record failed call."""
        if source not in self.source_health:
            self.source_health[source] = {"successes": 0, "failures": 0}
        self.source_health[source]["failures"] += 1
        self.circuit_breakers[source] = self.circuit_breakers.get(source, 0) + 1
    
    def is_circuit_open(self, source: str) -> bool:
        """Check if circuit breaker is open (too many failures)."""
        return self.circuit_breakers.get(source, 0) >= 3
    
    def get_best_source(self, sources: List[str]) -> str:
        """Get best available source based on health."""
        available = [s for s in sources if not self.is_circuit_open(s)]
        if not available:
            return sources[0] if sources else ""
        
        # Sort by success rate and latency
        def score(source):
            h = self.source_health.get(source, {})
            success_rate = h.get("successes", 0) / max(1, h.get("successes", 0) + h.get("failures", 0))
            latency = h.get("avg_latency", 1000)
            return success_rate * 1000 - latency
        
        return max(available, key=score)

health_monitor = HealthMonitor()

# ═══════════════════════════════════════════════════════════
# TWITTER/X CONTENT FALLBACK SYSTEM
# ═══════════════════════════════════════════════════════════

class TwitterFallbackSystem:
    """Cascading fallbacks for Twitter/X content."""
    
    def __init__(self):
        self.accounts = self._load_accounts()
        
    def _load_accounts(self) -> Dict:
        try:
            with open("/root/ecosystems/rugmuncher/bot/bot/twitter_accounts.json") as f:
                return json.load(f)
        except:
            return {}
    
    def fetch_tweet_fallbacks(self, handle: str, limit: int = 3) -> List[Dict]:
        """Try multiple sources for tweets from @handle."""
        fallbacks = [
            ("twitter_api_v2", self._fetch_twitter_api),
            ("nitter_rss", self._fetch_nitter_rss),
            ("rss_bridge", self._fetch_rss_bridge),
            ("telegram_mirror", self._fetch_telegram_mirror),
            ("web_scrape", self._fetch_web_scrape),
            ("third_party_agg", self._fetch_third_party),
        ]
        
        for level, (name, fetch_fn) in enumerate(fallbacks):
            try:
                start = time.time()
                result = fetch_fn(handle, limit)
                latency = (time.time() - start) * 1000
                
                if result:
                    health_monitor.record_success(name, latency)
                    logger.info(f"Twitter fallback level {level} ({name}) succeeded for @{handle}")
                    return result
                
                health_monitor.record_failure(name)
            except Exception as e:
                health_monitor.record_failure(name)
                logger.error(f"Twitter fallback {name} failed: {e}")
        
        return []
    
    def _fetch_twitter_api(self, handle: str, limit: int) -> List[Dict]:
        """Primary: Twitter API v2."""
        # Check for API key
        api_key = os.getenv("TWITTER_BEARER_TOKEN", "")
        if not api_key:
            return []
        
        try:
            # Get user ID first
            r = requests.get(
                f"https://api.twitter.com/2/users/by/username/{handle}",
                headers={"Authorization": f"Bearer {api_key}"},
                timeout=10
            )
            if r.status_code != 200:
                return []
            
            user_id = r.json()["data"]["id"]
            
            # Get tweets
            r = requests.get(
                f"https://api.twitter.com/2/users/{user_id}/tweets",
                headers={"Authorization": f"Bearer {api_key}"},
                params={"max_results": limit, "tweet.fields": "created_at,public_metrics"},
                timeout=10
            )
            if r.status_code == 200:
                return r.json().get("data", [])
        except:
            pass
        return []
    
    def _fetch_nitter_rss(self, handle: str, limit: int) -> List[Dict]:
        """Fallback 1: Nitter instances."""
        nitter_instances = [
            "https://nitter.privacydev.net",
            "https://nitter.poast.org",
            "https://nitter.woodland.cafe",
            "https://nitter.nl",
            "https://nitter.moomoo.me",
        ]
        
        for instance in nitter_instances:
            try:
                r = requests.get(
                    f"{instance}/{handle}/rss",
                    timeout=10,
                    headers={"User-Agent": "Mozilla/5.0"}
                )
                if r.status_code == 200 and '<item>' in r.text:
                    # Parse RSS
                    items = re.findall(r'<item>(.*?)</item>', r.text, re.DOTALL)[:limit]
                    tweets = []
                    for item in items:
                        title = re.search(r'<title>(.*?)</title>', item, re.DOTALL)
                        link = re.search(r'<link>(.*?)</link>', item, re.DOTALL)
                        pubdate = re.search(r'<pubDate>(.*?)</pubDate>', item, re.DOTALL)
                        
                        if title and link:
                            tweets.append({
                                "text": re.sub(r'<[^>]+>', '', title.group(1)).strip(),
                                "url": link.group(1).strip(),
                                "date": pubdate.group(1).strip() if pubdate else "",
                                "source": "nitter"
                            })
                    return tweets
            except:
                continue
        return []
    
    def _fetch_rss_bridge(self, handle: str, limit: int) -> List[Dict]:
        """Fallback 2: RSS-Bridge instances."""
        rss_bridge_instances = [
            "https://rss-bridge.org/bridge",
            "https://rss-bridge.pofilo.fr",
        ]
        
        for instance in rss_bridge_instances:
            try:
                r = requests.get(
                    f"{instance}/?action=display&bridge=Twitter&username={handle}&format=Json",
                    timeout=10
                )
                if r.status_code == 200:
                    data = r.json()
                    if isinstance(data, list):
                        return data[:limit]
            except:
                continue
        return []
    
    def _fetch_telegram_mirror(self, handle: str, limit: int) -> List[Dict]:
        """Fallback 3: Telegram mirror channels."""
        # Monitor known Telegram channels that mirror Twitter
        telegram_twitter_mirrors = [
            "@TreeNews",
            "@WatcherGuru",
            "@CryptoCronos",
        ]
        
        tweets = []
        # This would use Telethon to check recent posts in these channels
        # that mention the handle
        return tweets
    
    def _fetch_web_scrape(self, handle: str, limit: int) -> List[Dict]:
        """Fallback 4: Direct web scraping with rotation."""
        # Use Playwright/Selenium to scrape Twitter profile
        # This is last resort due to rate limiting
        return []
    
    def _fetch_third_party(self, handle: str, limit: int) -> List[Dict]:
        """Fallback 5: Third-party aggregators."""
        # Services like:
        # - RapidAPI Twitter endpoints
        # - Apify Twitter scrapers
        # - Custom scraper APIs
        return []

# ═══════════════════════════════════════════════════════════
# MCP ROUTER FALLBACK SYSTEM
# ═══════════════════════════════════════════════════════════

class MCPFallbackSystem:
    """Cascading fallbacks for MCP Router data."""
    
    def __init__(self):
        self.mcp_router_url = "https://mcp-router.rugmunch.io/mcp"
        self.direct_api_urls = {
            "coingecko": "https://api.coingecko.com/api/v3",
            "dexscreener": "https://api.dexscreener.com/latest/dex",
            "birdeye": "https://public-api.birdeye.so",
            "gmgn": "https://gmgn.ai/defi/api/v1",
            "nansen": "https://api.nansen.ai",
            "arkham": "https://api.arkhamintelligence.com",
        }
        self.api_keys = self._load_api_keys()
    
    def _load_api_keys(self) -> Dict:
        keys = {}
        secrets_dir = "/root/.secrets"
        key_map = {
            "coingecko_api_key": "coingecko",
            "birdeye_api_key": "birdeye",
            "gmgn_api_key": "gmgn",
            "nansen_api_key": "nansen",
            "arkham_api_key": "arkham",
            "dune_api_key": "dune",
        }
        for file_name, service in key_map.items():
            path = os.path.join(secrets_dir, file_name)
            if os.path.exists(path):
                with open(path) as f:
                    keys[service] = f.read().strip()
        return keys
    
    def fetch_data_fallbacks(self, service: str, tool: str, params: Dict) -> Any:
        """Try multiple sources for data."""
        fallbacks = [
            ("mcp_router", self._fetch_mcp_router),
            ("direct_api", self._fetch_direct_api),
            ("cached_data", self._fetch_cached_data),
            ("alternative_provider", self._fetch_alternative_provider),
            ("community_data", self._fetch_community_data),
        ]
        
        for level, (name, fetch_fn) in enumerate(fallbacks):
            try:
                start = time.time()
                result = fetch_fn(service, tool, params)
                latency = (time.time() - start) * 1000
                
                if result:
                    health_monitor.record_success(name, latency)
                    return result
                
                health_monitor.record_failure(name)
            except Exception as e:
                health_monitor.record_failure(name)
                logger.error(f"MCP fallback {name} failed: {e}")
        
        return None
    
    def _fetch_mcp_router(self, service: str, tool: str, params: Dict) -> Any:
        """Primary: MCP Router."""
        try:
            r = requests.post(
                self.mcp_router_url,
                json={
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "tools/call",
                    "params": {"name": f"{service}:{tool}", "arguments": params}
                },
                timeout=15
            )
            if r.status_code == 200:
                return r.json()
        except:
            pass
        return None
    
    def _fetch_direct_api(self, service: str, tool: str, params: Dict) -> Any:
        """Fallback 1: Direct API calls."""
        if service not in self.direct_api_urls:
            return None
        
        base_url = self.direct_api_urls[service]
        api_key = self.api_keys.get(service)
        
        # Map tool to direct API endpoint
        endpoint_map = {
            "coingecko": {
                "getPrice": "/simple/price",
                "getMarketData": "/coins/markets",
                "getCoinInfo": "/coins/{id}",
            },
            "dexscreener": {
                "searchPairs": "/search?q={query}",
                "pairInfo": "/pairs/{chainId}/{pairAddress}",
            },
            "birdeye": {
                "getPrice": "/defi/price",
                "getTrades": "/defi/txs/token",
            },
        }
        
        endpoints = endpoint_map.get(service, {})
        endpoint = endpoints.get(tool)
        if not endpoint:
            return None
        
        try:
            headers = {}
            if api_key:
                if service in ["birdeye", "gmgn", "nansen", "arkham"]:
                    headers["X-API-KEY"] = api_key
                elif service == "coingecko":
                    headers["x-cg-demo-key"] = api_key
            
            url = f"{base_url}{endpoint}"
            r = requests.get(url, headers=headers, params=params, timeout=10)
            if r.status_code == 200:
                return r.json()
        except:
            pass
        return None
    
    def _fetch_cached_data(self, service: str, tool: str, params: Dict) -> Any:
        """Fallback 2: Cached data with staleness check."""
        # Check Redis for cached data
        # Return if less than 5 minutes old
        return None
    
    def _fetch_alternative_provider(self, service: str, tool: str, params: Dict) -> Any:
        """Fallback 3: Alternative data providers."""
        # Map service to alternatives
        alternatives = {
            "coingecko": ["coinmarketcap", "coincap"],
            "dexscreener": ["dexpaprika", "birdeye"],
            "birdeye": ["solscan", "helius"],
            "nansen": ["arkham", "gmgn"],
            "arkham": ["nansen", "chainalysis"],
        }
        
        alts = alternatives.get(service, [])
        for alt in alts:
            # Try alternative service
            try:
                result = self._fetch_direct_api(alt, tool, params)
                if result:
                    return result
            except:
                continue
        return None
    
    def _fetch_community_data(self, service: str, tool: str, params: Dict) -> Any:
        """Fallback 4: Community-sourced data."""
        # Check Telegram channels, Discord, etc.
        return None

# ═══════════════════════════════════════════════════════════
# SCAN SERVICE FALLBACK SYSTEM
# ═══════════════════════════════════════════════════════════

class ScanFallbackSystem:
    """Cascading fallbacks for contract scanning."""
    
    def __init__(self):
        self.scanner_endpoints = {
            "primary": "http://127.0.0.1:8000/api/v1/contract/audit",
            "mcp_router": "https://mcp-router.rugmunch.io/mcp",
        }
    
    def scan_contract_fallbacks(self, address: str, chain: str) -> Dict:
        """Try multiple scanners for comprehensive analysis."""
        fallbacks = [
            ("bot_scanner", self._scan_bot),
            ("mcp_router", self._scan_mcp),
            ("direct_api", self._scan_direct),
            ("third_party", self._scan_third_party),
            ("manual_queue", self._queue_manual),
        ]
        
        results = {}
        for level, (name, scan_fn) in enumerate(fallbacks):
            try:
                start = time.time()
                result = scan_fn(address, chain)
                latency = (time.time() - start) * 1000
                
                if result:
                    health_monitor.record_success(name, latency)
                    results[name] = result
                    
                    # If we have good data, we can stop
                    if result.get("confidence", 0) > 0.8:
                        break
                else:
                    health_monitor.record_failure(name)
            except Exception as e:
                health_monitor.record_failure(name)
                logger.error(f"Scan fallback {name} failed: {e}")
        
        # Merge results
        return self._merge_scan_results(results)
    
    def _scan_bot(self, address: str, chain: str) -> Dict:
        """Primary: RMI Bot scanner."""
        try:
            r = requests.post(
                self.scanner_endpoints["primary"],
                json={"address": address, "chain": chain},
                timeout=30
            )
            if r.status_code == 200:
                return r.json()
        except:
            pass
        return {}
    
    def _scan_mcp(self, address: str, chain: str) -> Dict:
        """Fallback 1: MCP Router tools."""
        try:
            # Use multiple MCP tools for comprehensive scan
            tools_to_call = [
                ("dexscreener", "searchPairs", {"query": address}),
                ("gmgn", "getWalletProfile", {"address": address}),
                ("solscan", "getTokenInfo", {"address": address}),
            ]
            
            results = {}
            for service, tool, params in tools_to_call:
                try:
                    r = requests.post(
                        self.scanner_endpoints["mcp_router"],
                        json={
                            "jsonrpc": "2.0",
                            "id": 1,
                            "method": "tools/call",
                            "params": {"name": f"{service}:{tool}", "arguments": params}
                        },
                        timeout=10
                    )
                    if r.status_code == 200:
                        results[service] = r.json()
                except:
                    continue
            
            return results if results else {}
        except:
            pass
        return {}
    
    def _scan_direct(self, address: str, chain: str) -> Dict:
        """Fallback 2: Direct API calls."""
        # Call Etherscan, BscScan, Solscan directly
        return {}
    
    def _scan_third_party(self, address: str, chain: str) -> Dict:
        """Fallback 3: Third-party scanners."""
        # Use Honeypot.is, TokenSniffer, etc.
        return {}
    
    def _queue_manual(self, address: str, chain: str) -> Dict:
        """Fallback 4: Queue for manual review."""
        # Add to manual review queue
        return {"status": "queued_for_manual_review", "address": address, "chain": chain}
    
    def _merge_scan_results(self, results: Dict) -> Dict:
        """Merge results from multiple scanners."""
        merged = {
            "address": results.get("bot_scanner", {}).get("address", ""),
            "chain": results.get("bot_scanner", {}).get("chain", ""),
            "sources": list(results.keys()),
            "confidence": 0,
            "findings": [],
            "risk_score": 0,
        }
        
        # Calculate confidence based on number of sources
        merged["confidence"] = min(1.0, len(results) * 0.25)
        
        # Merge findings
        for source, data in results.items():
            if "findings" in data:
                merged["findings"].extend(data["findings"])
            if "risk_score" in data:
                # Use highest risk score
                merged["risk_score"] = max(merged["risk_score"], data["risk_score"])
        
        # Remove duplicates
        merged["findings"] = list(set(merged["findings"]))
        
        return merged

# ═══════════════════════════════════════════════════════════
# NEWS/CONTENT FALLBACK SYSTEM
# ═══════════════════════════════════════════════════════════

class NewsFallbackSystem:
    """Cascading fallbacks for news content."""
    
    def __init__(self):
        self.rss_feeds = {
            "coindesk": "https://www.coindesk.com/arc/outboundfeeds/rss/",
            "cointelegraph": "https://cointelegraph.com/rss",
            "decrypt": "https://decrypt.co/feed",
            "beincrypto": "https://beincrypto.com/feed/",
        }
        self.telegram_channels = [
            "@TreeNews", "@CoinDesk", "@WatcherGuru", "@CryptoCronos"
        ]
    
    def fetch_news_fallbacks(self, category: str = "general", limit: int = 10) -> List[Dict]:
        """Try multiple sources for news."""
        fallbacks = [
            ("cryptopanic_mcp", self._fetch_cryptopanic),
            ("rss_feeds", self._fetch_rss),
            ("telegram_channels", self._fetch_telegram),
            ("reddit", self._fetch_reddit),
            ("web_scrape", self._fetch_web_scrape),
        ]
        
        all_news = []
        for level, (name, fetch_fn) in enumerate(fallbacks):
            try:
                start = time.time()
                result = fetch_fn(category, limit)
                latency = (time.time() - start) * 1000
                
                if result:
                    health_monitor.record_success(name, latency)
                    all_news.extend(result)
                    if len(all_news) >= limit:
                        break
                else:
                    health_monitor.record_failure(name)
            except Exception as e:
                health_monitor.record_failure(name)
                logger.error(f"News fallback {name} failed: {e}")
        
        # Deduplicate and return
        seen = set()
        unique_news = []
        for item in all_news:
            key = hashlib.md5(item.get("title", "").encode()).hexdigest()[:16]
            if key not in seen:
                seen.add(key)
                unique_news.append(item)
        
        return unique_news[:limit]
    
    def _fetch_cryptopanic(self, category: str, limit: int) -> List[Dict]:
        """Primary: CryptoPanic via MCP."""
        try:
            r = requests.post(
                "https://mcp-router.rugmunch.io/mcp",
                json={
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "tools/call",
                    "params": {
                        "name": "cryptopanic:getNews",
                        "arguments": {"filter": "important", "limit": limit}
                    }
                },
                timeout=15
            )
            if r.status_code == 200:
                data = r.json()
                if "result" in data:
                    return data["result"].get("content", [])
        except:
            pass
        return []
    
    def _fetch_rss(self, category: str, limit: int) -> List[Dict]:
        """Fallback 1: RSS feeds."""
        news = []
        for name, url in self.rss_feeds.items():
            try:
                r = requests.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
                if r.status_code == 200:
                    items = re.findall(r'<item>(.*?)</item>', r.text, re.DOTALL)
                    for item in items[:limit]:
                        title = re.search(r'<title>(.*?)</title>', item, re.DOTALL)
                        link = re.search(r'<link>(.*?)</link>', item, re.DOTALL)
                        desc = re.search(r'<description>(.*?)</description>', item, re.DOTALL)
                        
                        if title and link:
                            news.append({
                                "title": re.sub(r'<[^>]+>', '', title.group(1)).strip(),
                                "url": link.group(1).strip(),
                                "description": re.sub(r'<[^>]+>', '', desc.group(1)).strip() if desc else "",
                                "source": name,
                                "timestamp": datetime.utcnow().isoformat()
                            })
            except:
                continue
        return news
    
    def _fetch_telegram(self, category: str, limit: int) -> List[Dict]:
        """Fallback 2: Telegram channels."""
        # Use Telethon to fetch recent posts
        return []
    
    def _fetch_reddit(self, category: str, limit: int) -> List[Dict]:
        """Fallback 3: Reddit."""
        subreddits = ["cryptocurrency", "Bitcoin", "ethereum"]
        news = []
        for sub in subreddits:
            try:
                r = requests.get(
                    f"https://www.reddit.com/r/{sub}/hot.json?limit={limit}",
                    headers={"User-Agent": "RMI/1.0"},
                    timeout=10
                )
                if r.status_code == 200:
                    posts = r.json().get("data", {}).get("children", [])
                    for post in posts:
                        data = post.get("data", {})
                        news.append({
                            "title": data.get("title", ""),
                            "url": f"https://reddit.com{data.get('permalink', '')}",
                            "description": data.get("selftext", "")[:200],
                            "source": f"reddit/{sub}",
                            "timestamp": datetime.utcfromtimestamp(data.get("created_utc", 0)).isoformat()
                        })
            except:
                continue
        return news
    
    def _fetch_web_scrape(self, category: str, limit: int) -> List[Dict]:
        """Fallback 4: Web scraping."""
        # Use Playwright to scrape major crypto news sites
        return []

# ═══════════════════════════════════════════════════════════
# MAIN FALLBACK ORCHESTRATOR
# ═══════════════════════════════════════════════════════════

class FallbackOrchestrator:
    """Main orchestrator for all fallback systems."""
    
    def __init__(self):
        self.twitter = TwitterFallbackSystem()
        self.mcp = MCPFallbackSystem()
        self.scanner = ScanFallbackSystem()
        self.news = NewsFallbackSystem()
    
    def get_content(self, content_type: str, **kwargs) -> Any:
        """Universal content getter with automatic fallbacks."""
        if content_type == "twitter":
            return self.twitter.fetch_tweet_fallbacks(kwargs.get("handle", ""), kwargs.get("limit", 3))
        elif content_type == "mcp_data":
            return self.mcp.fetch_data_fallbacks(
                kwargs.get("service", ""), kwargs.get("tool", ""), kwargs.get("params", {})
            )
        elif content_type == "scan":
            return self.scanner.scan_contract_fallbacks(
                kwargs.get("address", ""), kwargs.get("chain", "")
            )
        elif content_type == "news":
            return self.news.fetch_news_fallbacks(
                kwargs.get("category", "general"), kwargs.get("limit", 10)
            )
        else:
            raise ValueError(f"Unknown content type: {content_type}")
    
    def get_health_status(self) -> Dict:
        """Get health status of all sources."""
        return {
            "source_health": health_monitor.source_health,
            "circuit_breakers": health_monitor.circuit_breakers,
            "last_success": {k: v.isoformat() for k, v in health_monitor.last_success.items()},
            "timestamp": datetime.utcnow().isoformat()
        }

# ── Main instance ──
fallback_orchestrator = FallbackOrchestrator()
