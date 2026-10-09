"""캐릭터 시안: 로고 타일에 눈과 팔다리를 붙인 것. 표정마다 SVG 한 장과, 한눈에 보는 표(PNG)를 만든다.

    python assets/character/make.py            # svg/ 에 표정별 SVG, sheet.png 에 표

- 로고의 체크와 마침표(assets/brand/logo_symbol.svg)는 좌표를 그대로 둔다. 더한 것은 눈, 팔다리, 소품뿐이다.
- 표정은 templates/voice_guide.md §4 의 감정 포인트에 맞췄다. 사람이 다친 일(연대)에는 캐릭터를 쓰지 않는다.
- 시안이다. 쓸지, 이름을 무엇으로 할지는 정해지지 않았다 (docs/16 §5).
"""
import os

HERE = os.path.dirname(os.path.abspath(__file__))
G, INK, W = "#0E9F7B", "#17181A", "#fff"
CHECK = f'<path fill="none" stroke="{W}" stroke-width="11" stroke-linecap="round" stroke-linejoin="round" d="M24 52 L39 67 L66 33"/><circle cx="77" cy="66" r="6.5" fill="{W}"/>'
LIMB = f'fill="none" stroke="{INK}" stroke-width="5" stroke-linecap="round" stroke-linejoin="round"'


def eye(cx, cy, kind="open", look=(0, 0), r=5.6):
    if kind == "open":
        return f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="{W}"/><circle cx="{cx + look[0]}" cy="{cy + look[1]}" r="{r * .5}" fill="{INK}"/>'
    if kind == "happy":      # 웃는 눈 ∩
        return f'<path d="M{cx - 5} {cy + 2} Q{cx} {cy - 6} {cx + 5} {cy + 2}" fill="none" stroke="{W}" stroke-width="3.6" stroke-linecap="round"/>'
    if kind == "down":       # 내리깐 눈 ∪
        return f'<path d="M{cx - 5} {cy - 1} Q{cx} {cy + 6} {cx + 5} {cy - 1}" fill="none" stroke="{W}" stroke-width="3.6" stroke-linecap="round"/>'
    if kind == "half":       # 졸린 눈
        return (f'<path d="M{cx - r} {cy} A{r} {r} 0 0 0 {cx + r} {cy} Z" fill="{W}"/>'
                f'<circle cx="{cx}" cy="{cy + 2.4}" r="2.2" fill="{INK}"/><path d="M{cx - r - 1} {cy} H{cx + r + 1}" stroke="{W}" stroke-width="3" stroke-linecap="round"/>')
    if kind == "wink":
        return f'<path d="M{cx - 5} {cy} H{cx + 5}" stroke="{W}" stroke-width="3.6" stroke-linecap="round"/>'
    raise ValueError(kind)


def figure(eyes, arms, extra="", tilt=0, legs=True):
    """한 표정. 좌표는 -30..130 × -30..140 안."""
    leg = f'<path {LIMB} d="M36 100 V116 H29"/><path {LIMB} d="M64 100 V116 H71"/>' if legs else ""
    body = (f'<g transform="rotate({tilt} 50 100)">{arms}<rect width="100" height="100" rx="26" fill="{G}"/>{CHECK}{eyes}</g>')
    return f'{leg}{body}{extra}'


POSES = {
    "기본": ("평소. 숫자를 전할 때",
           figure(eye(31, 34) + eye(48, 34),
                  f'<path {LIMB} d="M2 58 Q-12 62 -14 74"/><path {LIMB} d="M98 52 Q112 44 116 30"/>')),
    "궁금함": ("큰 일정을 앞둔 주. 밤 9시 30분을 기다릴 때",
            figure(eye(31, 33, look=(2.2, -2), r=6.6) + eye(49, 33, look=(2.2, -2), r=6.6),
                   f'<path {LIMB} d="M2 60 Q-10 66 -12 78"/><path {LIMB} d="M98 56 Q110 56 118 46"/>',
                   f'<g transform="translate(104 2)"><rect x="0" y="0" width="58" height="26" rx="13" fill="{INK}"/>'
                   f'<text x="29" y="18.5" text-anchor="middle" font-family="Plus Jakarta Sans, sans-serif" font-weight="800" font-size="14" fill="{W}">21:30</text></g>')),
    "안도": ("걱정하던 일이 지나간 뒤",
           figure(eye(31, 35, "happy") + eye(48, 35, "happy"),
                  f'<path {LIMB} d="M2 60 Q-8 72 -4 84"/><path {LIMB} d="M98 60 Q108 72 104 84"/>',
                  f'<path d="M112 40 q8 -4 12 2 q6 -1 6 5 q0 6 -7 6 h-10 q-6 0 -6 -6 q0 -6 5 -7z" fill="none" stroke="{INK}" stroke-width="3.2" stroke-linejoin="round"/>')),
    "걱정": ("급락이 있었던 주. 들고 있는 분들을 생각할 때",
           figure(eye(31, 36, look=(0, 2.4)) + eye(48, 36, look=(0, 2.4))
                  + f'<path d="M24 28.5 L35 24.5" stroke="{W}" stroke-width="3.2" stroke-linecap="round"/><path d="M55 28.5 L44 24.5" stroke="{W}" stroke-width="3.2" stroke-linecap="round"/>',
                  f'<path {LIMB} d="M2 60 Q-6 54 4 46"/><path {LIMB} d="M98 60 Q106 54 96 46"/>')),
    "응원": ("손실 구간이 길어질 때",
           figure(eye(31, 34) + eye(48, 34, "wink"),
                  f'<path {LIMB} d="M2 56 Q-12 46 -10 30"/><path {LIMB} d="M98 56 Q112 46 110 30"/>',
                  f'<path d="M-22 22 l5 -9 M-10 14 v-10 M2 22 l5 -9" stroke="{G}" stroke-width="3.6" stroke-linecap="round" fill="none"/>')),
    "사과": ("정정이 있을 때. 틀린 숫자를 바로잡을 때",
           figure(eye(31, 37, "down") + eye(48, 37, "down"),
                  f'<path {LIMB} d="M4 62 Q-4 76 6 88"/><path {LIMB} d="M96 62 Q104 76 94 88"/>',
                  f'<path d="M-6 6 q-7 11 0 15 q7 -4 0 -15z" fill="{W}" stroke="{INK}" stroke-width="3"/>', tilt=-13)),
    "새벽 3시": ("연준 발표처럼 새벽에 나오는 일정",
              figure(eye(31, 35, "half") + eye(48, 35, "half"),
                     f'<path {LIMB} d="M2 62 Q-6 74 -2 86"/><path {LIMB} d="M98 62 Q106 74 102 86"/>',
                     f'<text x="108" y="26" font-family="Plus Jakarta Sans, sans-serif" font-weight="800" font-size="20" fill="{INK}">z</text>'
                     f'<text x="122" y="10" font-family="Plus Jakarta Sans, sans-serif" font-weight="800" font-size="14" fill="{INK}">z</text>')),
    "확인": ("세어 본 숫자가 맞았을 때. 글의 끝",
           figure(eye(31, 34, "happy") + eye(48, 34, "happy"),
                  f'<path {LIMB} d="M2 58 Q-12 62 -14 74"/><path {LIMB} d="M98 54 Q110 44 104 30"/>',
                  f'<circle cx="104" cy="22" r="13" fill="{INK}"/><path d="M98 22 l4.5 4.5 l8 -9" fill="none" stroke="{W}" stroke-width="3.6" stroke-linecap="round" stroke-linejoin="round"/>')),
}
VB = "-36 -24 204 152"


def svg(inner, vb=VB, w=None):
    size = f' width="{w}"' if w else ""
    return f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{vb}"{size}>{inner}</svg>'


def main():
    os.makedirs(os.path.join(HERE, "svg"), exist_ok=True)
    names = {"기본": "base", "궁금함": "curious", "안도": "relief", "걱정": "worry", "응원": "cheer", "사과": "sorry", "새벽 3시": "dawn", "확인": "checked"}
    for k, (_, inner) in POSES.items():
        with open(os.path.join(HERE, "svg", names[k] + ".svg"), "w", encoding="utf-8") as f:
            f.write(svg(inner) + "\n")
    cells = "".join(
        f'<div class="c"><div class="p">{svg(inner)}</div><b>{k}</b><span>{desc}</span></div>' for k, (desc, inner) in POSES.items())
    face = svg(figure(eye(31, 34) + eye(48, 34), "", legs=False), vb="0 0 100 100")
    small = "".join(f'<div class="s" style="width:{n}px;height:{n}px">{face}</div>' for n in (120, 64, 40, 32))
    html = f'''<!doctype html><html lang="ko"><head><meta charset="utf-8">
<link rel="stylesheet" href="../cards/node_modules/@fontsource/gothic-a1/500.css"><link rel="stylesheet" href="../cards/node_modules/@fontsource/gothic-a1/800.css">
<link rel="stylesheet" href="../cards/node_modules/@fontsource/plus-jakarta-sans/800.css">
<style>body{{margin:0;font-family:'Gothic A1';color:{INK}}}#sheet{{width:1600px;background:#E9F6F3;padding:64px 64px 56px}}
h1{{font-size:44px;font-weight:800;letter-spacing:-.04em;margin:0 0 8px}}h1+p{{font-size:24px;color:#5C6966;margin:0 0 36px;font-weight:500}}
.g{{display:grid;grid-template-columns:repeat(4,1fr);gap:24px}}.c{{background:#fff;border-radius:32px;padding:20px 24px 26px;display:flex;flex-direction:column}}
.p svg{{width:100%;display:block}}.c b{{font-size:30px;font-weight:800;letter-spacing:-.03em}}.c span{{font-size:20px;color:#5C6966;font-weight:500;line-height:1.45;margin-top:4px}}
.row{{display:flex;align-items:flex-end;gap:28px;margin-top:36px}}.row em{{font-style:normal;font-size:22px;color:#5C6966;font-weight:500}}.s svg{{width:100%;height:100%;display:block}}</style></head>
<body><div id="sheet"><h1>캐릭터 시안 — 로고에 눈이 달린 것</h1><p>체크와 마침표의 자리는 로고 그대로입니다. 표정은 글에 감정을 붙이는 여섯 자리에 맞췄습니다.</p>
<div class="g">{cells}</div><div class="row">{small}<em>작게 줄였을 때: 120 · 64 · 40 · 32px (프로필 사진은 지금 로고 그대로 둡니다)</em></div></div></body></html>'''
    tmp = os.path.join(HERE, ".sheet.html")
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(html)
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        b = p.chromium.launch()
        page = b.new_page(viewport={"width": 1600, "height": 1200})
        page.goto("file://" + tmp)
        page.evaluate("() => document.fonts.ready")
        page.wait_for_timeout(300)
        page.locator("#sheet").screenshot(path=os.path.join(HERE, "sheet.png"))
        b.close()
    os.remove(tmp)
    print("만듦 svg/ 8장, sheet.png")


if __name__ == "__main__":
    main()
