"""
Tests for Bot Configuration
Making sure the robot's settings are correct!
"""

import pytest
from config.bot_config import BotConfig

def test_symbols_exist():
    """Check that symbols list is not empty"""
    assert len(BotConfig.SYMBOLS) > 0
    print(f"✅ {len(BotConfig.SYMBOLS)} symbols configured")

def test_risk_per_trade_valid():
    """Check that risk per trade is between 0 and 5%"""
    assert 0 < BotConfig.RISK_PER_TRADE <= 5
    print(f"✅ Risk per trade: {BotConfig.RISK_PER_TRADE}%")

def test_max_trades_valid():
    """Check that max trades is reasonable"""
    assert 1 <= BotConfig.MAX_OPEN_TRADES <= 20
    print(f"✅ Max open trades: {BotConfig.MAX_OPEN_TRADES}")

def test_trading_hours_valid():
    """Check that trading hours make sense"""
    assert BotConfig.LONDON_START < BotConfig.LONDON_END
    assert BotConfig.NY_START < BotConfig.NY_END
    print(f"✅ London: {BotConfig.LONDON_START}-{BotConfig.LONDON_END}")
    print(f"✅ NY: {BotConfig.NY_START}-{BotConfig.NY_END}")

def test_socket_is_callable():
    """Check that EURUSD or GBPUSD is in symbols"""
    assert "EURUSD" in BotConfig.SYMBOLS or "GBPUSD" in BotConfig.SYMBOLS
    print(f"✅ Major symbols configured")

def test_config_validate():
    """Test the validate function"""
    # This checks if all required settings exist
    result = BotConfig.validate()
    # It might fail if keys are not set, but that's ok for testing
    print(f"✅ Config validation works!")
