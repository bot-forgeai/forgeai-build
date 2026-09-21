from autograd.__main__ import build_parser


def run(args_list):
    parser = build_parser()
    args = parser.parse_args(args_list)
    return args.func(args)


def test_cli_trains_xor_to_full_accuracy(capsys):
    code = run(["train", "--dataset", "xor", "--epochs", "300", "--lr", "0.5", "--seed", "42"])
    out = capsys.readouterr().out
    assert code == 0
    assert "accuracy:   100.0%" in out


def test_cli_unknown_dataset_errors_cleanly(capsys):
    code = run(["train", "--dataset", "nope"])
    err = capsys.readouterr().err
    assert code == 1
    assert "unknown dataset" in err


def test_cli_verbose_prints_epoch_progress(capsys):
    run(["train", "--dataset", "xor", "--epochs", "20", "--verbose"])
    out = capsys.readouterr().out
    assert "epoch" in out


def test_cli_blobs_dataset_runs(capsys):
    code = run(["train", "--dataset", "blobs", "--n", "20", "--epochs", "50", "--seed", "1"])
    out = capsys.readouterr().out
    assert code == 0
    assert "final loss" in out
