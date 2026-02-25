# Yahoo Finance Connector

Connects ClawFounder to financial data using the [yfinance](https://github.com/ranaroussi/yfinance) library.

## What It Does

- Get stock quotes (price, change, volume)
- Get company info
- Get historical data

The best part: **no API key needed.** yfinance is free and open.

## Environment Variables

None! 🎉

## Setup

```bash
cd connectors/yahoo_finance
bash install.sh
```

## Available Tools

| Tool | Description |
|---|---|
| `yahoo_finance_quote` | Get current stock price and key metrics |
| `yahoo_finance_history` | Get historical price data |

## Testing

```bash
python3 -m pytest connectors/yahoo_finance/test_connector.py -v
python3 -m agent.runner --provider gemini
# Ask: "What's the current price of AAPL?"
```
