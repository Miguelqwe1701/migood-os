"""Markdown -> GTK (Pango) markup, for Migood AI's answers.

Migood AI writes Markdown (**bold**, lists, `code`, ...). GTK labels don't
read Markdown, but they read Pango markup (a small HTML-like language), so
this turns one into the other. Only the standard library; small on purpose.

  blocks(md) -> [("text", markup), ("code", plain_code, language), ...]

Text blocks go in a Gtk.Label with use_markup; code blocks get their own
monospace box with a Copy button. Everything from the AI is escaped first,
so an answer can never inject its own markup.
"""
import re
from html import escape

# (`code` spans are set aside first in inline(), so ** inside code stays as it is.)
INLINE = [
    (re.compile(r"\*\*(.+?)\*\*|__(.+?)__"), lambda m: f"<b>{m.group(1) or m.group(2)}</b>"),
    (re.compile(r"(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?![\w*])|(?<!\w)_(?!\s)(.+?)(?<!\s)_(?!\w)"),
     lambda m: f"<i>{m.group(1) or m.group(2)}</i>"),
    (re.compile(r"~~(.+?)~~"), lambda m: f"<s>{m.group(1)}</s>"),
]
LINK = re.compile(r"\[([^\]\n]+)\]\((https?://[^)\s]+)\)")
HEADING = re.compile(r"^(#{1,6})\s+(.*)$")
BULLET = re.compile(r"^(\s*)[-*+]\s+(.*)$")
NUMBER = re.compile(r"^(\s*)(\d+)[.)]\s+(.*)$")
QUOTE = re.compile(r"^>\s?(.*)$")
SIZES = {1: "x-large", 2: "large", 3: "medium"}


def inline(text):
    """One line of Markdown -> Pango markup (escaped first)."""
    links = []

    def keep_link(m):  # set links aside BEFORE escaping, so they're escaped once
        links.append((m.group(1), m.group(2)))
        return f"\x00{len(links) - 1}\x00"
    out = escape(LINK.sub(keep_link, text), quote=False)
    # Protect `code` spans from the other rules.
    codes = []

    def keep_code(m):
        codes.append(m.group(1))
        return f"\x01{len(codes) - 1}\x01"
    out = re.sub(r"`([^`\n]+)`", keep_code, out)
    for rx, fn in INLINE:
        out = rx.sub(fn, out)
    out = re.sub("\x01(\\d+)\x01", lambda m: f"<tt>{codes[int(m.group(1))]}</tt>", out)
    out = re.sub("\x00(\\d+)\x00", lambda m: '<a href="{1}">{0}</a>'.format(
        inline(links[int(m.group(1))][0]), escape(links[int(m.group(1))][1], quote=True)), out)
    return out


def blocks(md):
    result, para, fence = [], [], None

    def flush():
        if para:
            result.append(("text", "\n".join(para)))
            para.clear()

    for line in (md or "").replace("\r\n", "\n").split("\n"):
        if fence is not None:
            if line.strip().startswith("```"):
                result.append(("code", "\n".join(fence["lines"]), fence["lang"]))
                fence = None
            else:
                fence["lines"].append(line)
            continue
        if line.strip().startswith("```"):
            flush()
            fence = {"lang": line.strip()[3:].strip(), "lines": []}
            continue
        if not line.strip():
            flush()
            continue
        m = HEADING.match(line)
        if m:
            flush()
            size = SIZES.get(len(m.group(1)), "medium")
            result.append(("text", f'<span size="{size}" weight="bold">{inline(m.group(2))}</span>'))
            continue
        m = BULLET.match(line)
        if m:
            indent = "    " * (len(m.group(1)) // 2)
            para.append(f"{indent}•  {inline(m.group(2))}")
            continue
        m = NUMBER.match(line)
        if m:
            indent = "    " * (len(m.group(1)) // 2)
            para.append(f"{indent}{m.group(2)}.  {inline(m.group(3))}")
            continue
        m = QUOTE.match(line)
        if m:
            para.append(f'<span foreground="#9aa4ad">▎ <i>{inline(m.group(1))}</i></span>')
            continue
        if re.fullmatch(r"\s*([-*_])(\s*\1){2,}\s*", line):
            flush()
            result.append(("text", '<span foreground="#5a6470">────────────</span>'))
            continue
        para.append(inline(line))
    if fence is not None:  # an unclosed ``` (answer cut off): still show it as code
        result.append(("code", "\n".join(fence["lines"]), fence["lang"]))
    flush()
    return result
