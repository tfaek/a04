#######
# Regendering Script for "John Shepard" to "Jane Shepard" (v3) #######
# Takes a whole ebook (.azw3 or .epub) and makes Shepard female, editing the
# book's XHTML paragraph-by-paragraph so all formatting is preserved.
#
# How it differs from v2:
#   - Input is an ebook, output is a regendered .epub (+ .azw3 if Calibre's
#     `ebook-convert` is installed). No more hand-split chapter txt files.
#   - The model sees numbered paragraphs and returns ONLY the paragraphs it
#     changes (structured output). Untouched paragraphs stay byte-identical,
#     so there's no truncation/drift and no chunk-overlap merging.
#   - Two passes per chapter: an EDIT pass, then a REVIEW pass that sees
#     original vs revised text and fixes missed references, pronoun ambiguity
#     between Shepard and other women, body descriptions and over-editing.
#     A small BODY CHECK pass then removes gratuitous added breast mentions.
#   - Results are cached per chapter, so an interrupted run resumes.
#   - A word-level change report (changes.md) lists every edit for review.
#
# USAGE:
#   From the project root directory:
#     uv run src/regender_v3.py <book.azw3|book.epub> [options]
#
#   Examples:
#     uv run src/regender_v3.py inputs/rekindling/Rekindling_A_Hero.azw3
#     uv run src/regender_v3.py inputs/veryend     # books 1-3 become prologues to book 4
#     uv run src/regender_v3.py inputs/rekindling/Rekindling_A_Hero.azw3 --only part0003,part0004
#     uv run src/regender_v3.py book.epub --model gpt-5.5 --effort high --no-review
#
#   Output goes to outputs/{input directory name}/:
#     ch{N}.txt per chapter (numbered as in the book) for scripts/create_html_chapters.py,
#     {book}_regendered.epub, {book}_regendered.azw3 (if Calibre available),
#     {book}_changes.md, and v3_work/ (cache; delete it or pass --fresh to redo)
#######

from openai import OpenAI
from pydantic import BaseModel
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
import argparse
import difflib
import html
import json
import re
import shutil
import subprocess
import threading
import zipfile
import mobi
from dotenv import load_dotenv

load_dotenv()
client = OpenAI(max_retries=5, timeout=900)

DEFAULT_MODEL = "gpt-6.1-sol"
MAX_CHUNK_CHARS = 40000   # editable text per request; most chapters fit in one
CONTEXT_PARAS = 12        # read-only paragraphs shown before each chunk
SERVICE_TIER = "auto"     # "flex" = half price, slower; set by --flex

RULES = """The story is Mass Effect fan fiction. Its protagonist, Commander Shepard, is currently a man and must become a woman. Nothing else about the story changes.

WHAT TO CHANGE (only where it refers to Shepard)
- Pronouns: he/him/his/himself → she/her/her/herself.
- First name: John → Jane (and any diminutive of it). "Shepard", "Commander", "the commander", "Spectre", ranks and titles stay as they are.
- Gendered nouns and forms of address, including in other characters' dialogue: man/guy/boy/gentleman/brother/son/boyfriend/husband/lad/mister → the natural female equivalent; "sir" → "ma'am"; James Vega's nickname "Loco" → "Lola".
- Book metadata, summaries and notes that describe Shepard (e.g. a "Male Shepard" tag → "Female Shepard"; "F/M" → "F/F" when it's Shepard's pairing with a woman).

SHEPARD'S BODY
Wherever the text describes Shepard's body it must read as a woman's:
- Remove or replace male-only features: beard, stubble, shaving, five o'clock shadow, Adam's apple, chest hair and other heavy body hair, a deep/baritone voice (→ low or husky), etc. If removing leaves a gap, substitute something comparable ("his beard and hair" → "her hair"; scratching his stubble → rubbing her jaw; hair on his chest tickling her palms → her skin's warmth under her palms).
- Keep athletic, soldierly traits — muscle, scars, height, strength. Don't feminise beyond what's needed.
- When Shepard's chest is bare or exposed, or a sensual moment dwells on her chest or body, the scene must acknowledge that she has breasts — a brief, natural mention, in your own words, woven into the existing sentence. Once per scene is enough, and don't reuse the same phrasing. Never add one in fights, injuries, medical scenes, descriptions of her corpse or body under reconstruction, or hugs and touches over clothing or armour. Match the original's tone and level of explicitness — no more, no less.
- If an intimate scene describes male anatomy, adapt it consistently to female anatomy at the same level of explicitness.

AVOID PRONOUN AMBIGUITY
Swapping pronouns can leave a sentence with two women where "she"/"her" no longer clearly points at one of them (e.g. Shepard and Tali). Whenever a pronoun could now reasonably be read as either woman, disambiguate with the lightest touch: replace one pronoun with a name ("Shepard", "Tali") or an epithet the story already uses ("the commander", "the quarian"), or minimally restructure. Watch for collisions like "with her on top of her" and "her hands on her chest". The riskiest spots are possessives on body parts during physical contact between two women (her hand, her neck, her hair, her chest): check every one of those. Don't overdo it — this matters as much as resolving ambiguity:
- Only intervene where a reader would genuinely stumble. Where context already makes the referent clear, keep the pronoun.
- A sentence or paragraph that involves only one woman needs no names swapped in at all.
- In a scene told from one woman's point of view, she can usually keep "she"/"her"; name the other woman only where needed.
- Use as few substitutions as possible and don't stack them: avoid strings like "Shepard's … the commander … Shepard's … the commander". Prefer names; use epithets sparingly.

Examples (Tali is a woman):
  Original: Tali ran her hand up his neck, feeling the slow pulse beneath the skin. Afterward, she indulged in the textures of his beard and hair.
  Revised:  Tali ran her hand up Shepard’s neck, feeling the slow pulse beneath the skin. Afterward, she indulged in the texture of the commander’s hair.
  Original: She leaned forward, her hands on his chest again.   (She = Tali)
  Revised:  She leaned forward, her hands on Shepard’s chest again.
  Original: Rubbing her fingers together nervously, she placed her hands on his bare chest. The couple were just inches apart, and she could feel him looking at her from above.
  Revised:  Rubbing her fingers together nervously, Tali placed her hands on Shepard’s bare chest, between her breasts. The couple were just inches apart, and she could feel Shepard looking at her from above.
  (Write your own wording for body descriptions; don't copy the examples.)

LEAVE ALONE
- Every other character's gender. Track referents carefully: in a scene with Shepard and another man, only Shepard's pronouns change.
- All other wording, plot, dialogue, style and spelling. Match the source's punctuation and typography exactly, including curly quotes and apostrophes (’ “ ”).
- Inline tags such as <em>…</em>: keep every tag, in the same order."""

EDIT_PROMPT = f"""You are a meticulous fiction editor.

{RULES}

You'll receive numbered paragraphs. Return ONLY the paragraphs you change, each with its complete revised text. Paragraphs you don't return are kept exactly as they are. Paragraphs under CONTEXT are earlier text for reference only — never return them."""

REVIEW_PROMPT = f"""You are a meticulous fiction editor reviewing another editor's draft.

{RULES}

You'll receive numbered paragraphs. A paragraph the draft left alone is shown once; a paragraph the draft changed is shown as ORIGINAL and REVISED. Read the passage as a reader would, then check:
1. Missed references: any remaining male reference to Shepard — pronoun, noun, name, form of address or physical trait — including in paragraphs the draft left alone.
2. Wrong changes: another character's reference changed, or edits unrelated to Shepard's gender.
3. Ambiguity: any "she"/"her" that could now be read as either Shepard or another woman, judged in light of the surrounding paragraphs.
4. Body: Shepard's physical description not yet reading as a woman's (see SHEPARD'S BODY).
5. Over-correction: names or epithets swapped in where the pronoun was already clear, stacked substitutions that make the prose clunky, or breast mentions repeated within a scene. Restore the original pronoun where it reads clearly.
6. Typography and tags not matching the original.

For each paragraph that needs fixing, return its complete final text and a short reason. To revert a change, return the original text. Return nothing for paragraphs that are fine. Paragraphs under CONTEXT are for reference only — never return them."""


BODY_PROMPT = f"""You are a meticulous fiction editor checking another editor's work.

{RULES}

An earlier pass added mentions of Shepard's breasts that the original text didn't have, and many are gratuitous. Each paragraph to check is shown as ORIGINAL and CURRENT, after a few preceding paragraphs (current text) for context. Decide whether each added mention earns its place:
- Keep it only if Shepard's chest is bare or exposed in the scene, or a sensual moment dwells on her chest or body.
- Remove it in fights, injuries, medical scenes, descriptions of her corpse or body under reconstruction, hugs and touches over clothing or armour, and anywhere else it reads as gratuitous.
- Remove it if the same scene already mentions her breasts in an earlier paragraph.
To remove a mention, return the CURRENT text with only that mention taken out — restore the original wording of that phrase and keep every other edit. Return nothing for paragraphs whose mention should stay."""

BODY_CONTEXT_PARAS = 4


class Edit(BaseModel):
    id: int
    text: str


class EditResult(BaseModel):
    edits: list[Edit]


class ReviewEdit(BaseModel):
    id: int
    text: str
    reason: str


class ReviewResult(BaseModel):
    edits: list[ReviewEdit]


# ---------------------------------------------------------------- ebook I/O

def unpack(book, dest):
    """Unpack .azw3/.epub into dest/ as an exploded EPUB."""
    if dest.exists():
        shutil.rmtree(dest)
    if book.suffix.lower() == ".epub":
        epub = book
    else:
        tmp, epub = mobi.extract(str(book))
        epub = Path(epub)
        if epub.suffix.lower() != ".epub":
            raise SystemExit(f"{book} isn't a KF8/azw3 book (got {epub.name}); convert it to EPUB first.")
    with zipfile.ZipFile(epub) as z:
        z.extractall(dest)
    if book.suffix.lower() != ".epub":
        shutil.rmtree(tmp, ignore_errors=True)


def spine_files(root):
    """XHTML files in reading order, from the OPF spine."""
    container = (root / "META-INF/container.xml").read_text(encoding="utf-8")
    opf_path = root / re.search(r'full-path="([^"]+)"', container).group(1)
    opf = opf_path.read_text(encoding="utf-8")
    manifest = {m.group(1): m.group(2) for m in re.finditer(
        r'<item\b[^>]*?id="([^"]+)"[^>]*?href="([^"]+)"', opf)}
    manifest.update({m.group(2): m.group(1) for m in re.finditer(
        r'<item\b[^>]*?href="([^"]+)"[^>]*?id="([^"]+)"', opf)})
    return [opf_path.parent / manifest[i] for i in re.findall(r'<itemref\b[^>]*idref="([^"]+)"', opf)]


def pack(root, out):
    """Zip an exploded EPUB, mimetype first and uncompressed as the spec requires."""
    with zipfile.ZipFile(out, "w") as z:
        z.write(root / "mimetype", "mimetype", compress_type=zipfile.ZIP_STORED)
        for f in sorted(root.rglob("*")):
            if f.is_file() and f.name != "mimetype":
                z.write(f, f.relative_to(root).as_posix(), compress_type=zipfile.ZIP_DEFLATED)


def is_chapter(src):
    """AO3 exports put each chapter's story text in a userstuff2 div."""
    return 'class="userstuff2"' in src


def heading(src):
    m = re.search(r"<h2\b[^>]*>(.*?)</h2>", src, re.S)
    return " ".join(html.unescape(re.sub(r"<[^>]+>", "", m.group(1))).split()) if m else None


def book_order(path):
    m = re.match(r"\d+", path.name)
    return (int(m.group()) if m else 0, path.name)


def compile_books(main, prologues, dest):
    """Unpack `main` into dest/, inserting each prologue book's story before its first
    chapter as "Prologue N: <title>" (spine, manifest, NCX and the in-book TOC page)."""
    unpack(main, dest)
    files = spine_files(dest)
    opf_path = next(dest.rglob("*.opf"))
    first = next(f for f in files if is_chapter(f.read_text(encoding="utf-8")))
    first_href = first.relative_to(opf_path.parent).as_posix()
    opf = opf_path.read_text(encoding="utf-8")
    ncx_path = next(dest.rglob("*.ncx"))
    ncx = ncx_path.read_text(encoding="utf-8")
    toc_page = next((f for f in files if f != first and f'href="{first.name}#' in f.read_text(encoding="utf-8")), None)
    item_id = next(re.search(r'id="([^"]+)"', m.group(0)).group(1)
                   for m in re.finditer(r"<item\b[^>]*>", opf) if f'href="{first_href}"' in m.group(0))
    itemref = re.search(rf'<itemref\b[^>]*idref="{re.escape(item_id)}"[^>]*>', opf).group(0)
    nav = re.search(rf'<navPoint\b(?:(?!<navPoint\b).)*?src="{re.escape(first_href)}[#"]', ncx, re.S)

    for k, book in enumerate(prologues, 1):
        tmp = dest.parent / f"prologue{k}"
        unpack(book, tmp)
        story = next(f for f in spine_files(tmp) if is_chapter(f.read_text(encoding="utf-8")))
        src = story.read_text(encoding="utf-8")
        title = f"Prologue {k}: {heading(src)}"
        src = re.sub(r"(<h2\b[^>]*>).*?(</h2>)", lambda m: m.group(1) + html.escape(title, quote=False) + m.group(2), src, count=1, flags=re.S)
        anchor = re.search(r'<h2\b[^>]*id="([^"]+)"', src)
        anchor = f"#{anchor.group(1)}" if anchor else ""
        new_items = []
        # Bring the prologue's own stylesheets along under unique names
        for css in re.findall(r'href="([^"]+\.css)"', src):
            css_src = (story.parent / css).resolve()
            css_name = f"prologue{k}_{css_src.name}"
            shutil.copy(css_src, first.parent.parent / "Styles" / css_name)
            src = src.replace(f'href="{css}"', f'href="../Styles/{css_name}"')
            new_items.append(f'<item id="prologue{k}_{css_src.stem}" media-type="text/css" href="Styles/{css_name}"/>')
        name = f"prologue{k}.xhtml"
        (first.parent / name).write_text(src, encoding="utf-8")
        href = (first.parent / name).relative_to(opf_path.parent).as_posix()
        new_items.append(f'<item id="prologue{k}" media-type="application/xhtml+xml" href="{href}"/>')
        opf = opf.replace("</manifest>", "\n".join(new_items) + "\n</manifest>")
        opf = opf.replace(itemref, f'<itemref idref="prologue{k}"/>\n{itemref}')
        if nav:
            ncx = ncx.replace(nav.group(0), f'<navPoint id="prologue{k}" playOrder="0"><navLabel><text>{html.escape(title)}</text></navLabel>'
                                             f'<content src="{href}{anchor}"/></navPoint>\n' + nav.group(0))
        if toc_page:
            t = toc_page.read_text(encoding="utf-8")
            t = re.sub(rf'(<li>\s*<a href="{re.escape(first.name)}#)',
                       lambda m: f'<li><a href="{name}{anchor}">{html.escape(title)}</a></li>\n' + m.group(1), t, count=1)
            toc_page.write_text(t, encoding="utf-8")
        shutil.rmtree(tmp)

    order = iter(range(1, 10000))
    ncx = re.sub(r'playOrder="\d+"', lambda m: f'playOrder="{next(order)}"', ncx)
    opf_path.write_text(opf, encoding="utf-8")
    ncx_path.write_text(ncx, encoding="utf-8")


# ---------------------------------------------------------------- paragraphs

BLOCK_RE = re.compile(r"(<(p|li|dd|h[1-6])\b[^>]*>)(.*?)(</\2>)", re.S)
INLINE_RE = re.compile(r"<(/?)(em|strong|b|i|span)\b[^>]*>")
TAG_RE = re.compile(r"<(/?[a-zA-Z0-9]+)")


def normalise(inner):
    """Some AO3 exports wrap every run of text in a bare <span> on its own line, so the
    whitespace between tags renders as stray spaces ("Pride and Prejudice , when").
    Drop the bare spans and that inter-tag whitespace; real spaces live inside the spans."""
    if "<span>" not in inner:
        return inner
    return re.sub(r"</?span>", "", re.sub(r">\s+<", "><", inner.strip()))


class Para:
    def __init__(self, match):
        self.span = match.span(3)
        self.tag = match.group(2)
        inner = normalise(match.group(3))
        # Strip attributes off inline tags for the model; remember them for writing back
        self.open_tags = {}
        for m in INLINE_RE.finditer(inner):
            if not m.group(1):
                self.open_tags.setdefault(m.group(2), m.group(0))
        self.text = " ".join(INLINE_RE.sub(r"<\1\2>", inner).split())

    def to_html(self, text):
        text = re.sub(r"&(?!#?\w+;)", "&amp;", text)
        return re.sub(r"<(em|strong|b|i|span)>", lambda m: self.open_tags.get(m.group(1), m.group(0)), text)


def load_paragraphs(path):
    src = path.read_text(encoding="utf-8")
    paras = [Para(m) for m in BLOCK_RE.finditer(src)]
    return src, [p for p in paras if html.unescape(re.sub(r"<[^>]+>", "", p.text)).strip()]


def fix_typography(original, new):
    """Models drift to straight quotes; restore curly ones if the original used them (outside tags)."""
    parts = re.split(r"(<[^>]+>)", new)
    for i in range(0, len(parts), 2):
        s = parts[i]
        if "'" not in original and ("’" in original or "‘" in original):
            s = re.sub(r"(^|[\s(“—])'", r"\1‘", s).replace("'", "’")
        if '"' not in original and "“" in original:
            s = re.sub(r'(^|[\s(—])"', r"\1“", s).replace('"', "”")
        parts[i] = s
    return "".join(parts)


# ---------------------------------------------------------------- model calls

usage = {"input": 0, "output": 0}
usage_lock = threading.Lock()


def call(model, effort, system, user, schema):
    r = client.responses.parse(
        model=model,
        service_tier=SERVICE_TIER,
        reasoning={"effort": effort},
        input=[{"role": "system", "content": system}, {"role": "user", "content": user}],
        text_format=schema,
    )
    with usage_lock:
        usage["input"] += r.usage.input_tokens
        usage["output"] += r.usage.output_tokens
    if r.output_parsed is None:
        raise RuntimeError(f"no parsed output (refusal or incomplete: {r.status})")
    return r.output_parsed


def chunks(paras):
    """Split a chapter into requests of at most MAX_CHUNK_CHARS of editable text."""
    out, start, size = [], 0, 0
    for i, p in enumerate(paras):
        if size + len(p.text) > MAX_CHUNK_CHARS and i > start:
            out.append((start, i))
            start, size = i, 0
        size += len(p.text)
    out.append((start, len(paras)))
    return out


def context_block(context):
    if not context:
        return ""
    return "CONTEXT (earlier text, do not return):\n" + "\n".join(context) + "\n\n"


def edit_chapter(name, paras, prev_context, model, effort, flags):
    """Pass 1: returns {index: revised_text}."""
    edits = {}
    for a, b in chunks(paras):
        context = [p.text for p in paras[max(0, a - CONTEXT_PARAS):a]] if a else prev_context
        body = "\n".join(f"[{i}] {paras[i].text}" for i in range(a, b))
        try:
            result = call(model, effort, EDIT_PROMPT, context_block(context) + "TEXT:\n" + body, EditResult)
        except Exception as e:
            flags.append((name, None, f"edit pass failed for paragraphs {a}-{b - 1}: {e}"))
            continue
        for e in result.edits:
            if a <= e.id < b and e.text != paras[e.id].text:
                edits[e.id] = e.text
    return edits


def review_chapter(name, paras, edits, prev_context, model, effort, flags):
    """Pass 2: returns {index: (final_text, reason)} corrections on top of `edits`."""
    fixes = {}
    for a, b in chunks(paras):
        context = [edits.get(i, paras[i].text) for i in range(max(0, a - CONTEXT_PARAS), a)] if a else prev_context
        lines = []
        for i in range(a, b):
            if i in edits:
                lines.append(f"[{i}] ORIGINAL: {paras[i].text}\n[{i}] REVISED: {edits[i]}")
            else:
                lines.append(f"[{i}] {paras[i].text}")
        try:
            result = call(model, effort, REVIEW_PROMPT, context_block(context) + "TEXT:\n" + "\n".join(lines), ReviewResult)
        except Exception as e:
            flags.append((name, None, f"review pass failed for paragraphs {a}-{b - 1}: {e}"))
            continue
        for e in result.edits:
            if a <= e.id < b and e.text != edits.get(e.id, paras[e.id].text):
                fixes[e.id] = (e.text, e.reason)
    return fixes


def body_check(name, paras, final, model, effort, flags):
    """Pass 3: drop gratuitous breast mentions the earlier passes added. Returns {index: (text, reason)}."""
    candidates = [i for i, t in final.items()
                  if re.search(r"breast", t, re.I) and not re.search(r"breast", paras[i].text, re.I)]
    if not candidates:
        return {}
    blocks = []
    for i in sorted(candidates):
        context = [final.get(j, paras[j].text) for j in range(max(0, i - BODY_CONTEXT_PARAS), i)]
        blocks.append("CONTEXT:\n" + "\n".join(context) + f"\nCHECK [{i}]\nORIGINAL: {paras[i].text}\nCURRENT: {final[i]}")
    try:
        result = call(model, effort, BODY_PROMPT, "\n\n---\n\n".join(blocks), ReviewResult)
    except Exception as e:
        flags.append((name, None, f"body check failed: {e}"))
        return None
    return {e.id: (e.text, e.reason) for e in result.edits if e.id in candidates and e.text != final[e.id]}


def merged(data):
    """Paragraph index -> latest text after edit, review and body-check passes."""
    final = {int(i): t for i, t in data["edits"].items()}
    for key in ("fixes", "body"):
        for i, (t, _) in data.get(key, {}).items():
            final[int(i)] = t
    return final


# ---------------------------------------------------------------- per chapter

def process_chapter(path, prev_context, args, cache_dir):
    name = path.stem
    cache = cache_dir / f"{name}.json"
    src, paras = load_paragraphs(path)
    if cache.exists():
        data = json.loads(cache.read_text(encoding="utf-8"))
    else:
        flags = []
        edits = edit_chapter(name, paras, prev_context, args.model, args.effort, flags) if paras else {}
        fixes = {}
        if paras and not args.no_review:
            fixes = review_chapter(name, paras, edits, prev_context, args.model, args.effort, flags)
        data = {
            "edits": {str(i): t for i, t in edits.items()},
            "fixes": {str(i): list(v) for i, v in fixes.items()},
            "flags": [list(f) for f in flags],
        }
    # Body check runs separately so chapters cached before it existed get it too
    if "body" not in data and not data["flags"]:
        body = body_check(name, paras, merged(data), args.model, args.effort, data["flags"])
        if body is not None:
            data["body"] = {str(i): list(v) for i, v in body.items()}
    # Don't cache a chapter whose API calls failed, so a rerun retries it
    if not data["flags"]:
        cache.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    return name, src, paras, data


def finalize(name, src, paras, data):
    """Apply edits + fixes with sanity checks. Returns (new_src, changes, flags)."""
    flags = [tuple(f) for f in data["flags"]]
    final = merged(data)
    reasons = {}
    for key in ("fixes", "body"):
        for i, (_, reason) in data.get(key, {}).items():
            reasons[int(i)] = reason

    changes = []
    for i in sorted(final):
        p, new = paras[i], fix_typography(paras[i].text, final[i])
        if new == p.text:
            continue
        if TAG_RE.findall(new) != TAG_RE.findall(p.text):
            flags.append((name, i, f"edit dropped/added inline tags, kept original: {p.text[:80]}"))
            continue
        ratio = len(new) / max(len(p.text), 1)
        if len(p.text) > 80 and not 0.6 < ratio < 1.6:
            flags.append((name, i, f"length changed {ratio:.0%} — check this paragraph"))
        changes.append((i, p, new, reasons.get(i)))

    for i, p in enumerate(paras):
        text = final.get(i, p.text)
        if re.search(r"\bJohn\b", text):
            flags.append((name, i, "still mentions 'John' — check it isn't Shepard"))

    # Splice changed paragraphs back into the XHTML, back to front so offsets stay valid
    for i, p, new, _ in sorted(changes, key=lambda c: c[1].span[0], reverse=True):
        s, e = p.span
        src = src[:s] + p.to_html(new) + src[e:]
    return src, changes, flags


def chapter_txt(src):
    """Front-end format (scripts/create_html_chapters.py): heading line, then the story's
    paragraphs separated by blank lines. None if the file isn't a chapter."""
    title = heading(src)
    body = re.search(r'<div class="userstuff2">(.*?)</div>', src, re.S)
    if not title or not body:
        return None
    paras = [" ".join(html.unescape(re.sub(r"<[^>]+>", "", normalise(m.group(1)))).split()) or "\u00a0"
             for m in re.finditer(r"<p\b[^>]*>(.*?)</p>", body.group(1), re.S)]
    # Drop the empty spacer paragraph AO3 puts at the top of every chapter
    while paras and not paras[0].strip():
        paras.pop(0)
    return title + "\n\n" + "\n\n".join(paras) + "\n"


def word_diff(old, new):
    a, b = old.split(), new.split()
    out = []
    for op, i1, i2, j1, j2 in difflib.SequenceMatcher(None, a, b).get_opcodes():
        if op == "equal":
            out.append(" ".join(a[i1:i2]))
        else:
            if i2 > i1:
                out.append("~~" + " ".join(a[i1:i2]) + "~~")
            if j2 > j1:
                out.append("**" + " ".join(b[j1:j2]) + "**")
    return " ".join(out)


# ---------------------------------------------------------------- main

if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Regender Shepard in an ebook (v3)")
    ap.add_argument("book", type=Path, help=".azw3/.epub file, or a directory of numbered books: "
                    "the last is the main story, the earlier ones become its prologues")
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--effort", default="medium", choices=["low", "medium", "high"], help="reasoning effort")
    ap.add_argument("--no-review", action="store_true", help="skip the review pass (about half the cost)")
    ap.add_argument("--only", help="comma-separated chapter files to process, e.g. part0003,part0004")
    ap.add_argument("--workers", type=int, default=6, help="chapters processed in parallel")
    ap.add_argument("--flex", action="store_true", help="use Flex processing: half price, slower responses")
    ap.add_argument("--fresh", action="store_true", help="ignore cached results from earlier runs")
    args = ap.parse_args()
    if args.flex:
        SERVICE_TIER = "flex"

    if args.book.is_dir():
        books = sorted([b for b in args.book.iterdir() if b.suffix.lower() in (".azw3", ".epub")], key=book_order)
        output_dir = Path("outputs") / args.book.name
        stem = args.book.name
    else:
        books = [args.book]
        output_dir = Path("outputs") / args.book.parent.name
        stem = args.book.stem
    work_dir = output_dir / "v3_work"
    cache_dir = work_dir / "cache" / stem
    epub_dir = work_dir / "epub"
    if args.fresh and cache_dir.exists():
        shutil.rmtree(cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)

    print(f"Input:  {args.book}")
    print(f"Output: {output_dir}")
    print(f"Model:  {args.model} (effort {args.effort}, review {'off' if args.no_review else 'on'}, tier {SERVICE_TIER})")

    for k, b in enumerate(books[:-1], 1):
        print(f"Prologue {k}: {b.name}")
    compile_books(books[-1], books[:-1], epub_dir)
    files = spine_files(epub_dir)
    # Front-end txt files are numbered in reading order: ch1.txt is the first chapter
    chapter_numbers = {f: n for n, f in enumerate((f for f in files if is_chapter(f.read_text(encoding="utf-8"))), 1)}
    if args.only:
        wanted = set(args.only.split(","))
        selected = [f for f in files if f.stem in wanted]
    else:
        selected = files
    print(f"Chapters: {len(selected)} of {len(files)} spine files\n")

    # Read-only context for each chapter = last paragraphs of the previous spine file (original text)
    prev_context = {}
    for prev, cur in zip([None] + files, files):
        prev_context[cur] = [p.text for p in load_paragraphs(prev)[1][-CONTEXT_PARAS:]] if prev else []

    results = {}
    with ThreadPoolExecutor(args.workers) as pool:
        futures = {pool.submit(process_chapter, f, prev_context[f], args, cache_dir): f for f in selected}
        for n, fut in enumerate(as_completed(futures), 1):
            name, src, paras, data = fut.result()
            results[futures[fut]] = (name, src, paras, data)
            print(f"  [{n}/{len(selected)}] {name}: {len(paras)} paragraphs, "
                  f"{len(data['edits'])} edited, {len(data['fixes'])} fixed in review, "
                  f"{len(data.get('body', {}))} body-check fixes"
                  + (f", {len(data['flags'])} FAILED calls" if data["flags"] else ""))

    report = []
    all_flags = []
    total_changes = 0
    txt_count = 0
    ncx_path = next(epub_dir.rglob("*.ncx"))
    ncx = ncx_path.read_text(encoding="utf-8")
    for f in selected:
        name, src, paras, data = results[f]
        new_src, changes, flags = finalize(name, src, paras, data)
        f.write_text(new_src, encoding="utf-8")
        chapter = chapter_txt(new_src)
        if chapter and f in chapter_numbers:
            (output_dir / f"ch{chapter_numbers[f]}.txt").write_text(chapter, encoding="utf-8")
            txt_count += 1
        # Keep the ebook's table of contents in step with regendered headings
        for i, p, new, _ in changes:
            if p.tag.startswith("h"):
                ncx = ncx.replace(f"<text>{p.text}</text>", f"<text>{new}</text>")
        all_flags += flags
        total_changes += len(changes)
        if changes:
            report.append(f"\n## {name}\n")
            for i, p, new, reason in changes:
                report.append(f"**[{i}]**" + (f" _review: {reason}_" if reason else "") + f"\n\n{word_diff(p.text, new)}\n")

    ncx_path.write_text(ncx, encoding="utf-8")
    epub_out = output_dir / f"{stem}_regendered.epub"
    pack(epub_dir, epub_out)
    print(f"\n✓ Saved {epub_out} ({total_changes} paragraphs changed)")
    print(f"✓ Saved {txt_count} chapter txt files to {output_dir}/ "
          f"(for the web: python scripts/create_html_chapters.py {output_dir})")

    if shutil.which("ebook-convert"):
        azw3_out = output_dir / f"{stem}_regendered.azw3"
        subprocess.run(["ebook-convert", str(epub_out), str(azw3_out)], check=True, capture_output=True)
        print(f"✓ Saved {azw3_out}")
    else:
        print("  (install Calibre for `ebook-convert` to also get an .azw3; Kindle accepts the .epub via Send to Kindle)")

    flag_lines = [f"- {n}" + (f" [{i}]" if i is not None else "") + f": {msg}" for n, i, msg in all_flags]
    report_out = output_dir / f"{stem}_changes.md"
    report_out.write_text(
        f"# {stem}: regender changes\n\nModel {args.model}, effort {args.effort}, "
        f"review {'off' if args.no_review else 'on'}. {total_changes} paragraphs changed.\n"
        f"~~struck~~ = removed, **bold** = added.\n\n# Flags ({len(all_flags)})\n\n"
        + ("\n".join(flag_lines) or "None") + "\n" + "\n".join(report),
        encoding="utf-8",
    )
    print(f"✓ Saved {report_out} ({len(all_flags)} flags)")
    print(f"  Tokens this run: {usage['input']:,} in / {usage['output']:,} out")
