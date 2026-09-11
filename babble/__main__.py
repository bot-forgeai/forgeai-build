import argparse
import sys

from .model import MarkovModel
from .storage import load_model, save_model


def cmd_train(args):
    model = MarkovModel(order=args.order, unit=args.unit)
    for corpus_path in args.corpus:
        with open(corpus_path) as f:
            model.train(f.read())
    save_model(model, args.out)
    print(f"trained order-{args.order} {args.unit}-level model on {len(args.corpus)} file(s) "
          f"-> {args.out} ({model.vocab_size()} distinct {args.unit}s, "
          f"{len(model.chain)} states)")


def cmd_generate(args):
    model = load_model(args.model)
    try:
        for _ in range(args.count):
            text = model.generate(
                length=args.length, seed=args.seed, temperature=args.temperature
            )
            if not text:
                print("(model has no training data to generate from)", file=sys.stderr)
                return 1
            print(text)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


def cmd_merge(args):
    if len(args.models) < 2:
        print("error: merge requires at least two model files", file=sys.stderr)
        return 1
    models = [load_model(path) for path in args.models]
    merged = models[0]
    try:
        for other in models[1:]:
            merged.merge(other)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    save_model(merged, args.out)
    print(f"merged {len(args.models)} model(s) -> {args.out} "
          f"({merged.vocab_size()} distinct words, {len(merged.chain)} states)")
    return 0


def cmd_info(args):
    model = load_model(args.model)
    print(f"order: {model.order}")
    print(f"unit: {model.unit}")
    print(f"distinct {model.unit}s: {model.vocab_size()}")
    print(f"states: {len(model.chain)}")
    print(f"sentence starts: {len(model.starts)}")


def main(argv=None):
    parser = argparse.ArgumentParser(prog="babble", description="Word-level Markov chain text generator")
    sub = parser.add_subparsers(dest="command", required=True)

    p_train = sub.add_parser("train", help="train a model from one or more text files")
    p_train.add_argument("corpus", nargs="+", help="text file(s) to train on")
    p_train.add_argument("--order", type=int, default=2, help="Markov chain order (default: 2)")
    p_train.add_argument("--unit", choices=["word", "char"], default="word",
                          help="tokenize by whole words or individual characters (default: word)")
    p_train.add_argument("--out", default="model.json", help="path to write the trained model (default: model.json)")
    p_train.set_defaults(func=cmd_train)

    p_gen = sub.add_parser("generate", help="generate text from a trained model")
    p_gen.add_argument("model", help="path to a trained model file")
    p_gen.add_argument("--length", type=int, default=50, help="max words to generate (default: 50)")
    p_gen.add_argument("--seed", default=None, help="starting words (must match the model's order)")
    p_gen.add_argument("--count", type=int, default=1, help="number of lines to generate (default: 1)")
    p_gen.add_argument("--temperature", type=float, default=1.0,
                        help="sampling temperature: <1 more predictable, >1 more random (default: 1.0)")
    p_gen.set_defaults(func=cmd_generate)

    p_merge = sub.add_parser("merge", help="combine two or more trained models (must share the same order)")
    p_merge.add_argument("models", nargs="+", help="paths to trained model files to merge")
    p_merge.add_argument("--out", default="merged.json", help="path to write the merged model (default: merged.json)")
    p_merge.set_defaults(func=cmd_merge)

    p_info = sub.add_parser("info", help="show stats about a trained model")
    p_info.add_argument("model", help="path to a trained model file")
    p_info.set_defaults(func=cmd_info)

    args = parser.parse_args(argv)
    return args.func(args) or 0


if __name__ == "__main__":
    sys.exit(main())
