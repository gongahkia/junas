import html
import re
import unittest
from pathlib import Path
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parent.parent
README = ROOT / "README.md"
MARKDOWN_LINK_RE = re.compile(r"!?(?<!\\)\[[^\]]*]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")
HTML_LINK_RE = re.compile(r"\b(?:href|src)=\"([^\"]+)\"")


def _without_fenced_blocks(text: str) -> str:
    return re.sub(r"```.*?```", "", text, flags=re.S)


def _local_links(path: Path) -> list[str]:
    text = _without_fenced_blocks(path.read_text(encoding="utf-8"))
    links = [match.group(1) for match in MARKDOWN_LINK_RE.finditer(text)]
    links.extend(html.unescape(match.group(1)) for match in HTML_LINK_RE.finditer(text))
    return [link for link in links if _is_local(link)]


def _is_local(link: str) -> bool:
    return not link.startswith(("http://", "https://", "mailto:", "data:"))


def _resolve(base: Path, link: str) -> tuple[Path, str]:
    raw_path, _, anchor = link.partition("#")
    raw_path = unquote(raw_path)
    if not raw_path:
        return base, anchor
    path = Path(raw_path.removeprefix("./"))
    if path.is_absolute():
        target = ROOT / str(path).lstrip("/")
    elif base == README:
        target = ROOT / path
    else:
        target = base.parent / path
    return target.resolve(), anchor


def _github_slug(text: str) -> str:
    text = re.sub(r"`([^`]*)`", r"\1", text.strip())
    text = re.sub(r"<[^>]+>", "", text)
    text = text.lower()
    text = re.sub(r"[^a-z0-9\s-]", "", text)
    text = re.sub(r"\s", "-", text)
    return text.strip("-")


def _markdown_anchors(path: Path) -> set[str]:
    anchors = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        match = re.match(r"^(#{1,6})\s+(.+?)\s*#*$", line)
        if match:
            anchors.add(_github_slug(match.group(2)))
    return anchors


def _assert_local_link(testcase: unittest.TestCase, base: Path, link: str) -> Path:
    target, anchor = _resolve(base, link)
    testcase.assertTrue(target.exists(), f"{base.relative_to(ROOT)} links missing local target {link}")
    testcase.assertTrue(
        target == ROOT or ROOT in target.parents,
        f"{base.relative_to(ROOT)} links outside repo: {link}",
    )
    if anchor and target.suffix.lower() == ".md":
        testcase.assertIn(anchor, _markdown_anchors(target), f"{base.relative_to(ROOT)} has dead anchor {link}")
    elif anchor:
        testcase.assertRegex(anchor, r"^L\d+(-L\d+)?$", f"{base.relative_to(ROOT)} has unsupported anchor {link}")
    return target


class DocsLinkTests(unittest.TestCase):
    def test_readme_local_links_exist_and_anchors_resolve(self):
        for link in _local_links(README):
            with self.subTest(link=link):
                _assert_local_link(self, README, link)

    def test_docs_pages_linked_from_readme_have_no_dead_local_links(self):
        pages: set[Path] = set()
        for link in _local_links(README):
            target, _ = _resolve(README, link)
            if not (target == ROOT or ROOT in target.parents) or not target.exists():
                continue
            if target.suffix.lower() == ".md" and ROOT / "docs" in {target, *target.parents}:
                pages.add(target)
            elif target.is_dir() and ROOT / "docs" in {target, *target.parents}:
                index = target / "README.md"
                if index.exists():
                    pages.add(index)
        self.assertTrue(pages)
        for page in sorted(pages):
            for link in _local_links(page):
                with self.subTest(page=page.relative_to(ROOT), link=link):
                    _assert_local_link(self, page, link)


if __name__ == "__main__":
    unittest.main()
