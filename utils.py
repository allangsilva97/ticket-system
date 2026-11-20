"""Small helpers shared by the routers."""

LIKE_ESCAPE = "\\"


def like_contains(term: str) -> str:
    """Pattern for a case-insensitive "contains" search that treats % and _ literally.

    Use with ``column.ilike(like_contains(term), escape=LIKE_ESCAPE)``.
    """
    escaped = (term.replace(LIKE_ESCAPE, LIKE_ESCAPE * 2)
                   .replace("%", LIKE_ESCAPE + "%")
                   .replace("_", LIKE_ESCAPE + "_"))
    return f"%{escaped}%"
