from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class Step22ArtifactsTest(unittest.TestCase):
    def test_memory_pressure_has_hold_seconds(self) -> None:
        content = Path(ROOT, "scripts/fault-scenarios/memory-pressure.sh").read_text(encoding="utf-8")
        self.assertIn("HOLD_SECONDS", content)
        self.assertIn("sleep ${HOLD_SECONDS}", content)

    def test_memory_pressure_default_hold_at_least_30s(self) -> None:
        content = Path(ROOT, "scripts/fault-scenarios/memory-pressure.sh").read_text(encoding="utf-8")
        # Default must be >= 30s to span at least one 30s scoring window
        import re
        m = re.search(r'HOLD_SECONDS[^:]*:-(\d+)', content)
        self.assertIsNotNone(m, "HOLD_SECONDS default not found")
        assert m is not None
        self.assertGreaterEqual(int(m.group(1)), 30)

    def test_memory_pressure_still_has_dd(self) -> None:
        content = Path(ROOT, "scripts/fault-scenarios/memory-pressure.sh").read_text(encoding="utf-8")
        self.assertIn("dd if=/dev/zero", content)
        self.assertIn("SIZE_MB", content)

    def test_step22_docs_exist(self) -> None:
        path = Path(ROOT, "docs/steps/step22/README.md")
        self.assertTrue(path.exists())
        content = path.read_text(encoding="utf-8")
        for term in [
            "memory-pressure Detection Fix",
            "HOLD_SECONDS",
            "fault_target_verdict",
            "cpu-stress",
            "step16_repeat_experiments.sh",
            "Detection rate",
        ]:
            with self.subTest(term=term):
                self.assertIn(term, content)


if __name__ == "__main__":
    unittest.main()
