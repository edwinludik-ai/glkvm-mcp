"""
Smoke test for glkvm_mcp.py.

Imports the server module without launching the stdio loop and asserts that the
expected MCP tools are registered. Run from the repo root:

    python -m unittest tests.test_smoke

or directly:

    python tests/test_smoke.py
"""
from __future__ import annotations

import asyncio
import importlib.util
import os
import sys
import unittest

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
SERVER_PATH = os.path.join(REPO_ROOT, "glkvm_mcp.py")

EXPECTED_TOOLS = {
    "kvm_connect",
    "kvm_disconnect",
    "kvm_send_text",
    "kvm_send_keys",
    "kvm_hold_key",
    "kvm_release_all",
    "kvm_mouse_move",
    "kvm_mouse_move_pct",
    "kvm_mouse_click",
    "kvm_mouse_scroll",
    "kvm_screenshot",
    "kvm_screenshot_to_file",
    "kvm_status",
    "kvm_reload_env",
}


def _load_module():
    spec = importlib.util.spec_from_file_location("glkvm_mcp", SERVER_PATH)
    assert spec is not None and spec.loader is not None, "could not load glkvm_mcp.py"
    mod = importlib.util.module_from_spec(spec)
    sys.modules["glkvm_mcp"] = mod
    spec.loader.exec_module(mod)
    return mod


class SmokeTest(unittest.TestCase):
    def test_module_imports(self):
        mod = _load_module()
        self.assertTrue(hasattr(mod, "mcp"), "module should expose `mcp` (FastMCP instance)")

    def test_tools_registered(self):
        mod = _load_module()
        tools = asyncio.run(mod.mcp.list_tools())
        names = {t.name for t in tools}
        missing = EXPECTED_TOOLS - names
        self.assertFalse(
            missing,
            msg=f"Missing tools: {sorted(missing)}. Got: {sorted(names)}",
        )

    def test_kvm_connect_signature(self):
        mod = _load_module()
        tools = asyncio.run(mod.mcp.list_tools())
        connect = next((t for t in tools if t.name == "kvm_connect"), None)
        self.assertIsNotNone(connect, "kvm_connect tool not registered")
        schema = connect.inputSchema
        required = set(schema.get("required", []))
        self.assertEqual(
            required, set(),
            msg=f"kvm_connect args should all be optional (.env fallback), got {required}",
        )

    def test_reload_env(self):
        import tempfile
        from pathlib import Path
        mod = _load_module()
        with tempfile.TemporaryDirectory() as d:
            mod.ENV_FILE = Path(d, ".env")
            mod.ENV_FILE.write_text("GLKVM_KEYMAP=de\nGLKVM_TEST_X=1\n")
            r = asyncio.run(mod.kvm_reload_env())
            self.assertEqual((r["keymap"], mod.KEYMAP_NAME, os.environ["GLKVM_TEST_X"]), ("de", "de", "1"))
            self.assertEqual(mod.CHAR_TO_KEY["z"][0], "KeyY")
            mod.ENV_FILE.write_text("")
            asyncio.run(mod.kvm_reload_env())
            self.assertNotIn("GLKVM_TEST_X", os.environ)
            self.assertEqual(mod.KEYMAP_NAME, os.environ.get("GLKVM_KEYMAP", "us"))

    def test_keymaps(self):
        mod = _load_module()
        us, de = mod._build_keymap(), mod._build_keymap_de()
        self.assertEqual(us["A"], ("KeyA", ("ShiftLeft",)))
        self.assertEqual(us["z"], ("KeyZ", ()))
        self.assertEqual(de["z"], ("KeyY", ()))
        self.assertEqual(de["@"], ("KeyQ", ("AltRight",)))
        self.assertEqual(de["|"], ("IntlBackslash", ("AltRight",)))
        # every printable ASCII char is typeable on both layouts
        for ch in map(chr, range(32, 127)):
            self.assertIn(ch, us, ch)
            self.assertIn(ch, de, ch)


if __name__ == "__main__":
    unittest.main(verbosity=2)