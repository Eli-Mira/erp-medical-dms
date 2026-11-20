"""Wait for actual retained routes or browser-owned delayed callbacks."""

from itertools import count as _counter
from weakref import WeakKeyDictionary

_bindings = WeakKeyDictionary()
_poll_seq = _counter(1)


def wait_for_held(page, held, *, count=1):
    assert count > 0, "Readiness must require an actual held request"
    if isinstance(held, str):
        predicate = f"() => ({held}) >= {count}"
    else:
        name = f"__heldCount_{id(held):x}"
        names = _bindings.setdefault(page, set())
        if name not in names:
            page.expose_function(name, lambda: len(held))
            names.add(name)
        key = f"p{next(_poll_seq)}"
        predicate = (
            "() => {"
            " const st = (window.__heldPoll ??= {});"
            f" const s = (st[{key!r}] ??= {{ pending: false, val: 0 }});"
            " if (!s.pending) {"
            "   s.pending = true;"
            f"   Promise.resolve(window.{name}()).then("
            "     v => { s.val = v; s.pending = false; },"
            "     () => { s.pending = false; }"
            "   );"
            " }"
            f" if (s.val >= {count}) {{ delete st[{key!r}]; return true; }}"
            " return false;"
            "}"
        )
    page.wait_for_function(predicate, polling=20, timeout=10000)
    actual = page.evaluate(held) if isinstance(held, str) else len(held)
    assert actual >= count, (
        f"Expected at least {count} retained request(s), got {actual}"
    )
