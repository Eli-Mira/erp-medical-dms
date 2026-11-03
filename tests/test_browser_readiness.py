"""Control plumbing must not weaken the browser tests' original oracles."""

import pytest
from browser_readiness import wait_for_held


class PageProbe:
    def __init__(self, counts=None):
        self.bindings = {}
        self.counts = counts or {}
        self.waits = []

    def expose_function(self, name, callback):
        assert name not in self.bindings, "A repeated wait must reuse its binding"
        self.bindings[name] = callback

    def wait_for_function(self, expression, *, polling, timeout):
        self.waits.append((expression, polling, timeout))

    def evaluate(self, expression):
        return self.counts[expression]


def test_ready_with_multiple_routes_keeps_exact_count_oracle_with_caller():
    page, held = PageProbe(), [object(), object()]
    wait_for_held(page, held)
    assert len(held) == 2
    assert page.waits[0][1:] == (20, 10000)


def test_repeated_wait_reuses_the_live_binding():
    page, held = PageProbe(), [object()]
    wait_for_held(page, held)
    held.append(object())
    wait_for_held(page, held, count=2)
    assert len(page.bindings) == 1
    assert next(iter(page.bindings.values()))() == 2


def test_two_retained_lists_have_distinct_bindings():
    page, first, second = PageProbe(), [object()], [object(), object()]
    wait_for_held(page, first)
    wait_for_held(page, second, count=2)
    assert sorted(getter() for getter in page.bindings.values()) == [1, 2]


def test_empty_list_cannot_pass_vacuously_when_a_wait_returns():
    with pytest.raises(AssertionError):
        wait_for_held(PageProbe(), [])


def test_browser_owned_held_callback_count_uses_same_bounded_poll():
    expression = "window.__heldHomeFrames.length"
    page = PageProbe({expression: 4})
    wait_for_held(page, expression, count=4)
    assert page.bindings == {}
    assert page.waits[0][1:] == (20, 10000)


def test_a_zero_requested_count_cannot_make_readiness_vacuous():
    with pytest.raises(AssertionError):
        wait_for_held(PageProbe(), [], count=0)
