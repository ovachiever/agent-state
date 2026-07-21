"""Command-line entry point: summarize a measurements file."""

import argparse

from flowline.transforms import consolidate_partition_metrics


def summarize(rows):
    """One-line human summary of folded partition totals."""
    totals = consolidate_partition_metrics(rows)
    grand = round(sum(totals.values()), 2)
    return f"{len(totals)} partitions, grand total {grand:.2f}"


def load_measurements(path):
    """Parse `partition,value` lines into measurement pairs."""
    rows = []
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            partition, _, value = line.partition(",")
            rows.append((partition.strip(), float(value)))
    return rows


def main(argv=None):
    parser = argparse.ArgumentParser(prog="flowline")
    parser.add_argument("measurements", help="csv of partition,value lines")
    args = parser.parse_args(argv)
    print(summarize(load_measurements(args.measurements)))


if __name__ == "__main__":
    main()
