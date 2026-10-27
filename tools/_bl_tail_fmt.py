"""Formatter for tools/bl-tail. A separate file ON PURPOSE: the first version inlined this
python inside a bash heredoc, the nested quotes were mangled into a SyntaxError, and it shipped
broken because the test output was empty and I read the emptiness as 'quiet' instead of reading
the error."""
import sys, time

for line in sys.stdin:
    line = line.strip()
    if not line:
        continue
    try:
        import json
        r = json.loads(line)
    except Exception:
        continue
    seq = r.get("seq", 0)
    t = time.strftime("%H:%M:%S", time.localtime(r.get("t", 0)))
    kind = r.get("kind", "?")
    rest = " ".join("%s=%s" % (a, b) for a, b in r.items() if a not in ("seq", "t", "kind"))
    print("[%4d] %s  %-14s %s" % (seq, t, kind, rest), flush=True)
