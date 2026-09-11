import random

import pytest

from babble.__main__ import main
from babble.model import MarkovModel
from babble.storage import load_model, save_model

CORPUS = """the quick brown fox jumps over the lazy dog
the quick brown fox runs away from the dog
a lazy dog sleeps all day
"""


def test_train_builds_expected_states():
    model = MarkovModel(order=2)
    model.train("the quick brown fox\n")
    assert model.chain[("the", "quick")]["brown"] == 1
    assert model.chain[("quick", "brown")]["fox"] == 1
    assert model.starts[("the", "quick")] == 1


def test_train_skips_lines_shorter_than_order():
    model = MarkovModel(order=3)
    model.train("too short\n")
    assert model.chain == {}
    assert model.starts == {}


def test_train_counts_repeated_transitions():
    model = MarkovModel(order=1)
    model.train("a b\na c\na b\n")
    assert model.chain[("a",)]["b"] == 2
    assert model.chain[("a",)]["c"] == 1


def test_generate_is_deterministic_with_seeded_rng():
    model = MarkovModel(order=2)
    model.train(CORPUS)
    text1 = model.generate(length=15, rng=random.Random(42))
    text2 = model.generate(length=15, rng=random.Random(42))
    assert text1 == text2


def test_generate_respects_explicit_seed_words():
    model = MarkovModel(order=2)
    model.train(CORPUS)
    text = model.generate(length=6, seed="the quick", rng=random.Random(1))
    assert text.startswith("the quick")


def test_generate_rejects_wrong_length_seed():
    model = MarkovModel(order=2)
    model.train(CORPUS)
    with pytest.raises(ValueError):
        model.generate(seed="onlyone")


def test_generate_on_empty_model_returns_empty_string():
    model = MarkovModel(order=2)
    assert model.generate() == ""


def test_vocab_size_counts_distinct_words():
    model = MarkovModel(order=1)
    model.train("a b c\nb c a\n")
    assert model.vocab_size() == 3


def test_save_and_load_round_trip(tmp_path):
    model = MarkovModel(order=2)
    model.train(CORPUS)
    path = tmp_path / "model.json"
    save_model(model, path)
    loaded = load_model(path)
    assert loaded.order == model.order
    assert loaded.vocab_size() == model.vocab_size()
    text1 = model.generate(length=10, rng=random.Random(7))
    text2 = loaded.generate(length=10, rng=random.Random(7))
    assert text1 == text2


def test_cli_train_generate_info_end_to_end(tmp_path, capsys):
    corpus_path = tmp_path / "corpus.txt"
    corpus_path.write_text(CORPUS)
    model_path = tmp_path / "model.json"

    main(["train", str(corpus_path), "--order", "2", "--out", str(model_path)])
    capsys.readouterr()

    assert model_path.exists()

    main(["info", str(model_path)])
    info_out = capsys.readouterr().out
    assert "order: 2" in info_out

    main(["generate", str(model_path), "--length", "8", "--seed", "the quick"])
    gen_out = capsys.readouterr().out
    assert gen_out.startswith("the quick")


def test_cli_generate_bad_seed_prints_clean_error_not_traceback(tmp_path, capsys):
    corpus_path = tmp_path / "corpus.txt"
    corpus_path.write_text(CORPUS)
    model_path = tmp_path / "model.json"
    main(["train", str(corpus_path), "--out", str(model_path)])
    capsys.readouterr()

    exit_code = main(["generate", str(model_path), "--seed", "onlyoneword"])
    err = capsys.readouterr().err
    assert exit_code == 1
    assert "error:" in err


def test_cli_generate_multiple_count(tmp_path, capsys):
    corpus_path = tmp_path / "corpus.txt"
    corpus_path.write_text(CORPUS)
    model_path = tmp_path / "model.json"
    main(["train", str(corpus_path), "--out", str(model_path)])
    capsys.readouterr()

    main(["generate", str(model_path), "--count", "3", "--length", "5"])
    lines = [l for l in capsys.readouterr().out.splitlines() if l]
    assert len(lines) == 3
