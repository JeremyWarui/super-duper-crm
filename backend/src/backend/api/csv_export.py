"""CSV downloads: cells a spreadsheet will not run, and the file response."""

import csv
import io
from collections.abc import Iterable, Sequence

from fastapi import Response

FORMULA_LEADS = ("=", "+", "-", "@", chr(9), chr(13))


def cell(text: str) -> str:
    """Text a spreadsheet will not run as a formula."""
    return "'" + text if text[:1] in FORMULA_LEADS else text


def csv_response(filename: str, columns: Sequence[str], rows: Iterable[Sequence[str]]) -> Response:
    """A CSV attachment with a header row; values are written as given."""
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(columns)
    writer.writerows(rows)
    return Response(
        out.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
