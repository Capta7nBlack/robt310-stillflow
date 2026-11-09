"""Record the exact installed dependency graph without unrelated packages."""

from importlib.metadata import PackageNotFoundError, requires, version
from pathlib import Path

from packaging.requirements import Requirement
from packaging.utils import canonicalize_name

ROOT=Path(__file__).resolve().parents[1]


def main():
    pending=["numpy","Pillow","fastapi","uvicorn","python-multipart","pytest","httpx","psutil","matplotlib","python-pptx","playwright"]
    selected={}
    while pending:
        name=canonicalize_name(pending.pop())
        if name in selected:continue
        try:installed=version(name)
        except PackageNotFoundError:
            raise SystemExit(f"Required dependency is not installed: {name}")
        selected[name]=installed
        for raw in requires(name) or []:
            requirement=Requirement(raw)
            if requirement.marker is None or requirement.marker.evaluate({"extra":""}):
                pending.append(requirement.name)
    lines=["# Tested versions; install with: pip install -r requirements.txt -c constraints.txt",
           "# Includes optional development packages; a constraint does not install a package."]
    lines.extend(f"{name}=={selected[name]}" for name in sorted(selected))
    (ROOT/"constraints.txt").write_text("\n".join(lines)+"\n",encoding="utf-8")
    print(f"Recorded {len(selected)} tested dependency versions.")


if __name__=="__main__":main()
