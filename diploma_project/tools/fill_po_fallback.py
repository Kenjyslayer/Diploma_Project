from __future__ import annotations

from pathlib import Path


def fill_empty_msgstr_with_msgid(po_path: Path) -> int:
    """
    Best-effort fallback: for single-line msgid/msgstr pairs, replace empty msgstr with msgid text.
    This avoids blank UI while manual translations are completed.
    """
    lines = po_path.read_text(encoding="utf-8").splitlines(True)
    out: list[str] = []
    i = 0
    changed = 0
    while i < len(lines):
        line = lines[i]
        if line.startswith("msgid "):
            msgid_lines = [line]
            i += 1
            while i < len(lines) and lines[i].startswith('"'):
                msgid_lines.append(lines[i])
                i += 1

            if i < len(lines) and lines[i].startswith("msgstr "):
                msgstr_line = lines[i]

                # Header block must remain untouched.
                if msgid_lines[0].strip() == 'msgid ""':
                    out.extend(msgid_lines)
                    out.append(msgstr_line)
                    i += 1
                    while i < len(lines) and lines[i].startswith('"'):
                        out.append(lines[i])
                        i += 1
                    continue

                if msgstr_line.strip() == 'msgstr ""' and len(msgid_lines) == 1:
                    msgid_text = msgid_lines[0].strip()[len("msgid ") :]  # includes quotes
                    out.extend(msgid_lines)
                    out.append("msgstr " + msgid_text + "\n")
                    i += 1
                    while i < len(lines) and lines[i].startswith('"'):
                        # drop any msgstr continuation lines (shouldn't exist for empty msgstr)
                        i += 1
                    changed += 1
                    continue

                out.extend(msgid_lines)
                out.append(msgstr_line)
                i += 1
                continue

            out.extend(msgid_lines)
            continue

        out.append(line)
        i += 1

    po_path.write_text("".join(out), encoding="utf-8")
    return changed


def main() -> None:
    base = Path(__file__).resolve().parents[1]  # diploma_project/
    for lang in ("uk", "de"):
        po_path = base / "locale" / lang / "LC_MESSAGES" / "django.po"
        if not po_path.exists():
            continue
        n = fill_empty_msgstr_with_msgid(po_path)
        print(f"{lang}: filled {n}")


if __name__ == "__main__":
    main()

