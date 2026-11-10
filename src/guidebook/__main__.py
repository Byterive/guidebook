"""CLI: `facts`, `pages`, `build`, `status`, `update`, `serve`. (`init` is the first-run command.)"""
import argparse
import sys
from pathlib import Path

from .build import build_guide
from .collect import collect
from . import state
from .config import load_config
from .engine import status, update
from .init import describe, make_plan, write_config
from . import __version__
from .config import SUPPORTED_CONTRACT
from .explain import ClaudeRunner, Explainer
from .facts import FactStore
from .pages import Builder
from .writer import stale_generated, write_pages


def _facts(root, cfg, dry_run):
    sources = collect(root)
    store = FactStore(root / ".guidebook" / "facts.json")
    changed, removed = store.update(sources, cfg.status_map)
    if not dry_run:
        store.save()
    return sources, store, changed, removed


def cmd_facts(a) -> int:
    root = Path(a.project).resolve()
    cfg = load_config(root)
    sources, store, changed, removed = _facts(root, cfg, a.dry_run)
    kinds = {k: len(store.by_kind(k)) for k in ("purpose", "step", "result", "decision", "term", "risk")}
    print(f"sources: {len(sources)}  changed: {len(changed)}  removed: {len(removed)}  facts: {len(store.facts)}")
    print("facts by kind: " + ", ".join(f"{k}={n}" for k, n in kinds.items()))
    print("dry run: nothing written" if a.dry_run else f"wrote {root / '.guidebook' / 'facts.json'}")
    return 0


def cmd_pages(a) -> int:
    root = Path(a.project).resolve()
    cfg = load_config(root)
    sources, store, _, _ = _facts(root, cfg, a.dry_run)
    runner = None if a.no_model else ClaudeRunner()
    ex = Explainer(root / ".guidebook" / "cache", runner, max_calls=a.max_calls)
    versions = [v for v in cfg.versions if not a.version or v.name == a.version]
    if a.version and not versions:
        print(f"no version named {a.version!r}; configured: {', '.join(v.name for v in cfg.versions)}", file=sys.stderr)
        return 2
    src_root = root / "docs" / "guide-src"
    total = {"created": 0, "updated": 0, "unchanged": 0, "proposed": 0, "skipped_user": 0}
    for spec in versions:
        pages = Builder(store, sources, spec, cfg.brand).build(None if a.no_model else ex)
        rep = write_pages(src_root, spec.name, pages, a.dry_run)
        for k in total:
            total[k] += len(getattr(rep, k))
            for p in getattr(rep, k):
                print(f"  {k:12} {p}")
        for p in stale_generated(src_root, spec.name, {rel for rel, _ in pages}):
            print(f"  no longer produced (kept): {p}")
    print("pages: " + ", ".join(f"{k}={n}" for k, n in total.items()))
    print(f"model calls: {ex.calls}  cache hits: {ex.hits}  capped: {len(ex.capped)}  errors: {len(ex.errors)}"
          + ("  (--no-model)" if a.no_model else ""))
    for e in ex.errors:
        print(f"  model error: {e}", file=sys.stderr)
    if ex.capped:
        print(f"  call cap {a.max_calls} reached; not explained: {', '.join(ex.capped)}")
    if a.dry_run:
        print("dry run: no files written")
    else:
        state.record_pages(root, sources)
    return 0


def cmd_build(a) -> int:
    root = Path(a.project).resolve()
    cfg = load_config(root)
    out = root / cfg.output
    rep = build_guide(root, root / "docs" / "guide-src", out, cfg.brand, cfg.versions, cfg.output)
    for name, n in rep.built.items():
        print(f"  built {name}: {n} page{'s' if n != 1 else ''}")
    for name in rep.missing:
        print(f"  no pages for version {name} (run `guidebook pages` first)")
    if not rep.built:
        print("nothing built", file=sys.stderr)
        return 1
    state.record_build(root, root / "docs" / "guide-src")
    print(f"open {out / 'index.html'}")
    return 0


def _gate(project) -> int:
    """Print config warnings; return 0 normally, or -1 when kickoff disabled the guide (callers then do nothing and succeed)."""
    cfg = load_config(Path(project).resolve())
    for w in cfg.warnings:
        print(f"warning: {w}", file=sys.stderr)
    if not cfg.enabled:
        print("guide is disabled in .kickoff/guide.json (enabled: false); nothing to do")
        return -1
    return 0


def cmd_init(a) -> int:
    root = Path(a.project).resolve()
    versions = [v.strip() for v in a.versions.split(",") if v.strip()] if a.versions else None
    plan = make_plan(root, versions)
    for line in describe(plan):
        print(line)
    if plan.disabled:
        return 0
    if plan.empty:
        return 1
    if a.dry_run or not a.yes:
        print(f"{'would create' if a.dry_run else 'files init would create'} ({len(plan.files)}):")
        for f in plan.files:
            print(f"  {f}")
    if a.dry_run:
        print("dry run: nothing written")
        return 0
    if not a.yes:
        names = ",".join(p.name for p in plan.proposals)
        print(f"nothing written yet. To approve: guidebook init {a.project} --versions {names} --yes" + ("" if a.model else "   (add --model to let `claude -p` write the plain-words sections)"))
        return 0
    if plan.already:
        print("nothing changed")
        return 0
    write_config(root, plan.brand, [p.name for p in plan.proposals])
    print("wrote .guidebook/guide.json and .guidebook/ignore")
    ns = argparse.Namespace(project=str(root), version=None, no_model=not a.model, max_calls=a.max_calls, dry_run=False)
    cmd_pages(ns)
    return cmd_build(argparse.Namespace(project=str(root)))


def cmd_status(a) -> int:
    if _gate(a.project) < 0:
        return 0
    rep = status(a.project)
    for line in rep.lines():
        print(line)
    return 0 if rep.ok else 1


def cmd_update(a) -> int:
    if _gate(a.project) < 0:
        return 0
    try:
        rep = update(a.project, a.version, a.dry_run, a.no_model, a.max_calls)
    except ValueError as e:
        print(e, file=sys.stderr)
        return 2
    verb = "would write" if a.dry_run else "wrote"
    for p in rep.written:
        print(f"  {verb:11} {p}")
    for p in rep.proposed:
        print(f"  {'proposal':11} {p}  (you edited this page; new text goes to .proposed.md)")
    for p in rep.skipped_edited:
        print(f"  {'kept':11} {p}  (your edit; sources unchanged)")
    for name, n in rep.built.items():
        print(f"  built {name}: {n} page{'s' if n != 1 else ''}")
    if rep.nothing_to_do:
        print("nothing to update: the guide is up to date")
    print(f"sources changed: {len(rep.changed_sources)}  pages written: {len(rep.written)}  proposals: {len(rep.proposed)}  model calls: {rep.calls}  cache hits: {rep.hits}"
          + ("  (--no-model)" if a.no_model else ""))
    for e in rep.errors:
        print(f"  model error: {e}", file=sys.stderr)
    if rep.capped:
        print(f"  call cap {a.max_calls} reached; not explained: {', '.join(rep.capped)}")
    if a.dry_run:
        print("dry run: nothing written")
    return 0


def cmd_serve(a) -> int:
    from .serve import make_server
    try:
        srv = make_server(a.project, a.port, a.model)
    except (ValueError, FileNotFoundError, OSError) as e:
        print(e, file=sys.stderr)
        return 2
    host, port = srv.server_address[:2]
    print(f"serving the guide at http://{host}:{port}/  (this computer only; Ctrl+C to stop)")
    print("the Check and update button " + ("may call the model" if a.model else "runs update WITHOUT the model (start with --model to allow it)"))
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("stopped")
    finally:
        srv.server_close()
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="guidebook")
    ap.add_argument("--version", action="version", version=f"guidebook {__version__} (kickoff contract {SUPPORTED_CONTRACT})")
    sub = ap.add_subparsers(dest="cmd", required=True)
    i = sub.add_parser("init", help="propose guide versions for a project; writes nothing until you approve with --yes")
    i.add_argument("project", nargs="?", default=".")
    i.add_argument("--versions", help="comma-separated version names instead of the proposal")
    i.add_argument("--yes", action="store_true", help="approve: write the config and build the first guide")
    i.add_argument("--dry-run", action="store_true", help="list every file init would create, write nothing")
    i.add_argument("--model", action="store_true", help="let `claude -p` write the plain-words sections (default: no model)")
    i.add_argument("--max-calls", type=int, default=20)
    i.set_defaults(fn=cmd_init)
    f = sub.add_parser("facts", help="collect a project and refresh its facts cache")
    f.add_argument("project", nargs="?", default=".")
    f.add_argument("--dry-run", action="store_true", help="report what would change, write nothing")
    f.set_defaults(fn=cmd_facts)
    p = sub.add_parser("pages", help="write Markdown pages for each version into docs/guide-src/")
    p.add_argument("project", nargs="?", default=".")
    p.add_argument("--version", help="only this version")
    p.add_argument("--no-model", action="store_true", help="deterministic pages only; cached explanations are not even read")
    p.add_argument("--max-calls", type=int, default=20, help="most model calls in this run (default 20)")
    p.add_argument("--dry-run", action="store_true", help="list what would be written, write nothing")
    p.set_defaults(fn=cmd_pages)
    b = sub.add_parser("build", help="build HTML from the existing pages (no model calls)")
    b.add_argument("project", nargs="?", default=".")
    b.set_defaults(fn=cmd_build)
    s = sub.add_parser("status", help="say which pages are fresh or stale and why; exit code 1 if anything is stale")
    s.add_argument("project", nargs="?", default=".")
    s.set_defaults(fn=cmd_status)
    u = sub.add_parser("update", help="refresh only what changed: facts, affected pages, then the HTML")
    u.add_argument("project", nargs="?", default=".")
    u.add_argument("--version", help="only this version")
    u.add_argument("--no-model", action="store_true", help="deterministic text only, zero model calls")
    u.add_argument("--max-calls", type=int, default=20)
    u.add_argument("--dry-run", action="store_true", help="report what would change, write nothing")
    u.set_defaults(fn=cmd_update)
    v = sub.add_parser("serve", help="show the guide on http://127.0.0.1 with a working Check and update button")
    v.add_argument("project", nargs="?", default=".")
    v.add_argument("--port", type=int, default=8765)
    v.add_argument("--model", action="store_true", help="let the button call the model (default: no model)")
    v.set_defaults(fn=cmd_serve)
    a = ap.parse_args(argv)
    return a.fn(a)


if __name__ == "__main__":
    sys.exit(main())
