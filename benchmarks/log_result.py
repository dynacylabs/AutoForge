#!/usr/bin/env python3
"""Append one row to results.tsv in the required tab-separated format.

Columns: commit  execution_time  loss  memory_gb  status  description

Usage:
    python benchmarks/log_result.py --commit a1b2c3d --exec-time 1.11341 \
        --loss 0.997900 --mem 44.0 --status keep --description "baseline"
"""
import argparse
import os

RESULTS_PATH = os.path.join(os.path.dirname(__file__), "..", "results.tsv")
HEADER = "commit\texecution_time\tloss\tmemory_gb\tstatus\tdescription\n"


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--commit", required=True)
    p.add_argument("--exec-time", required=True, type=float)
    p.add_argument("--loss", required=True, type=float)
    p.add_argument("--mem", required=True, type=float)
    p.add_argument("--status", required=True, choices=["keep", "discard", "crash"])
    p.add_argument("--description", required=True)
    args = p.parse_args()

    if "\t" in args.description:
        raise ValueError("description must not contain tab characters")

    exists = os.path.exists(RESULTS_PATH)
    with open(RESULTS_PATH, "a") as f:
        if not exists:
            f.write(HEADER)
        f.write(
            f"{args.commit}\t{args.exec_time:.5f}\t{args.loss:.6f}\t"
            f"{args.mem:.5f}\t{args.status}\t{args.description}\n"
        )
    print(f"Logged: {args.commit} {args.status} {args.description}")


if __name__ == "__main__":
    main()
