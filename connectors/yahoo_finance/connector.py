"""
Yahoo Finance connector — Stock quotes and historical data via yfinance.

No API key needed! 🎉
"""

import json

TOOLS = [
    {
        "name": "yahoo_finance_quote",
        "description": "Get the current stock price and key metrics for a ticker symbol (e.g., AAPL, GOOGL, TSLA).",
        "parameters": {
            "type": "object",
            "properties": {
                "symbol": {
                    "type": "string",
                    "description": "Stock ticker symbol (e.g., 'AAPL', 'GOOGL', 'TSLA')",
                },
            },
            "required": ["symbol"],
        },
    },
    {
        "name": "yahoo_finance_history",
        "description": "Get historical stock price data for a ticker symbol.",
        "parameters": {
            "type": "object",
            "properties": {
                "symbol": {
                    "type": "string",
                    "description": "Stock ticker symbol",
                },
                "period": {
                    "type": "string",
                    "description": "Time period: '1d', '5d', '1mo', '3mo', '6mo', '1y', '5y', 'max' (default: '1mo')",
                },
            },
            "required": ["symbol"],
        },
    },
]


def _get_quote(symbol: str) -> str:
    try:
        import yfinance as yf
    except ImportError:
        raise ImportError("yfinance not installed. Run: bash connectors/yahoo_finance/install.sh")

    ticker = yf.Ticker(symbol.upper())
    info = ticker.info

    quote = {
        "symbol": symbol.upper(),
        "name": info.get("longName", info.get("shortName", symbol)),
        "price": info.get("currentPrice", info.get("regularMarketPrice", "N/A")),
        "currency": info.get("currency", "USD"),
        "change": info.get("regularMarketChange", "N/A"),
        "change_percent": info.get("regularMarketChangePercent", "N/A"),
        "volume": info.get("volume", "N/A"),
        "market_cap": info.get("marketCap", "N/A"),
        "52w_high": info.get("fiftyTwoWeekHigh", "N/A"),
        "52w_low": info.get("fiftyTwoWeekLow", "N/A"),
    }
    return json.dumps(quote, indent=2, default=str)


def _get_history(symbol: str, period: str = "1mo") -> str:
    try:
        import yfinance as yf
    except ImportError:
        raise ImportError("yfinance not installed. Run: bash connectors/yahoo_finance/install.sh")

    ticker = yf.Ticker(symbol.upper())
    hist = ticker.history(period=period)

    if hist.empty:
        return f"No historical data found for {symbol}"

    # Convert to list of dicts, keep last 20 entries max
    records = hist.tail(20).reset_index().to_dict("records")
    # Clean up datetime objects
    for r in records:
        for k, v in r.items():
            if hasattr(v, "isoformat"):
                r[k] = v.isoformat()

    return json.dumps(records, indent=2, default=str)


def handle(tool_name: str, args: dict) -> str:
    try:
        if tool_name == "yahoo_finance_quote":
            return _get_quote(args["symbol"])
        elif tool_name == "yahoo_finance_history":
            return _get_history(args["symbol"], args.get("period", "1mo"))
        else:
            return f"Unknown tool: {tool_name}"
    except Exception as e:
        return f"Yahoo Finance error: {e}"
