# 휴가 낼게요 · Vue 프런트엔드

Vue 3 + Vite + JavaScript + Vue Router 기반의 사내 지침 챗봇입니다. API 계약은 [APIS-15_41.md](APIS-15_41.md)를 기준으로 합니다.

## 화면

| 경로 | 화면 | 기능 |
| --- | --- | --- |
| `/` | 사내 지침 챗봇 | 텍스트·음성 질문, 출처·검토 안내, 답변 듣기, 대화 초기화 |
| `/login` | 로그인 | 사원번호·비밀번호 입력, 쿠키 기반 로그인 |
| `/signup` | 회원가입 | 이름·사원번호·비밀번호 입력, 가입 후 로그인 안내 |

대화는 현재 화면의 메모리에만 유지합니다. 대화 목록·검색·이전 대화 복원은 제공하지 않으며, **대화 초기화**, 새로고침 또는 페이지 이동 시 사라집니다. 초기화와 페이지 이동은 요청·녹음·재생을 중단하고 늦은 응답도 버립니다. 서버 측 데이터 보관 정책은 별도입니다.

## 실행·검증

Node.js 22.12 이상을 사용합니다. 저장소 루트에서 다음을 실행하세요.

```bash
cd frontend
npm install
npm run dev
```

접속 주소는 http://localhost:5173 입니다. 포트 사용 중이면 오류로 종료됩니다. 다른 포트는 `npm run dev -- --port 5175`로 지정합니다. 실제 API 사용에는 MariaDB, Java 인증 서버(8080), 음성·답변 서버(8008)가 필요합니다. 서버 실행은 [RUN.md](../RUN.md)를 참고하세요.

```bash
npm test
npm run build
npm run preview
```

빌드 결과는 `dist/`에 생성됩니다. 테스트는 실제 마이크나 모델 API를 호출하지 않고 요청 형식, 응답 처리, 오류, 중복 전송 방지, 취소 및 재생 상태를 검증합니다.

## API 연결

| 기능 | 프런트엔드 요청 | 서버 |
| --- | --- | --- |
| 로그인·가입·인증 확인·로그아웃 | `/api/*` | 8080, 경로 유지 |
| 텍스트 질문 | `POST http://localhost:8008/voice-query-text` | 8008 직접 요청 |
| 음성 인식·질문 확인 | `POST http://localhost:8008/voice-transcribe` | 8008 직접 요청 |
| 확인한 음성 질문의 답변 | `POST http://localhost:8008/voice-query-text` | 8008 직접 요청 |
| 서버 음성 재생 | `http://localhost:8008/voice-audio/*` | 8008 직접 요청 |

위 주소는 개발 환경 기본값입니다. `voice.js`의 `VOICE_API_BASE_URL`로 음성·답변 요청 주소를 통일하며, `VITE_VOICE_API_BASE_URL`로 변경할 수 있습니다. 8008 서버 CORS에는 `http://localhost:5173`과 `http://127.0.0.1:5173`을 허용합니다. 인증 쿠키가 공유되도록 로그인과 메인은 모두 `localhost`로 접속하세요.

모든 API 요청은 `credentials: include`로 서버 쿠키를 사용합니다. 비밀번호와 토큰을 브라우저 저장소에 저장하지 않습니다. 로그인 성공 시 서버의 기존 8008 리다이렉트 주소 대신 Vue 메인(`/`)으로 이동합니다.

### 인증 호환성

명세의 필수 필드 `username`, `password`에 사원번호와 비밀번호를 폼 데이터로 전달합니다. 현재 Java 코드는 `employeeId`를 사용하므로 같은 사원번호를 두 필드로 보내고, 회원가입에는 기존 `name`도 함께 보냅니다. 사원번호는 앞자리 `0`을 보존하는 문자열입니다.

현재 Java 응답의 `user: { name, employeeId }`가 있으면 이름을 표시합니다. 명세처럼 로그인 응답에 사용자 정보가 없으면 `/api/auth/check`로 조회하며, `username`만 있으면 사원번호를 표시합니다. 명세에는 이름 저장·조회 필드가 없으므로 해당 서버에서 실제 이름을 표시하려면 백엔드 확장이 필요합니다.

### 질문·음성 답변

텍스트 질문은 `{"question":"질문"}` JSON으로 전송합니다. 질문은 1~2,000자이며 응답 대기 중 중복 전송을 막습니다. `VoiceAnswer`의 `answer`, `sources`, `needs_review`, `handoff`, `warning`을 표시하며, `mode`가 `demo` 또는 `mock`이면 데모·연결 테스트임을 표시합니다. 서버 실패 시 가짜 답변을 추가하지 않고 입력창에 질문을 복원합니다.

음성 질문은 입력창을 비운 뒤 **음성 질문 → 녹음 종료**로 전송합니다. 최대 60초·10MB의 WebM을 `audio` 파일로 `/voice-transcribe`에 보내고, `raw_transcript`, `corrected_question`, `changed`, `warning`을 질문 확인 화면에 표시합니다. 입력 중인 텍스트와 녹음은 각각 별개의 질문으로 전송합니다.

**답변 전 질문 확인**은 기본 ON입니다. 원문과 교정 질문을 비교하고 질문을 수정하거나 **원문 사용**으로 되돌린 뒤 **이 질문으로 답변 받기**를 눌러야 `/voice-query-text`를 호출합니다. OFF이면 인식·교정 결과를 표시하고 교정 질문으로 자동 요청합니다. 설정은 녹음 시작 시 확정되므로 다음 녹음부터 적용됩니다. `confirmation_required`의 서버 기본값과 별도로 사용자 ON/OFF 선택을 따르는 동작은 기존 `voice-query.html`과 같습니다.

답변 요청 실패 시 확인 화면과 수정한 질문을 유지해 재시도할 수 있습니다. 확인 화면의 **닫기/취소**, 대화 초기화, 페이지 이동은 확인 내용과 진행 중 요청을 정리합니다. 확인 중인 음성 질문은 일반 텍스트 전송과 섞이지 않으며 질문·확인 설정은 브라우저 저장소에 저장하지 않습니다.

음성 질문의 답변은 `audio_url`을 자동 재생합니다. 텍스트 질문의 음성은 **다시 듣기**를 눌러 재생합니다. 상대 음성 주소와 기존 프록시 주소도 같은 음성 API 기본 주소로 변환합니다. 오디오 요소의 `crossOrigin`은 `use-credentials`로 설정해 인증 쿠키를 전달합니다. 오디오가 없으면 브라우저 Web Speech API의 한국어 음성을 사용합니다. 자동 재생 차단·재생 실패·기간 만료 시 오류를 안내하고 텍스트는 유지합니다.

401은 재로그인, 422는 입력 확인을 안내하며 서버의 문자열 `detail`도 표시합니다. 녹음·처리 중 취소할 수 있습니다. WebM 녹음 지원 브라우저와 `localhost` 또는 HTTPS, 마이크 권한이 필요합니다.

### 503 오류와 실제 RAG 연결 시 확인 사항

기존 개발 프록시에서도 브라우저에는 5173 주소가 표시되지만 실제 요청은 8008로 전달됩니다. 503이 발생하면 포트 표시만으로 오배선을 판단하지 말고 응답 JSON의 `detail`을 확인하세요. 직접 호출로 바꿔도 RAG 서비스가 중단되었거나 응답 계약이 맞지 않으면 503이 계속 발생할 수 있습니다.

현재 `voice-ai_code/app/services/voice_pipeline.py`는 8001 RAG 응답에 `answer`, `sources`, `needs_review`, `handoff`를 요구하지만, 명세의 `/rag-query`는 `{prompt, response}` 형식입니다. 실제 `live` 연동은 백엔드에서 이 계약을 맞춰야 합니다. 프런트엔드는 8008의 `VoiceAnswer`를 사용하며 이 불일치가 발생하면 서버 오류를 표시합니다.

### 배포

빌드 환경은 `VITE_VOICE_API_BASE_URL`을 지정하지 않으면 `/voice-api`를 기본값으로 사용합니다. Vite `server.proxy`는 개발 전용이므로 `npm run preview`나 배포 환경에서는 웹 서버가 `/api/*`를 8080으로, `/voice-api/*`는 접두사를 제거해 8008로 전달해야 합니다. 배포 시 음성 API를 직접 호출하려면 `VITE_VOICE_API_BASE_URL`에 서버 주소를 지정하고 해당 프런트엔드 출처의 CORS를 허용해야 합니다. `/login`·`/signup` 직접 접근은 `index.html`로 연결합니다. 인증 쿠키가 전달되도록 같은 출처를 유지하세요.

필요한 프런트엔드 환경변수는 `.env.local`의 `VITE_` 접두사로 지정합니다. 이 값은 브라우저에 노출되므로 API 비밀키를 넣지 않습니다. 개발 환경의 음성 API 주소 예시는 [.env.example](.env.example)에 있습니다. 주소를 변경하면 Vite를 재시작하세요. 프런트엔드 비밀키는 필요하지 않습니다.

## 주요 파일

- `src/services/auth.js`: 인증 API·사용자 상태
- `src/services/voice.js`: 질의 API·응답 검증·공통 API 주소
- `src/composables/useChat.js`: 일회성 대화·요청 대기·취소
- `src/composables/useVoiceInput.js`: 녹음·교정 질문 확인·확인 후 질의·취소·마이크 해제
- `src/composables/useSpeechOutput.js`: 서버 오디오·브라우저 음성 재생
- `src/views/`: 세 페이지, `src/components/`: 공통 인증 레이아웃·브랜드·아이콘
- `src/config/project.js`: 서비스명, `src/router/index.js`: 라우팅
- `tests/`: 인증·질의·녹음·재생 테스트
- `vite.config.js`: 개발 프록시, `@` 경로 별칭

VS Code는 Vue - Official 확장을 권장합니다. 공식 문서: [Vue](https://vuejs.org/guide/quick-start.html), [Vite](https://vite.dev/guide/).
