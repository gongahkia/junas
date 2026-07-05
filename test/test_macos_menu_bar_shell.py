from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
APP_ROOT = ROOT / "apps" / "macos-menu-bar"


class MacosMenuBarShellTests(unittest.TestCase):
    def test_swiftpm_menu_bar_shell_contains_required_controls(self):
        app = (APP_ROOT / "Sources" / "JunasMenuBar" / "App" / "JunasMenuBarApp.swift").read_text(encoding="utf-8")
        menu = (APP_ROOT / "Sources" / "JunasMenuBar" / "Views" / "MenuBarContentView.swift").read_text(
            encoding="utf-8"
        )
        status = (APP_ROOT / "Sources" / "JunasMenuBar" / "Views" / "StatusWindowView.swift").read_text(
            encoding="utf-8"
        )
        store = (APP_ROOT / "Sources" / "JunasMenuBar" / "Stores" / "PipelineStore.swift").read_text(encoding="utf-8")
        client = (APP_ROOT / "Sources" / "JunasMenuBar" / "Services" / "SidecarClient.swift").read_text(
            encoding="utf-8"
        )

        for token in (
            "MenuBarExtra",
            'WindowGroup("Junas", id: "main")',
            ".menuBarExtraStyle(.window)",
            "Start Redaction",
            "Pause Redaction",
            "Stop Redaction",
        ):
            self.assertIn(token, app)
        for token in ('Picker("Source"', 'Picker("Transform"', 'Picker("Output"', "Open TUI"):
            self.assertIn(token, menu)
            self.assertIn(token, status)
        for token in ("source.select", "transform.select", "output.select", "capture.start", "capture.pause"):
            self.assertIn(token, client)
        self.assertIn("JUNAS_SIDECAR_COMMAND", client)
        self.assertIn("junas-sidecar/junas-sidecar", client)
        self.assertIn("junas --tui", store)

    def test_run_script_and_codex_environment_build_menu_bar_app(self):
        script = (ROOT / "script" / "build_and_run.sh").read_text(encoding="utf-8")
        environment = (ROOT / ".codex" / "environments" / "environment.toml").read_text(encoding="utf-8")

        for token in (
            'APP_NAME="JunasMenuBar"',
            'PACKAGE_DIR="$ROOT_DIR/apps/macos-menu-bar"',
            "swift build --package-path",
            "CFBundlePackageType",
            "--bundle-only|bundle",
            "--verify|verify",
        ):
            self.assertIn(token, script)
        self.assertIn('command = "./script/build_and_run.sh"', environment)

    def test_menu_bar_shell_docs_cover_ui_sidecar_tui_and_packaging(self):
        doc = (ROOT / "docs" / "integrations" / "macos-menu-bar-shell.md").read_text(encoding="utf-8")
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        docs_index = (ROOT / "docs" / "README.md").read_text(encoding="utf-8")
        integrations_index = (ROOT / "docs" / "integrations" / "README.md").read_text(encoding="utf-8")

        for token in (
            "SwiftPM shell scaffold",
            "MenuBarExtra",
            "source picker",
            "transform picker",
            "output picker",
            "start, pause, and stop",
            "junas --tui",
            "JUNAS_SIDECAR_COMMAND",
            "dist/JunasMenuBar.app",
        ):
            self.assertIn(token, doc)
        self.assertIn("docs/integrations/macos-menu-bar-shell.md", readme)
        self.assertIn("integrations/macos-menu-bar-shell.md", docs_index)
        self.assertIn("macos-menu-bar-shell.md", integrations_index)


if __name__ == "__main__":
    unittest.main()
