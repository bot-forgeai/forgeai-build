import pytest

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


def test_cli_cosine_lr_schedule_trains_successfully(capsys):
    code = run(["train", "--dataset", "xor", "--epochs", "300", "--lr", "0.5", "--seed", "42",
                "--lr-schedule", "cosine"])
    out = capsys.readouterr().out
    assert code == 0
    assert "accuracy:   100.0%" in out


def test_cli_step_lr_schedule_prints_decaying_lr_in_verbose(capsys):
    code = run(["train", "--dataset", "xor", "--epochs", "20", "--lr", "1.0", "--seed", "1",
                "--lr-schedule", "step", "--lr-step-size", "5", "--lr-decay", "0.1", "--verbose"])
    out = capsys.readouterr().out
    assert code == 0
    assert "lr=1.0000" in out
    assert "lr=0.0010" in out  # after two decay steps: 1.0 * 0.1 * 0.1


def test_cli_invalid_lr_schedule_errors_cleanly():
    parser = build_parser()
    with pytest.raises(SystemExit) as exc_info:
        parser.parse_args(["train", "--dataset", "xor", "--epochs", "5", "--lr-schedule", "nope"])
    assert exc_info.value.code == 2  # argparse rejects the bad choice itself


def test_cli_predict_wrong_input_count_errors_cleanly(tmp_path, capsys):
    model_path = str(tmp_path / "model.json")
    run(["train", "--dataset", "xor", "--epochs", "10", "--save", model_path])
    capsys.readouterr()

    code = run(["predict", model_path, "1.0", "2.0", "3.0"])
    err = capsys.readouterr().err
    assert code == 1
    assert "expects 2 input" in err


def test_version(capsys):
    parser = build_parser()
    with pytest.raises(SystemExit) as exc_info:
        parser.parse_args(["--version"])
    assert exc_info.value.code == 0
    out = capsys.readouterr().out
    assert "0.1.0" in out or "0.1" in out
