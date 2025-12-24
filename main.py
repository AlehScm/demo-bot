import argparse
import os
from datetime import datetime

from application.policies.timeframe_policy import TimeframePolicy
from application.use_cases.fetch_historical_ohlcv import FetchHistoricalOHLCV
from application.use_cases.fetch_latest_ohlcv import FetchLatestOHLCV
from domain.value_objects.timeframe import Timeframe
from infrastructure.data_providers.twelve_data_client import TwelveDataClient
from infrastructure.storage.logging.logger import get_logger
from interfaces.controllers.market_data_controller import MarketDataController
from interfaces.presenters.console_presenter import format_candles


def build_controller(api_key: str) -> MarketDataController:
    timeframe_policy = TimeframePolicy()
    data_provider = TwelveDataClient(api_key=api_key)

    fetch_latest = FetchLatestOHLCV(
        market_data_service=data_provider,
        timeframe_policy=timeframe_policy,
    )
    fetch_historical = FetchHistoricalOHLCV(
        market_data_service=data_provider,
        timeframe_policy=timeframe_policy,
    )

    return MarketDataController(fetch_latest=fetch_latest, fetch_historical=fetch_historical)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fetch OHLCV data from Twelve Data.")
    parser.add_argument("--symbol", required=True, help="Asset symbol (e.g., AAPL, BTC/USD).")
    parser.add_argument(
        "--timeframe",
        default=Timeframe.ONE_MINUTE.value,
        help=f"Timeframe (options: {[tf.value for tf in Timeframe]}).",
    )
    parser.add_argument("--latest", action="store_true", help="Fetch the latest candles (default).")
    parser.add_argument("--historical", action="store_true", help="Fetch historical candles.")
    parser.add_argument("--count", type=int, default=5, help="Number of recent candles to fetch.")
    parser.add_argument("--start", help="Start datetime (ISO 8601).")
    parser.add_argument("--end", help="End datetime (ISO 8601).")
    parser.add_argument(
        "--limit",
        type=int,
        help="Maximum number of historical candles to fetch when using --historical.",
    )
    return parser.parse_args()


def main() -> None:
    logger = get_logger(__name__)
    api_key = os.getenv("TWELVEDATA_API_KEY")
    if not api_key:
        logger.error("TWELVEDATA_API_KEY environment variable is required.")
        raise SystemExit(1)

    args = parse_args()
    timeframe = Timeframe(args.timeframe)

    controller = build_controller(api_key=api_key)

    if args.historical:
        start = datetime.fromisoformat(args.start) if args.start else None
        end = datetime.fromisoformat(args.end) if args.end else None
        candles = controller.historical(
            symbol=args.symbol,
            timeframe=timeframe,
            start=start,
            end=end,
            limit=args.limit,
        )
    else:
        candles = controller.latest(symbol=args.symbol, timeframe=timeframe, count=args.count)

    print(format_candles(list(candles)))


if __name__ == "__main__":
    main()
