"""카드 이미지 만들기: 카드 설계 파일(JSON) → 1080×1350 PNG.

    python assets/cards/render.py assets/cards/specs/<이름>.json            # samples/ 에 PNG
    python assets/cards/render.py assets/cards/specs/<이름>.json --jpeg     # 인스타 API 는 JPEG 만 받는다
    python assets/cards/render.py assets/cards/specs/<이름>.json --check    # 글자 검사만 (그림을 만들지 않는다)

- 글자와 숫자만 그린다. 사진, 가격 차트, 화살표는 틀에 없다 (D26, assets/brand/README.md).
- 그림을 만들기 전에 카드 속 글자를 검사한다: 금지어(templates/banned_terms.txt), 쓰지 않는 말(templates/avoid_terms.txt),
  주소(이미지에는 링크를 넣지 않는다), 채우지 않은 칸([채울 것: …]). 걸리면 만들지 않는다.
- 만든 뒤에는 글자가 카드 밖으로 넘쳤는지 본다. 넘치면 알리고 0이 아닌 값으로 끝난다.
- 글꼴은 저장소에 없다. 이 폴더에서 `npm install @fontsource/gothic-a1 @fontsource/plus-jakarta-sans` 를 한 번 돌린다
  (둘 다 SIL Open Font License). 다른 곳에 있으면 --fonts 로 node_modules 가 든 폴더를 알려 준다.
- 서버(EC2)에는 브라우저가 없다. 지금은 세션이 만들어 올린다 — 서버로 옮길지는 docs/16 §6 의 정할 것.

설계 파일의 모양은 specs/ 의 파일들과 README.md 를 본다.
"""
import argparse
import html
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
W, H = 1080, 1350
LEGAL_SHORT = "원금 손실 가능 · 개별 상담 불가"

MARK = ('<svg viewBox="0 0 100 100"><rect width="100" height="100" rx="26" fill="{bg}"/>'
        '<path fill="none" stroke="{fg}" stroke-width="11" stroke-linecap="round" stroke-linejoin="round" '
        'd="M24 52 L39 67 L66 33"/><circle cx="77" cy="66" r="6.5" fill="{fg}"/></svg>')
BIGCHECK = ('<svg class="bigcheck" viewBox="0 0 100 100"><path fill="none" stroke="#fff" stroke-width="11" '
            'stroke-linecap="round" stroke-linejoin="round" d="M24 52 L39 67 L66 33"/>'
            '<circle cx="77" cy="66" r="6.5" fill="#fff"/></svg>')


def fmt(text):
    """설계 파일의 글 → HTML. **굵게**, *강조*, 줄바꿈만 안다."""
    t = html.escape(str(text), quote=False)
    t = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", t, flags=re.S)
    t = re.sub(r"\*(.+?)\*", r"<em>\1</em>", t, flags=re.S)
    return t.replace("\n", "<br>")


def title_html(lines, size=""):
    """제목. 끝의 마침표는 로고의 둥근 점으로 그린다."""
    if isinstance(lines, str):
        lines = [lines]
    out = "<br>".join(fmt(x) for x in lines)
    dot = ""
    if out.endswith("."):
        out, dot = out[:-1], '<span class="dot"></span>'
    return f'<div class="title {size}">{out}{dot}</div>'


def num_html(n):
    """'825번' 같은 값에서 숫자와 단위를 나눠 그린다."""
    m = re.match(r"^([−\-+]?[\d,.:]+)(.*)$", str(n))
    if not m:
        return fmt(n)
    return f'{html.escape(m.group(1))}<span class="u">{html.escape(m.group(2))}</span>' if m.group(2) else html.escape(m.group(1))


def main_html(s):
    k = s["type"]
    parts = []
    if k == "cover":
        parts.append(title_html(s["title"], s.get("size", "")))
        if s.get("sub"):
            parts.append(f'<div class="sub">{fmt(s["sub"])}</div>')
    elif k == "shift":
        if s.get("title"):
            parts.append(title_html(s["title"], s.get("size", "m")))
        rows = "".join(
            f'<div class="row {cls}"><div class="when">{fmt(s[cls]["when"])}</div><div class="val">{fmt(s[cls]["val"])}</div></div>'
            for cls in ("before", "after"))
        parts.append(f'<div class="shift {"long" if s.get("long") else ""}">{rows}</div>')
    elif k == "figs":
        if s.get("title"):
            parts.append(title_html(s["title"], s.get("size", "s")))
        two = any(len(r["nums"]) > 1 for r in s["rows"])
        head = ""
        if s.get("colhead"):
            head = '<div class="colhead">' + "".join(f"<span>{fmt(c)}</span>" for c in s["colhead"]) + "</div>"
        rows = ""
        for r in s["rows"]:
            small = f'<small>{fmt(r["small"])}</small>' if r.get("small") else ""
            nums = "".join(f'<div class="num">{num_html(n)}</div>' for n in r["nums"])
            rows += f'<div class="fig {"hi" if r.get("hi") else ""}"><div class="lab">{fmt(r["lab"])}{small}</div>{nums}</div>'
        parts.append(f'<div>{head}<div class="figs {"two" if two else ""}">{rows}</div></div>')
    elif k == "ord":
        parts.append(f'<div><div class="ord">{fmt(s["ord"])}</div><div class="term">{fmt(s["term"])}</div></div>')
        parts.append('<div class="body">' + "".join(f"<p>{fmt(p)}</p>" for p in s["body"]) + "</div>")
    elif k == "text":
        if s.get("title"):
            parts.append(title_html(s["title"], s.get("size", "m")))
        parts.append('<div class="body">' + "".join(f"<p>{fmt(p)}</p>" for p in s["body"]) + "</div>")
    elif k == "sheet":
        if s.get("title"):
            parts.append(title_html(s["title"], s.get("size", "s")))
        rows = "".join(
            f'<div class="r"><div class="k">{fmt(r["k"])}</div><div class="v"><b>{fmt(r["b"])}</b>{fmt(r.get("v", ""))}</div></div>'
            for r in s["rows"])
        parts.append(f'<div class="sheet">{rows}</div>')
    elif k == "agenda":
        if s.get("title"):
            parts.append(title_html(s["title"], s.get("size", "m")))
        items = ""
        for a in s["items"]:
            small = f'<small>{fmt(a["small"])}</small>' if a.get("small") else ""
            items += (f'<div class="a"><div class="t">{fmt(a["t"])}</div><div><div class="d">{fmt(a["d"])}</div>'
                      f'<div class="n">{fmt(a["n"])}{small}</div></div></div>')
        parts.append(f'<div class="agenda">{items}</div>')
    elif k == "end":
        parts.append(title_html(s["title"], s.get("size", "m")))
        if s.get("body"):
            parts.append('<div class="body">' + "".join(f"<p>{fmt(p)}</p>" for p in s["body"]) + "</div>")
        if s.get("legal"):
            parts.append('<div class="legalbox">' + "<br>".join(fmt(x) for x in s["legal"]) + "</div>")
    else:
        raise ValueError(f"모르는 카드 종류: {k}")
    if s.get("note"):
        parts.append(f'<div class="note">{fmt(s["note"])}</div>')
    return "".join(parts)


def card_html(spec, i):
    s = spec["slides"][i]
    theme = s.get("theme", "green" if s["type"] == "cover" else "")
    green = theme == "green"
    mark = MARK.format(bg="#fff" if green else "#0E9F7B", fg="#0E9F7B" if green else "#fff")
    n = len(spec["slides"])
    page = f'<div class="page">{i + 1} / {n}</div>' if n > 1 else ""
    kicker = s.get("kicker", spec.get("kicker", ""))
    align = s.get("align", "mid" if s["type"] in ("text", "end") else "")
    if s.get("dense"):
        theme += " dense"
    deco = BIGCHECK if (s["type"] == "cover" and green and s.get("deco", True)) else ""
    legal = spec.get("legal_short", LEGAL_SHORT)
    return (f'<section class="card {theme}" id="c{i + 1}">{deco}'
            f'<div class="head"><div class="kicker">{mark}<span>{fmt(kicker)}</span></div>{page}</div>'
            f'<div class="main {align}">{main_html(s)}</div>'
            f'<div class="foot"><div class="wm">checksum<i>.</i></div><div class="legal">{fmt(legal)}</div></div>'
            f'</section>')


def page_html(spec, fonts):
    fs = os.path.join(fonts, "node_modules", "@fontsource")
    links = "".join(
        f'<link rel="stylesheet" href="file://{os.path.join(fs, fam, w + ".css")}">'
        for fam, ws in (("gothic-a1", ("500", "700", "800")), ("plus-jakarta-sans", ("700", "800"))) for w in ws)
    with open(os.path.join(HERE, "card.css"), encoding="utf-8") as f:
        css = f.read()
    cards = "".join(card_html(spec, i) for i in range(len(spec["slides"])))
    return f'<!doctype html><html lang="ko"><head><meta charset="utf-8">{links}<style>{css}</style></head><body>{cards}</body></html>'


# ── 글자 검사 ──

def strings(node):
    if isinstance(node, str):
        yield node
    elif isinstance(node, list):
        for x in node:
            yield from strings(x)
    elif isinstance(node, dict):
        for key, x in node.items():
            if key not in ("type", "theme", "size", "align", "deco", "id", "memo", "source", "long", "dense"):
                yield from strings(x)


def read_terms(name):
    path = os.path.join(ROOT, "templates", name)
    try:
        with open(path, encoding="utf-8-sig") as f:
            return [ln.strip() for ln in f if ln.strip() and not ln.lstrip().startswith("#")]
    except OSError:
        return []


def check(spec):
    """카드 속 글자의 문제 목록. 비어 있으면 이상 없음."""
    text = "\n".join(strings({"slides": spec["slides"], "kicker": spec.get("kicker", ""), "legal": spec.get("legal_short", LEGAL_SHORT)}))
    problems = []
    for pat in read_terms("banned_terms.txt"):
        if re.search(pat, text):
            problems.append(f"금지어: {pat}")
    for term in read_terms("avoid_terms.txt"):
        if term in text:
            problems.append(f"쓰지 않는 말: {term}")
    if re.search(r"https?://|www\.", text):
        problems.append("주소가 들어 있다 (이미지에는 링크를 넣지 않는다)")
    blanks = re.findall(r"\[채울 것[^\]]*\]", text)
    if blanks:
        problems.append("채우지 않은 칸: " + ", ".join(blanks))
    return problems


OVERFLOW_JS = """() => [...document.querySelectorAll('.card')].map(c => {
  const m = c.querySelector('.main'); const cr = c.getBoundingClientRect(); const bad = [];
  if (m.scrollHeight > m.clientHeight + 1) bad.push('세로로 넘침 ' + (m.scrollHeight - m.clientHeight) + 'px');
  for (const el of m.querySelectorAll('*')) { const r = el.getBoundingClientRect();
    if (r.right > cr.right - 40 || r.left < cr.left + 40) { bad.push('가로로 넘침: ' + (el.textContent || '').slice(0, 20)); break; } }
  return bad; })"""


def render(spec, out_dir, fonts, jpeg=False):
    from playwright.sync_api import sync_playwright
    os.makedirs(out_dir, exist_ok=True)
    tmp = os.path.join(out_dir, f".{spec['id']}.html")
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(page_html(spec, fonts))
    made, overflow = [], []
    with sync_playwright() as p:
        b = p.chromium.launch()
        page = b.new_page(viewport={"width": W, "height": H}, device_scale_factor=1)
        page.goto("file://" + tmp)
        page.evaluate("() => document.fonts.ready")
        page.wait_for_timeout(300)
        fams = page.evaluate("() => [...document.fonts].filter(f => f.status === 'loaded').map(f => f.family + ' ' + f.weight)")
        if not any("Gothic A1" in x for x in fams):
            raise SystemExit("글꼴(Gothic A1)을 읽지 못했다. 이 폴더에서 npm install 을 돌렸는지, --fonts 가 맞는지 본다")
        for i, bad in enumerate(page.evaluate(OVERFLOW_JS)):
            if bad:
                overflow.append(f"{i + 1}쪽: " + "; ".join(bad))
        for i in range(len(spec["slides"])):
            ext = "jpg" if jpeg else "png"
            path = os.path.join(out_dir, f"{spec['id']}-{i + 1:02d}.{ext}")
            opts = {"path": path, "type": "jpeg", "quality": 92} if jpeg else {"path": path}
            page.locator(f"#c{i + 1}").screenshot(**opts)
            made.append(path)
        b.close()
    os.remove(tmp)
    return made, overflow


def main():
    ap = argparse.ArgumentParser(description="카드 설계 파일 → 1080×1350 이미지")
    ap.add_argument("spec")
    ap.add_argument("--out", default=os.path.join(HERE, "samples"))
    ap.add_argument("--fonts", default=HERE, help="node_modules 가 든 폴더")
    ap.add_argument("--jpeg", action="store_true")
    ap.add_argument("--check", action="store_true", help="글자 검사만")
    a = ap.parse_args()
    with open(a.spec, encoding="utf-8") as f:
        spec = json.load(f)
    problems = check(spec)
    if problems:
        print(f"{spec['id']}: 글자 검사에 걸렸다 — 그림을 만들지 않는다")
        for x in problems:
            print("  -", x)
        return 1
    print(f"{spec['id']}: 글자 검사 이상 없음 ({len(spec['slides'])}장)")
    if a.check:
        return 0
    made, overflow = render(spec, a.out, a.fonts, a.jpeg)
    for path in made:
        print("  만듦", os.path.relpath(path, ROOT))
    for x in overflow:
        print("  넘침", x)
    return 2 if overflow else 0


if __name__ == "__main__":
    sys.exit(main())
