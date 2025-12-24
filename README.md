# Demo Bot - Twelve Data Integration

This project demonstrates a Clean Architecture approach for consuming the Twelve Data API to retrieve OHLCV market data across multiple timeframes, including historical queries for swing memory and validation workflows.

## Project Layout

```
domain/          # Entities, value objects, and domain services
application/     # Use cases and policies
infrastructure/  # Integrations such as the Twelve Data provider and logging
interfaces/      # Controllers and presenters
main.py          # Dependency orchestration
```

## Requirements

- Python 3.11+
- A Twelve Data API key (`TWELVEDATA_API_KEY`)

Install dependencies:

```bash
pip install -r requirements.txt
```

## Usage

Fetch the latest candles (default):

```bash
export TWELVEDATA_API_KEY="your-api-key"
python main.py --symbol AAPL --timeframe 1min --count 5
```

Fetch historical candles within a window:

```bash
python main.py --symbol AAPL --timeframe 15min --historical --start 2024-01-01T00:00:00 --end 2024-01-02T00:00:00 --limit 100
```

## Testing

Run the test suite with:

```bash
pytest
```

## Docker

Build the image:

```bash
docker build -t demo-bot .
```

Run the container (example):

```bash
docker run --rm \
  -e TWELVEDATA_API_KEY="your-api-key" \
  -e APP_ENV=PROD \
  demo-bot \
  --symbol AAPL --timeframe 1min --count 5
```

Configuration is environment-driven:

- `APP_ENV`: `DEV`, `PAPER`, or `PROD` (default: `DEV`).
- `TWELVEDATA_API_KEY`: required Twelve Data API key.
- `TWELVEDATA_BASE_URL`: optional override of the Twelve Data API base URL.
- `LOG_LEVEL`: logging verbosity (e.g., `INFO`, `DEBUG`).
