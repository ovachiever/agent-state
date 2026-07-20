"""Command-line entry point."""

import argparse

from warehouse.ops import compute_reorder_point


def summarize(sku_id, daily_demand, lead_time_days, safety_stock):
    point = compute_reorder_point(daily_demand, lead_time_days, safety_stock)
    return f"{sku_id}: reorder at {point:.1f}"


def main(argv=None):
    parser = argparse.ArgumentParser(prog="warehouse")
    parser.add_argument("sku_id")
    parser.add_argument("daily_demand", type=float)
    parser.add_argument("lead_time_days", type=float)
    parser.add_argument("safety_stock", type=float)
    args = parser.parse_args(argv)
    print(summarize(args.sku_id, args.daily_demand, args.lead_time_days, args.safety_stock))


if __name__ == "__main__":
    main()
