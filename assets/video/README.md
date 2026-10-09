# 타이포 영상 — 코드가 그리는 1080×1920

상태: **시안(2026-10-10).** 하려면 D15에 예외를 더하는 결정이 필요하다 — `docs/16_expression_formats.md` §4 · §6.

| 파일 | 내용 |
|---|---|
| `leverage_math.html` | 장면 설계. `render(t)`에 시각(초)을 넣으면 그 순간의 그림이 정해진다. 글은 초안 b-1016-1200 에서 옮겼고 숫자는 계산 예시다 |
| `render.py` | HTML → MP4 (브라우저로 한 장씩 찍어 ffmpeg 로 묶는다. 30fps, H.264, 소리 없음, 1분쯤) |
| `samples/leverage_math.mp4` | 시안 25.5초 |

```
python assets/video/render.py assets/video/leverage_math.html --seconds 25.5
python assets/video/render.py assets/video/leverage_math.html --seconds 25.5 --stills 1.6,4.9,13.2   # 장면 확인용 그림
ffmpeg -i samples/leverage_math.mp4 -i voice.m4a -c:v copy -c:a aac -shortest -movflags +faststart out.mp4   # 목소리 얹기
```
글꼴은 `assets/cards/`에서 `npm install` 한 것을 쓴다.

지킬 것
- 글자는 릴스 · 쇼츠의 화면 단추에 가리지 않는 자리(위 270px, 아래 670px, 양옆 65px 밖)에만 둔다
- 핵심 숫자는 처음 4~5초 안에. 한 장면의 글자는 한 줄 16자 안팎, 읽을 시간은 넉넉히
- AI 음성 · 스톡 영상 · 아바타는 쓰지 않는다(D15). 유튜브에 올리는 판에는 본인 목소리를 얹는다(틀이 같은 글자 영상은 수익 창출 정책의 "흘러가는 글자"와 겉모습이 겹친다)
- 끝 화면에 "계산 예시" 같은 조건과 고지를 넣는다. 가격 차트는 그리지 않는다(D26)
