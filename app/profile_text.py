"""Field Guide profile layout for the game's multiline text table."""
import re
import textwrap


# Horizontal advances from the English commonfont, in thousandths of an em.
# The printable ASCII range starts at space. No installed font is required.
_ASCII_ADVANCES = (
    345, 400, 500, 690, 690, 1000, 741, 345, 400, 400, 500, 690, 345, 476, 345, 400,
    690, 690, 690, 690, 690, 690, 690, 690, 690, 690, 400, 400, 690, 690, 690, 690,
    891, 727, 722, 729, 791, 678, 636, 784, 792, 342, 484, 706, 621, 934, 789, 806,
    701, 802, 726, 698, 624, 792, 710, 956, 666, 632, 683, 400, 400, 400, 690, 500,
    400, 602, 649, 584, 656, 612, 355, 644, 652, 290, 302, 575, 293, 905, 652, 649,
    649, 656, 422, 558, 391, 652, 555, 810, 531, 576, 546, 400, 345, 400, 500,
)
# 27.4 em best approximates the word breaks in the English patch table.
# Stock manually laid-out lines reach 29.856 em. Keep those breaks on export.
_WRAP_ADVANCE = 27400
_AUTHORED_ADVANCE = 30000
_HEADING = re.compile(r"(■[ \t]*Effects\s+of\s+the\s+X\s+Antibody\s+on\s+[^■:]+?\bDigiCore:)", re.I)
_PUNCTUATION = str.maketrans({"‘": "'", "’": "'", "`": "'", "“": '"', "”": '"',
                              "\u00a0": " ", "\u202f": " ", "\u200b": "", "\ufeff": ""})
_SPACED_SUFFIX = re.compile(r"(?<=[\w)])[^\S\n]*'[^\S\n]*(?=(?:s|t|re|ve|ll|d|m)\b)", re.I)


def _advance(text):
    return sum(_ASCII_ADVANCES[n - 32] if 32 <= n < 127 else 1000 for n in map(ord, text))


def _wrap_words(text):
    lines = []
    line = []
    advance = 0
    for word in text.split():
        word_width = _advance(word)
        next_width = advance + (_ASCII_ADVANCES[0] if line else 0) + word_width
        if line and next_width > _WRAP_ADVANCE:
            lines.append(" ".join(line))
            line = []
            next_width = word_width
        line.append(word)
        advance = next_width
    if line:
        lines.append(" ".join(line))
    return lines


def _layout_lines(text):
    lines = []
    for line in text.split("\n"):
        if _advance(line) <= _AUTHORED_ADVANCE:
            lines.append(line)
        else:
            lines.extend(_wrap_words(line))
    return "\n".join(lines)


def _format_english_paragraph(paragraph):
    # Captured headings alternate with prose. A heading may cross an old hard wrap.
    preface, *sections = _HEADING.split(paragraph)
    if not sections:
        return _layout_lines(preface)
    blocks = []
    if preface.strip():
        if preface.rstrip(" \t").endswith("\n"):
            blocks.append(_layout_lines(preface.rstrip("\n ")))
        else:
            blocks.append("\n".join(_wrap_words(preface)))

    for heading, body in zip(sections[::2], sections[1::2]):
        if "\n" in heading and body.startswith(" ") and not preface.strip():
            # A few authored headings (e.g. UlforceVeedramon) share their
            # continuation line with the first sentence. Keep that layout.
            blocks.append(_layout_lines(heading + body))
            continue
        title = " ".join(heading.split()).replace("■ ", "■")
        block = _layout_lines(title)
        if body.strip():
            if body.lstrip(" \t").startswith("\n"):
                prose = _layout_lines(body.lstrip(" \t").removeprefix("\n").rstrip("\n"))
            else:
                prose = "\n".join(_wrap_words(body))
            block += "\n" + prose
        blocks.append(block)
    return "\n\n".join(blocks)


def format_profile_text_for_game(text: str, *, english: bool = True) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n").strip("\n")
    if not text.strip():
        return ""
    if english:
        text = _SPACED_SUFFIX.sub("'", text.translate(_PUNCTUATION))
    paragraphs = re.split(r"\n(?:[ \t]*\n)+", text)
    if english:
        return "\n\n".join(_format_english_paragraph(p) for p in paragraphs)
    # Other language folders keep their punctuation and existing wrap convention.
    return "\n\n".join("\n".join(wrapped for line in p.splitlines()
                                 for wrapped in textwrap.wrap(" ".join(line.split()), width=50,
                                                              break_long_words=False, break_on_hyphens=False))
                       for p in paragraphs)


def profile_line_stats(text: str) -> str:
    lines = text.splitlines() or [""]
    return f"Lines: {len(lines)} | Longest line: {max(map(len, lines))} characters"
