"""migoodmd: Migood AI's Markdown answers -> GTK (Pango) markup."""
import os
import sys
import unittest
import xml.etree.ElementTree as ET

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "overlay/usr/lib/migood-os"))
import migoodmd  # noqa: E402


def well_formed(markup):
    ET.fromstring(f"<markup>{markup}</markup>")  # raises if GTK would reject it


class Markdown(unittest.TestCase):
    def test_inline(self):
        self.assertEqual(migoodmd.inline("**hi** and *there* `x**y`"),
                         "<b>hi</b> and <i>there</i> <tt>x**y</tt>")

    def test_ai_text_is_escaped(self):
        out = migoodmd.inline('<b onclick="x">&</b> 2 < 3')
        self.assertNotIn("<b onclick", out)
        well_formed(out)

    def test_link(self):
        out = migoodmd.inline("see [Migood](https://www.welltypers.it.com/a?b=1&c=2)")
        self.assertIn('<a href="https://www.welltypers.it.com/a?b=1&amp;c=2">Migood</a>', out)
        well_formed(out)
        self.assertNotIn("<a", migoodmd.inline("[x](javascript:alert(1))"))  # only http(s)

    def test_blocks(self):
        md = "# Title\n\nSome **text**.\n- one\n- two\n1. first\n\n```bash\nls -l\n```\n> tip"
        b = migoodmd.blocks(md)
        self.assertEqual(b[0][0], "text")
        self.assertIn('weight="bold"', b[0][1])
        self.assertIn("•  one", b[1][1])
        self.assertIn("1.  first", b[1][1])
        self.assertEqual(b[2], ("code", "ls -l", "bash"))
        self.assertIn("tip", b[3][1])
        for kind, *rest in b:
            if kind == "text":
                well_formed(rest[0])

    def test_unclosed_code_block_still_shown(self):
        self.assertEqual(migoodmd.blocks("```\nhalf an ans")[-1], ("code", "half an ans", ""))

    def test_tricky_input_stays_valid(self):
        for md in ["**unclosed", "a * b * c", "snake_case_name", "x < y > z & w",
                   "**bold `code**` end", "[a](https://x.y) **[b](https://z.w)**"]:
            for kind, *rest in migoodmd.blocks(md):
                if kind == "text":
                    well_formed(rest[0])
        self.assertEqual(migoodmd.inline("snake_case_name"), "snake_case_name")


if __name__ == "__main__":
    unittest.main()
