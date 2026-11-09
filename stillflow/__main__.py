"""Run `python -m stillflow serve` or `python -m stillflow render --help`."""

import argparse
import json
from pathlib import Path

from .io import Project, load_example
from .pipeline import render_project


def main():
    parser = argparse.ArgumentParser(description="Stillflow: animate a still image with NumPy")
    commands = parser.add_subparsers(dest="command", required=True)
    serve = commands.add_parser("serve", help="Start the local browser editor")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8000)
    render = commands.add_parser("render", help="Render a saved project or example recipe")
    source = render.add_mutually_exclusive_group(required=True)
    source.add_argument("--project", type=Path)
    source.add_argument("--example", type=Path)
    render.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "serve":
        import uvicorn
        uvicorn.run("stillflow.server:app", host=args.host, port=args.port)
    else:
        project = (load_example(args.example) if args.example else
                   Project.model_validate_json(args.project.read_text(encoding="utf-8")))
        gif, metrics, _, _ = render_project(project)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_bytes(gif)
        args.output.with_suffix(".metrics.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")
        print(json.dumps(metrics, indent=2))
        print(f"Saved {args.output}")


if __name__ == "__main__":
    main()
