# tests/test_run_step.py
from generate_report import run_step, _items_count


def test_run_step_ok_with_list():
    step, value = run_step("posty", lambda: [1, 2, 3])
    assert step.name == "posty"
    assert step.status == "ok"
    assert step.items_count == 3
    assert step.error is None
    assert value == [1, 2, 3]
    assert step.duration_s >= 0.0


def test_run_step_failed_returns_none_value():
    def boom():
        raise RuntimeError("bang")
    step, value = run_step("krok", boom)
    assert step.status == "failed"
    assert step.error == "bang"
    assert value is None
    assert step.items_count == 0


def test_run_step_passes_args_kwargs():
    def add(a, b, c=0):
        return a + b + c
    step, value = run_step("sum", add, 1, 2, c=3)
    assert step.status == "ok"
    assert value == 6


def test_items_count_handles_types():
    assert _items_count(None) == 0
    assert _items_count([1, 2]) == 2
    assert _items_count({"a": 1}) == 1
    assert _items_count("hello") == 0
    assert _items_count(42) == 0
