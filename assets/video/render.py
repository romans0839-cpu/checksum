"""타이포 영상 만들기: 시간에 따라 그림이 정해지는 HTML(render(t) 함수가 있는 것) → 1080×1920 MP4.

    python assets/video/render.py assets/video/leverage_math.html --seconds 25.5
    python assets/video/render.py assets/video/leverage_math.html --seconds 25.5 --stills 1.5,4.6,12.6,17.8,24.5   # 장면 확인용 그림만

- 브라우저로 한 장씩 찍어 ffmpeg 로 묶는다(H.264, 30fps, 소리 없음, moov 를 앞에 — 인스타·스레드 API 가 요구한다).
- 같은 HTML 은 언제 만들어도 같은 영상이 된다(시계가 아니라 t 로 그린다).
- 글꼴은 assets/cards/ 에서 npm install 한 것을 쓴다. 목소리를 얹을 때는 만든 뒤에 ffmpeg 로 합친다(README).
"""
import argparse
import os
import subprocess
import sys

W, H = 1080, 1920


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("html")
    ap.add_argument("--seconds", type=float, required=True)
    ap.add_argument("--fps", type=int, default=30)
    ap.add_argument("--out", default=None)
    ap.add_argument("--stills", default="", help="쉼표로 나눈 시각(초). 주면 영상 대신 그 시각의 그림만 만든다")
    a = ap.parse_args()
    from playwright.sync_api import sync_playwright
    src = os.path.abspath(a.html)
    out = a.out or os.path.join(os.path.dirname(src), "samples", os.path.splitext(os.path.basename(src))[0] + ".mp4")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with sync_playwright() as p:
        b = p.chromium.launch()
        page = b.new_page(viewport={"width": W, "height": H}, device_scale_factor=1)
        page.goto("file://" + src)
        page.evaluate("() => document.fonts.ready")
        # 뒤쪽 장면에만 나오는 글자의 글꼴도 미리 읽게 한다
        page.evaluate("() => { for (let t = 0; t < %f; t += 0.5) render(t); return document.fonts.ready }" % a.seconds)
        page.wait_for_timeout(400)
        fams = page.evaluate("() => [...document.fonts].filter(f => f.status === 'loaded').map(f => f.family)")
        if not any("Gothic A1" in x for x in fams):
            raise SystemExit("글꼴(Gothic A1)을 읽지 못했다 — assets/cards/ 에서 npm install 을 돌렸는지 본다")
        stage = page.locator("#stage")
        if a.stills:
            for s in a.stills.split(","):
                t = float(s)
                page.evaluate("t => render(t)", t)
                path = out.replace(".mp4", f"-{t:05.1f}s.png")
                stage.screenshot(path=path)
                print("만듦", path)
            b.close()
            return 0
        ff = subprocess.Popen(
            ["ffmpeg", "-y", "-loglevel", "error", "-f", "image2pipe", "-framerate", str(a.fps), "-c:v", "mjpeg", "-i", "-",
             "-c:v", "libx264", "-preset", "slow", "-crf", "18", "-pix_fmt", "yuv420p", "-r", str(a.fps),
             "-movflags", "+faststart", out], stdin=subprocess.PIPE)
        n = int(round(a.seconds * a.fps))
        for f in range(n):
            page.evaluate("t => render(t)", f / a.fps)
            ff.stdin.write(stage.screenshot(type="jpeg", quality=96))
        ff.stdin.close()
        ff.wait()
        b.close()
    print(f"만듦 {out} ({n}장, {a.seconds}초)")
    return ff.returncode


if __name__ == "__main__":
    sys.exit(main())
