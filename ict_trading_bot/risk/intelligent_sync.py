"""
Intelligent Execution Sync to Supabase
========================================
Syncs local intelligence stats to Supabase for:
1. Cross-machine learning (if running multiple bots)
2. Long-term data persistence
3. Analytics/dashboards
4. Backup in case local file corrupts

STRATEGY:
- Primary: Local JSON files (fast, reliable, always works)
- Secondary: Supabase sync (database backup, analytics)
"""
import json
import os
import logging
from datetime import datetime
from threading import Thread
from pathlib import Path

# Shared Bot Identifier: Use this to group records even if the MT5 account changes.
# You can set this in your .env file as PERSISTENT_BOT_ID
PERSISTENT_BOT_ID = os.getenv("PERSISTENT_BOT_ID", "jaguar_shared_intelligence")

logger = logging.getLogger(__name__)


def _get_supabase_client():
    """Get Supabase client for syncing."""
    try:
        from supabase import create_client
        url = os.getenv("SUPABASE_URL")
        key = os.getenv("SUPABASE_KEY")
        if not url or not key:
            return None
        return create_client(url, key)
    except Exception as e:
        logger.warning(f"Supabase not available: {e}")
        return None


def sync_intelligent_stats_to_supabase(stats: dict, async_mode=True):
    """
    Sync intelligent execution statistics to Supabase.
    
    Creates/updates records in 'intelligence_stats' table:
    - symbol (TEXT, PRIMARY KEY)
    - total_trades (INTEGER)
    - wins (INTEGER)  
    - win_rate (FLOAT)
    - avg_confidence (FLOAT)
    - recent_outcomes (JSONB - last 30 outcomes)
    - recent_trades (JSONB - last 20 trades with details)
    - market_condition (TEXT - "volatile" / "consolidating" / "stable")
    - volatility_index (FLOAT - 0.0-1.0)
    - last_updated (TIMESTAMP)
    
    Args:
        stats: Dictionary of symbol stats from intelligent_execution_stats.json
        async_mode: If True, run sync in background thread (non-blocking)
    """
    if not stats:
        return
    
    def _do_sync():
        client = _get_supabase_client()
        if not client:
            return
        
        try:
            table = client.table("intelligence_stats")
            
            for symbol, data in stats.items():
                record = {
                    "symbol": symbol,
                    "total_trades": data.get("total_trades", 0),
                    "wins": data.get("wins", 0),
                    "win_rate": data.get("win_rate", 0.0),
                    "avg_confidence": data.get("avg_confidence", 0.0),
                    "recent_outcomes": data.get("recent_outcomes", []),
                    "recent_trades": data.get("recent_trades", []),
                    "market_condition": data.get("market_condition", "unknown"),
                    "volatility_index": data.get("volatility_index", 0.0),
                    "bot_identity": PERSISTENT_BOT_ID,
                    "last_updated": data.get("last_updated", datetime.utcnow().isoformat()),
                }
                
                # Try upsert (update or insert)
                try:
                    table.upsert(record).execute()
                except Exception as e:
                    logger.debug(f"Upsert failed for {symbol}, trying insert: {e}")
                    try:
                        table.insert(record).execute()
                    except Exception as e2:
                        logger.warning(f"Failed to sync {symbol} stats: {e2}")
        
        except Exception as e:
            logger.warning(f"Intelligence stats sync failed: {e}")
    
    if async_mode:
        thread = Thread(target=_do_sync, daemon=True)
        thread.start()
    else:
        _do_sync()


def sync_trade_outcome_to_supabase(
    symbol: str,
    win: bool,
    confirmation_score: float,
    entry_price: float,
    exit_price: float,
    pnl: float,
    execution_route: str,
):
    """
    Sync individual trade outcome to Supabase.
    
    Creates record in 'intelligence_trades' table:
    - id (UUID, auto)
    - symbol (TEXT)
    - timestamp (TIMESTAMP)
    - win (BOOLEAN)
    - confirmation_score (FLOAT)
    - entry_price (FLOAT)
    - exit_price (FLOAT)
    - pnl (FLOAT)
    - execution_route (TEXT - "weighted_confirmation", "four_confirmation_direct", etc.)
    """
    client = _get_supabase_client()
    if not client:
        return
    
    try:
        record = {
            "symbol": symbol,
            "timestamp": datetime.utcnow().isoformat(),
            "win": win,
            "confirmation_score": confirmation_score,
            "entry_price": entry_price,
            "exit_price": exit_price,
            "pnl": pnl,
            "execution_route": execution_route,
            "bot_identity": PERSISTENT_BOT_ID,
        }
        
        client.table("intelligence_trades").insert(record).execute()
    except Exception as e:
        logger.debug(f"Trade outcome sync failed: {e}")


def load_intelligent_stats_from_supabase(symbols: list = None):
    """
    Load intelligent stats from Supabase (for backup/recovery).
    Returns merged stats from local file with Supabase data.
    
    Use case: If local file corrupts, fallback to Supabase.
    """
    client = _get_supabase_client()
    if not client:
        return {}
    
    try:
        query = client.table("intelligence_stats").select("*").eq("bot_identity", PERSISTENT_BOT_ID)
        if symbols:
            # Load specific symbols
            query = query.in_("symbol", symbols)
        
        response = query.execute()
        data = response.data or []
        
        # Convert to intelligence_execution_stats format
        stats = {}
        for record in data:
            symbol = record.get("symbol")
            stats[symbol] = {
                "symbol": symbol,
                "total_trades": record.get("total_trades", 0),
                "wins": record.get("wins", 0),
                "losses": record.get("total_trades", 0) - record.get("wins", 0),
                "win_rate": record.get("win_rate", 0.0),
                "confidence_scores": [],  # Not stored in Supabase to save space
                "avg_confidence": record.get("avg_confidence", 0.0),
                "recent_outcomes": record.get("recent_outcomes", []),
                "recent_trades": record.get("recent_trades", []),
                "market_condition": record.get("market_condition", "unknown"),
                "volatility_index": record.get("volatility_index", 0.0),
                "pnl_total": sum(t.get("pnl", 0) for t in record.get("recent_trades", [])),
                "last_updated": record.get("last_updated"),
            }
        
        return stats
    except Exception as e:
        logger.warning(f"Failed to load stats from Supabase: {e}")
        return {}


# ============================================
# CREATE SUPABASE TABLES (SQL)
# ============================================
"""
RUN THIS IN SUPABASE SQL EDITOR:

-- Intelligence Stats Table
CREATE TABLE IF NOT EXISTS intelligence_stats (
  symbol TEXT PRIMARY KEY,
  total_trades INTEGER DEFAULT 0,
  wins INTEGER DEFAULT 0,
  win_rate FLOAT DEFAULT 0.0,
  avg_confidence FLOAT DEFAULT 0.0,
  recent_outcomes JSONB DEFAULT '[]'::jsonb,
  recent_trades JSONB DEFAULT '[]'::jsonb,
  market_condition TEXT DEFAULT 'unknown',
  volatility_index FLOAT DEFAULT 0.0,
  last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_intelligence_stats_win_rate ON intelligence_stats(win_rate DESC);
CREATE INDEX idx_intelligence_stats_updated_at ON intelligence_stats(last_updated DESC);

-- Intelligence Trades Table  
CREATE TABLE IF NOT EXISTS intelligence_trades (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  symbol TEXT NOT NULL,
  timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  win BOOLEAN NOT NULL,
  confirmation_score FLOAT DEFAULT 0.0,
  entry_price FLOAT DEFAULT 0.0,
  exit_price FLOAT DEFAULT 0.0,
  pnl FLOAT DEFAULT 0.0,
  execution_route TEXT DEFAULT 'unknown',
  FOREIGN KEY (symbol) REFERENCES intelligence_stats(symbol) ON DELETE CASCADE
);

CREATE INDEX idx_intelligence_trades_symbol ON intelligence_trades(symbol);
CREATE INDEX idx_intelligence_trades_timestamp ON intelligence_trades(timestamp DESC);
CREATE INDEX idx_intelligence_trades_win ON intelligence_trades(win);

-- Volatility Analysis Table (for market condition detection per pair)
CREATE TABLE IF NOT EXISTS pair_volatility_analysis (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  symbol TEXT NOT NULL,
  timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  volatility_index FLOAT NOT NULL,
  atr FLOAT DEFAULT 0.0,
  atr_percent FLOAT DEFAULT 0.0,
  condition TEXT DEFAULT 'consolidating',
  recent_range FLOAT DEFAULT 0.0,
  last_20_bars_range FLOAT DEFAULT 0.0,
  FOREIGN KEY (symbol) REFERENCES intelligence_stats(symbol) ON DELETE CASCADE
);

CREATE INDEX idx_volatility_symbol ON pair_volatility_analysis(symbol);
CREATE INDEX idx_volatility_timestamp ON pair_volatility_analysis(timestamp DESC);

"""
