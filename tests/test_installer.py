import pytest
import yaml
from scripts.install_rime import install


def test_backup_merge_and_idempotence(tmp_path):
    custom = tmp_path / "luna_pinyin_simp.custom.yaml"
    custom.write_text("patch:\n  translator/enable_user_dict: false\n", encoding="utf-8")
    loader = tmp_path / "rime.lua"
    loader.write_text("existing_plugin = require('existing')\n", encoding="utf-8")
    result = install(tmp_path, "luna_pinyin_simp")
    assert len(result["backups"]) == 2
    assert "existing_plugin" in loader.read_text(encoding="utf-8")
    assert yaml.safe_load(custom.read_text(encoding="utf-8"))["patch"]["translator/enable_user_dict"] is False
    install(tmp_path, "luna_pinyin_simp")
    assert loader.read_text(encoding="utf-8").count("-- BEGIN CONTEXT_KAOMOJI_IME") == 1


def test_conflicts_leave_all_original_files_untouched(tmp_path):
    custom = tmp_path / "test.custom.yaml"
    original = "patch:\n  engine/filters/@next: lua_filter@another\n"
    custom.write_text(original, encoding="utf-8")
    with pytest.raises(ValueError):
        install(tmp_path, "test")
    assert custom.read_text(encoding="utf-8") == original
    assert not (tmp_path / "rime.lua").exists()


def test_dry_run_is_read_only(tmp_path):
    result = install(tmp_path, "luna_pinyin_simp", dry_run=True)
    assert result["dry_run"]
    assert list(tmp_path.iterdir()) == []


def test_duplicate_keys_are_rejected(tmp_path):
    custom = tmp_path / "test.custom.yaml"
    custom.write_text("patch:\n  foo: 1\n  foo: 2\n", encoding="utf-8")
    with pytest.raises(ValueError, match="Duplicate YAML key"):
        install(tmp_path, "test")


def test_existing_loader_return_is_not_broken(tmp_path):
    loader = tmp_path / "rime.lua"
    loader.write_text("return {}\n", encoding="utf-8")
    with pytest.raises(ValueError, match="does not compile"):
        install(tmp_path, "test")
    assert not (tmp_path / "test.custom.yaml").exists()
    assert loader.read_text(encoding="utf-8") == "return {}\n"


@pytest.mark.parametrize("schema", ["../x", "x/y", "", "x.schema.yaml"])
def test_schema_validation(tmp_path, schema):
    with pytest.raises(ValueError):
        install(tmp_path, schema)
