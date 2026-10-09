> 조사 메모 (2026-10-10, 영어). 타이포 영상의 읽는 목소리를 AI 음성으로 하는 결정(D35)의 근거 자료다: 음성 합성 서비스와 공개 모델의 값 · 이용 조건, 유튜브 · 메타 · 한국 법규의 표시 의무, 시청자 반응. 조사 보조 작업이 쓴 메모 그대로이며, 1차 출처에서 확인하지 못한 것은 각 절의 Gaps 에 적혀 있다. 이 조사를 우리 일에 적용한 것은 `docs/16_expression_formats.md` §4다. 법률 자문이 아니다.

# AI TTS voice options and AI-narration disclosure rules for short vertical video in South Korea (as of 2026-10-10)

Reading notes for the report writer
- All pages were fetched on 2026-10-10 unless another date is given. "Primary" = the provider's / platform's / regulator's own page. "Secondary" = press, law-firm newsletter, vendor blog, third-party tracker.
- Several primary pages render prices or body text with JavaScript and came back masked or empty (Azure price table, NAVER Cloud price figures, Meta/Instagram Help Center bodies). Those points are marked "not verified from primary".
- Model line-ups changed a lot in Aug–Sep 2026 (Eleven v4, Gemini 3.8 TTS, MAI-Voice-2). Names below are exactly as the fetched pages showed them; nothing is filled in from memory unless labelled so.
- This is research, not legal advice. Points that need a lawyer are flagged "LAWYER".

---

## 1. Commercial TTS APIs with Korean voices in 2026 — price, licence, consistency controls, Korean number/ticker handling

### Takeaway
At 1,000–4,200 Korean characters a month the API usage cost is close to zero at every major provider; what actually decides the choice is (a) the cheapest tier that carries a commercial licence, (b) whether the same named voice can be pinned, and (c) contractual disclosure duties. Verified cheapest commercial routes: Google Chirp 3 HD (ko-KR GA, 1M chars/month free tier, SSML say-as + custom pronunciation supported for Korean), Gemini 3.8 Flash TTS / OpenAI gpt-4o-mini-tts (cents per month, prompt-steered, no SSML), ElevenLabs Starter ($6/month list, commercial licence, seed + timestamps), Typecast API Light ($15/month; free tier is non-commercial). Supertone (Play, API, Voice Builder) shut down on 2026-08-31 and NAVER CLOVA Voice forbids saving/re-using generated files, so neither is a candidate.

### Cited Findings

**ElevenLabs** (primary unless noted)
- Models listed on the models page: `eleven_v4` (90+ languages, Korean yes, 10,000 chars/request, "keeps speaker identity reliable in long generations"), `eleven_v4_turbo`, `eleven_v3` (70+ languages, Korean yes, 5,000 chars/request), `eleven_v3_conversational`, `eleven_multilingual_v2` (29 languages, Korean yes, 10,000 chars, "Most stable on long-form generations"), `eleven_flash_v2_5` (32 languages, Korean yes, 40,000 chars), English-only `eleven_flash_v2`. `eleven_turbo_v2_5` and `eleven_turbo_v2` are marked deprecated (replacement: Flash). — [ElevenLabs models](https://elevenlabs.io/docs/overview/models)
- API price per 1,000 characters: v3 $0.08, Multilingual v2 $0.08, Flash/Turbo $0.04, v3 Conversational $0.04; v4 shown at $0.022 and v4 Turbo at $0.011 "72% off until Oct 12". — [ElevenLabs API pricing](https://elevenlabs.io/pricing/api)
- Secondary: v4 and v4 Turbo went GA on 2026-09-28; list price of v4 reported as $0.08/1K chars with the $0.022 launch promotion ending 2026-10-12 (the article contradicts itself on whether list is equal to or double v3 — verify on the pricing page after Oct 12). — [OrcaRouter blog, 2026-09-28](https://www.orcarouter.ai/blog/eleven-v4-tops-the-voice-arena)
- Plans: Free $0 / 10k credits; Starter $6 list ($1 first-month offer "Until Oct 18") / 30k credits, "commercial license" and Instant Voice Cloning listed; Creator $22 list ($11 first month) / 121k credits, adds Professional Voice Cloning; Pro $99 / 600k; Scale $299; Business $990. — [ElevenLabs pricing](https://elevenlabs.io/pricing)
- Licence: "The free plan does not include a commercial license and cannot be used for any commercial purpose."; free-plan content must carry attribution "elevenlabs.io" or "11.ai" in the title; "All paid plans include a commercial license, provided you're not using Beta Services."; content generated during a paid subscription "can be used commercially, and indefinitely"; "Content created outside of a paid subscription (before or after) cannot be used commercially." — [ElevenLabs Help: Can I publish the content I generate?](https://help.elevenlabs.io/hc/en-us/articles/13313564601361-Can-I-publish-the-content-I-generate-on-the-platform)
- Reproducibility controls on the TTS endpoint: `seed` (0–4294967295) — "our system will make a best effort to sample deterministically"; "Determinism is not guaranteed."; `voice_settings` override per request (5 properties, not expanded in the fetched page); `language_code` (ISO 639-1; "is not supported for multilingual_v2 models"); `pronunciation_dictionary_locators` (up to 3); `apply_text_normalization` (auto/on/off); `apply_language_text_normalization` "Currently only supported for Japanese"; `previous_text`/`next_text`; `output_format` default `mp3_44100_128` (MP3 192 kbps needs Creator+, PCM/WAV 44.1 kHz needs Pro+). A separate "Create speech with timing" endpoint (`/text-to-speech/convert-with-timestamps`) exists. — [ElevenLabs API reference: Create speech](https://elevenlabs.io/docs/api-reference/text-to-speech/convert)
- Text normalization: Flash v2.5 reads "$1,000,000" as "one thousand thousand dollars" while Multilingual v2 reads it correctly; recommended fixes are a larger model, normalizing with an LLM or regex before TTS, and writing numbers as spoken words. Alias tags work on Multilingual v2; phoneme tags are "only compatible with `eleven_flash_v2`" (English-only model); Eleven v4 takes IPA between forward slashes. The page gives no Korean-specific guidance (all examples are English). — [ElevenLabs normalization best practices](https://elevenlabs.io/docs/best-practices/prompting/normalization)

**OpenAI** (primary unless noted)
- TTS models on the guide: `gpt-4o-mini-tts` ("newest and most reliable"), `tts-1`, `tts-1-hd`; no newer dedicated TTS model is named on the guide or the models index (realtime voice models `gpt-realtime-2.1`, `gpt-live-1` exist but are not described as TTS). — [OpenAI TTS guide](https://developers.openai.com/api/docs/guides/text-to-speech); [OpenAI models index](https://developers.openai.com/api/docs/models)
- 13 voices: alloy, ash, ballad, coral, echo, fable, nova, onyx, sage, shimmer, verse, marin, cedar (marin/cedar recommended). "Voices are currently optimized for English."; language support "generally follows the Whisper model" and Korean is in the list. `instructions` steers accent, emotional range, intonation, speed, tone, whispering. Output: mp3 (default), opus, aac, flac, wav, pcm. — [OpenAI TTS guide](https://developers.openai.com/api/docs/guides/text-to-speech)
- Contractual disclosure duty: "Our usage policies require you to provide a clear disclosure to end users that the TTS voice they are hearing is AI-generated and not a human voice." — [OpenAI TTS guide](https://developers.openai.com/api/docs/guides/text-to-speech)
- Price: gpt-4o-mini-tts text input $0.60 / 1M tokens, audio output $12.00 / 1M tokens; max input 2,000 tokens. The model page shows snapshots `gpt-4o-mini-tts-2025-12-15` and `gpt-4o-mini-tts-2025-03-20` with "Deprecated" labels (no dates given) — i.e. the alias has already moved across snapshots. — [OpenAI model page: gpt-4o-mini-tts](https://developers.openai.com/api/docs/models/gpt-4o-mini-tts)
- Secondary estimate: about $0.015 per minute of audio for gpt-4o-mini-tts (competitor-published comparison, Sept 2026). — [Gradium pricing comparison, updated 2026-09-10](https://gradium.ai/content/how-to-compare-tts-pricing-across-providers-2026)
- Custom voices exist ("Create an approved custom voice from a speaker's consent recording and matching audio sample") but eligibility/limits are in a separate guide not fetched. — [OpenAI TTS guide](https://developers.openai.com/api/docs/guides/text-to-speech)

**Google — Cloud Text-to-Speech (Chirp 3 HD) and Gemini TTS** (primary)
- Cloud TTS list prices per 1M characters / monthly free tier: Chirp 3 HD $30 (free 0–1M chars), Instant custom voice $60 (no free tier), WaveNet $4 (free 0–4M), Standard $4 (free 0–4M), Neural2 $16 (free 0–1M), Studio $160 (free 0–1M). Character counts include spaces, newlines and SSML tags except `<mark>`. — [Google Cloud TTS pricing](https://cloud.google.com/text-to-speech/pricing)
- Chirp 3 HD: `ko-KR` listed and not marked Preview; voice names follow `<locale>-Chirp3-HD-<voice>` with 30 named voices (female: Achernar, Aoede, Autonoe, Callirrhoe, Despina, Erinome, Gacrux, Kore, Laomedeia, Leda, Pulcherrima, Sulafat, Vindemiatrix, Zephyr; male: Achird, Algenib, Algieba, Alnilam, Charon, Enceladus, Fenrir, Iapetus, Orus, Puck, Rasalgethi, Sadachbia, Sadaltager, Schedar, Umbriel, Zubenelgenubi). SSML (synchronous only): `<speak> <say-as> <p> <s> <phoneme> <sub> <break> <audio> <prosody> <voice>`; `speaking_rate` 0.25–2.0; pause tags `[pause short]`/`[pause long]` via the `markup` field (Korean not in the exclusion list); custom pronunciations in IPA/X-SAMPA (Korean not in the exclusion list); outputs LINEAR16 (default), MP3, OGG_OPUS, ALAW, MULAW, PCM. SSML and voice-control sections carry Preview banners. — [Chirp 3 HD docs](https://docs.cloud.google.com/text-to-speech/docs/chirp3-hd)
- Gemini API TTS models: `gemini-3.8-flash-tts`, `gemini-3.8-flash-lite-tts`, `gemini-3.1-flash-tts-preview`, `gemini-2.5-pro-preview-tts`; 30 prebuilt voices (same star-names as Chirp 3 HD: Zephyr, Puck, Charon, Kore, …) plus an "Extended Voice Library"; language auto-detected, 3.8 Flash TTS "over 130 languages" with Korean listed; style set by natural-language `style` text, inline cues such as `<short pause>`; output WAV 24 kHz mono 16-bit; no seed parameter documented; stateful custom voices 200/project with 1-year TTL. — [Gemini API speech generation docs](https://ai.google.dev/gemini-api/docs/speech-generation)
- Gemini TTS price (per 1M tokens): 3.8 Flash TTS input $0.50 / audio output $9.00 through 2026-12-31, then $1.00 / $18.00 from 2027-01-01; 3.8 Flash-Lite TTS $0.50 / $6.00 then $1.00 / $12.00; 3.1 Flash TTS Preview $1.00 / $20.00; audio is 25 tokens per second. Free tier shown as "Free of charge" for the 3.8 TTS models on the Gemini API; free-tier content is used to improve Google products, paid-tier content is not. — [Google Cloud TTS pricing](https://cloud.google.com/text-to-speech/pricing); [Gemini API pricing](https://ai.google.dev/gemini-api/docs/pricing)

**Microsoft Azure Speech** (primary docs; price table masked)
- ko-KR voices in the official language-support source file: `ko-KR-SunHiNeural` (F), `ko-KR-InJoonNeural` (M), `ko-KR-HyunsuMultilingualNeural` (M), `ko-KR-BongJinNeural`, `ko-KR-GookMinNeural`, `ko-KR-HyunsuNeural`, `ko-KR-JiMinNeural`, `ko-KR-SeoHyeonNeural`, `ko-KR-SoonBokNeural`, `ko-KR-YuJinNeural`; HD: `ko-KR-SunHi:DragonHDLatestNeural`, `ko-KR-Hyunsu:DragonHDLatestNeural`; newer: `ko-KR-Haena:MAI-Voice-2`, `ko-KR-Haena:MAI-Voice-2-Flash`, `ko-KR-Junho:MAI-Voice-2`, `ko-KR-Junho:MAI-Voice-2-Flash` (the MAI voices list 11–13 styles such as happy, sad, excited, softvoice; InJoon lists "sad"). — [MicrosoftDocs azure-ai-docs: tts.md](https://raw.githubusercontent.com/MicrosoftDocs/azure-ai-docs/main/articles/ai-services/speech-service/includes/language-support/tts.md)
- Conflict: the HD-voices article lists DragonHD locales as de-DE, en-US, es-ES, fr-FR, ja-JP, zh-CN only (no ko-KR), while the language-support file above lists two ko-KR DragonHD voices. HD voices support `say-as`, `sub`, `phoneme`, `break`, lexicon (alias only) but not `prosody`; `temperature` parameter 0–1; no seed; voice names contain "Latest" (the underlying model is updated in place). — [Azure HD voices](https://learn.microsoft.com/en-us/azure/ai-services/speech-service/high-definition-voices)
- Price: the official pricing page returned every TTS price as "$-"; only "0.5 million characters free per month" for neural voices (F0) was readable. — [Azure Speech pricing](https://azure.microsoft.com/en-us/pricing/details/cognitive-services/speech-services/)
- Secondary price figures (conflicting): $30 per 1M characters for "azure-tts-hd" (tracker dated 2026-10-09); $22 per 1M for "Azure AI Speech HD 2.5" (competitor comparison). — [CloudPrice](https://cloudprice.net/models/microsoft-tts-hd); [Gradium](https://gradium.ai/content/how-to-compare-tts-pricing-across-providers-2026)

**NAVER CLOVA Voice / CLOVA Dubbing** (primary; price figures masked)
- CLOVA Voice (NAVER Cloud Platform API): only a Premium plan is shown; usage up to 1,000,000 chars/month is covered by the base fee (base-fee amount and overage price were blank in the fetched page); max 2,000 chars per call; mp3 (default) or wav. — [NCP CLOVA Voice](https://www.ncloud.com/product/aiService/clovaVoice)
- CLOVA Voice usage policy: "CLOVA Voice 는 반드시 실시간 API 호출 방식으로 이용해야 합니다."; file download not supported; generated files may not be stored or edited for re-use — content production must use CLOVA Dubbing; "CLOVA Voice API 또는 생성된 음성 파일을 재판매할 수 없습니다."; building a voice/video editing service is not allowed. — [CLOVA Voice 이용 정책](https://guide.ncloud-docs.com/docs/ko/clovavoice-policy)
- CLOVA Dubbing (NCP paid): Standard includes 20 projects / 40 downloads / 30,000 chars per month; Premium 100 projects / 150 downloads / 180,000 chars; attribution not required on paid plans; the free NAVER CLOVA Dubbing requires attribution and limits commercial use. Monthly fees were masked ("-"). — [NCP CLOVA Dubbing](https://www.ncloud.com/product/aiService/clovaDubbing)
- CLOVA Dubbing plan policy: "CLOVA Dubbing은 콘텐츠 제작 용도로만 사용할 수 있으며"; Standard "개인 및 비영리 용도로만 이용할 수 있습니다."; blogs/SNS/online lectures/podcasts are allowed on Standard, but paid sale, broadcast, "광고 및 홍보" require Premium. — [CLOVA Dubbing 요금제별 이용 정책](https://guide.ncloud-docs.com/docs/ko/clovadubbing-serviceplan)

**Supertone (Supertone Play / Supertone API / Supertonic)** (primary)
- "all Supertone services will be discontinued on August 31, 2026."; schedule: 2026-07-15 notice and end of new sign-ups/payments, 2026-08-31 end of Play, API and Voice Builder; an extraordinary shareholders' meeting on 2026-07-15 resolved dissolution; no replacement service named; Play outputs had to be exported by 08-31. — [Supertone sunset notice](https://www.supertone.ai/ko/sunset); [Supertone Help: Play plan features](https://support.supertone.ai/hc/en-us/articles/16564749196815-Play-Plan-Features-Credits)
- The marketing page still shows the old plans (Free 3,000 credits with "Supertone" attribution; Starter $2.99 / 20,000 credits, unlimited commercial use; Creator $14.99; Pro $79.99) — stale after the shutdown. — [Supertone API page](https://www.supertone.ai/en/api)

**Typecast (Neosapience)** (primary)
- API plans (1 credit = 1 character): Free $0 / 15,000 credits per month — "무료 플랜을 통해 생성한 음성은 상업적 목적으로 이용할 수 없으며, 반드시 출처를 표기해야 합니다."; Light (shown as "Lite" on the English page) $15/month / 200,000 credits ($0.075 per 1K; overage $0.09 per 1K billed in $9 blocks); Plus $280/month / 4M credits; Enterprise custom. Quick/premium voice cloning slots on paid API plans (Light: 50 custom-voice slots, up to 2 premium). 600+ voices on SSFM 3.0. The page does not spell out paid-plan commercial terms; it links to API terms and an attribution guideline. — [Typecast API pricing (KR)](https://typecast.ai/kr/pricing/api/); [Typecast API pricing (EN)](https://typecast.ai/pricing/api)
- Web-editor plans: Free (3,000 lifetime credits; "Attribution is required for all content downloaded on the Free plan."), Basic $5/month (30,000 credits ≈ 35 min, "Commercial license"), Plus $19, Pro $29, Business $69. — [Typecast pricing](https://typecast.ai/pricing)
- API request parameters: `model` `ssfm-v30` (37 languages) or `ssfm-v21` (27); `text` 1–2,000 chars; `language` ISO 639-3 or auto; emotion `preset` (normal, happy, sad, angry, whisper, toneup, tonedown; intensity 0–2) or `smart` with `previous_text`/`next_text`; output `volume`, `audio_pitch` (−12..+12), `audio_tempo` (0.5–2.0), `target_lufs` (−70..0), `audio_format` wav (16-bit mono 44.1 kHz) or mp3 (320 kbps), `remove_silence_ms`. No `seed` parameter in the fetched reference. A separate text-to-speech-with-timestamps endpoint exists. — [Typecast API reference](https://typecast.ai/docs/api-reference/text-to-speech/text-to-speech); [Typecast docs index](https://typecast.ai/docs/llms.txt)
- Korean number handling helper ("autotag"): `auto_tag()` (Python ≥3.11) converts e.g. `50000원` → "오만원", `14:30` → "오후 두시 삼십분", `2024년 1월 15일` → "이천이십사년 일월 십오일", `010-1234-5678` → digit-by-digit; manual tags `digits(1234)`, `name(김철수)`. Decimal/percent/English-acronym outputs are not shown on the page. — [Typecast autotag best practice](https://typecast.ai/docs/ko/bestpractice/autotag.md)

**Vrew, KT, Kakao**
- Vrew publishes a help article titled "[상업 이용] AI 목소리를 상업적인 용도로 사용할 수 있을까요?" (body could not be fetched; URL too long for the fetch proxy). — [Vrew help category](https://docs.channel.io/vrew-kr/ko/categories/%EA%B8%B0%ED%83%80-68f755e1)

### Inferences
- Usage maths: 4–12 videos × 250–350 chars = 1,000–4,200 chars/month; even with 5× retakes (~21,000 chars) every pay-per-use API costs well under $1/month: Chirp 3 HD stays inside the 1M-char free tier (list $30/1M → ~$0.13 for 4,200 chars if billed); Gemini 3.8 Flash TTS ≈ 12 videos × 40 s × 25 tokens/s = 12,000 audio tokens ≈ $0.11 at $9/1M; gpt-4o-mini-tts ≈ 8 minutes × ~$0.015 ≈ $0.12 (secondary per-minute estimate).
- Subscription floors for a commercial licence: ElevenLabs Starter $6/month list (30k credits covers the volume if 1 credit ≈ 1 char — the credit-per-character rate per model was not readable); Typecast API Light $15/month (API free tier is non-commercial); Typecast web Basic $5/month carries a commercial licence but is the editor, not the API.
- CLOVA Voice is unusable for this workflow by its own policy (no saving/re-using files), and CLOVA Dubbing Standard excludes "광고 및 홍보"/paid use — a business account promoting a paid subscription would likely need Premium, and no headless API for Dubbing was confirmed. Both are effectively out for an automated, API-driven pipeline.
- Voice stability over time is a real risk everywhere: OpenAI snapshots already show deprecated labels; ElevenLabs deprecated Turbo models and launched v4 on 2026-09-28; Azure HD voice IDs contain "Latest"; Gemini TTS models are partly Preview with a price doubling on 2027-01-01; Supertone disappeared entirely. Pinning a dated snapshot/model ID where offered, storing every generated WAV, and keeping the script→audio step re-runnable is the practical mitigation.
- For on-screen text sync, providers with a verified timestamps endpoint are ElevenLabs (`convert-with-timestamps`) and Typecast (timestamps API). For Google/OpenAI, timing would have to come from forced alignment or per-sentence synthesis (durations measured from the returned audio).
- For Korean numbers and tickers the only verified provider-side controls are Google Chirp 3 HD (`say-as`, `sub`, custom pronunciations — Korean supported), Azure (`say-as`, `sub`, alias lexicon) and Typecast autotag; ElevenLabs' and OpenAI's guidance is to normalize text before sending. Since the project already requires numbers to be produced by code, spelling numbers out in Hangul in code is provider-independent and the safest route.
- OpenAI's usage-policy disclosure sentence means that choosing OpenAI TTS creates a labelling duty by contract, regardless of platform rules or Korean law.

### Gaps
- Azure per-character prices (standard neural, HD, MAI-Voice-2) and whether the F0 free tier permits production/commercial use: price table masked; not verified from primary. Secondary figures conflict ($22 vs $30 per 1M for HD).
- NAVER CLOVA Voice base fee and CLOVA Dubbing Standard/Premium monthly fees: masked on the fetched pages. (Unverified recollection only: CLOVA Voice Premium base fee has historically been around ₩90,000/month and CLOVA Dubbing Standard around ₩19,900/month — do not cite without checking the live page.)
- ElevenLabs: credit cost per character by model, IVC/PVC availability matrix by plan (the pricing table was garbled; "Starter: Instant Voice Cloning", "Creator: Professional Voice Cloning" come from feature lists), and whether attribution wording changed. The mapping of character allowances to plan names on the API pricing page was inferred by order.
- ElevenLabs/OpenAI/Gemini: no primary statement on how each reads Korean decimals, percentages, minus signs or English tickers; needs a hands-on test with the actual scripts ("9.28%", "−10.6%", "TQQQ", "S&P 500").
- OpenAI: max characters per request is expressed as 2,000 input tokens; custom-voice eligibility and price not fetched; meaning of the "Deprecated" labels on snapshots (and on the model page itself) is unclear.
- Google: text-length limit per Chirp 3 HD request, timepoint support for Chirp 3 HD, and Instant Custom Voice requirements (allowlist, consent statement, Korean support) were not on the fetched page. Whether Gemini TTS free-tier output may be used commercially is not stated on the pricing page.
- Typecast: paid-plan commercial terms (API terms of service) not fetched; KRW prices not shown.
- Vrew built-in voice terms, KT (AI Voice Studio) and Kakao TTS: no primary pricing/terms retrieved; not verified whether KT or Kakao currently offer a self-serve TTS API.
- Whether any provider's Korean terms pass AI Basic Act labelling duties to users: not found.

---

## 2. Published comparisons / benchmarks of Korean TTS naturalness (2025–2026)

### Takeaway
No independent Korean-language naturalness benchmark covering these providers was found. The best-known leaderboard (Artificial Analysis Speech Arena) ranks models by blind listener preference but exposes only US/UK accent filters, i.e. the evidence is English; Korean comparisons found are vendor marketing.

### Cited Findings
- Artificial Analysis Speech Arena top entries (page fetched 2026-10-10, no as-of date shown): Eleven v4 Turbo 1329, Eleven v4 1326, Qwen-Audio-3.1-TTS-Plus 1298, Sonic 3.6 1281, Gemini 3.8 Flash TTS 1275, Qwen-Audio-3.0-TTS-Plus 1267, Realtime TTS-2 1257, Simba 3.2 1244, Gemini 3.8 Flash-Lite TTS 1243, … Gemini 3.1 Flash TTS 1210, v3 Conversational 1206. The page mentions only US and UK accent filters and does not state a multilingual scope. — [Artificial Analysis TTS leaderboard](https://artificialanalysis.ai/text-to-speech/leaderboard)
- Secondary description of the arena: "Controlled Voice" uses eight fixed voices (four US, four UK); Eleven v4 is first on Provider Voice and second on Controlled Voice (1,157 vs Qwen-Audio-3.1-TTS-Plus 1,178); ElevenLabs' "three-quarters preferred v4" is a vendor figure. — [OrcaRouter blog, 2026-09-28](https://www.orcarouter.ai/blog/eleven-v4-tops-the-voice-arena)
- Typecast's own comparison (published 2026-05-13, updated 2026-09-29, written by a Typecast marketer) compares Typecast, ElevenLabs, Google Cloud TTS, Amazon Polly and CLOVA Dubbing with no test method, scores or samples; it states "단일 1위를 말하기 어렵습니다." and credits CLOVA with "한국어 발음·억양 정밀도 매우 높음". — [Typecast blog](https://typecast.ai/kr/learn/tts-natural-pronunciation-comparison-2026/)
- OpenAI itself states "Voices are currently optimized for English." — [OpenAI TTS guide](https://developers.openai.com/api/docs/guides/text-to-speech)

### Inferences
- Rankings from English arenas should not be transferred to Korean prosody, number reading or English-ticker pronunciation. The decision needs a small blind listening test on the service's real scripts (same 3–5 scripts through 4–5 candidate voices), which costs cents.
- Providers with dedicated ko-KR voices trained per locale (Azure ko-KR, Google ko-KR Chirp 3 HD, Typecast, CLOVA) versus "multilingual voice speaking Korean" (OpenAI, ElevenLabs stock voices) is the distinction most likely to matter for naturalness — plausible but unverified.

### Gaps
- No independent 2025–2026 Korean MOS/arena comparison across ElevenLabs, OpenAI, Google, Azure, CLOVA, Typecast was found. TTS Arena v2 (Hugging Face) was not fetched; its scope is believed to be English but this was not verified.

---

## 3. Open-source / self-hostable TTS with Korean support, commercially usable, CPU-runnable

### Takeaway
Verified Korean-capable models with licences that are not research-only: Supertonic 3 (ONNX, ~99M params, 31 languages incl. Korean; code MIT, weights OpenRAIL-M; repo being archived after Supertone's shutdown), MeloTTS-Korean (MIT, CPU real-time; training data undisclosed), Chatterbox Multilingual (MIT, Korean in list, ~500M params, outputs carry an inaudible watermark), Fun-CosyVoice3 0.5B (Apache-2.0 tag, Korean among 9 languages, GPU-oriented). Not usable: Kokoro (no Korean), Zonos (no Korean), Fish Speech/S2 (research/non-commercial licence), F5-TTS weights (CC-BY-NC), XTTS-v2 (CPML).

### Cited Findings
| Model | Korean | Licence (code / weights) | Commercial use | Hosting / size | Source |
|---|---|---|---|---|---|
| Supertonic 3 (Supertone) | Yes (`ko`, 31 languages) | Sample code MIT / model OpenRAIL-M | Not spelled out on the card ("see LICENSE") | Hugging Face `Supertone/supertonic-3`; ~99M params; ONNX Runtime (also browser WASM/WebGPU) | [GitHub supertone-inc/supertonic](https://github.com/supertone-inc/supertonic); [HF Supertone/supertonic-3](https://huggingface.co/Supertone/supertonic-3) |
| Supertonic 2 / 1 | v2: 5 languages (list not shown); v1: English only | same | same | HF `Supertone/supertonic-2`, `Supertone/supertonic`; ~66M params | [GitHub supertone-inc/supertonic](https://github.com/supertone-inc/supertonic) |
| MeloTTS (MyShell) | Yes (`language='KR'`) | MIT | "free for both commercial and non-commercial use" | HF `myshell-ai/MeloTTS-Korean`; "CPU real-time inference"; install from GitHub repo | [GitHub myshell-ai/MeloTTS](https://github.com/myshell-ai/MeloTTS); [HF MeloTTS-Korean](https://huggingface.co/myshell-ai/MeloTTS-Korean) |
| Chatterbox Multilingual (Resemble AI) | Yes (`ko` in Multilingual list; Turbo and Nano are English-only) | Repo MIT; no separate weights licence stated | MIT | `pip install chatterbox-tts`; Multilingual ~500M params; HF ResembleAI; every output has an "imperceptible neural watermark" (PerTh) | [GitHub resemble-ai/chatterbox](https://github.com/resemble-ai/chatterbox) |
| Fun-CosyVoice3 0.5B (Alibaba) | Yes (9 languages incl. Korean) | Apache-2.0 tag on the model page | Apache-2.0 | HF `FunAudioLLM/Fun-CosyVoice3-0.5B-2512`; 0.5B params; released Dec 2025; no CPU guidance | [HF Fun-CosyVoice3-0.5B-2512](https://huggingface.co/FunAudioLLM/Fun-CosyVoice3-0.5B-2512) |
| Kokoro-82M | No — v1.0 covers American/British English, Japanese, Mandarin, Spanish, French, Hindi, Italian, Brazilian Portuguese | Apache-2.0 | Yes | HF; 82M params | [HF Kokoro-82M](https://huggingface.co/hexgrad/Kokoro-82M); [VOICES.md](https://huggingface.co/hexgrad/Kokoro-82M/blob/main/VOICES.md) |
| Zonos v0.1 (Zyphra) | No (English, Japanese, Chinese, French, German) | Apache-2.0 | Yes | HF `Zyphra/Zonos-v0.1-*`; GPU 6GB+ VRAM; CPU "much slower" | [GitHub Zyphra/Zonos](https://github.com/Zyphra/Zonos) |
| Fish Speech / Fish Audio S2-Pro | Yes (Tier 2) | "FISH AUDIO RESEARCH LICENSE" (updated 2026-03-07) for code and weights | No — "No commercial rights are granted."; commercial use "requires a separate written license agreement" | HF; S2-Pro 4B params; GPU | [GitHub fishaudio/fish-speech](https://github.com/fishaudio/fish-speech); [LICENSE](https://github.com/fishaudio/fish-speech/blob/main/LICENSE) |
| F5-TTS | Not listed for official checkpoints (ZH/EN) | Code MIT / "pre-trained models are licensed under the CC-BY-NC license due to the training data Emilia" | No (weights) | GPU-oriented | [GitHub SWivid/F5-TTS](https://github.com/SWivid/F5-TTS) |
| XTTS-v2 (Coqui) | Yes (one of 17) | Coqui Public Model License (CPML) | Card does not state; CPML is generally understood as non-commercial (not verified here) | HF `coqui/XTTS-v2` | [HF coqui/XTTS-v2](https://huggingface.co/coqui/XTTS-v2) |
| sherpa-onnx Korean TTS | The Korean models page lists exactly one pre-converted model: `supertonic-3-ko` | follows Supertonic 3 | — | sherpa-onnx docs | [sherpa-onnx Korean TTS models](https://k2-fsa.github.io/sherpa/onnx/tts/all/Korean/index.html) |

- Supertonic repo notice dated 2026-07-23: "This repository will be archived."; no "further development or official support" for the open-source models; Supertonic 3 was released 2026-04-29; the README claims built-in handling of currency, units and phone numbers (English examples such as "$5.2M"). — [GitHub supertone-inc/supertonic](https://github.com/supertone-inc/supertonic)
- Community KSS-trained Korean models exist on Hugging Face (`neurlang/piper-onnx-kss-korean`, `neurlang/coqui-vits-kss-korean`). — [HF neurlang/piper-onnx-kss-korean](https://huggingface.co/neurlang/piper-onnx-kss-korean)

### Inferences
- For a headless CPU server, the realistic open candidates are Supertonic 3 (ONNX, small, fixed preset voices → the same voice forever, no vendor to deprecate it) and MeloTTS-Korean. Both remove subscription cost and vendor-shutdown risk, but Supertonic's weights licence (OpenRAIL-M use restrictions) must be read in full and the model will receive no further support.
- A self-hosted model that never changes solves the "same voice week after week" requirement better than any hosted API, at the price of lower expressiveness and self-managed text normalization.
- Whether a model is hosted only on Hugging Face matters for this project's server (egress allow-lists): Supertonic, MeloTTS, CosyVoice and Chatterbox weights were all found on Hugging Face only; none was confirmed on GitHub Releases or PyPI (Chatterbox's code is on PyPI, weights download from HF).

### Gaps
- Supertonic 3 OpenRAIL-M licence text (commercial-use and attribution terms), ONNX file sizes and number of preset voices: not read.
- MeloTTS-Korean training data (KSS, which is CC BY-NC-SA, is commonly assumed but not disclosed on the card) — a licence-cleanliness risk that could not be resolved; checkpoint size not stated.
- Korean quality and CPU real-time factors for all open models: no measured data found.
- CosyVoice code-repo licence and CPU feasibility (GitHub page failed to load); CosyVoice 2 Korean support not verified.
- sherpa-onnx `vits-mimic3-ko_KO-kss_low` existence/licence: not verified (not on the current Korean models page). KSS dataset licence was not checked on a primary page.
- XTTS-v2 CPML commercial terms not read (Coqui shut down; licence purchase path unknown).

---

## 4. Cloning the owner's own voice — providers, plans, verification, price, legal points

### Takeaway
Cloning one's own voice is available cheaply (ElevenLabs Instant Voice Cloning on the $6 Starter plan from ~1–2 minutes of audio; Professional cloning needs Creator $22 and ≥30 minutes plus a read-aloud verification) and YouTube explicitly exempts "Cloning one's own voice to create voice overs or dubs" from disclosure. No Korean legal obstacle to cloning one's own voice was found; the open issues are provider consent terms and Meta's label rule, which turns on "realistic-sounding audio" rather than whose voice it is.

### Cited Findings
- ElevenLabs IVC: "Approximately 1-2 minutes of clear audio"; "Avoid recording more than 3 minutes."; user must confirm right and consent; the clone mimics accent/tonality of the sample. Listed under Starter on the pricing page. — [ElevenLabs IVC guide](https://elevenlabs.io/docs/product-guides/voices/voice-cloning/instant-voice-cloning); [ElevenLabs pricing](https://elevenlabs.io/pricing)
- ElevenLabs PVC: "Free and Starter plan: No PVC slots available."; Creator/Pro 1 slot; "The bare minimum we recommend is 30 minutes of audio." (2–3 hours ideal); voice verification by reading prompted lines in the browser before training; "It is best to use samples speaking where you are speaking the language that the PVC will mainly be used for."; training "roughly 3-6 hours" (up to 6–24 h); if you downgrade below Creator the clone stays but cannot be used. — [ElevenLabs PVC guide](https://elevenlabs.io/docs/product-guides/voices/voice-cloning/professional-voice-cloning)
- Secondary: Eleven v4 supports instant clones from ten seconds of audio. — [OrcaRouter blog, 2026-09-28](https://www.orcarouter.ai/blog/eleven-v4-tops-the-voice-arena)
- Typecast API: quick and premium cloning on paid API plans (Light: up to 2 premium slots, 5 premium clonings/month). — [Typecast API pricing (KR)](https://typecast.ai/kr/pricing/api/)
- OpenAI: custom voice "from a speaker's consent recording and matching audio sample" (details in a separate guide). — [OpenAI TTS guide](https://developers.openai.com/api/docs/guides/text-to-speech)
- Google: Instant custom voice priced at $60 per 1M characters, no free tier. — [Google Cloud TTS pricing](https://cloud.google.com/text-to-speech/pricing)
- Azure: personal voice — creation free, synthesis per 1M characters (price masked). — [Azure Speech pricing](https://azure.microsoft.com/en-us/pricing/details/cognitive-services/speech-services/)
- Supertone voice cloning (Play/Voice Builder) ended 2026-08-31. — [Supertone sunset notice](https://www.supertone.ai/ko/sunset)
- YouTube lists "Cloning one's own voice to create voice overs or dubs" among content that does not need disclosure. — [YouTube Help: altered or synthetic content](https://support.google.com/youtube/answer/14328491?hl=en)
- Comparative law signal (Japan, not Korea): on 2026-09-30 press reported the Tokyo District Court's first ruling that a voice is protected by publicity rights, in voice actor Kenjiro Tsuda's suit over at least 188 TikTok narration videos imitating his voice; the court did not hold all AI-imitated voices illegal. — [파이낸셜뉴스, 2026-09-30](https://www.fnnews.com/news/202609301613552047)

### Inferences
- An own-voice clone keeps the project's existing "본인 목소리" principle (D15) arguably intact while automating production, and it is the only AI-voice variant YouTube names as disclosure-exempt. It is still "digitally generated realistic-sounding audio" under Meta's wording (section 6), so an Instagram AI label would still be the cautious reading.
- A cloned voice is tied to one provider's model generation: ElevenLabs PVC auto-trains on Flash v2.5/Turbo v2.5/Multilingual v2 (per the PVC guide), and a clone becomes unusable after a downgrade below Creator. Keep the source recordings so the clone can be rebuilt elsewhere.
- The owner is faceless by choice; a clone of his real voice is as identifying as his real voice. That is a privacy trade-off, not a legal one.

### Gaps
- Korean commentary on 음성권/퍼블리시티권 specifically for cloning one's own voice: none found (searches returned only third-party-voice disputes and the Japanese case). The commonly cited Korean basis for protecting others' voices (부정경쟁방지법의 성명·초상·음성 등 무단사용 조항) was not verified on law.go.kr in this research. LAWYER only if the voice of anyone other than the owner is ever used.
- Korean-language clone quality by provider: no evidence found.
- OpenAI custom-voice eligibility, Google Instant Custom Voice access requirements and Korean support, Azure personal-voice access gating: not verified.

---

## 5. YouTube — disclosure of AI voice narration, and monetization policy ("inauthentic content", "AI Personas Related to Sensitive Topics")

### Takeaway
YouTube's disclosure list does not name a generic synthetic narrator voice as something to disclose; it requires disclosure for realistic altered/synthetic content (e.g. "Making it appear as if someone gave advice that they did not actually give") and explicitly exempts "Cloning one's own voice to create voice overs or dubs". For monetization, the page does not mention text-to-speech at all, but two sections bite on this use case: templated mass-produced content, and — most relevant for finance — "AI-generated personas" that present as a human expert giving financial advice.

### Cited Findings
- Must disclose (verbatim examples on the current page): "AI generated music"; "AI generated extra footage of a real place…"; "Making it appear as if someone gave advice that they did not actually give"; "Depicting a public figure stealing something they did not steal"; "Making it look like a real person has been arrested or imprisoned"; general criterion "Makes a real person appear to say or do something they didn't do." — [YouTube Help 14328491](https://support.google.com/youtube/answer/14328491?hl=en)
- Need not disclose (verbatim): "Cloning one's own voice to create voice overs or dubs"; "Video sharpening, upscaling or repair and voice or audio repair"; "Production assistance, like using generative AI tools to create or improve a video outline, script…"; "Caption creation"; "Using effects to enhance previously recorded audio"; unrealistic/animated content. The page has no item on a synthetic stock voice used as narrator. — [YouTube Help 14328491](https://support.google.com/youtube/answer/14328491?hl=en)
- "Disclosing AI content won't limit a video's audience or impact its eligibility to earn money."; creators who consistently fail to disclose may face manual labelling, content removal or YPP suspension; YouTube may auto-label content made with its own GenAI tools, with C2PA metadata, or detected as AI. The page contains no special finance/health label rule. — [YouTube Help 14328491](https://support.google.com/youtube/answer/14328491?hl=en)
- API: `status.containsSyntheticMedia` (added 2024-10-30) indicates realistic altered/synthetic content and "can be set when calling the `videos.insert` or `videos.update` methods." — [YouTube Data API revision history](https://developers.google.com/youtube/v3/revision_history)
- Monetization policy, update notice: "July 15, 2025: We're making a minor update to our "repetitious content" policy…"; "We are also renaming this policy from "repetitious content" to "inauthentic content."" The section itself is headed "Generic or Repetitive Content". No July 2026 notice appears on the page. — [YouTube Help 1311392](https://support.google.com/youtube/answer/1311392?hl=en)
- Not allowed to monetize (verbatim): "Image slideshows, templated storylines, or scrolling text with minimal or no narrative, commentary, or educational value"; "AI-generated content made with generic or unoriginal templates giving the impression of mass production"; "Similar or repetitive content with low educational value, commentary, narratives, or minimal variation across videos". Allowed: "Same intro and outro for your videos, but the bulk of your content is different". — [YouTube Help 1311392](https://support.google.com/youtube/answer/1311392?hl=en)
- "If you use automated tools or templates to help create your content, the final product must still demonstrate your creative vision and provide educational or entertainment value." — [YouTube Help 1311392](https://support.google.com/youtube/answer/1311392?hl=en)
- Reused content, not allowed: "Content that exclusively features readings of other materials you did not originally create". — [YouTube Help 1311392](https://support.google.com/youtube/answer/1311392?hl=en)
- AI Personas Related to Sensitive Topics (verbatim): "This policy refers to channels that use AI-generated personas to deliver information on sensitive topics."; "This includes any content that presents itself as a human expert providing advice to viewers on topics such as health, legal issues, finances, or politics."; such channels "will not be allowed to monetize."; example: "AI-generated podcast hosts offering financial guidance, investment tips, or wealth management advice". The section does not define "persona" and does not say whether a synthetic voice alone counts. — [YouTube Help 1311392](https://support.google.com/youtube/answer/1311392?hl=en)
- The page does not use the terms text-to-speech, AI voice, synthetic voice or "identical narration". — [YouTube Help 1311392](https://support.google.com/youtube/answer/1311392?hl=en)
- Rene Ritchie (YouTube Head of Editorial & Creator Liaison) called the July 2025 change a "minor update"; mass-produced or repetitive content has been "ineligible for monetization for years"; the article notes it is "common to find an AI voice overlaid on photos, video clips, or other repurposed content". — [TechCrunch, 2025-07-09](https://techcrunch.com/2025/07/09/youtube-prepares-crackdown-on-mass-produced-and-repetitive-videos-as-concern-over-ai-slop-grows)
- Korean press, 2026-07-26: YouTube revised YPP guidelines; channels making many near-identical videos with AI/CGI on a fixed template are restricted; AI avatars mimicking a real person's look or voice while giving finance/medical/legal information are excluded from monetization; YouTube does not restrict AI use itself — the criterion is whether the creator's judgment and originality show. — [뉴시스, 2026-07-26](https://mobile.newsis.com/view/NISX20260726_0003723647)
- Vendor blog (Typecast, Aug 2026; secondary, promotional): says three items were made explicit from 2026-07-16 (generic/templated content, distressing content, AI personas on sensitive topics) and quotes a YouTube representative: "AI can actually allow people to make a lot of videos." — [Typecast blog](https://typecast.ai/kr/learn/youtube-ai-voice-monetization-2026/)
- YPP thresholds: "Get 1,000 subscribers with 4,000 qualified watch hours in the last 12 months" or "…10 million qualified Shorts views in the last 90 days."; "Starting February 1, 2027, we are introducing updates to the YouTube Partner Program (YPP)." (creators must accept updated terms by 2027-01-31). — [YouTube Help 72851](https://support.google.com/youtube/answer/72851?hl=en)

### Inferences
- Disclosure: a non-cloned synthetic narrator reading the channel's own code-generated text over typography does not match any "must disclose" example (no real person, no realistic scene), and an own-voice clone is expressly exempt. Disclosure is therefore not clearly required by YouTube's text — but it is also cost-free ("won't limit a video's audience"), and the API flag exists. Voluntary disclosure in the description is the low-risk choice.
- Monetization risk for this format is not the AI voice per se; it is the combination "typography template + numbers + TTS" repeated weekly, which reads close to "scrolling text … with minimal or no narrative" and "templates giving the impression of mass production" unless each video carries distinct commentary/insight.
- The AI-persona section is the finance-specific trap: a named AI narrator who speaks in the first person as an expert ("저는 … 추천합니다") giving investment guidance is the stated non-monetizable example. A voice that only reads sourced facts and states, with no expert persona and no advice, is further from the wording — but the page does not define the boundary. Whether a voice alone is a "persona" is unresolved.
- These are YPP (ad-revenue) eligibility rules; they do not remove or block videos. They matter only if/when the channel seeks YouTube monetization.

### Gaps
- No official YouTube sentence was found stating "AI voiceover alone does not make a video ineligible"; the closest primary text is the "automated tools or templates" sentence above. Statements attributed to YouTube in Korean press and vendor blogs are secondary.
- The July 2026 YPP revision reported by 뉴시스/Typecast is not reflected as a dated notice on the Help page; exact effective date (07-16?) not verified. The Typecast claim that YPP thresholds rise on 2027-02-01 (8,000 hours or 20M Shorts views) is NOT confirmed by the Help page, which only announces "updates" without numbers.
- No Shorts-specific rule on AI voice was found; YouTube's own built-in Shorts TTS voices and how they are labelled were not researched.
- Korean-language Help page was served in English; no Korean wording captured.

---

## 6. Meta (Instagram Reels, Threads, Facebook) — AI label for realistic-sounding audio, API field, AI-generated profile rule

### Takeaway
Meta's rule, as reported, covers realistic AI narration: organic content with "photorealistic video or realistic-sounding audio that was digitally generated or altered, including with AI" must be labelled, with unspecified "penalties" for not doing so. Since 2026-06-22 the Instagram API accepts `is_ai_generated=true` at publish time; no equivalent was found for the Threads API. The 2026-08-31 "AI-generated profile" label concerns profiles that feature an AI-generated person, and nothing found extends it to voice-only AI use.

### Cited Findings
- Secondary quotation of Instagram's Help wording (article dated 2026-10-01, says it reflects Meta's pages as read that day): "Instagram requires you to label content you share that has photorealistic video or realistic-sounding audio that was digitally generated or altered, including with AI."; the Help article "warns that there may be penalties if you do not label content as required"; AI images are not required to be labelled; in-app: turn on "Add AI label" on the share screen; the article's decision table lists "A reel narrated by a realistic AI voiceover" as requiring a label, and says AI dubbing and cloned voices reading a script fall within the requirement (the article's interpretation). — [Sirency blog, 2026-10-01](https://www.sirency.com/blog/instagram-ai-label-rules) (cites [Instagram Help 761121959519495](https://help.instagram.com/761121959519495) and [Meta Help 1783222608822690](https://www.meta.com/help/artificial-intelligence/1783222608822690/), whose bodies could not be fetched)
- Meta newsroom history: labels apply when Meta detects industry-standard AI signals or when "people disclose that they're uploading AI-generated content"; organic labelling started May 2024; "Made with AI" renamed "AI info" on 2024-07-01; from 2024-09-12 the label for content only modified/edited by AI moved to the post's menu. — [Meta Newsroom, 2024-04-05, updated](https://about.fb.com/news/2024/04/metas-approach-to-labeling-ai-generated-content-and-manipulated-media/)
- Instagram Platform changelog, 2026-06-22 ("AI Info Label"): "Set the new `is_ai_generated` parameter to `true` when creating a media container to apply the AI info label."; for carousels set it on the carousel container; available with both Facebook Login and Instagram Login; readable via `GET /{ig_media_id}?fields=is_ai_generated`. — [Instagram Platform changelog](https://developers.facebook.com/documentation/instagram-platform/changelog.md)
- Threads API changelog: no entry about AI labels or `is_ai_generated` found; `VIDEO` media type is supported for posts. — [Threads changelog](https://developers.facebook.com/documentation/threads/changelog)
- Third-party publishing tool docs list API fields: Instagram `is_ai_generated`, TikTok `is_aigc`, YouTube `containsSyntheticMedia`, X `made_with_ai` (media posts); Facebook has no API field (in-app or C2PA/IPTC detection); Threads not mentioned. — [Upload-Post docs](https://docs.upload-post.com/guides/ai-content-labeling)
- AI-generated profile (2026-08-31): Instagram renamed its "AI creator" label to "AI-generated profile"; it tells users the person featured on a profile was "generated or substantially created with AI"; Instagram: "They want to know when a profile features an AI-generated person."; not needed for using AI to edit photos, polish captions or create graphics; unlabelled AI profiles can have reach reduced. AI voice is not mentioned. — [TechCrunch, 2026-08-31](https://techcrunch.com/2026/08/31/instagram-puts-new-limits-on-undisclosed-ai-profiles/)
- Further detail (secondary): "The policy covers the identity presented by a profile, not every use of AI in production."; unlabelled detected profiles become ineligible for recommendations (Reels, Explore, suggested accounts); enforcement to begin "in the coming weeks"; toggle under Edit profile. — [Implicator, 2026](https://www.implicator.ai/instagram-will-cut-the-reach-of-ai-personas-that-skip-its-new-label/)

### Inferences
- A natural-sounding Korean TTS narrator on a Reel is "realistic-sounding audio that was digitally generated" on a plain reading; the cautious course is to set `is_ai_generated=true` (API) or "Add AI label" (app) on every narrated Reel. For a typography-only video the label would refer to the audio alone.
- Threads: since no API field was found, a Threads video with AI narration would need the label added in the app (if the app offers it for Threads) or a text disclosure in the post — to be checked hands-on.
- A faceless account with code-rendered text and an AI voice presents no AI-generated person, so the profile-level "AI-generated profile" label does not appear to apply; this is inference from press descriptions, not from Meta's own text.

### Gaps
- Exact current Help Center/Transparency Center wording, the "penalties" sentence, and whether the audio rule distinguishes one's own cloned voice: not verified from primary (pages returned metadata only; facebook.com blocked by robots).
- Whether the Threads app has an AI-label toggle for video posts; whether labelled posts are distributed differently: not found.
- The reported X `made_with_ai` API field is from a third-party doc only; not verified on X's developer docs.

---

## 7. X — synthetic voice

### Takeaway
X has no labelling rule for non-deceptive AI audio; its authenticity policy targets deceptive manipulated media about real people.

### Cited Findings
- "You may not share inauthentic media, including, manipulated, or out-of-context media"; covers "media depicting a real person that has been fabricated or simulated, especially through use of algorithms or broader artificial intelligence" and media with altered "visual or auditory information (such as new video frames, overdubbed audio, or modified subtitles)"; sharing manipulated media "in non-deceptive ways" is permitted. No labelling requirement for AI-generated voice is stated. — [X Help: Authenticity policy](https://help.x.com/en/rules-and-policies/authenticity)

### Inferences
- A synthetic narrator that impersonates no real person and makes no deceptive claim is outside the policy's target; no X-side action is required.

### Gaps
- X developer-doc confirmation of any "made with AI" posting field: not verified (see section 6).

---

## 8. Korea — AI Basic Act Art. 31, 정보통신망법 amendment, 공정위 "가상인물" guideline, 금감원, 표시광고법

### Takeaway
As of 2026-10-10 a creator who merely uses a TTS tool has no statutory AI-labelling duty in Korea: AI Basic Act Art. 31 binds "인공지능사업자" (the TTS provider), not users, and enforcement is in a grace period of at least one year. A poster-side duty is coming but not law yet: a 정보통신망법 amendment (의안 2216186, covering hard-to-distinguish AI voice, images and video) is in committee, and the 방미통위 announced on 2026-09-30 that it targets December 2026 for the amendment work. The 공정위 "가상인물" rule (in force 2026-06-01) concerns a hard-to-distinguish virtual person giving endorsements; no source addresses a voice-only narrator.

### Cited Findings
**(a) AI Basic Act (인공지능기본법, effective 2026-01-22), Art. 31**
- Obligated party is the "인공지능사업자" (developer or deployer); a person who simply uses AI output to make their own content is a user — the firm's example is a YouTuber making video with Sora — and the transparency duty is unlikely to apply to such users. — [법무법인 세종 뉴스레터, 2026-02-26](https://www.shinkim.com/kor/media/newsletter/3142)
- "이용자가 아니라 AI 제품·서비스를 이용자에게 직접 제공하는 '인공지능사업자'가 의무 주체다."; "AI를 업무나 창작의 도구로 활용하는 이용자는 의무 대상이 아니다"; overseas providers serving Korean users are covered. — [뉴시스, 2026-01-21](https://www.newsis.com/view/NISX20260121_0003485509)
- What the provider must do: label generative-AI output by a human-perceivable or machine-readable method (if machine-readable only, give a notice at least once); output exported by download/sharing must be labelled on the output itself; for audio, announce AI generation at the start (not for the whole duration) or use audio watermarking/metadata; deepfakes need clearly perceivable labelling (audio: at the start of playback). — [세종 뉴스레터, 2026-02-26](https://www.shinkim.com/kor/media/newsletter/3142); [뉴시스, 2026-01-21](https://www.newsis.com/view/NISX20260121_0003485509)
- Deepfake criterion: "실제 인물이나 현실과 구분이 어려운지 여부가 핵심 기준이다." — [뉴시스, 2026-01-21](https://www.newsis.com/view/NISX20260121_0003485509)
- Sanctions and grace period: corrective orders and fines up to ₩30 million; "1년 이상 계도기간이 운영되며, 해당 기간 동안 사실조사와 과태료 부과는 유예된다." — [헤럴드경제, 2026-01-21](https://www.heraldk.com/article/2026012118293709444); [뉴시스, 2026-01-21](https://www.newsis.com/view/NISX20260121_0003485509)
- If a user strips a provider's watermark during distribution there is currently no direct sanction; a 정보통신망법 amendment imposing a labelling duty on posters has been introduced to close this gap. — [세종 뉴스레터, 2026-02-26 (footnote 6)](https://www.shinkim.com/kor/media/newsletter/3142)
- Pending AI Basic Act amendment (안철수 의원, 2026-07-27): would split Art. 31(2) duties — developers label machine-readably, service businesses label so users clearly recognise AI output; effective one year after promulgation; nothing on end users. — [디지털데일리, 2026-07-27](https://www.ddaily.co.kr/page/view/2026072711281547343)

**(b) 정보통신망법 amendment — labelling duty for people who post AI-generated content**
- 의안 2216186: proposed 2026-01-20; subcommittee review recorded 2026-09-15; no plenary vote or promulgation — "국회 심사 중"; it proposes a labelling duty for those who directly make or edit and provide "실제와 구분하기 어려운 AI 음성, 이미지와 영상 등". — [디지털마케터 가이드, 2026-09-28, updated 2026-10-04](https://www.digitalmarketer.co.kr/insights/ai-ad-labeling-korea-guide)
- A 정보통신망법 amendment led by 서영석 의원 (reported 2026-01-27) introduces a labelling duty for "인공지능 생성물", defined to include "음향·이미지·영상 등", bans damaging/forging labels, requires platform technical and managerial measures, and treats illegal ads using AI output as blockable illegal information. — [헤럴드경제, 2026-01-27](https://www.heraldk.com/article/2026012716224311894)
- Government line: on 2026-09-30 the 방송미디어통신위원회 adopted its policy agenda — amend the 정보통신망법 so that users who post AI-generated images or video must label them, ban tampering, make platforms check compliance; amendment targeted for December 2026. — [MTN, 2026-09-30](https://news.mtn.co.kr/news-detail/2026093017122478426)
- 2026-07-15: individuals uploading AI-made video currently have no legal labelling duty; the amendment was stalled by National Assembly deadlock. — [MTN, 2026-07-15](https://news.mtn.co.kr/news-detail/2026071516414928239)
- Related product-specific rules: new AI fake-expert advertising provisions take effect 2026-11-27 (식품표시광고법, 약사법) and 2026-12-10 (의료기기법). — [디지털마케터 가이드](https://www.digitalmarketer.co.kr/insights/ai-ad-labeling-korea-guide)

**(c) 공정위 추천·보증 심사지침 — "가상인물" (in force 2026-06-01)**
- The KFTC prepared the revision on 2026-05-26 and applied it from 2026-06-01; it adds "인공지능을 활용하여 생성한 가상인물" as an endorser type; the guideline treats as a virtual person a "실제와 구분하기 어려운 가상의 인물" generated with AI that gives a recommendation/endorsement. — [법률사무소 청출 블로그, 2026-06-08](https://cheongchul.com/blog/ai-%EA%B0%80%EC%83%81%EC%9D%B8%EB%AC%BC-%EA%B4%91%EA%B3%A0-%EA%B7%9C%EC%A0%9C); [세종 뉴스레터, 2026-04-23](https://www.shinkim.com/kor/media/newsletter/3242)
- Labelling method: text media — "AI를 기반으로 생성된 가상인물이 포함된 게시물입니다." or "가상인물 포함" in the title or opening; video/photo — "가상인물" near the virtual person while it appears. If a virtual person speaks as though from experience and it does not match fact, it may be an unfair representation. — [디지털인사이트, 2026-06-04](https://ditoday.com/그-광고-모델-ai가-만들었나요-공정위-가상인물-표시/)
- Sanctions under 표시광고법: corrective measures, surcharges, publication orders, criminal penalties (up to 2 years or ₩150 million) and damages. — [세종 뉴스레터, 2026-04-23](https://www.shinkim.com/kor/media/newsletter/3242); [디지털마케터 가이드](https://www.digitalmarketer.co.kr/insights/ai-ad-labeling-korea-guide)
- None of the four sources addresses an AI voice with no visible person.

**(d) 금융감독원 / 금융위**
- 2026-01-26 consumer alert ("주의") on illegal 리딩방: scammers impersonate well-known brokerage staff on YouTube and SNS "인공지능(AI) 딥페이크 기술을 악용해", steer victims to group chats and fake trading apps. — [SBS Biz, 2026-01-26](https://biz.sbs.co.kr/amp/article/20000287460)
- 2026-04-28: FSS runs AI-based 24/7 monitoring of finfluencers; signs of illegal conduct found on five channels; flagged types include unregistered 유사투자자문 with tiered monthly fees and selling auto-trading software without registration. No mention of AI-generated voice. — [머니S(시대), 2026-04-28](https://www.sidae.com/article/2026042810115120226)

**(e) Provider contract terms that reach the user**
- OpenAI requires users "to provide a clear disclosure to end users that the TTS voice they are hearing is AI-generated and not a human voice." — [OpenAI TTS guide](https://developers.openai.com/api/docs/guides/text-to-speech)

### Inferences
- Today the creator's labelling obligations come from platform rules (Meta; arguably YouTube) and provider contracts (OpenAI), not from Korean statute. A poster-side statutory duty is likely within months to a year; both pending texts are framed around AI output that is hard to distinguish from the real thing and expressly include voice/음향. A natural-sounding TTS narrator plausibly falls inside. Designing a standing label now (a line in the caption/description and a small on-screen "AI 음성" mark) avoids rework.
- The KFTC rule is triggered by a virtual *person* giving an *endorsement*. A voice-only narrator explaining market facts is neither clearly a "가상의 인물" nor an endorser; but subscription-promotion videos are advertising by the business itself, where the general 표시광고법 ban on deceptive representation applies regardless. LAWYER: whether a human-sounding AI voice saying first-person lines ("저는 매주 화요일…", "제가 직접 …") in a subscription pitch could mislead consumers about who is speaking or about lived experience. A conservative script rule is to keep the AI voice out of first-person experience claims and to state that the narration is an AI voice.
- Regulators' public framing of AI voice/video in investing is exclusively the scam frame (deepfake impersonation, 리딩방). For a service that will register as 유사투자자문업, an undisclosed synthetic voice sits uncomfortably close to that pattern in audience perception; clear disclosure is a positioning asset as much as a compliance step.
- The TTS provider, not the user, must mark its output under Art. 31 (possibly with inaudible watermarks/metadata — e.g. Chatterbox's PerTh watermark is an example of the technique). Editing audio may strip such marks; there is currently no sanction for that, but the pending amendment would ban tampering with labels.

### Gaps
- Full text, sponsor and exact scope of 의안 2216186 (who is "제공하는 자", exemptions, fines, effective date) not read on the National Assembly system; it is unclear whether 의안 2216186 and the 서영석 bill are the same bill. Whether the 방미통위's planned December 2026 amendment will cover audio (its summary mentions "이미지나 영상") is not confirmed.
- KFTC guideline primary text (law.go.kr / ftc.go.kr press release) not fetched; whether "가상인물" can include a voice-only persona is unaddressed in every source — LAWYER / KFTC inquiry.
- No 금감원/금융위 guidance on AI-generated voices in 유사투자자문업 advertising or content was found; 금융투자협회/유사투자자문업 광고 규정 were not checked for AI clauses.
- 전자상거래법 points: nothing specific found.
- AI Basic Act enforcement decree/transparency guideline primary text not fetched (relied on law-firm and press summaries).

---

## 9. Audience evidence — reaction to AI narration vs human narration; effect of disclosure

### Takeaway
No Korean study isolating AI *voice* narration in short-form video was found. The nearest Korean data (Opensurvey, Sept 2026, n=900 platform users) shows broad discomfort with AI content and a strong demand for labels — 85.6% want AI labels and 33.8% feel deceived when AI use is not disclosed. Overseas experiments suggest listeners often cannot tell a good AI voice from a human one, yet state lower trust once they know, with disclosure splitting reactions.

### Cited Findings
- Opensurvey "소셜미디어 트렌드 리포트 2026" (fieldwork 2026-09-03~09; n=3,000 aged 15–59, plus 300 recent users each of YouTube/Instagram/TikTok = 900; published 2026-09-21). — [Opensurvey blog](https://blog.opensurvey.co.kr/trendreport/socialmedia-2026/)
- From that report (n=900 platform users): AI content needs labelling 85.6% ("꼭 필요하다" 54.1%); by platform YouTube 88.0%, Instagram 85.3%, TikTok 83.3%; reactions to AI content — artificial/awkward 49.9%, doubt whether true 39.0%, "AI 사용을 밝히지 않으면 속는 느낌이 든다" 33.8%, confusing whether real 23.7%, creative 11.4%, interesting 10.4%; negative ad memory because "AI로 만든 것 같아서" 13.2%; most-wanted disclosure: whether AI was used 54.7%. — [SBS Biz, 2026-09-26](https://biz.sbs.co.kr/amp/article/20000336750); [이코노미스트, 2026-09-26](https://economist.co.kr/article/view/ecn202609230048)
- 한국언론진흥재단 미디어연구센터 survey (2025-09-04~08, n=1,000 adults 20–60s): 60% say an article using an AI-generated image is hard to regard as news; 48.1% say so for data-based AI auto-generated articles. — [한국기자협회, 2025-09-17](https://www.journalist.or.kr/news/article.html?no=59349)
- Kapwing study (as of late Oct 2025): Korea-based AI-slop channels had 8.45 billion views, the most of any country (Pakistan 5.3bn, US 3.4bn); 4 of the top-10 most-viewed AI channels globally were Korea-based. — [조선일보 via Daum, 2025-12-15](https://v.daum.net/v/20251215005250515)
- Radio experiment (Crowd React Media / Harker Bos Group; n=1,326 weekly radio listeners aged 18–45; fieldwork May–June 2026; country not stated): 59% identified the human read as human and 55% judged the AI read to be human; ratings were statistically indistinguishable on professionalism, authenticity, credibility; if a station used AI voices 47% said no difference, 21% more favourable, 33% less favourable; after the reveal 25% of AI-voice listeners felt more favourable and 20% less. — [Radio Ink, 2026-07-07](https://radioink.com/2026/07/07/radio-listeners-cant-detect-ai-voice-but-dont-trust-it-either/)
- Adobe Express survey (850 consumers, 205 marketers; country not stated): "88% of respondents said they have heard a voice and wondered if it was AI-generated."; "77% of consumers trust human voices the most."; for AI voices in ads "58% said they would trust the brand less"; "Nearly 3 in 4 consumers believe brands should disclose when they use AI-generated voice or music." — [ContentGrip, 2026-03-06](https://www.contentgrip.com/ai-voices-in-marketing-adobe/)
- Korean community commentary (anecdotal, one forum thread, 2026-07-20): poster downvotes and blocks videos as soon as an AI voice and typical AI animation appear; "AI영상을 보면 일방적인 정보전달만 한다는 느낌이라 거부감이 큽니다."; comment: "이제 특유의 카랑카랑한 남성 AI음성은 듣기조차 싫습니다." — [다모앙 자유게시판, 2026-07-20](https://damoang.net/free/6753999)

### Inferences
- The Korean data point to non-disclosure, not AI use itself, as the trust-destroying factor (a third feel deceived when AI is not disclosed; 85.6% want labels). For a service whose positioning is transparency, a labelled AI voice is consistent with the brand; an unlabelled human-sounding one is the worst combination.
- The community reaction targets a recognisable cluster — stock "카랑카랑한" male TTS + template animation + AI script. A distinctive, calmer voice, human-written scripts and visibly original data lower the chance of being pattern-matched as AI slop, but the stated-preference data (77% trust human voices most) mean an AI voice starts with a trust handicap that the content has to overcome.
- Blind-test results (55% took the AI read for human) imply that current top voices are good enough that naturalness is no longer the binding constraint; disclosure and content quality are.

### Gaps
- No Korean survey or experiment on AI-voiced vs human-voiced Shorts/Reels (retention, completion, trust) was found; no retention analytics by voice type.
- No study specific to finance/investment content narrated by AI voice.
- Radio Ink and Adobe studies are non-Korean, self-reported or industry-sponsored; Adobe fieldwork dates and country not stated.
- Korean creator-community evidence is a single thread; press coverage specifically about backlash to "AI 더빙 쇼츠" was not found.

---

## 10. Practical production facts — Korean number/ticker reading, narration speed, loudness

### Takeaway
No provider documents its Korean reading of decimals, percentages, minus signs or tickers; every verified control mechanism points the same way — convert numbers and symbols to Hangul words in code before synthesis and use alias/sub tags (or a dictionary) for tickers. Korean read speech measures about 5 syllables per second overall, so 250–350 characters will not fit in 40 seconds without speeding up. No platform-published LUFS target for Shorts/Reels was found.

### Cited Findings
- Typecast autotag converts amounts, times, dates and phone numbers to Korean readings (e.g. `50000원` → "오만원", `14:30` → "오후 두시 삼십분"); manual tags `digits()`, `name()`, `address()`; a `ratio` tag type (e.g. 50%, 1:2) exists but its Korean output is not shown. — [Typecast autotag](https://typecast.ai/docs/ko/bestpractice/autotag.md)
- ElevenLabs: smaller models misread complex numbers; recommended to normalize with an LLM or regex and write numbers as spoken words; alias tags replace a word with other words (works on Multilingual v2); `apply_language_text_normalization` is Japanese-only. — [ElevenLabs normalization](https://elevenlabs.io/docs/best-practices/prompting/normalization); [ElevenLabs API reference](https://elevenlabs.io/docs/api-reference/text-to-speech/convert)
- Google Chirp 3 HD supports `<say-as>`, `<sub>`, `<phoneme>`, `<break>`, `<prosody>` (sync requests), `speaking_rate` 0.25–2.0, pause tags and custom pronunciations (IPA/X-SAMPA) with Korean not excluded. — [Chirp 3 HD docs](https://docs.cloud.google.com/text-to-speech/docs/chirp3-hd)
- Azure HD voices: `say-as`, `sub`, `phoneme`, `break` supported; `prosody` not supported on DragonHD; `enhancePronunciation` flag for names/acronyms/mixed text. — [Azure HD voices](https://learn.microsoft.com/en-us/azure/ai-services/speech-service/high-definition-voices)
- OpenAI gpt-4o-mini-tts: speed and tone via `instructions`; no SSML or dictionary mechanism is described on the guide. — [OpenAI TTS guide](https://developers.openai.com/api/docs/guides/text-to-speech)
- Korean read-speech rate: Korean women reading a passage — overall speech rate 5.04 syllables/s, articulation rate (pauses excluded) 6.48 syllables/s (n=6 per group; reading task; 2012); the authors cite 5–5.5 syllables/s as an adult reading norm. — [황지성·이숙향, 한국음향학회지 31(2), 2012](https://www.koreascience.kr/article/JAKO201212961960491.pdf)
- Loudness: a third-party guide says "YouTube recommends -14 LUFS integrated with a -1 dBFS true peak maximum" and that TikTok and Instagram Reels "don't publish exact specs" (its own suggested safe range −14 to −16 LUFS); no platform documentation is cited. — [OpenClip guide](https://openclip.app/learn/audio-normalization)
- Typecast API can normalise output loudness directly via `target_lufs` (−70..0, e.g. −14). — [Typecast API reference](https://typecast.ai/docs/api-reference/text-to-speech/text-to-speech)
- Timestamps for text sync: ElevenLabs "Create speech with timing" endpoint; Typecast text-to-speech-with-timestamps endpoint. — [ElevenLabs API reference](https://elevenlabs.io/docs/api-reference/text-to-speech/convert); [Typecast docs index](https://typecast.ai/docs/llms.txt)

### Inferences
- Script-length budget (inference from the 5.04 syll/s figure): 250–350 characters including spaces is roughly 190–280 spoken syllables once spaces/punctuation are removed, but spelled-out numbers add syllables ("9.28%" → "구 점 이팔 퍼센트" = 7 syllables from 5 characters). At ~5 syll/s that is about 38–56+ seconds. A 15–40 s video therefore supports roughly 75–200 syllables at natural pace; hitting 40 s with 350 characters needs a tempo of about 1.3–1.4×, which short-form viewers tolerate but which should be tested for clarity with numbers.
- Recommended control pattern (provider-independent): keep two strings per line — the display string ("−10.6%", "TQQQ", "S&P 500") for the typography layer and a code-generated spoken string in Hangul ("마이너스 십 점 육 퍼센트", "티큐큐큐", "에스앤피 오백") for TTS. This matches the project rule that numbers come only from code, and makes the audio reproducible across providers. Decide conventions once (decimal digits read individually: "구 점 이팔"; minus as "마이너스"; tickers letter-by-letter) and unit-test them.
- Because determinism is not guaranteed anywhere (ElevenLabs seed is best-effort; Gemini/OpenAI/Azure expose no seed), consistency should come from fixed voice ID + fixed model ID + fixed settings/instruction text, and from archiving the generated audio rather than regenerating.
- Loudness: with no official Shorts/Reels spec, normalising every clip to a fixed target around −14 LUFS with about −1 dBTP in the render step (ffmpeg `loudnorm`) gives week-to-week consistency, which matters more than the exact figure.

### Gaps
- How each candidate engine actually reads "9.28%", "−10.6%", "TQQQ", "S&P 500", dates and large dollar amounts in Korean: no documentation; requires a hands-on test.
- Short-form-specific Korean narration speed (syllables/s used by popular Shorts narrators) and news-anchor rates: no solid source found (one 2008 press article gives only "방송 뉴스는 160∼180wpm", a words-per-minute figure of unclear basis).
- Official YouTube/Meta loudness documentation for Shorts/Reels: not found; the −14 LUFS YouTube figure is secondary.
- Google `<say-as>` behaviour for ko-KR (which `interpret-as` values work in Korean) was not verified.
