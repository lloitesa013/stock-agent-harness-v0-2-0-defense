import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DOCS = [
    "docs/PRODUCT_VISION.md",
    "docs/ARCHITECTURE.md",
    "docs/UI_SPEC.md",
    "docs/MANAGING_AGENT.md",
    "docs/COMPARISON.md",
    "docs/PITCH_SCRIPT.md",
    "docs/ROADMAP.md",
    "docs/RISK_DISCLOSURE.md",
]


class ProductizationDocsTests(unittest.TestCase):
    def test_required_product_docs_exist(self):
        for relative in DOCS:
            with self.subTest(relative=relative):
                path = ROOT / relative
                self.assertTrue(path.exists(), relative)
                self.assertGreater(path.stat().st_size, 200)

    def test_readme_links_required_docs(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        for relative in DOCS:
            with self.subTest(relative=relative):
                self.assertIn(relative, readme)

    def test_product_identity_is_not_trading_bot(self):
        product = (ROOT / "docs" / "PRODUCT_VISION.md").read_text(encoding="utf-8")
        self.assertIn("Financial Agent Evidence OS", product)
        self.assertIn("It is not a trading bot.", product)

    def test_markdown_links_resolve_for_product_docs(self):
        link_pattern = re.compile(r"\[[^\]]+\]\(([^)]+)\)")
        for relative in ["README.md"] + DOCS:
            source = ROOT / relative
            text = source.read_text(encoding="utf-8")
            for href in link_pattern.findall(text):
                if "://" in href or href.startswith("#"):
                    continue
                target = (source.parent / href).resolve()
                with self.subTest(source=relative, href=href):
                    self.assertTrue(target.exists(), href)


if __name__ == "__main__":
    unittest.main()
