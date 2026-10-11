"""Minimal reader for phpMyAdmin/mysqldump INSERT statements.

Reads rows without needing a staging database, so the original dumps are never executed.
"""

import re
from collections.abc import Iterator
from pathlib import Path

_ESCAPES = {"n": "\n", "r": "\r", "t": "\t", "0": "\0", "Z": "\x1a"}


def _parse_values(text: str, pos: int) -> tuple[list[list], int]:
    """Parse `(a,'b',NULL),(...)` starting at pos; return rows and position after ';'."""
    rows: list[list] = []
    n = len(text)
    while pos < n:
        ch = text[pos]
        if ch == ";":
            return rows, pos + 1
        if ch != "(":
            pos += 1
            continue
        pos += 1
        row: list = []
        while True:
            while text[pos] in " \n\r\t":
                pos += 1
            ch = text[pos]
            if ch == "'":
                pos += 1
                buf = []
                while True:
                    c = text[pos]
                    if c == "\\":
                        nxt = text[pos + 1]
                        buf.append(_ESCAPES.get(nxt, nxt))
                        pos += 2
                    elif c == "'":
                        if text[pos + 1] == "'":
                            buf.append("'")
                            pos += 2
                        else:
                            pos += 1
                            break
                    else:
                        buf.append(c)
                        pos += 1
                row.append("".join(buf))
            else:
                end = pos
                while text[end] not in ",)":
                    end += 1
                raw = text[pos:end].strip()
                pos = end
                if raw.upper() == "NULL":
                    row.append(None)
                else:
                    try:
                        row.append(int(raw))
                    except ValueError:
                        try:
                            row.append(float(raw))
                        except ValueError:
                            row.append(raw)
            while text[pos] in " \n\r\t":
                pos += 1
            if text[pos] == ",":
                pos += 1
                continue
            if text[pos] == ")":
                pos += 1
                break
        rows.append(row)
    return rows, pos


def iter_rows(path: str | Path, table: str) -> Iterator[dict]:
    """Yield each row of `table` in the dump as a dict keyed by column name."""
    text = Path(path).read_text(encoding="utf-8")
    pattern = re.compile(r"INSERT INTO `" + re.escape(table) + r"` \(([^)]*)\) VALUES\s*")
    for m in pattern.finditer(text):
        cols = [c.strip().strip("`") for c in m.group(1).split(",")]
        rows, _ = _parse_values(text, m.end())
        for r in rows:
            yield dict(zip(cols, r, strict=False))
