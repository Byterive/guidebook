"""Stand-in for `claude -p` (no network). Reads the prompt on stdin, appends it to the file in FAKE_CLAUDE_LOG, prints a fixed answer."""
import os
import sys

prompt = sys.stdin.read()
log = os.environ.get("FAKE_CLAUDE_LOG")
if log:
    with open(log, "a", encoding="utf-8") as f:
        f.write(prompt.replace("\n", "\n") + "\n=====\n")
if os.environ.get("FAKE_CLAUDE_FAIL"):
    sys.stderr.write("boom")
    sys.exit(1)
sys.stdout.write("# heading to drop\nThe shop tracks repairs. Two parts are listed. <b>x</b>\n")
