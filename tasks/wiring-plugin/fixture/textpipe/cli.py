"""Apply a transform to text from the command line."""

import argparse

from textpipe.registry import REGISTRY, get_transform

EPILOG = "available transforms: lower, squeeze, titlecase"


def build_parser():
    parser = argparse.ArgumentParser(prog="textpipe", epilog=EPILOG)
    parser.add_argument("transform", choices=sorted(REGISTRY))
    parser.add_argument("text")
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    print(get_transform(args.transform).apply(args.text))


if __name__ == "__main__":
    main()
