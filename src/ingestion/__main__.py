"""
Land upstream exports in the lake.

    python -m src.ingestion                                   # every entity, every date
    python -m src.ingestion --entity conversions --date 2026-11-13
"""
import argparse
import logging

from src.ingestion.loader import ENTITIES, Loader
from src.utils.logging_config import setup_logging


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--entity", choices=list(ENTITIES), action="append",
                        help="Entity to load (repeatable). Default: all.")
    parser.add_argument("--date", help="Load only this partition (YYYY-MM-DD). Default: all dates.")
    parser.add_argument("--source", help="Override the source file (single entity only).")
    args = parser.parse_args()
    if args.source and len(args.entity or []) != 1:
        parser.error("--source needs exactly one --entity")

    setup_logging()
    for entity in args.entity or list(ENTITIES):
        summary = Loader(entity).run(partition_date=args.date, source_path=args.source)
        logging.getLogger("ingestion").info(
            f"{entity:<12} {summary['rows_in']:>9,} rows in   "
            f"{summary['rows_rejected']:>5,} rejected   {summary['partitions']:>3} partition(s)"
        )


if __name__ == "__main__":
    main()
