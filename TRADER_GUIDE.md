# Trading Strategies & Best Practices Guide

## Using the Integrated Trading Bot Platform

This guide is for traders, mentorship instructors, and platform admins who want to maximize the ICT Trading Bot + Jaguar platform.

## Platform Overview

- **ICT Trading Bot**: Fully automated trading based on market structure, liquidity, and order blocks
- **Jaguar Platform**: Dashboard for:
  - Subscription/lifetime access management
  - Real-time trade monitoring via WebSocket
  - Trade analytics and performance metrics
  - Admin controls to start/stop bot

## Trading Strategy (ICT Framework)

### 1. Market Structure Analysis
The bot analyzes price action to identify:
- **Trends**: Bullish (higher highs/lows) or bearish (lower highs/lows)
- **Swing Points**: Key support/resistance levels
- **Order Blocks**: Significant accumulation/distribution zones

### 2. Entry Conditions (All Must Pass)
- ✅ **Session Filter**: Trade only during London & New York hours
- ✅ **Liquidity Confirmation**: Liquidity pools must be taken
- ✅ **FVG & Order Block Alignment**: Entry near Fibonacci or order blocks
- ✅ **SMT Confirmation**: Structure, momentum, trend alignment
- ✅ **Quality Filters**: Rule-based + ML filters must approve

### 3. Risk Management
- **Position Size**: Dynamic based on ATR and portfolio risk
- **Stop Loss**: Below order block or swing point
- **Take Profit**: Multi-level targets using Fibonacci ratios
- **Maximum Risk Per Trade**: Controlled by portfolio allocator

### 4. Symbols Traded
Currently enabled (can add more):
- EURUSD, GBPUSD, USDJPY
- AUDUSD, NZDUSD, USDCAD
- BTCUSD, XAUUSD
- AUDJPY, EURJPY, ETHBTC

## Using the Admin Dashboard

### Real-Time Trade Monitoring
1. Login to `/admin` as super admin
2. Open bot logs (`/admin/bot-logs`)
3. Watch live trades appear as they execute
4. Check WebSocket connection to see live price updates

### Trade Analytics
1. Go to `/admin/analytics`
2. View key metrics:
   - **Win Rate**: % of winning trades
   - **Profit Factor**: Gross profit / Gross loss
   - **Sharpe Ratio**: Risk-adjusted return
   - **Max Drawdown**: Largest peak-to-trough decline
3. Filter by symbol to see performance per pair

### Bot Control
1. Use `/api/admin/bot-control` to start/stop trading
2. Stop before major news events or high-risk periods
3. Monitor P&L throughout the day

### User & Subscription Management
1. View all users in `/admin/users`
2. Toggle lifetime subscription for users who purchased
3. Track payment history in `/admin/payments`

## Performance Expectations

### Typical Trading Profile
- **Trade Frequency**: 2-8 trades per day (depends on market conditions)
- **Average Win**: 30-60 pips
- **Average Loss**: 15-30 pips
- **Win Rate Target**: 55-65% (profitable if large wins > small losses)
- **Monthly P&L**: Varies by market volatility

### Risk Per Trade
- Start with **0.5-1%** risk per trade
- Increase to **2%** once consistent profitability proven
- Never exceed **5%** risk per trade

## Common Issues & Troubleshooting

### Bot Not Trading
- [ ] Check bot is running (healthcheck: GET /bot_api/health)
- [ ] Verify MT5 connection (check bot logs for errors)
- [ ] Verify trading hours (London 08:00-16:00 UTC, NY 13:00-21:00 UTC)
- [ ] Check rules haven't excluded all symbols

### Unexpected Losses
- Monitor **Max Drawdown** metric daily
- Review losing trades in bot logs
- Adjust risk per trade if drawdown > 10%
- Check for news events that caused volatility

### High Slippage
- Slippage happens during news; check Economic Calendar
- Reduce lot size before major news events
- Use pending orders instead of market orders when possible

## Optimization Tips

### For Best Performance
1. **Trade During Liquid Hours**: London + New York overlap (12:00-16:00 UTC)
2. **Focus on Major Pairs**: EURUSD, GBPUSD (tighter spreads, predictable)
3. **Avoid News Events**: Check economic calendar before trading
4. **Monitor Correlation**: Avoid opening multiple positions on correlated pairs
5. **Daily Review**: Spend 10 min reviewing daily P&L and trade quality

### Seasonal Patterns
- **Summer (Jun-Aug)**: Lower volatility, wider spreads
- **Holidays**: Avoid (thin liquidity)
- **Fed/ECB Events**: May increase volatility significantly

## Setup Checklist for Traders

- [ ] Subscribe to Jaguar platform (lifetime access via `/subscribe`)
- [ ] Log in to admin dashboard
- [ ] Verify bot is running and connected to MT5
- [ ] Set account risk parameters (% per trade, max per day)
- [ ] Review sample trades in bot logs
- [ ] Start with micro/small account (risk first)
- [ ] Monitor first week daily
- [ ] Once consistent, increase to standard lot size

## Advanced: Custom Rules & Filters

To modify trading rules, edit:
- `ict_trading_bot/strategy/` — Entry and exit models
- `ict_trading_bot/risk/` — Risk management
- `ict_trading_bot/ml/` — ML filter models

Changes require:
1. Testing in backtest (`ict_trading_bot/backtest/`)
2. Validation on demo account
3. Gradual rollout on live account

## Support & Questions

- Check `/admin/bot-logs` for real-time debugging
- Review `/admin/analytics` for performance insights
- Contact admin for platform issues

---

**Last Updated**: Feb 10, 2026
**Best Practices by**: Professional Traders & System Instructors


