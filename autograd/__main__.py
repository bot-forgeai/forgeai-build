import argparse
import sys

from .datasets import DATASETS
from .nn import MLP
from .optim import OPTIMIZERS
from .train import accuracy, train


def cmd_train(args):
    if args.dataset not in DATASETS:
        print(f"error: unknown dataset {args.dataset!r} (choices: {', '.join(DATASETS)})", file=sys.stderr)
        return 1
    xs, ys = DATASETS[args.dataset](n=args.n, seed=args.seed)

    sizes = [len(xs[0])] + args.hidden + [1]
    model = MLP(sizes, activation="tanh", out_activation="sigmoid", seed=args.seed)

    log_every = max(1, args.epochs // 10) if args.verbose else None
    history = train(model, xs, ys, epochs=args.epochs, lr=args.lr, log_every=log_every, optimizer=args.optimizer)

    acc = accuracy(model, xs, ys)
    print(f"final loss: {history[-1]:.4f}")
    print(f"accuracy:   {acc * 100:.1f}%")
    return 0


def build_parser():
    parser = argparse.ArgumentParser(prog="autograd", description="Tiny scalar autograd engine + MLP trainer")
    sub = parser.add_subparsers(dest="command", required=True)

    p_train = sub.add_parser("train", help="train an MLP on a synthetic dataset")
    p_train.add_argument("--dataset", default="xor", help="xor, blobs, or circles (default: xor)")
    p_train.add_argument("--hidden", type=int, nargs="*", default=[4], help="hidden layer sizes (default: 4)")
    p_train.add_argument("--epochs", type=int, default=200)
    p_train.add_argument("--lr", type=float, default=0.5)
    p_train.add_argument("--optimizer", choices=sorted(OPTIMIZERS), default="sgd",
                          help="update rule (default: sgd; adam typically wants a smaller --lr, e.g. 0.05)")
    p_train.add_argument("--n", type=int, default=60, help="number of points for blobs/circles")
    p_train.add_argument("--seed", type=int, default=42)
    p_train.add_argument("--verbose", action="store_true", help="print loss every ~10% of epochs")
    p_train.set_defaults(func=cmd_train)

    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()
    sys.exit(args.func(args))


if __name__ == "__main__":
    main()
