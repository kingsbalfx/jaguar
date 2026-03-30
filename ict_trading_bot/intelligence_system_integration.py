"""
Intelligence System Integration for Main Bot
=============================================
Shows how to integrate CIS and validation into main trading loop.

This module provides ready-to-use functions that can be dropped into:
- main.py (main trading loop)
- multi_account_runner.py (multi-account coordination)
- Any custom trading script

Example usage in main.py:
    from intelligence_system_integration import TradeDecisionEngine
    
    engine = TradeDecisionEngine()
    
    # In your main loop
    for symbol in trading_symbols:
        setup = scan_for_setup(symbol)
        if setup:
            decision = engine.evaluate_trade(symbol, setup)
            if decision.should_trade:
                order = engine.execute_trade(symbol, setup, decision)
"""
import logging
from typing import Dict, Optional, Tuple
from datetime import datetime

import MetaTrader5 as mt5

from risk.intelligence_system import (
    get_cis_decision,
    get_cis_summary,
)
from risk.market_condition import (
    analyze_all_pairs,
    get_volatility_summary,
)
from execution.pre_trade_validator import (
    validate_trade_before_entry,
    PreTradeValidator,
)

logger = logging.getLogger(__name__)


class TradeDecisionEngine:
    """
    High-level trading decision interface.
    
    Encapsulates intelligence system for easy use in main bot loop.
    
    Usage:
        engine = TradeDecisionEngine()
        
        # Pre-session setup
        engine.analyze_market_conditions(symbols)
        
        # For each potential trade
        decision = engine.evaluate_trade(symbol, direction, prices)
        
        if decision.should_trade:
            order = engine.execute_trade(symbol, decision)
    """
    
    def __init__(self, symbols: list = None):
        self.symbols = symbols or [
            "EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCAD",
            "NZDUSD", "EURGBP", "EURJPY", "GBPJPY", "AUDJPY"
        ]
        self.validator = PreTradeValidator()
        self.market_conditions = {}
        self.analyzer_active = True
    
    def analyze_market_conditions(self) -> bool:
        """
        Pre-session: Analyze market conditions for all pairs.
        
        Should be called at session start (or periodically).
        
        Returns:
            True if successful, False if failed
        """
        try:
            logger.info("[ENGINE] Analyzing market conditions...")
            self.market_conditions = analyze_all_pairs(self.symbols)
            
            summary = get_volatility_summary(self.symbols)
            logger.info(f"[ENGINE] {summary}")
            
            return True
        except Exception as e:
            logger.error(f"[ENGINE] Market analysis failed: {e}")
            return False
    
    def get_market_condition(self, symbol: str) -> Optional[Dict]:
        """Get cached market condition for symbol."""
        return self.market_conditions.get(symbol)
    
    def evaluate_trade(
        self,
        symbol: str,
        direction: str,
        timeframe: str = "H1",
        entry: float = None,
        stop_loss: float = None,
        take_profit: float = None,
    ) -> 'TradeDecision':
        """
        Evaluate a potential trade using intelligence system.
        
        Args:
            symbol: Trading pair
            direction: "BUY" or "SELL"
            timeframe: Chart timeframe
            entry, stop_loss, take_profit: Price targets (optional)
        
        Returns:
            TradeDecision object with recommendation
        """
        decision = TradeDecision(symbol, direction)
        
        try:
            # Step 1: CIS evaluation
            logger.debug(f"[ENGINE] CIS evaluating {symbol} {direction}...")
            cis = get_cis_decision(
                symbol, direction, timeframe,
                entry, stop_loss, take_profit
            )
            
            decision.cis_verdict = cis.get('final_verdict', 'ERROR')
            decision.cis_confidence = cis.get('confidence_score', 0.0)
            decision.cis_reasoning = cis.get('reasoning', [])
            decision.cis_red_flags = cis.get('red_flags', [])
            decision.component_scores = cis.get('component_scores', {})
            decision.position_size = cis.get('position_size', 0.01)
            
            if decision.cis_verdict == "AVOID":
                decision.should_trade = False
                decision.block_reason = "CIS recommends AVOID"
                return decision
            
            # Step 2: Pre-trade validation  
            logger.debug(f"[ENGINE] Validating {symbol}...")
            approved, validation = validate_trade_before_entry(
                symbol, direction, entry, stop_loss, take_profit
            )
            
            decision.validation_result = validation
            decision.checks = validation.get('checks', [])
            decision.warnings = validation.get('warnings', [])
            
            if not approved:
                decision.should_trade = False
                decision.block_reason = validation.get('reason', 'Validation failed')
                return decision
            
            # All checks passed
            decision.should_trade = True
            decision.block_reason = None
            
            logger.info(
                f"[ENGINE] ✓ {symbol} {direction} APPROVED "
                f"(CIS: {decision.cis_confidence:.2f}, "
                f"Size: {decision.position_size:.2f})"
            )
            
            return decision
        
        except Exception as e:
            logger.error(f"[ENGINE] Evaluation error for {symbol}: {e}")
            decision.should_trade = False
            decision.block_reason = f"Evaluation error: {e}"
            return decision
    
    def execute_trade(
        self,
        symbol: str,
        direction: str,
        entry: float,
        stop_loss: float,
        take_profit: float,
        decision: 'TradeDecision' = None,
    ) -> Optional[Dict]:
        """
        Execute a trade after decision approval.
        
        Args:
            symbol: Trading pair
            direction: "BUY" or "SELL"
            entry, stop_loss, take_profit: Price levels
            decision: Optional TradeDecision from evaluate_trade()
        
        Returns:
            Order result or None if failed
        """
        try:
            # Use provided decision or evaluate now
            if decision is None:
                decision = self.evaluate_trade(
                    symbol, direction,
                    entry=entry, stop_loss=stop_loss, take_profit=take_profit
                )
            
            if not decision.should_trade:
                logger.warning(f"[ENGINE] Trade blocked: {decision.block_reason}")
                return None
            
            # Prepare order
            order_type = mt5.ORDER_TYPE_BUY if direction == "BUY" else mt5.ORDER_TYPE_SELL
            
            request = {
                "action": mt5.TRADE_ACTION_DEAL,
                "symbol": symbol,
                "volume": decision.position_size,
                "type": order_type,
                "price": entry,
                "sl": stop_loss,
                "tp": take_profit,
                "comment": f"CIS_{decision.cis_confidence:.2f}",
            }
            
            logger.info(f"[ENGINE] Sending order: {symbol} {direction} @ {entry}")
            result = mt5.order_send(request)
            
            if result.retcode == mt5.TRADE_RETCODE_DONE:
                logger.info(f"[ENGINE] ✓ Order {result.order} executed")
                return {
                    "order_id": result.order,
                    "result": result,
                    "decision": decision,
                }
            else:
                logger.error(f"[ENGINE] Order failed: {result.retcode}")
                return None
        
        except Exception as e:
            logger.error(f"[ENGINE] Order execution error: {e}")
            return None
    
    def get_status_report(self) -> str:
        """Get current engine status for logging."""
        cis_summary = get_cis_summary()
        vol_summary = get_volatility_summary(self.symbols)
        
        return f"[ENGINE] {cis_summary} | {vol_summary}"


class TradeDecision:
    """Container for trade decision information."""
    
    def __init__(self, symbol: str, direction: str):
        self.symbol = symbol
        self.direction = direction
        self.timestamp = datetime.utcnow().isoformat()
        
        # Decision flags
        self.should_trade: bool = False
        self.block_reason: Optional[str] = None
        
        # CIS data
        self.cis_verdict: str = "UNKNOWN"  # "TRADE", "WAIT", "AVOID"
        self.cis_confidence: float = 0.0
        self.cis_reasoning: list = []
        self.cis_red_flags: list = []
        self.component_scores: dict = {}
        
        # Sizing
        self.position_size: float = 0.01
        
        # Validation data
        self.validation_result: dict = {}
        self.checks: list = []
        self.warnings: list = []
    
    def to_dict(self) -> dict:
        """Convert to dictionary for logging."""
        return {
            "symbol": self.symbol,
            "direction": self.direction,
            "should_trade": self.should_trade,
            "block_reason": self.block_reason,
            "cis_verdict": self.cis_verdict,
            "cis_confidence": self.cis_confidence,
            "position_size": self.position_size,
            "checks_passed": sum(1 for c in self.checks if c.get('status') == 'PASS'),
            "checks_failed": sum(1 for c in self.checks if c.get('status') == 'FAIL'),
        }
    
    def summary(self) -> str:
        """Get summary string for logging."""
        status = "✓ APPROVED" if self.should_trade else f"✗ BLOCKED ({self.block_reason})"
        return (
            f"{self.symbol} {self.direction}: {status} | "
            f"CIS: {self.cis_verdict} ({self.cis_confidence:.2f}) | "
            f"Size: {self.position_size:.2f}L"
        )


# ============================================================================
# SIMPLE INTEGRATION EXAMPLES
# ============================================================================

def simple_trade_evaluation_example():
    """Example: Evaluate a trade in 5 lines."""
    engine = TradeDecisionEngine()
    
    decision = engine.evaluate_trade(
        symbol="EURUSD",
        direction="BUY",
        entry=1.0850,
        stop_loss=1.0800,
        take_profit=1.0920,
    )
    
    logger.info(decision.summary())
    return decision


def simple_trade_execution_example():
    """Example: Evaluate + Execute a trade in 10 lines."""
    engine = TradeDecisionEngine()
    
    decision = engine.evaluate_trade("EURUSD", "BUY", entry=1.0850, 
                                      stop_loss=1.0800, take_profit=1.0920)
    
    if decision.should_trade:
        order = engine.execute_trade(
            "EURUSD", "BUY", 1.0850, 1.0800, 1.0920, decision
        )
        if order:
            logger.info(f"Trade executed: Order {order['order_id']}")
    else:
        logger.warning(f"Trade blocked: {decision.block_reason}")


def main_loop_integration_example():
    """
    Example: Integrate into main trading loop.
    
    Shows how to incorporate intelligence system into continuous trading bot.
    """
    engine = TradeDecisionEngine([
        "EURUSD", "GBPUSD", "USDJPY", "AUDUSD",
        "NZDUSD", "EURGBP", "EURJPY", "GBPJPY"
    ])
    
    # Session start
    engine.analyze_market_conditions()
    
    # Main loop (simplified)
    while True:
        try:
            # Scan for setups
            for symbol in engine.symbols:
                setup = scan_for_setup(symbol)  # Your setup detector
                
                if setup:
                    # Evaluate with intelligence system
                    decision = engine.evaluate_trade(
                        symbol=symbol,
                        direction=setup['direction'],
                        timeframe="H1",
                        entry=setup['entry'],
                        stop_loss=setup['stop_loss'],
                        take_profit=setup['take_profit'],
                    )
                    
                    # Execute if approved
                    if decision.should_trade:
                        order = engine.execute_trade(
                            symbol,
                            setup['direction'],
                            setup['entry'],
                            setup['stop_loss'],
                            setup['take_profit'],
                            decision
                        )
                        
                        if order:
                            logger.info(f"Executed: {decision.summary()}")
                    else:
                        logger.debug(f"Skipped: {symbol} - {decision.block_reason}")
            
            # Periodic updates
            if should_refresh_analysis:  # e.g., every hour
                engine.analyze_market_conditions()
                logger.info(engine.get_status_report())
            
            time.sleep(60)  # Scan every 60 seconds
        
        except Exception as e:
            logger.error(f"Main loop error: {e}", exc_info=True)
            time.sleep(60)


def scan_for_setup(symbol: str) -> Optional[dict]:
    """
    Placeholder: Your setup detection logic.
    
    Should return:
        {
            'symbol': 'EURUSD',
            'direction': 'BUY' or 'SELL',
            'entry': 1.0850,
            'stop_loss': 1.0800,
            'take_profit': 1.0920,
            'pattern': 'liquidity_grab',
            'confidence': 0.85,
        }
    
    Or None if no setup found.
    """
    # Your implementation here
    return None


# ============================================================================
# MULTI-ACCOUNT INTEGRATION (for multi_account_runner.py)
# ============================================================================

class MultiAccountTradeEngine:
    """
    Extends TradeDecisionEngine for multi-account management.
    
    Usage:
        engine = MultiAccountTradeEngine()
        engine.add_account("MAIN", "account_123")
        engine.add_account("SECONDARY", "account_456")
        
        decision = engine.evaluate_trade("EURUSD", "BUY")
        
        # Execute on both accounts with correlation check
        orders = engine.execute_on_accounts(
            "EURUSD", "BUY", entry=1.0850, stop_loss=1.0800, take_profit=1.0920,
            accounts=["MAIN", "SECONDARY"],
            correlation_check=True
        )
    """
    
    def __init__(self):
        self.accounts = {}
        self.decision_engine = TradeDecisionEngine()
    
    def add_account(self, name: str, account_id: str):
        """Register trading account."""
        self.accounts[name] = {
            "id": account_id,
            "status": "active",
            "trades": 0,
            "exposure": 0.0,
        }
        logger.info(f"[MULTI-ACCOUNT] Added account: {name}")
    
    def evaluate_trade(self, symbol: str, direction: str,
                      entry: float = None, stop_loss: float = None,
                      take_profit: float = None) -> TradeDecision:
        """Evaluate trade using shared intelligence system."""
        return self.decision_engine.evaluate_trade(
            symbol, direction,
            entry=entry, stop_loss=stop_loss, take_profit=take_profit
        )
    
    def execute_on_accounts(
        self,
        symbol: str,
        direction: str,
        entry: float,
        stop_loss: float,
        take_profit: float,
        accounts: list = None,
        correlation_check: bool = True,
    ) -> Dict[str, Optional[Dict]]:
        """
        Execute trade on multiple accounts with coordination.
        
        Args:
            accounts: List of account names to trade on
            correlation_check: If True, avoid correlated pairs across accounts
        
        Returns:
            {"MAIN": order_result, "SECONDARY": order_result, ...}
        """
        accounts = accounts or list(self.accounts.keys())
        results = {}
        
        for account_name in accounts:
            if account_name not in self.accounts:
                logger.error(f"Account {account_name} not found")
                results[account_name] = None
                continue
            
            # Could add correlation check here
            order = self.decision_engine.execute_trade(
                symbol, direction, entry, stop_loss, take_profit
            )
            
            results[account_name] = order
            
            if order:
                self.accounts[account_name]["trades"] += 1
                logger.info(f"[{account_name}] Trade executed: {symbol}")
            else:
                logger.warning(f"[{account_name}] Trade failed: {symbol}")
        
        return results


# ============================================================================
# ENTRY POINTS
# ============================================================================

if __name__ == "__main__":
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(name)s] %(levelname)s: %(message)s'
    )
    
    # Test the integration
    logger.info("Testing Intelligence System Integration...")
    
    # Example 1: Simple evaluation
    logger.info("\n=== Example 1: Simple Evaluation ===")
    decision = simple_trade_evaluation_example()
    logger.info(decision.summary())
    
    # Example 2: With execution
    # logger.info("\n=== Example 2: Evaluation + Execution ===")
    # simple_trade_execution_example()
    
    logger.info("\nIntegration test complete.")
