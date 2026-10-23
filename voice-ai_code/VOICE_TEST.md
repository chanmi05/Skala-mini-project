# 이효준 · 음성 연동 실행 / 테스트

## 로컬 규정 검색 실험: demo 모드

현재 voice-ai_code/.env의 VOICE_RAG_MODE를 demo로 설정했습니다.
RAG_BASE_URL은 이 모드에서 사용하지 않습니다.
터미널 환경변수에 남은 mock 값이 덮어쓰지 않도록 서버를 종료한 뒤 아래처럼 시작하세요.

```bash
cd /Users/leehyojun/Desktop/Skala-mini-project/voice-ai_code
VOICE_RAG_MODE=demo /opt/homebrew/bin/python3.11 -m uvicorn app.main:app --host 127.0.0.1 --port 8008
```

로그인 후 /voice-query.html에서 '검색 실험 모드'를 확인합니다.
녹음 → STT/문맥 교정 → 질문 확인·수정 → '이 질문으로 답변 받기' 순서입니다.
음성 인식 오류를 검색 오류로 오해하지 않도록 확정한 질문을 먼저 확인하세요.
demo 규정 검색 자체는 외부 API를 부르지 않지만 문맥 교정과 TTS는 비용이 발생합니다.

모든 규정은 음성팀 실험용으로 임의 작성했습니다. 실제 법령·회사 규정이 아닙니다.
각 답변에도 이 안내가 붙습니다. 표시하는 페이지 번호는 가상 테스트 문서의 번호입니다.
정상 답변의 needs_review/handoff는 false/false,
근거 없음·개별 판단의 경우 true/true, sources=[]입니다.

| 확정할 질문 | 답변에 포함되어야 하는 내용 | 출처 |
| --- | --- | --- |
| 연차 신청은 며칠 전에 해야 하나요? | 3영업일 전, 사내 포털, 팀장 승인 | DEMO-01, 1쪽 |
| 남은 연차를 내년으로 이월할 수 있나요? | 최대 2일, 다음 해 2월 말, 인사팀 사전 승인 | DEMO-02, 2쪽 |
| 본인이 결혼하면 휴가는 며칠인가요? | 3일, 청첩장 또는 예식 확인서 | DEMO-03, 3쪽 |
| 재택근무는 일주일에 몇 번 가능한가요? | 주 1회, 전날 오후 3시까지 신청, 팀장 승인 | DEMO-04, 4쪽 |
| 육아휴직 신청에 필요한 서류는 무엇인가요? | 휴직 신청서, 휴직 일정표, 추가 서류는 담당자 확인 | DEMO-05, 5쪽 |
| 올해 연봉 인상률은 얼마인가요? | 테스트 규정에서 찾을 수 없음, 담당자 안내 | 없음 |
| 다음 회식은 언제인가요? | 테스트 규정에서 찾을 수 없음, 담당자 안내 | 없음 |
| 제가 받은 징계가 정당한가요? | 개별 판단 제공 안 함, 담당자 검토 필요 | 없음 |
| 육아휴직은 최대 몇 년인가요? | 기간 규정이 없으므로 찾을 수 없음 | 없음 |

구현: app/data/demo_hr_rules.json의 규정과 키워드를 읽고,
app/services/demo_rag.py가 주제/의도 키워드 그룹을 모두 만족하는 규정을 검색합니다.
검색된 문서 내용과 메타데이터로 답변/출처를 만들며, 답변 생성 LLM은 쓰지 않습니다.
인덱스·임베딩·FAISS가 없고 임의 문장에 대한 의미 이해도 제한적입니다.
따라서 이것은 음성/API/출처/담당자 표시 연결 실험이며 팀 RAG 검색 품질 평가는 아닙니다.
수량·시점·개인별 상황 추론까지 검증하지는 못합니다.

규정을 바꿔 실험하려면 JSON의 content와 match_all을 수정하세요.
같은 질문을 다시 보내 답변이 문서 내용에 따라 변하는지 확인할 수 있습니다.
실제 RAG 준비 후 VOICE_RAG_MODE=live와 RAG_BASE_URL을 설정하고 재시작합니다.

## 현재 테스트 화면: 원문 → 문맥 교정 → 확인 → 답변

화면은 POST /voice-transcribe로 녹음하여 STT 원문과 교정 제안을 받은 뒤,
사용자가 확인/수정하고 '이 질문으로 답변 받기'를 누르면
POST /voice-query-text로 확정 문장을 보내 RAG/TTS를 실행합니다.
기존 POST /voice-query는 직접 연동용 API로 유지하며 교정/확인 단계가 없습니다.

키는 voice-ai_code/.env에 OPENAI_API_KEY=발급받은키 형식으로 입력합니다.
기존 값이 있으면 같은 항목을 추가하지 말고 값을 교체하세요.
app/.env에 같은 항목이 있으면 그 값이 우선하므로 한 곳에서 관리하세요.
실제 키를 .env.voice.example이나 프론트 HTML에 넣지 않습니다.
VOICE_CORRECTION_ENABLED=true, VOICE_CORRECTION_MODEL=gpt-4o-mini가 기본값입니다.
키 변경 후 서버를 재시작합니다. 키는 문맥 교정과 기존 TTS에서 함께 사용합니다.

문맥 교정은 인식된 텍스트만 OpenAI에 전달하며 음성 원본은 전송하지 않습니다.
전화번호/주민번호 패턴을 먼저 마스킹하지만 이름·회사명 등은 남을 수 있습니다.
기존 RAG 모드가 mock이어도 문맥 교정과 TTS는 실제 API 호출이며 비용이 발생합니다.
교정은 녹음 1회당 1회 호출하고 자동 재시도는 하지 않습니다.
수동 수정이나 질문 확인 버튼은 교정 API를 다시 호출하지 않습니다.
교정 실패/불확실 결과는 원문으로 되돌리고 안내합니다.
이름·숫자·부정문을 임의로 바꾸지 않도록 지시하고 숫자 변경은 추가 검사하지만,
의미 보존을 보장하지 않으므로 사용자가 확인해야 합니다.

테스트: '육아휴직 신청 서류는 무엇인가요?'를 녹음하고 원문/제안을 비교합니다.
원문이 이미 정확하면 동일한 제안이 정상입니다.
수정란을 직접 고친 뒤 버튼을 누르면 결과의 '확정한 질문'에 그 문장이 나타나야 합니다.
확인 전에는 RAG와 TTS를 호출하지 않습니다.
mock 모드에서는 확인 후 개발용 답변, live에서는 실제 RAG 답변이 표시됩니다.

아래 기존 단일 API 테스트 설명과 함께 참고하세요.

## 구현 범위

POST /voice-query (끝에 슬래시 없음): JWT 검증 → 오디오 업로드 → FFmpeg WAV 변환
→ 로컬 Whisper STT → 전화번호/주민번호 마스킹 → RAG → TTS → JSON.

원본과 WAV는 비공개 임시 폴더에서 처리하고 STT 직후 삭제합니다.
출력 MP3는 .voice_output에 저장합니다. /voice-audio에서 같은 로그인 사용자만
15분 동안 재생할 수 있습니다. 만료 파일은 다음 음성 생성/접근 시 정리합니다.
개발 중 서버가 종료돼도 파일이 남을 수 있으므로 운영에서는 주기 정리가 필요합니다.
이번 API는 질문 원문을 로그에 기록하지 않습니다.
마스킹은 전화번호/주민번호 패턴만 처리하며 모든 개인정보 탐지를 보장하지 않습니다.
기존 교수님 예제는 별도 경로로 유지되어 이 보호 동작의 적용 대상이 아닙니다.

## 준비

저장소 루트가 아니라 voice-ai_code 디렉터리에서 실행합니다.

```bash
cd /Users/leehyojun/Desktop/Skala-mini-project/voice-ai_code
source .venv/bin/activate
python -m pip install -r requirements.txt
ffmpeg -version
```

.env 또는 app/.env에 OPENAI_API_KEY와 Java와 동일한 JWT_SECRET이 필요합니다.
실제 키를 .env.voice.example에 넣거나 Git에 커밋하지 마세요.
환경변수 > app/.env > 루트 .env 순으로 설정이 우선합니다.

기존 8008 서버가 실행 중이면 해당 터미널에서 Ctrl+C로 종료한 뒤 시작하세요.
STT는 로컬 모델을 사용하고, TTS는 설정된 OpenAI API를 호출해 비용이 발생합니다.
처음에는 Whisper 모델 다운로드가 필요할 수 있습니다.

## 1단계: RAG 없이 개인 파트 테스트

```bash
VOICE_RAG_MODE=mock python -m uvicorn app.main:app --host 127.0.0.1 --port 8008
```

1. Java/DB 서버를 실행하고 http://localhost:8080/login 에서 로그인합니다.
2. 같은 브라우저에서 http://localhost:8008/voice-query.html 을 엽니다.
3. 상단에 '개발용 모드' 표시가 나오는지 확인합니다.
4. 녹음 시작 → 마이크 허용 → '음성 연결을 테스트합니다' → 녹음 종료.
5. 인식한 질문과 개발용 고정 답변이 보입니다. 재생 버튼으로 음성을 듣습니다.
6. API 응답에서 mode=mock, sources=[], needs_review=true, handoff=true 확인.
   검토/연결 값도 테스트용 고정값이며 실제 질문 분류 결과가 아닙니다.
7. 다른 질문에도 같은 답변이 나오는 것이 정상입니다. 실제 규정 검색 성공을 뜻하지 않습니다.

이 모드에서도 JWT 검증, FFmpeg, STT, TTS는 실제로 동작합니다.
전화번호/주민번호 패턴은 인식 결과에서 마스킹됩니다.

## 2단계: 팀 RAG 통합

최수빈·신현중 담당자와 아래 계약을 확인합니다.

```json
{"prompt":"질문 텍스트","source":"pdf","top_k":4}
```

헤더는 Authorization: Bearer <로그인 JWT>.
반환은 다음 4개 필수 필드입니다.

```json
{
  "answer":"답변",
  "sources":[{"doc":"문서명","article":"조항","page":1}],
  "needs_review":false,
  "handoff":false
}
```

서버를 종료하고 다시 실행합니다.

```bash
VOICE_RAG_MODE=live RAG_BASE_URL=http://localhost:8001 python -m uvicorn app.main:app --host 127.0.0.1 --port 8008
```

화면에 '실제 RAG 연동 모드'가 표시되어야 합니다.
환경변수 변경은 서버 재시작 후 반영됩니다. 기본값도 live입니다.
RAG가 꺼졌거나 이전 {prompt,response} 스키마면 503입니다.
실제 모드에서 실패했다고 개발용 응답으로 자동 전환하지 않습니다.

정상 질문: 팀 평가셋의 질문을 말하고 답변/문서/조항/재생을 확인합니다.
근거 없는 질문: sources=[]와 담당자 안내가 반환되는지 확인합니다.
검토 필요 질문: RAG가 전달한 needs_review/handoff가 화면에 그대로 나타납니다.
법령의 정답과 출처 페이지는 팀의 검증된 평가셋을 기준으로 확인하세요.
본 음성 모듈은 해당 플래그를 자체 추론하거나 검색 품질을 판정하지 않습니다.

## API / 프론트 담당자 인계

- GET /voice-config: 인증 후 mode, max_seconds=60, max_bytes 제공.
- POST /voice-query: multipart/form-data, 필드 audio. WebM/WAV/M4A/MP4/OGG, 10MB/60초.
- 반환: transcript(마스킹됨), answer, sources, needs_review, handoff,
  audio_url, warning, mode, latency_ms.
- Cookie ACCESS_TOKEN 또는 Bearer 지원. Java와 동일한 JWT 서명/issuer/exp 검증.
- Vue가 5174에서 직접 호출하면 credentials: 'include'를 설정.
- audio_url은 음성 서버 기준 상대경로. Vue에서는 음성 서버 주소를 앞에 붙여야 함.
- Bearer만 쓰는 화면은 오디오도 인증 헤더로 fetch하여 Blob URL로 재생.
- TTS만 실패하면 200, audio_url=null, warning과 텍스트 답변 유지.
- 400: 형식, 401: 인증, 413: 크기, 422: 무음/손상/길이, 503: STT/RAG 오류.
- RAG의 'response'만 반환하는 옛 스키마는 지원하지 않음.
- Docker에서는 RAG_BASE_URL=http://rag:8001처럼 실제 compose 서비스명 사용.
  JWT_SECRET/OPENAI_API_KEY/VOICE_RAG_MODE도 명시적으로 컨테이너에 주입해야 함.
  전체 Compose 통합은 배포 담당자와 진행.

## 자동 검증 (유료 API 및 Whisper 호출 없음)

fastapi, httpx, python-jose, python-multipart, ffmpeg가 설치된 Python 사용:

```bash
cd /Users/leehyojun/Desktop/Skala-mini-project/voice-ai_code
python -m unittest discover -s tests -v
```

JWT 정상/만료/쿠키, 형식/크기/빈 파일, 실제 FFmpeg 변환과 임시 파일 삭제,
손상 오디오/길이 제한, mock 파이프라인, 실제 RAG 계약과 JWT 전달,
기존 스키마 거부, TTS 장애 시 텍스트 유지, 다른 사용자 MP3 차단/만료를 검증합니다.

## 수동 실패 테스트

### 한국어 오인식 점검

STT 기본값은 한국어(ko), transcribe, temperature=0입니다.
다국어 자동 감지가 필요하면 WHISPER_LANGUAGE를 빈 문자열로 설정합니다.
이름/구어 표현의 정확도를 보장하지 않으므로 같은 문장을 3회 녹음해 비교합니다.
이번 변경은 특정 오인식 문장을 정답으로 강제 치환하지 않습니다.
마이크 버튼을 누른 뒤 잠깐 기다리고 말한 뒤, 문장이 끝나고 녹음을 종료하세요.
원본 음성을 보관하지 않으므로 같은 녹음으로 비교하려면 파일 업로드를 사용하세요.
실제 개인정보 대신 테스트용 문장으로 녹음하는 것을 권장합니다.

용어 힌트는 선택 사항입니다. 예:

```dotenv
WHISPER_INITIAL_PROMPT=연차, 근태, 경조휴가, 육아휴직
```

기본 힌트는 육아휴직·연차·경조휴가 등 인사·근태 용어입니다.
힌트가 결과를 편향할 수 있으므로 무음 테스트도 함께 수행하세요.
WHISPER_INITIAL_PROMPT를 빈 문자열로 설정하면 힌트를 끌 수 있습니다.
화면의 모델/언어/용어 힌트 표시로 재시작 후 실제 설정을 확인합니다.
녹음 후 원본 재생과 저장 링크를 제공합니다. 서버 원본 보관 기능은 아닙니다.
저장한 동일 파일을 업로드하여 small과 medium의 인식 결과/처리 시간을 비교할 수 있습니다.
small 모델에서 여전히 오류가 많으면 WHISPER_MODEL=medium으로 바꿔 비교할 수 있습니다.
새 모델 다운로드와 CPU 처리 시간 증가가 있으므로 실제 평가 문장으로 속도/정확도를 비교하세요.
환경변수 변경 후 서버를 재시작합니다.

| 상황 | 기대 결과 |
| --- | --- |
| 시크릿 창에서 API/화면 접근 | 401 |
| 빈 녹음 또는 무음 | 422 (환경에 따라 Whisper 인식 결과도 직접 확인) |
| 손상 오디오 / 텍스트 파일 | 422 / 400 |
| 10MB 초과 | 413 |
| 실제 모드에서 RAG 종료 | 503 |
| TTS 키/네트워크 오류 | 답변 유지, 음성 생성 실패 안내 |
| 출력 MP3를 다른 로그인 사용자로 요청 | 404 |
| 새 요청 전후 로그 확인 | 새 API에서 질문 원문을 출력하지 않음 |

첫 시연 완료 후 hj 브랜치에서 변경 파일과 비밀키 미포함을 확인하고 커밋/푸시합니다.
자동 테스트 성공은 실제 마이크, Whisper 인식 품질, 외부 TTS, 팀 RAG 성공을 대신하지 않습니다.
