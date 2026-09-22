"""Command line interface."""

from __future__ import annotations

import argparse
import json
import sys

from . import APP_NAME, __version__

#: Default port of the local interface
PORT = 8779


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="lythos-spwa",
        description="Sheet pile wall analysis: limit equilibrium (free-earth support), "
                    "Winkler beam-spring with staged construction, and parametric / "
                    "reliability studies.")
    parser.add_argument("--version", action="version", version=f"{APP_NAME} {__version__}")
    # Running the program with no subcommand means "web", so the top level
    # carries that subcommand's defaults: without them the bare `lythos-spwa`
    # would reach serve() with a Namespace that has no host, port or language.
    parser.set_defaults(host="127.0.0.1", port=PORT, lang="en", no_browser=False)
    sub = parser.add_subparsers(dest="command")

    web = sub.add_parser("web", help="start the interface in a browser")
    web.add_argument("--port", type=int, default=PORT)
    web.add_argument("--host", default="127.0.0.1")
    web.add_argument("--lang", default="en", choices=["en", "tr"])
    web.add_argument("--no-browser", action="store_true")

    run = sub.add_parser("run", help="analyse a project file and print the results")
    run.add_argument("project", help="path to a .spwa / .json project file")
    run.add_argument("-o", "--out", default=None,
                     help="write a report here (.pdf / .html / .docx)")
    run.add_argument("--lang", default="en", choices=["en", "tr"])

    study = sub.add_parser("study", help="run the study defined in a project file")
    study.add_argument("project", help="path to a .spwa / .json project file")
    study.add_argument("-o", "--out", default=None, help="write the samples here (.csv / .xlsx)")
    study.add_argument("--lang", default="en", choices=["en", "tr"])

    example = sub.add_parser("example", help="write a starter project file")
    example.add_argument("-o", "--out", default="project.spwa")

    args = parser.parse_args(argv)
    command = args.command or "web"
    try:
        return _dispatch(command, args)
    except (ValueError, RuntimeError, OSError) as exc:
        # The analysis refuses impossible input with a sentence worth reading
        # (an anchor below the dredge line, a missing steel grade, an
        # unreadable project file). A traceback would bury it, so only
        # unexpected failures keep theirs.
        print(f"{APP_NAME}: {exc}", file=sys.stderr)
        return 1


def _dispatch(command: str, args) -> int:
    """Runs one command; raises on anything that goes wrong."""
    if command == "web":
        from .web.server import serve
        serve(host=args.host, port=args.port, open_browser=not args.no_browser,
              lang=args.lang)
        return 0

    from . import forms

    if command == "example":
        with open(args.out, "w", encoding="utf-8") as fh:
            json.dump(forms.project_file(forms.defaults()), fh, indent=2, ensure_ascii=False)
        print(args.out)
        return 0

    with open(args.project, encoding="utf-8") as fh:
        values = forms.from_config(json.load(fh))

    from .web.session import Session
    session = Session(lang=args.lang)

    if command == "run":
        result = session.analyse(values)
        print(result["text"])
        for warning in result["warnings"]:
            print(f"  ! {warning}", file=sys.stderr)
        if args.out:
            fmt = args.out.lower().rsplit(".", 1)[-1]
            print(session.report(fmt if fmt in ("pdf", "html", "docx") else "pdf", args.out))
        return 0

    # A study: analyse the wall first, so the report and the figures have
    # something to sit beside, then sweep.
    session.analyse(values)
    started = session.start_study(values)
    if not started["ok"]:
        print(started["error"], file=sys.stderr)
        return 1
    import time
    last = -1
    while session.state()["job"] == "running":
        state = session.state()
        if state["total"] and state["done"] != last:
            last = state["done"]
            print(f"\r{state['done']} / {state['total']}", end="", file=sys.stderr, flush=True)
        time.sleep(0.2)
    print("", file=sys.stderr)
    state = session.state()
    if state["job"] == "error":
        print(state["error"], file=sys.stderr)
        return 1
    payload = session.study_payload()
    if not payload["ok"]:
        print(payload["error"], file=sys.stderr)
        return 1
    print(payload["text"])
    if args.out:
        kind = "xlsx" if args.out.lower().endswith(".xlsx") else "csv"
        print(session.export_study(kind, args.out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
