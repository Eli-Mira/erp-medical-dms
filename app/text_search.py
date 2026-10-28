"""Shared ILIKE pattern builder.

User input must never act as a LIKE metacharacter: an unescaped ``%`` or ``_``
would silently widen a search, and a stray backslash would be eaten as the
escape character. Postgres uses backslash as the default LIKE escape.
"""


def like_pattern(q: str) -> str:
    escaped = q.replace("\\", r"\\").replace("%", r"\%").replace("_", r"\_")
    return f"%{escaped}%"
