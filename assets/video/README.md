# 타이포 영상 — 코드로 그린 글자 + AI 음성 (1080×1920)

상태: **D35(2026-10-10)로 정했다 — 짧은 세로 타이포 영상은 코드로 그린 글자 화면에 AI 음성을 얹는다.** 창간(10/20) 뒤 주 1편. 근거와 위험은 `docs/16_expression_formats.md` §4. 롱폼(화면 녹화 + 본인 목소리, D15)에는 쓰지 않는다.

| 파일 | 내용 |
|---|---|
| `<이름>.voice.json` | 읽을 글. 장면마다 한 줄 — `show`는 화면의 글, `say`는 엔진에 주는 글(숫자와 영문을 한글로 풀어 쓴다) |
| `voice.py` | 읽을 글 → 목소리(`samples/<이름>.voice.flac`)와 장면 시각표(`samples/<이름>.timing.json`). 엔진은 Supertonic 3 |
| `<이름>.html` | 장면 설계. `render(t)`에 시각(초)을 넣으면 그 순간의 그림이 정해진다. 시각표가 있으면 장면이 말에 맞춰진다 |
| `render.py` | HTML(+ 시각표, 목소리) → MP4. 브라우저로 한 장씩 찍어 ffmpeg 로 묶는다 |
| `samples/leverage_math_voice.mp4` | 시안 35.6초 (3배 레버리지, 목소리 8번) |

```
pip install sherpa-onnx soundfile numpy                                        # 한 번만. 모델(129MB)은 voice.py 가 처음 돌 때 받는다
python assets/video/voice.py assets/video/leverage_math.voice.json --check     # 목소리와 시각표. --sid 0~9 로 다른 목소리
python assets/video/render.py assets/video/leverage_math.html --voice          # 목소리를 얹은 MP4
python assets/video/render.py assets/video/leverage_math.html                  # 소리 없는 판
python assets/video/render.py assets/video/leverage_math.html --voice --stills 1.6,9.0,24.5   # 장면 확인용 그림
```
글꼴은 `assets/cards/`에서 `npm install` 한 것을 쓴다. 브라우저와 ffmpeg가 있어야 한다(서버에는 없다 — 세션이 만든다).

## 새 영상을 만들 때
1. 글을 고른다. 첫 편들은 계산 예시 · 일정 · 뜻풀이처럼 백테스트 숫자가 없는 글로(docs/16 §3)
2. 읽을 글을 쓴다: 180 ~ 200음절 안(40초 안), 첫 문장에 독자가 가져갈 것, `templates/copy_guide.md` 문체. 귀로 듣는 글이라 화면의 글보다 풀어 쓴다
3. `voice.py --check`로 만든다. "다름"이 남으면 그 줄의 낱말을 바꾼다 — 이 엔진은 외래어("나스닥")와 "-어납니다 · -어듭니다" 맺음을 또렷하게 읽지 못한다
4. HTML의 장면을 읽을 글의 줄(A, B, …)에 맞춘다. `leverage_math.html`을 본으로 삼는다
5. `render.py --voice`로 만들고, 그림 몇 장을 뽑아 글자가 넘치지 않는지 본다

## 지킬 것
- **"목소리는 AI 음성입니다"를 끝 화면과 설명란에 적는다**(끝 화면은 목소리를 얹은 판에 저절로 뜬다). 인스타에 올릴 때는 AI 표시를 켠다. 모델의 이용 조건(BigScience Open RAIL-M)과 플랫폼 규칙이 요구한다
- 목소리 번호는 하나로 고정한다(`*.voice.json`의 `voice.sid`). 지금은 8번이고 Nick이 듣고 정한다
- 글자는 릴스 · 쇼츠의 화면 단추에 가리지 않는 자리(위 270px, 아래 670px, 양옆 65px 밖)에만 둔다
- 핵심 숫자는 처음 4 ~ 5초 안에. 첫 문장을 단정으로 쓰지 않는다(계산 예시면 "…라면"의 조건문)
- 끝 화면에 "계산 예시" 같은 조건과 고지를 넣는다. 가격 차트는 그리지 않는다(D26). 스톡 영상 · 아바타 · 사람처럼 보이는 AI 인물은 쓰지 않는다
- 영상마다 질문과 자료가 달라야 한다(유튜브는 찍어 낸 듯한 틀의 AI 콘텐츠를 수익 창출에서 뺀다)
- 만든 소리와 시각표는 저장소에 올려 둔다. 같은 글도 읽힐 때마다 길이가 조금씩 달라서, 다시 만들면 영상도 다시 그려야 한다
