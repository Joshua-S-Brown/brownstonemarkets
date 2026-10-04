import argparse
import sys
from pathlib import Path

from .pipeline import read_config, run


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="TSM snapshot and opportunity screening")
    parser.add_argument("--config", type=Path, default=Path(__file__).resolve().parents[1] / "config/market.toml")
    parser.add_argument("--input", type=Path, help="Use a local TSM CSV instead of downloading")
    parser.add_argument("--market", help="Configured market ID (defaults to the first source)")
    args = parser.parse_args()
    try:
        config = read_config(args.config)
        if args.market:
            matches = [source for source in config.get("sources", [config]) if source["market_id"] == args.market]
            if not matches:
                raise ValueError(f"Unknown market: {args.market}")
            config = matches[0]
        result, output = run(config, args.input)
    except Exception as error:
        print(f"Pipeline failed: {error}", file=sys.stderr)
        sys.exit(1)
    print(result.select("rank", "item_id", "item_name", "buy_gold", "discount", "net_spread_gold"))
    print(f"Saved {result.height} screening candidates to {output}")
