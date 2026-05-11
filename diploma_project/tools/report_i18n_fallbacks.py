from __future__ import annotations

import sys
from pathlib import Path


def iter_entries(po_text: str):
    msgid = None
    msgstr = None
    for line in po_text.splitlines():
        if line.startswith("msgid "):
            if msgid is not None and msgstr is not None:
                yield msgid, msgstr
            msgid = line[len("msgid ") :].strip().strip('"')
            msgstr = None
        elif line.startswith("msgstr "):
            msgstr = line[len("msgstr ") :].strip().strip('"')
    if msgid is not None and msgstr is not None:
        yield msgid, msgstr


def main() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    base = Path(__file__).resolve().parents[1]  # diploma_project/
    for lang in ("uk", "de"):
        po_path = base / "locale" / lang / "LC_MESSAGES" / "django.po"
        txt = po_path.read_text(encoding="utf-8")
        same = []
        empty = []
        for mid, ms in iter_entries(txt):
            if mid == "":
                continue
            if ms == "":
                empty.append(mid)
            elif ms == mid:
                same.append(mid)
        print(f"{lang}: empty={len(empty)} same_as_msgid={len(same)}")
        for s in (empty + same)[:120]:
            print(" -", s)
        if len(empty) + len(same) > 120:
            print(" ...")


if __name__ == "__main__":
    main()

