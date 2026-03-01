"""CLI entry point for CodeSight.

Usage:
    python -m codesight index /path/to/docs     Index a folder
    python -m codesight search "query" [path]    Search indexed documents
    python -m codesight ask "question" [path]    Ask a question (uses Claude)
    python -m codesight status [path]            Check index status
    python -m codesight demo                     Launch Streamlit web chat
"""

from __future__ import annotations

import argparse
import json
import sys


def main():
    parser = argparse.ArgumentParser(
        prog="codesight",
        description="AI-powered document search engine",
    )
    sub = parser.add_subparsers(dest="command")

    # index
    p_index = sub.add_parser("index", help="Index a document folder")
    p_index.add_argument("path", help="Path to folder")
    p_index.add_argument("--force", action="store_true", help="Rebuild from scratch")

    # search
    p_search = sub.add_parser("search", help="Search indexed documents")
    p_search.add_argument("query", help="Search query")
    p_search.add_argument("path", nargs="?", default=".", help="Folder path (default: .)")
    p_search.add_argument("-k", "--top-k", type=int, default=8, help="Number of results")

    # ask
    p_ask = sub.add_parser("ask", help="Ask a question (LLM synthesizes answer)")
    p_ask.add_argument("question", help="Question to ask")
    p_ask.add_argument("path", nargs="?", default=".", help="Folder path (default: .)")
    p_ask.add_argument("-k", "--top-k", type=int, default=5, help="Chunks to use as context")

    # status
    p_status = sub.add_parser("status", help="Check index status")
    p_status.add_argument("path", nargs="?", default=".", help="Folder path (default: .)")

    # demo
    sub.add_parser("demo", help="Launch Streamlit web chat UI")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    if args.command == "demo":
        _launch_demo()
        return

    # Lazy import to avoid loading heavy deps for --help
    from .api import CodeSight

    if args.command == "index":
        engine = CodeSight(args.path)
        stats = engine.index(force_rebuild=args.force)
        print(json.dumps(stats.model_dump(), indent=2))

    elif args.command == "search":
        engine = CodeSight(args.path)
        results = engine.search(args.query, top_k=args.top_k)
        for r in results:
            print(f"\n--- {r.file_path} (page {r.start_line}-{r.end_line}, score: {r.score}) ---")
            print(f"[{r.scope}]")
            print(r.snippet[:500])

    elif args.command == "ask":
        engine = CodeSight(args.path)
        answer = engine.ask(args.question, top_k=args.top_k)
        print(f"\n{answer.text}")
        print(f"\n--- Sources ({len(answer.sources)}) ---")
        for s in answer.sources:
            print(f"  - {s.file_path} (page {s.start_line}-{s.end_line}): {s.scope}")

    elif args.command == "status":
        engine = CodeSight(args.path)
        status = engine.status()
        print(json.dumps(status.model_dump(), indent=2))


def _launch_demo():
    """Launch the Streamlit demo app."""
    import subprocess
    from pathlib import Path

    app_path = Path(__file__).parent.parent.parent / "demo" / "app.py"
    if not app_path.exists():
        print(f"Demo app not found at {app_path}")
        sys.exit(1)
    subprocess.run(["streamlit", "run", str(app_path)], check=True)


if __name__ == "__main__":
    main()
