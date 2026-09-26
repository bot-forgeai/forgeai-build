import argparse
import sys
from importlib.metadata import version as _get_version, PackageNotFoundError

from .datasets import DATASETS
from .lr_schedule import SCHEDULE_NAMES
from .nn import MLP
from .optim import OPTIMIZERS
from .train import accuracy, predict, train


def _get_package_version():
    try:
        return _get_version("eulerlib")
    except PackageNotFoundError:
        return "0.1.0"


def cmd_train(args):
    if args.dataset not in DATASETS:
        print(f"error: unknown dataset {args.dataset!r} (choices: {', '.join(DATASETS)})", file=sys.stderr)
        return 1
    xs, ys = DATASETS[args.dataset](n=args.n, seed=args.seed)

    sizes = [len(xs[0])] + args.hidden + [1]
    model = MLP(sizes, activation="tanh", out_activation="sigmoid", seed=args.seed)

    log_every = max(1, args.epochs // 10) if args.verbose else None
    try:
        history = train(model, xs, ys, epochs=args.epochs, lr=args.lr, log_every=log_every,
                         optimizer=args.optimizer, batch_size=args.batch_size, seed=args.seed,
                         lr_schedule=args.lr_schedule, lr_decay=args.lr_decay,
                         lr_step_size=args.lr_step_size)
    except ValueError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1

    acc = accuracy(model, xs, ys)
    print(f"final loss: {history[-1]:.4f}")
    print(f"accuracy:   {acc * 100:.1f}%")

    if args.save:
        model.save(args.save)
        print(f"saved model to {args.save}")
    return 0


def cmd_predict(args):
    try:
        model = MLP.load(args.model)
    except (OSError, ValueError, KeyError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1

    if len(args.x) != model.sizes[0]:
        print(f"error: model expects {model.sizes[0]} input(s), got {len(args.x)}", file=sys.stderr)
        return 1

    out = predict(model, args.x)
    print(f"{out.data:.4f}")
    return 0


def build_parser():
    parser = argparse.ArgumentParser(prog="autograd", description="Tiny scalar autograd engine + MLP trainer")
    parser.add_argument("--version", action="version", version=_get_package_version())
    sub = parser.add_subparsers(dest="command", required=True)

    p_train = sub.add_parser("train", help="train an MLP on a synthetic dataset")
    p_train.add_argument("--dataset", default="xor", help="xor, blobs, or circles (default: xor)")
    p_train.add_argument("--hidden", type=int, nargs="*", default=[4], help="hidden layer sizes (default: 4)")
    p_train.add_argument("--epochs", type=int, default=200)
    p_train.add_argument("--lr", type=float, default=0.5)
    p_train.add_argument("--optimizer", choices=sorted(OPTIMIZERS), default="sgd",
                          help="update rule (default: sgd; adam typically wants a smaller --lr, e.g. 0.05)")
    p_train.add_argument("--batch-size", type=int, default=None,
                          help="mini-batch size (default: full-batch, one step per epoch)")
    p_train.add_argument("--lr-schedule", choices=SCHEDULE_NAMES, default="constant",
                          help="how --lr changes over training (default: constant)")
    p_train.add_argument("--lr-decay", type=float, default=0.5,
                          help="multiplicative factor per step for --lr-schedule step (default: 0.5)")
    p_train.add_argument("--lr-step-size", type=int, default=None,
                          help="epochs per decay step for --lr-schedule step (default: epochs // 5)")
    p_train.add_argument("--n", type=int, default=60, help="number of points for blobs/circles")
    p_train.add_argument("--seed", type=int, default=42)
    p_train.add_argument("--verbose", action="store_true", help="print loss every ~10% of epochs")
    p_train.add_argument("--save", metavar="PATH", help="save the trained model (architecture + weights) as JSON")
    p_train.set_defaults(func=cmd_train)

    p_predict = sub.add_parser("predict", help="load a saved model and run it on one input")
    p_predict.add_argument("model", help="path to a model JSON file saved via `train --save`")
    p_predict.add_argument("x", type=float, nargs="+", help="input feature values")
    p_predict.set_defaults(func=cmd_predict)

    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()
    sys.exit(args.func(args))


if __name__ == "__main__":
    main()
