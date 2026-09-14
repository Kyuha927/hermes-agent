from lin3d_flash_benchmark.worker import _extract_json


def test_extract_json_plain() -> None:
    assert _extract_json('{"ok": true}') == {"ok": True}


def test_extract_json_fenced() -> None:
    assert _extract_json('```json\n{"ok": true}\n```') == {"ok": True}


def test_extract_json_with_preface() -> None:
    assert _extract_json('result follows\n{"ok": true}\nend') == {"ok": True}
