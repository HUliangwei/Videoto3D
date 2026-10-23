import importlib
import sys
import types


def _fake_base_cli():
    module = types.ModuleType("pipeline.cli_commands")
    module.command_spec = lambda key: {"tools": ("base",), "key": key}
    module.parse_cli_args = lambda argv: {"kind": "base", "argv": list(argv)}
    module.print_cli_help = lambda: None
    module.print_command_annotation = lambda spec, options: None
    return module


def test_special_turntable_commands_parse_with_canonical_run_grammar(monkeypatch):
    monkeypatch.setitem(sys.modules, "pipeline.cli_commands", _fake_base_cli())
    sys.modules.pop("pipeline.cli_commands_engineering", None)
    cli = importlib.import_module("pipeline.cli_commands_engineering")

    for stage, key, tools in (
        ("anchor", "run.anchor", ("colmap",)),
        ("pairs", "run.pairs", ()),
        ("orbit", "run.orbit", ()),
        ("triangulate", "run.triangulate", ("colmap",)),
    ):
        parsed = cli.parse_cli_args(["run", stage, "--run", "chair"])
        assert parsed["key"] == key
        assert parsed["options"]["run"] == "chair"
        assert tuple(cli.command_spec(key)["tools"]) == tools


def test_existing_commands_delegate_unchanged(monkeypatch):
    monkeypatch.setitem(sys.modules, "pipeline.cli_commands", _fake_base_cli())
    sys.modules.pop("pipeline.cli_commands_engineering", None)
    cli = importlib.import_module("pipeline.cli_commands_engineering")
    assert cli.parse_cli_args(["route", "mesh", "--run", "chair"])["kind"] == "base"
