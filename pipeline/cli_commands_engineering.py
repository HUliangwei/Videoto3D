"""Canonical CLI extension for Turntable engineering debug stages.

All existing commands delegate to pipeline.cli_commands unchanged.
"""
from __future__ import annotations

from pipeline import cli_commands as _base

_SPECIAL = {
    ("run", "anchor"): {
        "key": "run.anchor",
        "tools": ("colmap",),
        "title": "Turntable Anchor",
    },
    ("run", "pairs"): {
        "key": "run.pairs",
        "tools": (),
        "title": "Turntable Pair Angles",
    },
    ("run", "orbit"): {
        "key": "run.orbit",
        "tools": (),
        "title": "Turntable Global Orbit",
    },
    ("run", "triangulate"): {
        "key": "run.triangulate",
        "tools": ("colmap",),
        "title": "Turntable Known-Pose Triangulation",
    },
}

_BY_KEY = {
    item["key"]: dict(item, _turntable_custom=True)
    for item in _SPECIAL.values()
}


def _parse_run_option(argv):
    argv = list(argv)
    run_id = None
    index = 2
    while index < len(argv):
        token = argv[index]
        if token == "--run":
            if index + 1 >= len(argv):
                return None, "Missing value for --run"
            run_id = argv[index + 1]
            index += 2
            continue
        return None, "Unknown option for {} {}: {}".format(
            argv[0], argv[1], token
        )
    if not run_id:
        return None, "--run <run_id> is required"
    return {"run": run_id}, None


def parse_cli_args(argv):
    argv = list(argv)
    if len(argv) >= 2 and tuple(argv[:2]) in _SPECIAL:
        options, error = _parse_run_option(argv)
        if error:
            return {"kind": "error", "message": error}
        return {
            "kind": "command",
            "key": _SPECIAL[tuple(argv[:2])]["key"],
            "options": options,
        }
    return _base.parse_cli_args(argv)


def command_spec(key):
    if key in _BY_KEY:
        return _BY_KEY[key]
    return _base.command_spec(key)


def print_cli_help():
    _base.print_cli_help()
    print()
    print("Turntable debug stages (capture_mode=turntable only):")
    print("  python Videoto3D.py run anchor --run <run_id>")
    print("  python Videoto3D.py run pairs --run <run_id>")
    print("  python Videoto3D.py run orbit --run <run_id>")
    print("  python Videoto3D.py run triangulate --run <run_id>")


def print_command_annotation(spec, options):
    if spec.get("_turntable_custom"):
        print(
            "[COMMAND] {} | run={}".format(
                spec["title"],
                options.get("run", "-"),
            )
        )
        return
    return _base.print_command_annotation(spec, options)
