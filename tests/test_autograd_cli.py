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


def test_cli_train_save_then_predict_round_trips(tmp_path, capsys):
    model_path = str(tmp_path / "model.json")
    code = run(["train", "--dataset", "xor", "--epochs", "300", "--lr", "0.5", "--seed", "42",
                "--save", model_path])
    out = capsys.readouterr().out
    assert code == 0
    assert f"saved model to {model_path}" in out

    code = run(["predict", model_path, "0.0", "0.0"])
    out = capsys.readouterr().out
    assert code == 0
    assert float(out.strip()) < 0.5  # xor(0,0) == 0

    code = run(["predict", model_path, "1.0", "0.0"])
    out = capsys.readouterr().out
    assert code == 0
    assert float(out.strip()) > 0.5  # xor(1,0) == 1


def test_cli_predict_missing_file_errors_cleanly(capsys):
    code = run(["predict", "/tmp/does-not-exist-autograd-model.json", "1.0", "1.0"])
    err = capsys.readouterr().err
    assert code == 1
    assert "error:" in err


def test_cli_batch_size_trains_successfully(capsys):
    code = run(["train", "--dataset", "xor", "--epochs", "300", "--lr", "0.5", "--seed", "42",
                "--batch-size", "2"])
    out = capsys.readouterr().out
    assert code == 0
    assert "accuracy:   100.0%" in out


def test_cli_invalid_batch_size_errors_cleanly(capsys):
    code = run(["train", "--dataset", "xor", "--epochs", "5", "--batch-size", "0"])
    err = capsys.readouterr().err
    assert code == 1
    assert "error:" in err


def test_cli_predict_wrong_input_count_errors_cleanly(tmp_path, capsys):
    model_path = str(tmp_path / "model.json")
    run(["train", "--dataset", "xor", "--epochs", "10", "--save", model_path])
    capsys.readouterr()

    code = run(["predict", model_path, "1.0", "2.0", "3.0"])
    err = capsys.readouterr().err
    assert code == 1
    assert "expects 2 input" in err
