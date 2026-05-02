# RMI Content Categorization System

## Overview
Comprehensive content pipeline for distributing high-value crypto intelligence across 6 Telegram channels with strict quality standards and dedup protection.

## Channel Network

| Channel | ID | Purpose | Frequency |
|---------|----|---------|-----------|
| @cryptorugmuncher | -1002056885429 | Main brand - aggregated high-value content | 3-8/day |
| @rmicryptonews | -1003982391578 | Breaking news, market analysis | 8-15/day |
| @rmialerts | -1003818352164 | Critical alerts (rugs/scams/exploits) | 2-10/day |
| @rmialpha | -1003762675055 | Premium alpha signals ($5/mo) | 3-12/day |
| @rmiscans | -1003937506770 | Community scan activity | 10-30/day |
| @rmiupdates | -1003872387867 | Project updates, changelogs | 1-3/week |

## Content Categories (30 total)

### Main Channel (@cryptorugmuncher) - 5 categories
- **major_alert**: High-impact events (risk >= 85 or major news)
- **website_post**: Content from RMI website
- **twitter_highlight**: Curated tweets from trusted sources
- **market_movement**: Significant price action (>10% in 1h)
- **project_update**: RMI feature releases

### News Channel (@rmicryptonews) - 5 categories
- **breaking_news**: Major crypto events (cryptopanic votes > 50)
- **market_analysis**: Technical analysis, trends (fear_greed change > 10)
- **trending_tokens**: Top 10 by volume or social mentions
- **regulatory_news**: Government, SEC, policy updates
- **defi_updates**: DeFi protocol news, TVL changes > 10%

### Alerts Channel (@rmialerts) - 5 categories
- **rug_pull_detected**: Active or imminent rug (risk >= 85)
- **honeypot_confirmed**: sell_tax > 99% or honeypot=True
- **exploit_detected**: Active hack (votes > 30 or loss > $1M)
- **scam_contract**: Blacklisted dev or serial rugger
- **lp_drain_alert**: LP removed > 50% in 1h

### Alpha Channel (@rmialpha) - 7 categories
- **whale_movement**: Large movements (> $100k)
- **smart_money_signal**: Smart money buying patterns
- **insider_accumulation**: Insider wallets loading up
- **early_gem**: High-score token before trend
- **deployer_blacklist**: Known rugging deployer
- **pre_rug_warning**: Signals suggesting potential rug
- **deep_contract_scan**: Full premium analysis

### Scans Channel (@rmiscans) - 4 categories
- **user_scan**: Any scan performed via bot
- **trending_scans**: Most scanned tokens in last hour (> 5)
- **launch_radar**: New token launches detected
- **scan_digest**: Hourly digest of all scans

### Updates Channel (@rmiupdates) - 4 categories
- **feature_release**: New feature or capability
- **system_status**: System health, uptime, incidents
- **milestone**: User milestones, achievements
- **partnership**: Partnerships, integrations

## Data Sources

### MCP Router (154 tools across 28 services)
**Price/Market:** coingecko, coinmarketcap, coincap, cryptocompare, birdeye, jupiter, blockrun
**On-chain/DEX:** dexscreener, dexpaprika, raydium, pumpfun, defillama
**Intelligence:** nansen, arkham, gmgn, dune, cryptoiz, moralis, helius, solscan
**News/Sentiment:** cryptopanic, blockrun (twitter search)
**Network:** solana, blockchain, blockchair, mempool, quicknode
**Action:** agentfi, freeusdc

### External Telegram (9 accessible channels)
- @whale_alert - Large transactions
- @Lookonchain - Smart money tracking
- @spotonchain - On-chain analysis
- @TreeNews - Breaking crypto news
- @CoinDesk - News feed
- @WatcherGuru - Market updates
- @PumpFunNews - New launches
- @GMGN_AI - Trading signals
- @pumpdotfun - Pump.fun launches

### RSS Feeds (4 working)
- CoinDesk (25 items)
- Cointelegraph (30 items)
- Decrypt (35 items)
- BeInCrypto (12 items)

### Other Sources
- Reddit (r/cryptocurrency, r/Bitcoin, r/ethereum)
- Fear & Greed Index (alternative.me)
- Bot scanner results

## Global Standards

### Quality Rules
- **Minimum sources:** 2 (cross-verified)
- **Confidence threshold:** 70%
- **Max content age:** 30 minutes
- **Dedup window:** 24 hours
- **Language:** English only

### Posting Rules
- **No spam:** Max 3 posts in 10 minutes per channel
- **No duplicates:** Same content hash = delete old, keep newest
- **Source attribution:** Always cite primary source
- **Formatting:** Emoji headers, clear sections, call-to-action
- **Timing:** Peak hours 8am-10pm UTC, off-hours only for CRITICAL

### Priority Routing
- **IMMEDIATE:** All relevant channels, bypass rate limits
- **HIGH:** Post within 5 minutes
- **MEDIUM:** Post within 30 minutes
- **LOW:** Batch and post on schedule

## Files
- `/root/ecosystems/rugmuncher/bot/bot/content_strategy.json` - Full configuration
- `/root/ecosystems/rugmuncher/bot/bot/content_pipeline.py` - Pipeline implementation
- `/root/ecosystems/rugmuncher/bot/bot/channels.py` - Channel management (with dedup)
- `/root/ecosystems/rugmuncher/bot/bot/x402_integrations/crosspost_manager.py` - Cross-posting
