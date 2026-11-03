"""Wait for actual retained routes or browser-owned delayed callbacks."""

from weakref import WeakKeyDictionary

_bindings = WeakKeyDictionary()


def wait_for_held(page, held, *, count=1):
    assert count > 0, "Readiness must require an actual held request"
    if isinstance(held, str):
        expression = held
    else:
        name = f"__heldCount_{id(held):x}"
        names = _bindings.setdefault(page, set())
        if name not in names:
            page.expose_function(name, lambda: len(held))
            names.add(name)
        expression = f"await window.{name}()"
    page.wait_for_function(
        f"async () => ({expression}) >= {count}", polling=20, timeout=10000
    )
    actual = page.evaluate(held) if isinstance(held, str) else len(held)
    assert actual >= count, (
        f"Expected at least {count} retained request(s), got {actual}"
    )
