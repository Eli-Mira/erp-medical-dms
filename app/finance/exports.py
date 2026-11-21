"""CSV rendering for finance reports. Stdlib csv + StringIO only."""

import csv
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from io import StringIO

from fastapi.responses import PlainTextResponse

# A leading =, @, + or - makes Excel evaluate the cell as a formula. Real
# numbers must stay numeric, so only non-numeric text is neutralised.
# Include newline as a trigger to neutralise values that start with "\n=…" or
# similar.
_FORMULA_TRIGGERS = ("=", "@", "+", "-", "\t", "\r", "\n")


def _is_number(text):
    try:
        Decimal(text)
    except InvalidOperation:
        return False
    return True


def cell(value):
    """Exact string form: None -> empty, dates -> ISO, money -> Decimal text."""
    if value is None:
        return ""
    if isinstance(value, (date, datetime)):
        return value.isoformat()

    # Convert to string and keep the original whitespace for CSV output.
    text = str(value)
    # Strip leading whitespace characters that could hide a formula trigger.
    stripped = text.lstrip(" \t\r\n")

    # Detect potential formula triggers either on the raw string or after
    # stripping leading whitespace. If the (trimmed) content is not a number,
    # neutralise it by prefixing a single quote.
    if (
        (text.startswith(_FORMULA_TRIGGERS) or stripped.startswith(_FORMULA_TRIGGERS))
        and not _is_number(text.strip())
    ):
        return "'" + text

    return text


def render_csv(headers, rows):
    buffer = StringIO()
    writer = csv.writer(buffer)
    writer.writerow(headers)
    for row in rows:
        writer.writerow(row)
    return buffer.getvalue()


def csv_response(filename, headers, rows):
    # UTF-8 BOM so Arabic text renders correctly when the file is opened in Excel.
    return PlainTextResponse(
        "\ufeff" + render_csv(headers, rows),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
