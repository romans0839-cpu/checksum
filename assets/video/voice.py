"""읽는 목소리 만들기: 읽을 글(JSON) → 목소리(WAV)와 장면 시각표(JSON).

    python assets/video/voice.py assets/video/leverage_math.voice.json            # samples/ 에 <id>.voice.flac(목소리), <id>.timing.json(장면 시각표)
    python assets/video/voice.py assets/video/leverage_math.voice.json --sid 3    # 다른 목소리로 (0~9)
    python assets/video/voice.py assets/video/leverage_math.voice.json --check    # 만든 소리를 받아쓰게 해서 읽은 말이 맞는지 본다

- 엔진은 Supertonic 3(수퍼톤이 공개한 모델)을 sherpa-onnx 로 돌린다. 열 가지 목소리가 들어 있고(0~4는 높은 목소리, 5~9는 낮은 목소리),
  같은 번호를 쓰면 언제나 같은 사람의 목소리다. 키도 요금도 없고 CPU 로 돈다(한 문장에 3초쯤).
  모델 파일(129MB)은 저장소에 없다 — 처음 돌릴 때 깃허브의 sherpa-onnx 배포 파일에서 받아 .models/ 에 둔다.
- 모델의 이용 조건(BigScience Open RAIL-M)은 만든 소리를 쓸 때 **기계가 만든 것임을 밝히라**고 한다.
  영상의 끝 화면과 설명란에 "목소리는 AI 음성입니다"를 넣는다(D35).
- 숫자와 영문은 읽을 글의 say 에 한글로 풀어 쓴다("9.28%" → "구 점 이팔 퍼센트"). 엔진이 읽는 법에 맡기지 않는다.
- 같은 글도 읽힐 때마다 조금씩 다르게 나오고 가끔 한 음절을 흘린다. --check 를 주면 줄마다 받아써서 화면의 글(show)과 견주고,
  다르면 다섯 번까지 다시 읽혀 가장 가까운 것을 쓴다(받아쓰기 모델 330MB 를 더 받는다).
- 글을 쓴 뒤에는 --check 로 받아써 본다. 이 엔진은 외래어("나스닥")와 "-어납니다 · -어듭니다" 꼴의 맺음(불어납니다, 줄어듭니다)을
  또렷하게 읽지 못한다(10/10, 열 목소리 모두). 받아쓰기가 글과 다르면 낱말을 바꾼다. 받아쓰기는 숫자를 아라비아 숫자로 적으므로
  숫자가 든 줄은 "다름"으로 나와도 눈으로 보면 된다. 받아쓰기는 말이 맞는지만 알려 준다 — 사람처럼 들리는지는 사람이 들어야 안다.
- 같은 글도 돌릴 때마다 길이가 조금씩 다르다(목소리는 같다). 그래서 소리와 시각표를 한 번에 만들고, 영상은 그 시각표로 그린다.
  만든 소리는 samples/ 에 올려 두므로 다시 만들 일은 글이나 목소리를 바꿀 때뿐이다.
"""
import argparse
import json
import os
import subprocess
import sys
import tarfile
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
MODELS = os.path.join(HERE, ".models")
TTS_NAME = "sherpa-onnx-supertonic-3-tts-int8-2026-05-11"
ASR_NAME = "sherpa-onnx-zipformer-korean-2024-06-24"
BASE = "https://github.com/k2-fsa/sherpa-onnx/releases/download/"
URLS = {TTS_NAME: BASE + "tts-models/" + TTS_NAME + ".tar.bz2", ASR_NAME: BASE + "asr-models/" + ASR_NAME + ".tar.bz2"}


def model_dir(name):
    path = os.path.join(MODELS, name)
    if not os.path.isdir(path):
        os.makedirs(MODELS, exist_ok=True)
        tar = path + ".tar.bz2"
        print("모델을 받는다:", URLS[name])
        urllib.request.urlretrieve(URLS[name], tar)
        with tarfile.open(tar) as t:
            t.extractall(MODELS)
        os.remove(tar)
    return path + os.sep


def engine():
    import sherpa_onnx
    d = model_dir(TTS_NAME)
    cfg = sherpa_onnx.OfflineTtsConfig(model=sherpa_onnx.OfflineTtsModelConfig(
        supertonic=sherpa_onnx.OfflineTtsSupertonicModelConfig(
            duration_predictor=d + "duration_predictor.int8.onnx", text_encoder=d + "text_encoder.int8.onnx",
            vector_estimator=d + "vector_estimator.int8.onnx", vocoder=d + "vocoder.int8.onnx",
            tts_json=d + "tts.json", unicode_indexer=d + "unicode_indexer.bin", voice_style=d + "voice.bin"),
        debug=False, num_threads=4, provider="cpu"))
    return sherpa_onnx.OfflineTts(cfg)


def speak(tts, text, sid, speed, steps):
    import numpy as np
    import sherpa_onnx
    g = sherpa_onnx.GenerationConfig()
    g.sid, g.num_steps, g.speed = sid, steps, speed
    g.extra["lang"] = "ko"
    a = tts.generate(text, g)
    return np.array(a.samples, dtype=np.float32), a.sample_rate


def trim(x, sr, thr=0.006, keep=0.08):
    """앞뒤의 조용한 부분을 잘라 줄 사이의 쉼을 고르게 한다."""
    import numpy as np
    win = int(sr * 0.01)
    level = np.sqrt(np.convolve(x ** 2, np.ones(win) / win, "same"))
    idx = np.where(level > thr)[0]
    if len(idx) == 0:
        return x
    k = int(sr * keep)
    return x[max(0, idx[0] - k): min(len(x), idx[-1] + k)]


def transcribe(path):
    """만든 소리를 받아쓴다(읽은 말이 글과 같은지 보는 용도)."""
    import sherpa_onnx
    import soundfile as sf
    d = model_dir(ASR_NAME)
    rec = sherpa_onnx.OfflineRecognizer.from_transducer(
        encoder=d + "encoder-epoch-99-avg-1.int8.onnx", decoder=d + "decoder-epoch-99-avg-1.int8.onnx",
        joiner=d + "joiner-epoch-99-avg-1.int8.onnx", tokens=d + "tokens.txt", num_threads=4)
    x, sr = sf.read(path, dtype="float32")
    s = rec.create_stream()
    s.accept_waveform(sr, x)
    rec.decode_stream(s)
    return s.result.text


def squash(s):
    return "".join(ch for ch in s if ch.isalnum())


def norm(s):
    """받아쓴 글과 화면의 글(show)을 견줄 수 있게 고른다: 받아쓰기는 숫자를 아라비아 숫자로 적는다."""
    import re
    s = re.sub(r"\s+", "", s)
    s = s.replace("퍼센트", "%").replace("스무번", "20번").replace("세배", "3배")
    s = re.sub(r"(\d)[.점]+(\d)", r"\1.\2", s)
    s = re.sub(r"(\d)\.(?=\D)", r"\1", s)
    return "".join(ch for ch in s if ch.isalnum() or ch in "%.")


def closeness(heard, line):
    import difflib
    want = norm(line.get("show") or line["say"])
    return difflib.SequenceMatcher(None, norm(heard), want).ratio()


def main():
    ap = argparse.ArgumentParser(description="읽을 글 → 목소리와 장면 시각표")
    ap.add_argument("spec")
    ap.add_argument("--sid", type=int, default=None, help="목소리 번호 0~9 (읽을 글의 voice.sid 대신)")
    ap.add_argument("--speed", type=float, default=None)
    ap.add_argument("--out", default=os.path.join(HERE, "samples"))
    ap.add_argument("--tag", default="", help="파일 이름 뒤에 붙일 말 (목소리 후보를 여럿 만들 때)")
    ap.add_argument("--check", action="store_true", help="줄마다 받아써서 글과 견주고, 다르면 다시 읽혀 가장 가까운 것을 쓴다")
    ap.add_argument("--takes", type=int, default=5, help="--check 일 때 한 줄을 다시 읽히는 횟수의 상한")
    a = ap.parse_args()
    import numpy as np
    import soundfile as sf
    with open(a.spec, encoding="utf-8") as f:
        spec = json.load(f)
    v = spec["voice"]
    sid = v["sid"] if a.sid is None else a.sid
    speed = v.get("speed", 1.0) if a.speed is None else a.speed
    tts = engine()
    os.makedirs(a.out, exist_ok=True)
    name = spec["id"] + (("-" + a.tag) if a.tag else "")
    gap, lead, tail = spec.get("gap", 0.3), spec.get("lead", 0.25), spec.get("tail", 3.0)
    parts, lines, scenes, t, sr, bad = [], [], {}, lead, None, 0
    for i, ln in enumerate(spec["lines"]):
        best = None
        for take in range(a.takes if a.check else 1):
            x, sr = speak(tts, ln["say"], sid, speed, v.get("steps", 8))
            x = trim(x, sr)
            if not a.check:
                best = (1.0, x, "")
                break
            tmp = os.path.join(a.out, f".{name}-{i}.wav")
            sf.write(tmp, x, sr)
            heard = transcribe(tmp)
            os.remove(tmp)
            score = closeness(heard, ln)
            if best is None or score > best[0]:
                best = (score, x, heard)
            if score >= 0.999:
                break
        score, x, heard = best
        if a.check:
            bad += 0 if score >= 0.999 else 1
            print(f"  {'같음' if score >= 0.999 else '다름'} {ln['scene']} ({take + 1}번째, {score:.2f}) | {heard}")
        if not parts:
            parts.append(np.zeros(int(sr * lead), dtype=np.float32))
        start = t
        parts.append(x)
        t += len(x) / sr
        lines.append({"scene": ln["scene"], "start": round(start, 3), "end": round(t, 3), "say": ln["say"], "show": ln.get("show", "")})
        scenes.setdefault(ln["scene"], round(max(0.0, start - 0.12), 3))
        parts.append(np.zeros(int(sr * gap), dtype=np.float32))
        t += gap
    scenes["G"] = round(t - gap + 0.25, 3)          # 끝 화면
    scenes["END"] = round(scenes["G"] + tail, 3)
    audio = np.concatenate(parts + [np.zeros(int(sr * (scenes["END"] - t)) + 1, dtype=np.float32)])
    raw = os.path.join(a.out, f".{name}.raw.wav")
    wav = os.path.join(a.out, f"{name}.voice.flac")
    sf.write(raw, audio, sr)
    # 크기를 고르게(−16 LUFS 언저리, 꼭대기 −1.5dB). 플랫폼이 밝힌 기준은 없어 흔히 쓰는 값을 썼다
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", raw, "-af", "loudnorm=I=-16:TP=-1.5:LRA=11", "-ar", "44100", "-ac", "1", wav], check=True)
    os.remove(raw)
    timing = {"id": spec["id"], "voice": {"engine": TTS_NAME, "sid": sid, "speed": speed}, "scenes": scenes, "lines": lines}
    with open(os.path.join(a.out, f"{name}.timing.json"), "w", encoding="utf-8") as f:
        json.dump(timing, f, ensure_ascii=False, indent=2)
        f.write("\n")
    said = sum(ln["end"] - ln["start"] for ln in lines)
    chars = sum(len(squash(ln["say"])) for ln in lines)
    print(f"만듦 {os.path.relpath(wav)} · 목소리 {sid} · 전체 {scenes['END']:.1f}초 · 말하는 시간 {said:.1f}초 · 1초에 {chars / said:.1f}자"
          + (f" · 받아쓰기가 글과 다른 줄 {bad}" if a.check else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
