"""CSV rendering for finance reports. Stdlib csv + StringIO only."""

import csv
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from io import StringIO

from fastapi.responses import PlainTextResponse

# A leading =, @, + or - makes Excel evaluate the cell as a formula. Real
# numbers must stay numeric, so only non-numeric text is neutralised.
_FORMULA_TRIGGERS = ("=", "@", "+", "-", "\t", "\r")


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
    text = str(value)
    if text.startswith(_FORMULA_TRIGGERS) and not _is_number(text):
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
