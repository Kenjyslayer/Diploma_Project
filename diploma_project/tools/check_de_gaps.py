import polib

uk = polib.pofile("locale/uk/LC_MESSAGES/django.po")
de = polib.pofile("locale/de/LC_MESSAGES/django.po")
missing, empty = [], []
for e in uk:
    if not e.msgid:
        continue
    d = de.find(e.msgid)
    if d is None:
        missing.append(e.msgid)
    elif not (d.msgstr or "").strip():
        empty.append(e.msgid)
print("missing", len(missing))
print("empty", len(empty))
for m in missing + empty:
    print(m)
