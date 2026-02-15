"""
Configuration for Tests (pytest)
Like a practice ground for the robot!
"""

import pytest
import sys
import os

# Add the bot directory to the path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

@pytest.fixture
def sample_config():
    """Sample configuration for testing"""
    return {
        "SYMBOLS": ["EURUSD", "GBPUSD"],
        "RISK_PER_TRADE": 1.0,
        "MAX_OPEN_TRADES": 5,
        "BOT_ENABLED": True
    }

@pytest.fixture
def sample_trade():
    """Sample trade for testing"""
    return {
        "symbol": "EURUSD",
        "direction": "buy",
        "entry": 1.0950,
        "sl": 1.0920,
        "tp": 1.0980,
        "lot": 0.1
    }

@pytest.fixture
def sample_market_data():
    """Sample market data for testing"""
    return {
        "symbol": "EURUSD",
        "bid": 1.0945,
        "ask": 1.0946,
        "high": 1.0970,
        "low": 1.0920,
        "volume": 1000000
    }
