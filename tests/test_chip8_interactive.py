from chip8.cpu import CPU
from chip8.interactive import run_interactive, QUIT_KEY, KEY_LAYOUT


def make_recorders():
    frames = []
    bells = []
    sleeps = []
    return frames, bells, sleeps


def test_runs_fixed_number_of_frames_and_ticks_timers():
    cpu = CPU()
    cpu.delay_timer = 5
    frames, bells, sleeps = make_recorders()
    run_interactive(
        cpu, read_keys=lambda: [], render=frames.append, bell=bells.append,
        sleep_fn=sleeps.append, frame_limit=3,
    )
    assert len(frames) == 3
    assert cpu.delay_timer == 2  # ticked once per frame


def test_quit_key_stops_immediately():
    cpu = CPU()
    frames, bells, sleeps = make_recorders()
    keys_per_call = iter([[], [], [QUIT_KEY], ["1"]])
    run_interactive(
        cpu, read_keys=lambda: next(keys_per_call), render=frames.append,
        bell=bells.append, sleep_fn=sleeps.append, frame_limit=None,
    )
    assert len(frames) == 2  # stopped on the 3rd call, before rendering a 3rd frame


def test_key_press_and_release_across_frames():
    cpu = CPU()
    pressed_each_frame = []

    def render(display):
        pressed_each_frame.append(list(cpu.keys))

    keys_per_call = iter([["1"], []])  # held for frame 1, released by frame 2
    run_interactive(
        cpu, read_keys=lambda: next(keys_per_call), render=render, bell=lambda: None,
        sleep_fn=lambda s: None, frame_limit=2,
    )
    hexkey = KEY_LAYOUT["1"]
    assert pressed_each_frame[0][hexkey] is True
    assert pressed_each_frame[1][hexkey] is False


def test_bell_called_only_while_sound_timer_active():
    cpu = CPU()
    cpu.sound_timer = 2
    frames, bells, sleeps = make_recorders()
    run_interactive(
        cpu, read_keys=lambda: [], render=frames.append, bell=lambda: bells.append(1),
        sleep_fn=sleeps.append, frame_limit=3,
    )
    # tick_timers() runs before the bell check each frame, so sound_timer=2
    # decrements to 1 (still >0, bell rings) on frame 1, then to 0 on frame 2
    # (no bell), and stays 0 on frame 3 (no bell) -> exactly one ring total.
    assert bells == [1]


def test_sleep_called_once_per_frame_with_frame_seconds():
    cpu = CPU()
    frames, bells, sleeps = make_recorders()
    run_interactive(
        cpu, read_keys=lambda: [], render=frames.append, bell=bells.append,
        sleep_fn=sleeps.append, frame_limit=4,
    )
    assert len(sleeps) == 4
    assert all(s == 1 / 60 for s in sleeps)


def test_unmapped_key_is_ignored():
    cpu = CPU()
    frames, bells, sleeps = make_recorders()
    run_interactive(
        cpu, read_keys=lambda: ["g"], render=frames.append, bell=bells.append,
        sleep_fn=sleeps.append, frame_limit=1,
    )
    assert not any(cpu.keys)
