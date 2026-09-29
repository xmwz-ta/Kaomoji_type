"""Back up and merge the Rime plugin into an explicitly selected user directory."""
import argparse
import json
import re
import shutil
from datetime import datetime
from pathlib import Path
import sys
import yaml
from lupa.lua54 import LuaRuntime

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from python.config import ROOT

BEGIN = "-- BEGIN CONTEXT_KAOMOJI_IME"
END = "-- END CONTEXT_KAOMOJI_IME"


class UniqueLoader(yaml.SafeLoader):
    pass


def unique_mapping(loader, node, deep=False):
    mapping = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if key in mapping:
            raise ValueError(f"Duplicate YAML key: {key}")
        mapping[key] = loader.construct_object(value_node, deep=deep)
    return mapping


UniqueLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, unique_mapping)


def install(user_dir: Path, schema: str, dry_run: bool = False, ipc_dir: Path | None = None) -> dict:
    """Validate the full merge before writing; never replace another plugin's patch."""
    user_dir = user_dir.resolve()
    if not user_dir.is_dir():
        raise ValueError("Select the existing Rime user directory shown by Weasel")
    if not re.fullmatch(r"[A-Za-z0-9_-]+", schema):
        raise ValueError("Use a schema ID such as luna_pinyin_simp")
    custom = user_dir / f"{schema}.custom.yaml"
    original = custom.read_text(encoding="utf-8-sig") if custom.exists() else ""
    config = yaml.load(original, Loader=UniqueLoader) if original.strip() else {}
    if not isinstance(config, dict):
        raise ValueError("Existing custom YAML must be a mapping")
    patch = config.setdefault("patch", {})
    if not isinstance(patch, dict):
        raise ValueError("Existing patch must be a mapping")
    additions = yaml.safe_load((ROOT / "rime/example.custom.yaml").read_text(encoding="utf-8"))["patch"]
    if ipc_dir:
        additions["kaomoji/ipc_dir"] = ipc_dir.resolve().as_posix()
    for key, value in additions.items():
        if key in patch and patch[key] != value and not key.startswith(("kaomoji/", "menu/")):
            raise ValueError(f"Existing patch conflicts at {key}; merge manually using README before installing")
    patch.update(additions)
    lua_loader = user_dir / "rime.lua"
    loader = lua_loader.read_text(encoding="utf-8-sig") if lua_loader.exists() else ""
    snippet = (ROOT / "rime/rime.lua.snippet").read_text(encoding="utf-8")
    block = BEGIN + "\n" + snippet + END
    if BEGIN in loader:
        if END not in loader:
            raise ValueError("Incomplete previous kaomoji loader block")
        loader = re.sub(re.escape(BEGIN) + r".*?" + re.escape(END), lambda _: block, loader, flags=re.DOTALL)
    else:
        loader = loader.rstrip() + "\n\n" + block + "\n"
    compiler = LuaRuntime(unpack_returned_tuples=True)
    valid, error = compiler.eval("function(source) local chunk, err = load(source); return chunk ~= nil, err end")(loader)
    if not valid:
        raise ValueError(f"Merged rime.lua does not compile; merge the block manually: {error}")
    targets = {custom: yaml.safe_dump(config, allow_unicode=True, sort_keys=False), lua_loader: loader,
               user_dir / "lua/kaomoji.lua": (ROOT / "rime/kaomoji.lua").read_text(encoding="utf-8")}
    for module in ("kaomoji_local.lua", "kaomoji_data.lua"):
        targets[user_dir / "lua" / module] = (ROOT / "rime" / module).read_text(encoding="utf-8")
    result = {"user_dir": str(user_dir), "schema": schema, "files": [str(p) for p in targets],
              "ipc_dir": str(ipc_dir.resolve() if ipc_dir else user_dir / "kaomoji_ipc"), "dry_run": dry_run}
    if dry_run:
        return result
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    backups = []
    for path in targets:
        if path.exists():
            backup = path.with_name(path.name + f".kaomoji-backup-{timestamp}")
            shutil.copy2(path, backup)
            backups.append(str(backup))
    for path, content in targets.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8", newline="\n")
    Path(result["ipc_dir"]).mkdir(parents=True, exist_ok=True)
    result["backups"] = backups
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--user-dir", type=Path, required=True)
    parser.add_argument("--schema", required=True)
    parser.add_argument("--ipc-dir", type=Path)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    try:
        result = install(args.user_dir, args.schema, args.dry_run, args.ipc_dir)
    except (ValueError, OSError, yaml.YAMLError) as error:
        parser.exit(1, f"Installation failed: {error}\n")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if not args.dry_run:
        print("Redeploy Weasel. Recommendations run locally; no Python service is required.")


if __name__ == "__main__":
    main()
