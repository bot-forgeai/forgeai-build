import json
import os

import pytest

from quest.__main__ import DEFAULT_WORLD, build_arg_parser, run_game
from quest.engine import describe_room, process_command
from quest.parser import parse
from quest.save import load_game, save_game
from quest.world import GameState, WorldError, load_world


@pytest.fixture
def world():
    return load_world(DEFAULT_WORLD)


@pytest.fixture
def state(world):
    return GameState(load_world(DEFAULT_WORLD))


# --- parser ---

def test_parse_direction_shorthand():
    cmd = parse("n")
    assert cmd.verb == "go"
    assert cmd.arg == "north"


def test_parse_go_full_word():
    cmd = parse("go north")
    assert cmd.verb == "go"
    assert cmd.arg == "north"


def test_parse_take_alias():
    cmd = parse("get brass key")
    assert cmd.verb == "take"
    assert cmd.arg == "brass key"


def test_parse_unlock_with_item():
    cmd = parse("unlock east with brass key")
    assert cmd.verb == "unlock"
    assert cmd.arg == "east"
    assert cmd.extra == "brass key"


def test_parse_empty_returns_none():
    assert parse("   ") is None


def test_parse_unknown_verb():
    cmd = parse("dance")
    assert cmd.verb == "unknown"


def test_parse_talk_to():
    cmd = parse("talk to keeper")
    assert cmd.verb == "talk"
    assert cmd.arg == "keeper"


def test_parse_talk_without_to():
    cmd = parse("talk keeper")
    assert cmd.verb == "talk"
    assert cmd.arg == "keeper"


def test_parse_give_to():
    cmd = parse("give torch to keeper")
    assert cmd.verb == "give"
    assert cmd.arg == "torch"
    assert cmd.extra == "keeper"


# --- world loading ---

def test_load_world_missing_start(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({"rooms": {"a": {}}, "start": "nope"}))
    with pytest.raises(WorldError):
        load_world(str(bad))


def test_load_world_no_rooms(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({"rooms": {}}))
    with pytest.raises(WorldError):
        load_world(str(bad))


def test_load_world_normalizes_legacy_single_win_dict(tmp_path):
    path = tmp_path / "legacy.json"
    path.write_text(json.dumps({
        "start": "a",
        "rooms": {"a": {}},
        "win": {"room": "a"},
    }))
    world = load_world(str(path))
    assert world["win"] == [{"room": "a"}]


def test_load_world_defaults_win_to_empty_list(tmp_path):
    path = tmp_path / "nowin.json"
    path.write_text(json.dumps({"start": "a", "rooms": {"a": {}}}))
    world = load_world(str(path))
    assert world["win"] == []


def test_sample_world_loads(world):
    assert world["start"] == "hall"
    assert "library" in world["rooms"]


# --- engine: movement ---

def test_look_describes_room(state):
    result = process_command(state, "look")
    assert "Grand Hall" in result.message
    assert "Exits" in result.message


def test_go_blocked_when_locked(state):
    result = process_command(state, "go east")
    assert "locked" in result.message.lower()
    assert state.current_room == "hall"


def test_go_unknown_direction(state):
    result = process_command(state, "go up")
    assert "can't go" in result.message.lower()


def test_go_moves_between_rooms(state):
    result = process_command(state, "go north")
    assert state.current_room == "library"
    assert "Library" in result.message


# --- engine: items ---

def test_take_and_inventory(state):
    process_command(state, "go north")
    result = process_command(state, "take brass key")
    assert "take" in result.message.lower()
    assert "brass_key" in state.inventory

    inv = process_command(state, "inventory")
    assert "brass key" in inv.message.lower()


def test_take_nonexistent_item(state):
    result = process_command(state, "take dragon")
    assert "nothing like that" in result.message.lower()


def test_take_unmovable_item(state):
    process_command(state, "go north")
    result = process_command(state, "take statue")
    assert "can't take" in result.message.lower()
    assert "statue" not in state.inventory


def test_drop_item(state):
    process_command(state, "go north")
    process_command(state, "take brass key")
    result = process_command(state, "drop brass key")
    assert "brass_key" not in state.inventory
    assert "brass_key" in state.room()["items"]
    assert "drop" in result.message.lower()


def test_examine_item(state):
    process_command(state, "go north")
    result = process_command(state, "examine brass key")
    assert "tarnished" in result.message.lower()


def test_examine_missing_item(state):
    result = process_command(state, "examine nothing")
    assert "don't see" in result.message.lower()


# --- engine: unlocking and winning ---

def test_unlock_with_wrong_item_fails(state):
    # hall's east exit is locked and requires brass_key; torch is in hand but wrong
    process_command(state, "take torch")
    result = process_command(state, "unlock east with torch")
    assert "doesn't unlock" in result.message.lower()
    assert "east" in state.room().get("locked_exits", {})


def test_unlock_nonexistent_direction_fails(state):
    result = process_command(state, "unlock north with brass key")
    assert "nothing to unlock" in result.message.lower()


def test_unlock_and_full_playthrough_wins(state):
    process_command(state, "go north")
    process_command(state, "take brass key")
    process_command(state, "go south")
    result = process_command(state, "unlock east with brass key")
    assert "unlock" in result.message.lower()

    process_command(state, "go east")
    process_command(state, "take treasure")
    process_command(state, "go west")
    result = process_command(state, "go south")
    assert result.won is True
    assert state.flags.get("won") is True


def test_reaching_exit_without_treasure_does_not_win(state):
    result = process_command(state, "go south")
    assert result.won is False


# --- engine: multiple win conditions ---

def test_treasure_ending_is_recorded(state):
    process_command(state, "go north")
    process_command(state, "take brass key")
    process_command(state, "go south")
    process_command(state, "unlock east with brass key")
    process_command(state, "go east")
    process_command(state, "take treasure")
    process_command(state, "go west")
    result = process_command(state, "go south")
    assert result.won is True
    assert state.flags.get("ending") == "treasure_ending"
    assert "glorious victory" in result.message.lower()


def test_alternate_ending_reached_with_different_item(state):
    process_command(state, "take torch")
    process_command(state, "give torch to keeper")  # trades for silver_ring
    result = process_command(state, "go south")
    assert result.won is True
    assert state.flags.get("ending") == "ring_ending"
    assert "modest ending" in result.message.lower()


# --- engine: NPCs ---

def test_describe_room_lists_npc(state):
    result = process_command(state, "look")
    assert "old keeper" in result.message


def test_talk_to_npc_shows_dialogue(state):
    result = process_command(state, "talk to keeper")
    assert "reward" in result.message.lower()


def test_talk_to_missing_npc_fails(state):
    result = process_command(state, "talk to nobody")
    assert "no one like that" in result.message.lower()


def test_give_wrong_item_fails(state):
    process_command(state, "go north")
    process_command(state, "take brass key")
    process_command(state, "go south")
    result = process_command(state, "give brass key to keeper")
    assert "doesn't want" in result.message.lower()
    assert "brass_key" in state.inventory


def test_give_wanted_item_trades(state):
    process_command(state, "take torch")
    result = process_command(state, "give torch to keeper")
    assert "receive" in result.message.lower()
    assert "torch" not in state.inventory
    assert "silver_ring" in state.inventory

    # a second trade attempt is refused, and dialogue reflects the trade
    result = process_command(state, "talk to keeper")
    assert "thank you" in result.message.lower()


def test_give_item_not_carried_fails(state):
    result = process_command(state, "give torch to keeper")
    assert "aren't carrying" in result.message.lower()


# --- save/load ---

def test_save_and_load_roundtrip(state, tmp_path):
    process_command(state, "go north")
    process_command(state, "take brass key")
    save_path = tmp_path / "save.json"
    save_game(state, str(save_path), DEFAULT_WORLD)

    loaded_state, world_path = load_game(str(save_path))
    assert loaded_state.current_room == "library"
    assert "brass_key" in loaded_state.inventory
    assert world_path == DEFAULT_WORLD


def test_save_preserves_unlocked_state(state, tmp_path):
    process_command(state, "go north")
    process_command(state, "take brass key")
    process_command(state, "go south")
    process_command(state, "unlock east with brass key")

    save_path = tmp_path / "save.json"
    save_game(state, str(save_path), DEFAULT_WORLD)
    loaded_state, _ = load_game(str(save_path))

    assert "east" not in loaded_state.room().get("locked_exits", {})


# --- CLI loop ---

def test_run_game_scripted_playthrough_wins(world, capsys):
    state = GameState(world)
    commands = iter([
        "go north", "take brass key", "go south",
        "unlock east with brass key", "go east", "take treasure",
        "go west", "go south",
    ])

    def fake_input(prompt):
        return next(commands)

    outcome = run_game(state, DEFAULT_WORLD, input_fn=fake_input, print_fn=lambda *a: None)
    assert outcome == "won"


def test_run_game_quit():
    state = GameState(load_world(DEFAULT_WORLD))
    commands = iter(["look", "quit"])
    outcome = run_game(state, DEFAULT_WORLD, input_fn=lambda p: next(commands), print_fn=lambda *a: None)
    assert outcome == "quit"


def test_run_game_eof_on_no_input():
    def raise_eof(prompt):
        raise EOFError
    state = GameState(load_world(DEFAULT_WORLD))
    outcome = run_game(state, DEFAULT_WORLD, input_fn=raise_eof, print_fn=lambda *a: None)
    assert outcome == "eof"


def test_run_game_save_command(tmp_path):
    state = GameState(load_world(DEFAULT_WORLD))
    save_path = tmp_path / "mysave.json"
    commands = iter([f"save {save_path}", "quit"])
    messages = []
    outcome = run_game(
        state, DEFAULT_WORLD,
        input_fn=lambda p: next(commands),
        print_fn=lambda m="": messages.append(m),
    )
    assert outcome == "quit"
    assert save_path.exists()
    assert any("saved" in m.lower() for m in messages)


def test_build_arg_parser_play_defaults():
    parser = build_arg_parser()
    args = parser.parse_args(["play"])
    assert args.world == DEFAULT_WORLD
    assert args.load is None
