"""
Rug Muncher — API Sourcer
=========================
Pulls real blockchain data from multiple sources for accurate scans.

Sources:
  • Alchemy — EVM balances, transactions, token data
  • Etherscan/BscScan — Contract source, ABI, verification
  • Helius — Solana data, DAS API
  • Birdeye — Token prices, DEX liquidity, market data
  • DefiLlama — TVL, protocol data
  • Honeypot.is — Honeypot detection
  • Moralis — Wallet analytics, NFTs

All keys loaded from environment. Graceful degradation if a source fails.
"""

import os
import asyncio
import aiohttp
import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass

logger = logging.getLogger("api_sourcer")

# ── API Keys ──
ALCHEMY_KEY = os.getenv("ALCHEMY_API_KEY", "")
ETHERSCAN_KEY = os.getenv("ETHERSCAN_KEY", "")
BSCSCAN_KEY = os.getenv("BSCSCAN_KEY", "")
HELIUS_KEY = os.getenv("HELIUS_KEY", "")
# ── API Keys (all optional — bot degrades gracefully) ──
ALCHEMY_KEY = os.getenv("ALCHEMY_API_KEY", "")
ETHERSCAN_KEY = os.getenv("ETHERSCAN_KEY", "")
BSCSCAN_KEY = os.getenv("BSCSCAN_KEY", "")
HELIUS_KEY = os.getenv("HELIUS_KEY", "")
BIRDEYE_KEY = os.getenv("BIRDEYE_KEY", "")
MORALIS_KEY = os.getenv("MORALIS_KEY", "")
SOLSCAN_KEY = os.getenv("SOLSCAN_KEY", "")
COINGECKO_KEY = os.getenv("COINGECKO_KEY", "")
QUICKNODE_SOL = os.getenv("QUICKNODE_SOL", "")
QUICKNODE_ETH = os.getenv("QUICKNODE_ETH", "")
ARKHAM_KEY = os.getenv("ARKHAM_KEY", "")
CHAINBASE_KEY = os.getenv("CHAINBASE_KEY", "")
COVALENT_KEY = os.getenv("COVALENT_KEY", "")

# ── Free Public RPCs (no key required) ──
FREE_RPCS = {
    "ethereum": ["https://eth.llamarpc.com", "https://rpc.ankr.com/eth", "https://ethereum.publicnode.com"],
    "bsc": ["https://bsc-dataseed.binance.org", "https://rpc.ankr.com/bsc", "https://bsc.publicnode.com"],
    "polygon": ["https://polygon.llamarpc.com", "https://rpc.ankr.com/polygon", "https://polygon.publicnode.com"],
    "arbitrum": ["https://arb1.arbitrum.io/rpc", "https://rpc.ankr.com/arbitrum"],
    "base": ["https://base.llamarpc.com", "https://rpc.ankr.com/base", "https://base.publicnode.com"],
    "avalanche": ["https://avalanche.publicnode.com", "https://rpc.ankr.com/avalanche"],
    "optimism": ["https://optimism.publicnode.com", "https://rpc.ankr.com/optimism"],
    "solana": ["https://api.mainnet-beta.solana.com", "https://solana.publicnode.com"],
    "fantom": ["https://rpc.ankr.com/fantom", "https://fantom.publicnode.com"],
}

# ── Free Explorers (no key required, rate limited) ──
EXPLORER_APIS = {
    "ethereum": {"base": "https://api.etherscan.io/api", "key": ETHERSCAN_KEY},
    "bsc": {"base": "https://api.bscscan.com/api", "key": BSCSCAN_KEY},
    "polygon": {"base": "https://api.polygonscan.com/api", "key": os.getenv("POLYGONSCAN_KEY", "")},
    "arbitrum": {"base": "https://api.arbiscan.io/api", "key": os.getenv("ARBISCAN_KEY", "")},
    "base": {"base": "https://api.basescan.org/api", "key": os.getenv("BASESCAN_KEY", "")},
    "optimism": {"base": "https://api-optimistic.etherscan.io/api", "key": os.getenv("OPTIMISTIC_KEY", "")},
    "avalanche": {"base": "https://api.snowtrace.io/api", "key": os.getenv("SNOWTRACE_KEY", "")},
    "fantom": {"base": "https://api.ftmscan.com/api", "key": os.getenv("FTMSCAN_KEY", "")},
}


@dataclass
class ContractData:
    address: str
    chain: str
    is_contract: bool = False
    is_verified: bool = False
    source_code: str = ""
    creator: str = ""
    creation_tx: str = ""
    creation_date: str = ""
    has_mint: bool = False
    has_blacklist: bool = False
    has_pause: bool = False
    has_honeypot: bool = False
    honeypot_reason: str = ""
    buy_tax: float = 0.0
    sell_tax: float = 0.0
    holders: int = 0
    top_holder_pct: float = 0.0
    liquidity_usd: float = 0.0
    market_cap: float = 0.0
    price_usd: float = 0.0
    volume_24h: float = 0.0
    is_proxy: bool = False
    implementation: str = ""
    extra: Dict = None

    def __post_init__(self):
        if self.extra is None:
            self.extra = {}


class APISourcer:
    """Aggregate blockchain data from multiple APIs."""

    def __init__(self):
        self.session: Optional[aiohttp.ClientSession] = None

    async def _get_session(self) -> aiohttp.ClientSession:
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=15))
        return self.session

    async def _fetch(self, url: str, headers: Dict = None) -> Optional[Dict]:
        try:
            session = await self._get_session()
            async with session.get(url, headers=headers or {}) as resp:
                if resp.status == 200:
                    return await resp.json()
        except Exception as e:
            logger.debug(f"Fetch failed: {url[:60]}... — {e}")
        return None

    async def _post(self, url: str, data: Dict, headers: Dict = None) -> Optional[Dict]:
        try:
            session = await self._get_session()
            async with session.post(url, json=data, headers=headers or {}) as resp:
                if resp.status == 200:
                    return await resp.json()
        except Exception as e:
            logger.debug(f"Post failed: {url[:60]}... — {e}")
        return None

    # ── Etherscan / BscScan ──

    def _explorer_url(self, chain: str) -> tuple:
        if chain in ("bsc", "bnb"):
            return "https://api.bscscan.com/api", BSCSCAN_KEY
        return "https://api.etherscan.io/api", ETHERSCAN_KEY

    async def get_contract_source(self, address: str, chain: str = "ethereum") -> Dict:
        url, key = self._explorer_url(chain)
        if not key:
            return {}
        params = f"?module=contract&action=getsourcecode&address={address}&apikey={key}"
        data = await self._fetch(url + params)
        if data and data.get("status") == "1" and data.get("result"):
            result = data["result"][0]
            return {
                "source": result.get("SourceCode", ""),
                "abi": result.get("ABI", ""),
                "creator": result.get("ContractCreator", ""),
                "verified": result.get("ABI") != "Contract source code not verified",
                "is_proxy": result.get("Proxy", "0") == "1",
                "implementation": result.get("Implementation", ""),
            }
        return {}

    async def get_creation_info(self, address: str, chain: str = "ethereum") -> Dict:
        url, key = self._explorer_url(chain)
        if not key:
            return {}
        params = f"?module=contract&action=getcontractcreation&contractaddresses={address}&apikey={key}"
        data = await self._fetch(url + params)
        if data and data.get("status") == "1" and data.get("result"):
            r = data["result"][0]
            return {
                "creator": r.get("contractCreator", ""),
                "tx": r.get("txHash", ""),
            }
        return {}

    # ── Alchemy ──

    async def get_token_metadata(self, address: str, chain: str = "eth") -> Dict:
        if not ALCHEMY_KEY:
            return {}
        network = "eth-mainnet" if chain in ("eth", "ethereum") else "bnb-mainnet" if chain in ("bsc", "bnb") else f"{chain}-mainnet"
        url = f"https://{network}.g.alchemy.com/v2/{ALCHEMY_KEY}"
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "alchemy_getTokenMetadata",
            "params": [address],
        }
        data = await self._post(url, payload)
        if data and "result" in data:
            r = data["result"]
            return {
                "name": r.get("name", ""),
                "symbol": r.get("symbol", ""),
                "decimals": r.get("decimals", 18),
                "logo": r.get("logo", ""),
            }
        return {}

    # ── Helius (Solana) ──

    async def get_solana_asset(self, address: str) -> Dict:
        if not HELIUS_KEY:
            return {}
        url = f"https://mainnet.helius-rpc.com/?api-key={HELIUS_KEY}"
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "getAsset",
            "params": {"id": address},
        }
        data = await self._post(url, payload)
        if data and "result" in data:
            r = data["result"]
            return {
                "name": r.get("content", {}).get("metadata", {}).get("name", ""),
                "symbol": r.get("content", {}).get("metadata", {}).get("symbol", ""),
                "supply": r.get("token_info", {}).get("supply", 0),
                "decimals": r.get("token_info", {}).get("decimals", 9),
            }
        return {}

    # ── Honeypot.is ──

    async def check_honeypot(self, address: str, chain: str = "eth") -> Dict:
        chain_map = {"eth": "eth", "ethereum": "eth", "bsc": "bsc", "bnb": "bsc"}
        mapped = chain_map.get(chain, chain)
        url = f"https://api.honeypot.is/v2/IsHoneypot?address={address}&chainID={mapped}"
        data = await self._fetch(url)
        if data:
            return {
                "is_honeypot": data.get("honeypotResult", {}).get("isHoneypot", False),
                "buy_tax": data.get("simulationResult", {}).get("buyTax", 0),
                "sell_tax": data.get("simulationResult", {}).get("sellTax", 0),
                "transfer_tax": data.get("simulationResult", {}).get("transferTax", 0),
                "holders": data.get("holderAnalysis", {}).get("holders", 0),
                "total_supply": data.get("token", {}).get("totalSupply", 0),
            }
        return {"is_honeypot": False, "buy_tax": 0, "sell_tax": 0}

    # ── Solscan (Solana) ──

    async def get_solscan_meta(self, address: str) -> Dict:
        if not SOLSCAN_KEY:
            return {}
        url = f"https://pro-api.solscan.io/v2.0/token/meta?address={address}"
        headers = {"token": SOLSCAN_KEY}
        data = await self._fetch(url, headers)
        if data and data.get("success"):
            r = data.get("data", {})
            return {
                "name": r.get("name", ""),
                "symbol": r.get("symbol", ""),
                "decimals": r.get("decimals", 9),
                "supply": r.get("supply", "0"),
                "holder": r.get("holder", 0),
                "is_mutable": r.get("mutableMetadata", False),
                "creator": r.get("creator", ""),
            }
        return {}

    async def get_solscan_holders(self, address: str) -> Dict:
        if not SOLSCAN_KEY:
            return {}
        url = f"https://pro-api.solscan.io/v2.0/token/holders?address={address}&page=1&page_size=10"
        headers = {"token": SOLSCAN_KEY}
        data = await self._fetch(url, headers)
        if data and data.get("success"):
            holders = data.get("data", {}).get("items", [])
            if holders:
                total = sum(float(h.get("amount", 0)) for h in holders[:10])
                top_pct = (float(holders[0].get("amount", 0)) / total * 100) if total > 0 else 0
                return {"holders": len(holders), "top_holder_pct": round(top_pct, 2)}
        return {}

    # ── DexScreener (Pair Data) ──

    async def get_dex_screener(self, address: str, chain: str = "solana") -> Dict:
        """Get DEX pair data from DexScreener. Works for any chain."""
        url = f"https://api.dexscreener.com/latest/dex/tokens/{address}"
        data = await self._fetch(url)
        if data and data.get("pairs"):
            pairs = data["pairs"]
            best = max(pairs, key=lambda x: float(x.get("volume", {}).get("h24", 0) or 0))
            return {
                "price": float(best.get("priceUsd", 0) or 0),
                "market_cap": float(best.get("marketCap", 0) or 0),
                "liquidity": float(best.get("liquidity", {}).get("usd", 0) or 0),
                "volume_24h": float(best.get("volume", {}).get("h24", 0) or 0),
                "dex": best.get("dexId", ""),
                "pair": best.get("pairAddress", ""),
                "buy_tax": 0,  # DexScreener doesn't have this
                "sell_tax": 0,
            }
        return {}

    # ── CoinGecko (Market Data) ──

    async def get_coingecko_data(self, address: str, chain: str = "ethereum") -> Dict:
        """Get token data from CoinGecko by contract address."""
        platform = "solana" if chain in ("sol", "solana") else "binance-smart-chain" if chain in ("bsc", "bnb") else "ethereum"
        url = f"https://api.coingecko.com/api/v3/coins/{platform}/contract/{address}"
        headers = {"x-cg-demo-api-key": COINGECKO_KEY} if COINGECKO_KEY else {}
        data = await self._fetch(url, headers)
        if data:
            market = data.get("market_data", {})
            return {
                "price": market.get("current_price", {}).get("usd", 0),
                "market_cap": market.get("market_cap", {}).get("usd", 0),
                "volume_24h": market.get("total_volume", {}).get("usd", 0),
                "price_change_24h": market.get("price_change_percentage_24h", 0),
                "ath": market.get("ath", {}).get("usd", 0),
            }
        return {}

    # ── Moralis (Wallet/Token Analytics) ──

    async def get_moralis_token_meta(self, address: str, chain: str = "eth") -> Dict:
        if not MORALIS_KEY:
            return {}
        chain_map = {"eth": "eth", "ethereum": "eth", "bsc": "bsc", "bnb": "bsc", "sol": "solana", "solana": "solana"}
        mapped = chain_map.get(chain, chain)
        url = f"https://deep-index.moralis.io/api/v2.2/erc20/metadata?chain={mapped}&addresses={address}"
        headers = {"X-API-Key": MORALIS_KEY}
        data = await self._fetch(url, headers)
        if data and isinstance(data, list) and len(data) > 0:
            r = data[0]
            return {
                "name": r.get("name", ""),
                "symbol": r.get("symbol", ""),
                "decimals": r.get("decimals", 18),
                "logo": r.get("logo", ""),
                "total_supply": r.get("total_supply_formatted", "0"),
            }
        return {}

    async def get_moralis_token_prices(self, addresses: List[str], chain: str = "eth") -> Dict:
        if not MORALIS_KEY:
            return {}
        chain_map = {"eth": "eth", "ethereum": "eth", "bsc": "bsc", "bnb": "bsc", "sol": "solana", "solana": "solana"}
        mapped = chain_map.get(chain, chain)
        addr_str = "%2C".join(addresses)
        url = f"https://deep-index.moralis.io/api/v2.2/erc20/prices?chain={mapped}&include=percent_change&addresses={addr_str}"
        headers = {"X-API-Key": MORALIS_KEY}
        data = await self._fetch(url, headers)
        if data:
            return {item.get("tokenAddress", "").lower(): item for item in data}
        return {}

    # ── QuickNode RPC (Solana) ──

    async def get_solana_account_info(self, address: str) -> Dict:
        if not QUICKNODE_SOL:
            return {}
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "getAccountInfo",
            "params": [address, {"encoding": "jsonParsed"}],
        }
        data = await self._post(QUICKNODE_SOL, payload)
        if data and "result" in data:
            val = data["result"].get("value", {})
            return {
                "executable": val.get("executable", False),
                "lamports": val.get("lamports", 0),
                "owner": val.get("owner", ""),
                "data": val.get("data", []),
            }
        return {}

    # ── Birdeye (Market Data) ──

    async def get_market_data(self, address: str, chain: str = "solana") -> Dict:
        if not BIRDEYE_KEY:
            return {}
        url = f"https://public-api.birdeye.so/defi/v3/token/market-data?address={address}"
        headers = {"X-API-KEY": BIRDEYE_KEY, "x-chain": chain}
        data = await self._fetch(url, headers)
        if data and data.get("data"):
            d = data["data"]
            return {
                "price": d.get("price", 0),
                "market_cap": d.get("marketCap", 0),
                "liquidity": d.get("liquidity", 0),
                "volume_24h": d.get("volume24h", 0),
                "holders": d.get("holder", 0),
            }
        return {}

    # ── Main Aggregator ──

    async def analyze_contract(self, address: str, chain: str = "ethereum") -> ContractData:
        """Full contract analysis from all available sources."""
        cd = ContractData(address=address, chain=chain)

        # Parallel fetches
        tasks = [
            self.get_contract_source(address, chain),
            self.get_creation_info(address, chain),
            self.check_honeypot(address, chain),
        ]

        if chain in ("solana", "sol"):
            tasks.append(self.get_solana_asset(address))
        else:
            tasks.append(self.get_token_metadata(address, chain))

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Parse source
        source_data = results[0] if isinstance(results[0], dict) else {}
        if source_data:
            cd.is_verified = source_data.get("verified", False)
            cd.source_code = source_data.get("source", "")[:5000]
            cd.is_proxy = source_data.get("is_proxy", False)
            cd.implementation = source_data.get("implementation", "")
            src_lower = cd.source_code.lower()
            cd.has_mint = "mint" in src_lower and "function" in src_lower
            cd.has_blacklist = "blacklist" in src_lower or "blacklisted" in src_lower
            cd.has_pause = "pause" in src_lower and "function" in src_lower

        # Parse creation
        creation = results[1] if isinstance(results[1], dict) else {}
        cd.creator = creation.get("creator", "")
        cd.creation_tx = creation.get("tx", "")

        # Parse honeypot
        hp = results[2] if isinstance(results[2], dict) else {}
        cd.has_honeypot = hp.get("is_honeypot", False)
        cd.honeypot_reason = "Simulated buy/sell failed" if cd.has_honeypot else ""
        cd.buy_tax = hp.get("buy_tax", 0)
        cd.sell_tax = hp.get("sell_tax", 0)
        cd.holders = hp.get("holders", 0)

        # Parse token data
        token = results[3] if isinstance(results[3], dict) else {}
        cd.extra["token_name"] = token.get("name", "")
        cd.extra["token_symbol"] = token.get("symbol", "")
        cd.extra["decimals"] = token.get("decimals", 18)

        # Market data (async, don't block)
        if chain in ("solana", "sol"):
            market = await self.get_market_data(address, "solana")
        else:
            market = {}  # Birdeye mainly Solana
        cd.price_usd = market.get("price", 0)
        cd.market_cap = market.get("market_cap", 0)
        cd.liquidity_usd = market.get("liquidity", 0)
        cd.volume_24h = market.get("volume_24h", 0)
        if market.get("holders"):
            cd.holders = market["holders"]

        cd.is_contract = True
        return cd

    # ── Free RPC Fallbacks ──

    async def rpc_call(self, chain: str, method: str, params: list) -> Optional[Any]:
        """Call a public RPC with fallback nodes."""
        rpcs = FREE_RPCS.get(chain, [])
        payload = {"jsonrpc": "2.0", "id": 1, "method": method, "params": params}
        for rpc in rpcs:
            try:
                data = await self._post(rpc, payload)
                if data and "result" in data:
                    return data["result"]
            except Exception:
                continue
        return None

    async def get_code(self, address: str, chain: str = "ethereum") -> str:
        """Get contract bytecode via free RPC."""
        result = await self.rpc_call(chain, "eth_getCode", [address, "latest"])
        return result if result and result != "0x" else ""

    async def get_tx_count(self, address: str, chain: str = "ethereum") -> int:
        """Get transaction count via free RPC."""
        result = await self.rpc_call(chain, "eth_getTransactionCount", [address, "latest"])
        return int(result, 16) if result else 0

    async def get_balance(self, address: str, chain: str = "ethereum") -> float:
        """Get native balance via free RPC."""
        result = await self.rpc_call(chain, "eth_getBalance", [address, "latest"])
        if result:
            return int(result, 16) / 1e18
        return 0.0

    # ── Token Sniffer (Free tier) ──

    async def check_token_sniffer(self, address: str, chain: str = "eth") -> Dict:
        chain_map = {"eth": "1", "ethereum": "1", "bsc": "56", "bnb": "56", "polygon": "137", "base": "8453", "arbitrum": "42161"}
        chain_id = chain_map.get(chain, "1")
        url = f"https://tokensniffer.com/api/v2/tokens/{chain_id}/{address}"
        data = await self._fetch(url)
        if data:
            return {
                "is_scam": data.get("is_scam", False),
                "score": data.get("score", 0),
                "risks": data.get("risks", []),
                "buy_tax": data.get("buy_tax", 0),
                "sell_tax": data.get("sell_tax", 0),
                "transfer_tax": data.get("transfer_tax", 0),
            }
        return {}

    # ── Arkham Intel (Free tier) ──

    async def get_arkham_labels(self, address: str) -> Dict:
        if not ARKHAM_KEY:
            return {}
        url = f"https://api.arkhamintelligence.com/intelligence/address/{address}"
        headers = {"API-Key": ARKHAM_KEY}
        data = await self._fetch(url, headers)
        if data:
            return {
                "entity": data.get("entity", ""),
                "entity_type": data.get("entityType", ""),
                "labels": data.get("labels", []),
                "is_whale": data.get("isWhale", False),
            }
        return {}

    # ── Chainbase (Free tier) ──

    async def get_chainbase_token_meta(self, address: str, chain: str = "ethereum") -> Dict:
        if not CHAINBASE_KEY:
            return {}
        chain_map = {"eth": "1", "ethereum": "1", "bsc": "56", "polygon": "137", "base": "8453"}
        chain_id = chain_map.get(chain, "1")
        url = f"https://api.chainbase.online/v1/token/metadata?chain_id={chain_id}&contract_address={address}"
        headers = {"x-api-key": CHAINBASE_KEY}
        data = await self._fetch(url, headers)
        if data and data.get("data"):
            r = data["data"]
            return {
                "name": r.get("name", ""),
                "symbol": r.get("symbol", ""),
                "decimals": r.get("decimals", 18),
                "total_supply": r.get("total_supply", "0"),
            }
        return {}

    # ── Covalent (Free tier) ──

    async def get_covalent_balances(self, address: str, chain: str = "eth-mainnet") -> Dict:
        if not COVALENT_KEY:
            return {}
        url = f"https://api.covalenthq.com/v1/{chain}/address/{address}/balances_v2/"
        headers = {"Authorization": f"Bearer {COVALENT_KEY}"}
        data = await self._fetch(url, headers)
        if data and data.get("data"):
            items = data["data"].get("items", [])
            return {
                "items": items,
                "count": len(items),
            }
        return {}

    # ── DefiLlama (Completely Free) ──

    async def get_defillama_protocols(self) -> List[Dict]:
        url = "https://api.llama.fi/protocols"
        data = await self._fetch(url)
        return data if data else []

    async def get_defillama_tvl(self, protocol: str) -> Dict:
        url = f"https://api.llama.fi/tvl/{protocol}"
        data = await self._fetch(url)
        return {"tvl": data} if data else {}

    # ── Bubblemaps (Free public) ──

    async def get_bubblemaps(self, address: str, chain: str = "eth") -> Dict:
        chain_map = {"eth": "eth", "ethereum": "eth", "bsc": "bsc", "sol": "sol", "solana": "sol", "avax": "avax", "ftm": "ftm"}
        mapped = chain_map.get(chain, chain)
        url = f"https://api-legacy.bubblemaps.io/map-data?token={address}&chain={mapped}"
        data = await self._fetch(url)
        if data:
            return {
                "is_bubblemap": True,
                "clusters": data.get("clusters", []),
                "holders": data.get("nodes", []),
                "decentralization_score": data.get("decentralizationScore", 0),
            }
        return {}

    # ── Fallback Market Data Resolver ──

    async def resolve_market_data(self, address: str, chain: str = "ethereum") -> Dict:
        """Try multiple free sources for market data. Returns best result."""
        results = []

        # DexScreener — free, no key, multi-chain
        dex = await self.get_dex_screener(address, chain)
        if dex.get("price"):
            results.append(("dexscreener", dex))

        # CoinGecko — free tier
        cg = await self.get_coingecko_data(address, chain)
        if cg.get("price"):
            results.append(("coingecko", cg))

        # Birdeye — Solana focused
        if chain in ("sol", "solana"):
            be = await self.get_market_data(address, "solana")
            if be.get("price"):
                results.append(("birdeye", be))

        # Moralis — if key available
        if MORALIS_KEY:
            mp = await self.get_moralis_token_prices([address], chain)
            if mp:
                results.append(("moralis", {
                    "price": mp.get(address.lower(), {}).get("usdPrice", 0),
                    "market_cap": 0,
                }))

        # Pick best (highest liquidity first, then price)
        best = {}
        for source, data in results:
            if not best:
                best = data
                best["_source"] = source
            elif data.get("liquidity", 0) > best.get("liquidity", 0):
                best = data
                best["_source"] = source

        return best

    # ── Main Aggregator (Enhanced with Fallbacks) ──

    async def analyze_contract(self, address: str, chain: str = "ethereum") -> ContractData:
        """Full contract analysis using ALL available sources with fallback priority."""
        cd = ContractData(address=address, chain=chain)

        is_solana = chain in ("solana", "sol")

        # ── PARALLEL FETCHES ──
        # Try everything in parallel, then pick best results

        tasks = {
            "honeypot": self.check_honeypot(address, chain),
            "dexscreener": self.get_dex_screener(address, chain),
            "token_sniffer": self.check_token_sniffer(address, chain),
        }

        if is_solana:
            tasks["solscan_meta"] = self.get_solscan_meta(address)
            tasks["solscan_holders"] = self.get_solscan_holders(address)
            tasks["helius"] = self.get_solana_asset(address)
            tasks["solana_rpc"] = self.get_solana_account_info(address)
        else:
            tasks["etherscan_source"] = self.get_contract_source(address, chain)
            tasks["etherscan_creation"] = self.get_creation_info(address, chain)
            tasks["alchemy_meta"] = self.get_token_metadata(address, chain)
            tasks["moralis_meta"] = self.get_moralis_token_meta(address, chain)
            tasks["chainbase_meta"] = self.get_chainbase_token_meta(address, chain)
            tasks["coingecko"] = self.get_coingecko_data(address, chain)
            tasks["rpc_code"] = self.get_code(address, chain)

        results = {}
        for name, task in tasks.items():
            try:
                results[name] = await asyncio.wait_for(task, timeout=10)
            except Exception:
                results[name] = {}

        # ── PARSE RESULTS ──

        # Honeypot check (highest priority)
        hp = results.get("honeypot", {})
        cd.has_honeypot = hp.get("is_honeypot", False)
        cd.honeypot_reason = "Simulated buy/sell failed" if cd.has_honeypot else ""
        cd.buy_tax = hp.get("buy_tax", 0)
        cd.sell_tax = hp.get("sell_tax", 0)
        cd.holders = hp.get("holders", 0)

        # Token Sniffer (second opinion)
        ts = results.get("token_sniffer", {})
        if ts.get("is_scam"):
            cd.extra["token_sniffer_scam"] = True
            cd.extra["token_sniffer_score"] = ts.get("score", 0)
        if ts.get("buy_tax"):
            cd.buy_tax = max(cd.buy_tax, ts["buy_tax"])
        if ts.get("sell_tax"):
            cd.sell_tax = max(cd.sell_tax, ts["sell_tax"])

        if is_solana:
            # Solana parsing
            ss_meta = results.get("solscan_meta", {})
            if ss_meta:
                cd.extra["token_name"] = ss_meta.get("name", "")
                cd.extra["token_symbol"] = ss_meta.get("symbol", "")
                cd.extra["decimals"] = ss_meta.get("decimals", 9)
                cd.creator = ss_meta.get("creator", "")
                cd.holders = ss_meta.get("holder", cd.holders)

            ss_holders = results.get("solscan_holders", {})
            if ss_holders:
                cd.holders = max(cd.holders, ss_holders.get("holders", 0))
                cd.top_holder_pct = ss_holders.get("top_holder_pct", 0)

            helius = results.get("helius", {})
            if helius:
                cd.extra["token_name"] = cd.extra.get("token_name") or helius.get("name", "")
                cd.extra["token_symbol"] = cd.extra.get("token_symbol") or helius.get("symbol", "")

            sol_rpc = results.get("solana_rpc", {})
            cd.is_contract = sol_rpc.get("executable", True)

        else:
            # EVM parsing
            source = results.get("etherscan_source", {})
            if source:
                cd.is_verified = source.get("verified", False)
                cd.source_code = source.get("source", "")[:5000]
                cd.is_proxy = source.get("is_proxy", False)
                cd.implementation = source.get("implementation", "")
                src_lower = cd.source_code.lower()
                cd.has_mint = "mint" in src_lower and "function" in src_lower
                cd.has_blacklist = "blacklist" in src_lower or "blacklisted" in src_lower
                cd.has_pause = "pause" in src_lower and "function" in src_lower

            creation = results.get("etherscan_creation", {})
            cd.creator = creation.get("creator", cd.creator)
            cd.creation_tx = creation.get("tx", "")

            # Token metadata (try multiple sources, pick best)
            meta = results.get("alchemy_meta") or results.get("moralis_meta") or results.get("chainbase_meta") or {}
            if meta:
                cd.extra["token_name"] = meta.get("name", "")
                cd.extra["token_symbol"] = meta.get("symbol", "")
                cd.extra["decimals"] = meta.get("decimals", 18)

            # RPC bytecode check
            code = results.get("rpc_code", "")
            cd.is_contract = len(code) > 2

        # Market data (DexScreener is free + multi-chain)
        dex = results.get("dexscreener", {})
        if dex:
            cd.price_usd = dex.get("price", 0)
            cd.market_cap = dex.get("market_cap", 0)
            cd.liquidity_usd = dex.get("liquidity", 0)
            cd.volume_24h = dex.get("volume_24h", 0)
            cd.extra["dex_id"] = dex.get("dex", "")

        # CoinGecko fallback for market data
        if not cd.price_usd:
            cg = results.get("coingecko", {})
            cd.price_usd = cg.get("price", 0)
            cd.market_cap = cg.get("market_cap", 0)
            cd.volume_24h = cg.get("volume_24h", 0)
            cd.extra["price_change_24h"] = cg.get("price_change_24h", 0)

        # Arkham labels (whale/entity identification)
        if ARKHAM_KEY and not is_solana:
            try:
                ark = await asyncio.wait_for(self.get_arkham_labels(address), timeout=5)
                if ark.get("entity"):
                    cd.extra["arkham_entity"] = ark["entity"]
                    cd.extra["arkham_labels"] = ark.get("labels", [])
            except Exception:
                pass

        # Bubblemaps decentralization score
        try:
            bm = await asyncio.wait_for(self.get_bubblemaps(address, chain), timeout=5)
            if bm.get("decentralization_score"):
                cd.extra["bubblemap_score"] = bm["decentralization_score"]
                cd.top_holder_pct = bm.get("clusters", [{}])[0].get("percentage", 0) if bm.get("clusters") else 0
        except Exception:
            pass

        return cd

    async def close(self):
        if self.session and not self.session.closed:
            await self.session.close()


# Singleton
api_sourcer = APISourcer()
