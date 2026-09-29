"""Isolated Windows DLL integration test; never touches the installed IME.

Usage: python scripts/rime_smoke.py --dll C:/path/to/rime.dll
Bindings follow rime/librime src/rime_api.h (legacy C exports).
The tiny QA dictionary is intentionally not a user's normal pinyin dictionary.
"""
import argparse
import ctypes as C
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path
from time import sleep

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from python.config import ROOT
from python.ipc import FileBridge
from python.service import RecommendationService


class Traits(C.Structure):
    _fields_ = [("data_size", C.c_int), ("shared_data_dir", C.c_char_p), ("user_data_dir", C.c_char_p),
                ("distribution_name", C.c_char_p), ("distribution_code_name", C.c_char_p),
                ("distribution_version", C.c_char_p), ("app_name", C.c_char_p),
                ("modules", C.POINTER(C.c_char_p)), ("min_log_level", C.c_int),
                ("log_dir", C.c_char_p), ("prebuilt_data_dir", C.c_char_p), ("staging_dir", C.c_char_p)]


class Composition(C.Structure):
    _fields_ = [(name, C.c_int) for name in ("length", "cursor_pos", "sel_start", "sel_end")] + [("preedit", C.c_char_p)]


class Candidate(C.Structure):
    _fields_ = [("text", C.c_char_p), ("comment", C.c_char_p), ("reserved", C.c_void_p)]


class Menu(C.Structure):
    _fields_ = [(name, C.c_int) for name in ("page_size", "page_no", "is_last_page", "highlighted_candidate_index", "num_candidates")] + [("candidates", C.POINTER(Candidate)), ("select_keys", C.c_char_p)]


class Context(C.Structure):
    _fields_ = [("data_size", C.c_int), ("composition", Composition), ("menu", Menu),
                ("commit_text_preview", C.c_char_p), ("select_labels", C.POINTER(C.c_char_p))]


class Commit(C.Structure):
    _fields_ = [("data_size", C.c_int), ("text", C.c_char_p)]


def bind(dll, name: str, arguments: list, result) -> object:
    function = getattr(dll, name)
    function.argtypes = arguments
    function.restype = result
    return function


def run(dll_path: Path, shared_data: Path | None = None, schema_id: str = "kaomoji_smoke") -> dict:
    if os.name != "nt":
        raise RuntimeError("This test needs a Windows Rime DLL and matching Python architecture")
    # Keeps dependent DLL search local to the specified binary.
    with os.add_dll_directory(str(dll_path.resolve().parent)):
        dll = C.CDLL(str(dll_path.resolve()))
    find_module = bind(dll, "RimeFindModule", [C.c_char_p], C.c_void_p)
    if not find_module(b"lua"):
        raise RuntimeError("DLL does not include librime-lua")
    setup = bind(dll, "RimeSetup", [C.POINTER(Traits)], None)
    initialize = bind(dll, "RimeInitialize", [C.POINTER(Traits)], None)
    finalize = bind(dll, "RimeFinalize", [], None)
    maintenance = bind(dll, "RimeStartMaintenance", [C.c_int], C.c_int)
    join = bind(dll, "RimeJoinMaintenanceThread", [], None)
    create = bind(dll, "RimeCreateSession", [], C.c_size_t)
    destroy = bind(dll, "RimeDestroySession", [C.c_size_t], C.c_int)
    select = bind(dll, "RimeSelectSchema", [C.c_size_t, C.c_char_p], C.c_int)
    process = bind(dll, "RimeProcessKey", [C.c_size_t, C.c_int, C.c_int], C.c_int)
    get_context = bind(dll, "RimeGetContext", [C.c_size_t, C.POINTER(Context)], C.c_int)
    free_context = bind(dll, "RimeFreeContext", [C.POINTER(Context)], C.c_int)
    get_commit = bind(dll, "RimeGetCommit", [C.c_size_t, C.POINTER(Commit)], C.c_int)
    free_commit = bind(dll, "RimeFreeCommit", [C.POINTER(Commit)], C.c_int)
    clear = bind(dll, "RimeClearComposition", [C.c_size_t], None)
    set_option = bind(dll, "RimeSetOption", [C.c_size_t, C.c_char_p, C.c_int], None)
    with tempfile.TemporaryDirectory(prefix="kaomoji-rime-") as temporary:
        directory = Path(temporary)
        shared, user = shared_data.resolve() if shared_data else directory / "shared", directory / "user"
        if not shared_data:
            shared.mkdir()
        (user / "lua").mkdir(parents=True)
        if not shared_data:
            (shared / "default.yaml").write_text("config_version: '1.0'\nschema_list:\n  - schema: kaomoji_smoke\nswitcher:\n  caption: Test\n  hotkeys: []\nascii_composer:\n  switch_key:\n    Shift_L: commit_code\n    Shift_R: commit_code\n", encoding="utf-8")
        else:
            (user / "default.custom.yaml").write_text(f"patch:\n  schema_list:\n    - schema: {schema_id}\n", encoding="utf-8")
        schema = """schema:
  schema_id: kaomoji_smoke
  name: Kaomoji QA
  version: '1.0'
switches:
  - name: ascii_mode
    reset: 0
engine:
  processors: [ascii_composer, recognizer, speller, punctuator, selector, navigator, express_editor]
  segmentors: [ascii_segmentor, matcher, abc_segmentor, punct_segmentor, fallback_segmentor]
  translators: [table_translator, punct_translator]
  filters: [uniquifier]
speller:
  alphabet: abcdefghijklmnopqrstuvwxyz
translator:
  dictionary: kaomoji_smoke
  enable_user_dict: false
  enable_completion: true
menu:
  page_size: 9
"""
        if not shared_data:
            (shared / "kaomoji_smoke.schema.yaml").write_text(schema, encoding="utf-8")
            (shared / "kaomoji_smoke.dict.yaml").write_text("---\nname: kaomoji_smoke\nversion: '1.0'\nsort: by_weight\n...\n终于成功了\tzhongyuchenggongle\t1000\n终于\tzhongyuchenggongle\t900\n中于\tzhongyuchenggongle\t800\n终于成功\tzhongyuchenggongle\t700\n终\tzhongyuchenggongle\t600\n怎么又报错了\tzenmeyoubaocuole\t1000\n", encoding="utf-8")
        shutil.copy2(ROOT / "rime/kaomoji.lua", user / "lua/kaomoji.lua")
        for module in ("kaomoji_local.lua", "kaomoji_data.lua"):
            shutil.copy2(ROOT / "rime" / module, user / "lua" / module)
        shutil.copy2(ROOT / "rime/rime.lua.snippet", user / "rime.lua")
        shutil.copy2(ROOT / "rime/example.custom.yaml", user / f"{schema_id}.custom.yaml")
        traits = Traits()
        traits.data_size = C.sizeof(Traits) - C.sizeof(C.c_int)
        traits.shared_data_dir = str(shared).encode("utf-8")
        traits.user_data_dir = str(user).encode("utf-8")
        traits.app_name = b"rime.kaomoji_smoke"
        traits.min_log_level = 2
        traits.log_dir = b""
        setup(C.byref(traits))
        initialize(C.byref(traits))
        bridge = FileBridge(user / "kaomoji_ipc", RecommendationService())
        # Deliberately never start the service: all recommendations must be offline.
        session = 0
        def menu() -> list[dict]:
            context = Context()
            context.data_size = C.sizeof(Context) - C.sizeof(C.c_int)
            if not get_context(session, C.byref(context)):
                return []
            try:
                return [{"text": context.menu.candidates[i].text.decode("utf-8"),
                         "comment": (context.menu.candidates[i].comment or b"").decode("utf-8")}
                        for i in range(context.menu.num_candidates)]
            finally:
                free_context(C.byref(context))

        def commit_text() -> str:
            commit = Commit()
            commit.data_size = C.sizeof(Commit) - C.sizeof(C.c_int)
            assert get_commit(session, C.byref(commit)), "Expected a real commit"
            try:
                return commit.text.decode("utf-8")
            finally:
                free_commit(C.byref(commit))

        try:
            maintenance(1)
            join()
            session = create()
            assert session and select(session, schema_id.encode("ascii")), "Schema deployment failed"
            set_option(session, b"ascii_mode", 0)
            for ch in "zhongyuchenggongle":
                process(session, ord(ch), 0)
                menu()  # force lazy translation, as Weasel does when displaying candidates
            sleep(.3)
            with_faces = menu()
            assert with_faces[0]["text"] == "终于成功了", with_faces
            assert any("颜文字" in row["comment"] for row in with_faces), with_faces
            index = next(i for i, row in enumerate(with_faces) if "颜文字" in row["comment"])
            assert index == 3, with_faces
            assert sum("颜文字" in row["comment"] for row in with_faces) == 6
            process(session, ord(str(index + 1)), 0)
            selected = commit_text()
            assert selected == with_faces[index]["text"] and selected.startswith("终于成功了 "), selected
            # Plain sentence commit -> F8 -> faces-only translator.
            for ch in "zhongyuchenggongle":
                process(session, ord(ch), 0)
            menu()
            process(session, ord("1"), 0)
            assert commit_text() == "终于成功了"
            sleep(.3)
            process(session, 0xffc5, 0)
            faces_only = menu()
            assert faces_only and "颜文字" in faces_only[0]["comment"], faces_only
            process(session, ord("1"), 0)
            face_commit = commit_text()
            assert "终于" not in face_commit
            # Kill service and prove ordinary Chinese and digit selection still work.
            bridge.stop()
            clear(session)
            for ch in "zhongyuchenggongle":
                process(session, ord(ch), 0)
            without_service = menu()
            assert without_service[0]["text"] == "终于成功了"
            assert any("颜文字" in row["comment"] for row in without_service)
            process(session, 0xffc6, 0)  # F9 disables recommendations.
            assert not any("颜文字" in row["comment"] for row in menu())
            process(session, ord("1"), 0)
            assert commit_text() == "终于成功了"
            process(session, 0xffc6, 0)
            for ch in "ku":
                process(session, ord(ch), 0)
            homophones = menu()
            if shared_data:
                target = homophones[1]["text"]
                process(session, 0xff54, 0)  # Down highlights the second actual candidate.
                process(session, 0xffc5, 0)  # F8 expands the selected homophone.
                expanded = menu()
                assert all(row["text"].startswith(target + " ") for row in expanded), (target, expanded)
                process(session, 0xff56, 0)  # PageDown: expanded results span pages.
                second_page = menu()
                assert second_page and second_page[0]["text"] != expanded[0]["text"]
                assert second_page[0]["text"].startswith(target + " ")
                process(session, ord("1"), 0)
                assert commit_text() == second_page[0]["text"]
            return {"dll": str(dll_path.resolve()), "lua_module": True, "native_engine_passed": True,
                    "candidate_inserted_at": index + 1, "selected_text": selected,
                    "post_commit_face": face_commit, "service_down_chinese_passed": True,
                    "schema": schema_id, "offline": True,
                    "homophone_and_pagination": bool(shared_data),
                    "scope": "Isolated real Rime DLL with " + ("official pinyin dictionary" if shared_data else "QA table dictionary") + "; TSF/front-end UI not tested"}
        finally:
            bridge.stop()
            if session:
                destroy(session)
            finalize()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dll", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--shared-data", type=Path, help="Official Weasel data directory; read-only")
    parser.add_argument("--schema", default="kaomoji_smoke")
    args = parser.parse_args()
    result = run(args.dll, args.shared_data, args.schema)
    content = json.dumps(result, ensure_ascii=False, indent=2)
    print(content)
    if args.output:
        args.output.write_text(content + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
