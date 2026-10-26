# 프로젝트 실행 방법

macOS의 zsh/bash 기준입니다. 서버마다 별도의 터미널을 사용하고, 각 명령어 블록은 저장소 루트(`/Users/u085/Desktop/share`)에서 시작합니다. Python 프로젝트는 각각의 가상환경을 사용합니다.

| 프로젝트                  | 역할                    | 포트 | 접속 주소                             |
| ------------------------- | ----------------------- | ---- | ------------------------------------- |
| `workplace`             | Java 인증 서버          | 8080 | http://localhost:8080/login           |
| `voice-ai_code`         | 음성 인식·합성·통번역 | 8008 | http://localhost:8008/index.html      |
| `rag-code-template_ext` | 외부 웹·PDF RAG API    | 8001 | http://localhost:8001/docs            |
| 루트 HTML                 | RAG 선택·질의 화면     | 5174 | http://localhost:5174/intro_main.html |
| `frontend`              | Vue 3 프런트엔드       | 5173 | http://localhost:5173                |

실행 순서: **MariaDB → Java 인증 서버 → 음성 AI 서버**. 이후 8080에서 회원가입·로그인하면 8008로 이동합니다. 외부 RAG API와 HTML 화면 서버는 별도로 실행할 수 있습니다.

## 1. Java 인증 서버 (`workplace`)

### 최초 준비

JDK 17 이상과 Docker Desktop이 필요합니다. Docker Desktop을 먼저 실행합니다.

`workplace/.env`에 다음 항목을 설정합니다. 기존 파일이 있으면 필요한 항목만 확인·수정합니다.

```dotenv
DB_PASSWORD=사용할_DB_비밀번호
JWT_SECRET=충분히_긴_임의의_비밀키
```

Java 서버는 실행 위치를 기준으로 `workplace/.env`, 현재 디렉터리의 `.env`, 상위 디렉터리의 `.env` 순서로 설정 파일을 찾습니다. Gradle로 실행할 때 `workplace/.env`를 사용하며, 같은 키의 프로세스 환경변수가 있으면 우선합니다.

### 실행

```bash
cd /Users/u085/Desktop/share/workplace
docker compose up -d --wait mariadb
./gradlew :app:run --no-configuration-cache
```

MariaDB는 호스트 포트 `53301`, DB `sql_db`, 사용자 `user`를 사용합니다. 새 DB 볼륨을 처음 생성할 때 `docker/mariadb/init.sql`이 실행되어 `users` 테이블을 생성합니다.

Java 서버를 시작하면 기존 테이블에도 이름을 저장할 `name` 컬럼을 추가합니다. 기존 계정과 DB 볼륨은 유지되며, 기존 `username` 컬럼을 사원번호 저장에 사용합니다. 새 회원가입은 **이름·사원번호·비밀번호**, 로그인은 **사원번호·비밀번호**를 사용합니다.

Gradle 실행 권한 오류가 나면 `chmod +x gradlew`를 한 번 실행합니다.

접속: http://localhost:8080/login

## 2. 음성 AI 서버 (`voice-ai_code`)

### 최초 준비

Python 3.11과 ffmpeg가 필요합니다.

```bash
cd /Users/u085/Desktop/share/voice-ai_code
brew install ffmpeg
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip setuptools wheel
python -m pip install -r requirements.txt
```

`voice-ai_code/app/.env`에 다음 항목을 설정합니다.

```dotenv
OPENAI_API_KEY=발급받은_OpenAI_API_키
JWT_SECRET=workplace와_동일한_JWT_SECRET
```

로컬에서는 `JWT_SECRET`이 없으면 `workplace/.env`에서도 읽지만, 명시할 경우 반드시 Java 서버와 같은 값을 사용합니다.

### 실행

```bash
cd /Users/u085/Desktop/share/voice-ai_code
source .venv/bin/activate
python -m uvicorn app.main:app --host 127.0.0.1 --port 8008 --reload --env-file .env
```

`--env-file`은 서비스 모듈을 불러오기 전에 API 키를 로드하기 위해 지정합니다.

먼저 http://localhost:8080/login 에서 로그인합니다. 로그인 성공 시 http://localhost:8008/index.html 로 이동합니다. 로그인 없이 8008의 HTML 또는 음성 API에 접근하면 401을 반환합니다. 두 서버 모두 `localhost`로 접속해 인증 쿠키가 공유되도록 합니다.

음성 페이지:

- 음성 인식: http://localhost:8008/stt.html
- 음성 합성: http://localhost:8008/tts.html
- 음성 통번역: http://localhost:8008/stt-tts.html

### Docker로 실행하는 경우 (로컬 실행 대신 선택)

```bash
cd /Users/u085/Desktop/share/voice-ai_code
docker compose --env-file app/.env up -d --build
```

컨테이너는 로컬의 `workplace/.env`를 읽을 수 없으므로 `app/.env`에 `JWT_SECRET`을 반드시 설정합니다. 로컬 uvicorn과 Docker를 같은 8008 포트에서 동시에 실행하지 않습니다.

## 3. 외부 웹·PDF RAG API (`rag-code-template_ext`)

### 최초 준비

```bash
cd /Users/u085/Desktop/share/rag-code-template_ext
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip setuptools wheel
python -m pip install -r requirements-e.txt
```

`rag-code-template_ext/.env`에 다음 항목을 설정합니다.

```dotenv
OPENAI_API_KEY=발급받은_OpenAI_API_키
NAVER_CLIENT_ID=발급받은_네이버_클라이언트_ID
NAVER_CLIENT_SECRET=발급받은_네이버_클라이언트_시크릿
```

네이버 인증 정보는 웹 검색 기능에서 사용합니다. DB 연결 설정이 필요하면 같은 파일에 `ASYNC_DB_URL`을 추가합니다. 기본값은 `mysql+aiomysql://root:password@127.0.0.1:53301/sql_db?charset=utf8mb4`이며, 위 Docker DB의 사용자·비밀번호와 다르므로 DB를 사용할 때 실제 연결 정보로 바꿉니다.

### 실행

```bash
cd /Users/u085/Desktop/share/rag-code-template_ext
source .venv/bin/activate
python -m uvicorn rag_external-web_pdf_closed_llm:app --host 127.0.0.1 --port 8001 --reload
```

API 문서: http://localhost:8001/docs

처음에는 벡터 저장소가 없을 수 있습니다. 화면에서 웹 검색 또는 PDF 업로드로 자료를 등록한 뒤 질문합니다.

## 4. HTML 화면 서버 (저장소 루트)

```bash
cd /Users/u085/Desktop/share
python3 -m http.server 5174 --bind 127.0.0.1
```

- 시작 화면: http://localhost:5174/intro_main.html
- 외부 RAG 화면: http://localhost:5174/external_index.html
- 프로젝트 내 외부 RAG 화면: http://localhost:5174/rag-code-template_ext/external_index.html
- 내부 RAG 화면: http://localhost:5174/internal_index.html

외부 RAG 화면의 API 주소는 `http://localhost:8001`로 지정합니다. 내부 RAG 화면의 기본 API 주소는 `http://localhost:8002`지만, 현재 저장소에는 해당 백엔드 소스가 없어 실행 명령어를 제공할 수 없습니다. 별도의 내부 RAG 서버가 필요합니다.

## 5. Vue 프런트엔드 (`frontend`)

저장소 루트에서 실행합니다. Node.js 22.12 이상이 필요합니다.

```bash
cd frontend
npm install
npm run dev
```

접속: http://localhost:5173

Vue 3 + Vite + Vue Router로 다음 세 화면을 제공합니다.

- 메인 채팅: http://localhost:5173/
- 로그인: http://localhost:5173/login
- 회원가입: http://localhost:5173/signup

가입·로그인·로그아웃 및 세션 확인은 개발 서버의 `/api` 프록시를 통해 Java 인증 서버(8080)에 연결됩니다. 실제 인증은 위 1번의 MariaDB와 Java 서버를 먼저 실행해야 합니다. 로그인 성공 후 Vue 메인 화면으로 이동합니다.

프로젝트명은 **휴가 낼게요**입니다. 로그인 후 헤더와 프로필에 가입한 이름으로 `홍길동님.`을 표시하며, 새로고침 후에도 인증 확인 응답으로 이름을 복원합니다.

메인은 사내 지침 챗봇 화면입니다. 휴가·근태, 출장·경비, 보안·업무에 관한 예시 질문을 제공하며 텍스트와 음성으로 질문할 수 있습니다. 개발 환경에서 텍스트는 `http://localhost:8008/voice-query-text`, 음성 인식·교정은 `http://localhost:8008/voice-transcribe`에 직접 연결되어 서버의 답변과 출처를 표시합니다. 실제 지침 답변은 음성 서버의 RAG 연결이 준비되어야 합니다. 대화 목록·검색·저장 기능 없이 현재 대화만 표시하며, 상단 **대화 초기화**, 페이지 이동 또는 새로고침 시 초기화됩니다.

음성 질문은 위 2번의 음성 서버(8008)도 실행해야 합니다. Vue에서 로그인한 뒤 입력창을 비우고 **음성 질문 → 녹음 종료**를 누르면 `http://localhost:8008/voice-transcribe`로 녹음을 직접 전송합니다. **답변 전 질문 확인**이 기본 ON이며, 원문·교정 질문을 확인하거나 수정하고 **이 질문으로 답변 받기**를 누르면 `/voice-query-text`에 확인한 질문을 보냅니다. OFF에서는 교정된 질문을 자동 전송합니다. 서버가 반환한 지침 답변을 표시하고 `audio_url` 음성을 자동 재생합니다. 음성이 없으면 브라우저 한국어 음성을 사용합니다. 답변 아래 **다시 듣기 / 중지**를 사용할 수 있습니다. 질문은 2,000자 이내이며, API 호환성과 RAG 응답 계약에 대한 주의사항은 [프런트엔드 README](frontend/README.md)를 참고하세요.

마이크 권한과 WebM 녹음을 지원하는 브라우저가 필요하며, 녹음은 최대 60초입니다. 녹음·변환 중 취소할 수 있고, **대화 초기화**를 누르거나 페이지를 떠나면 녹음과 재생을 중지합니다. 자동 재생이 차단되면 **다시 듣기**를 누릅니다. 기존 HTML 화면은 위 4번 방법으로 실행할 수 있습니다.

프로덕션 빌드: `npm run build`. 자세한 설정은 [frontend/README.md](frontend/README.md)를 참고하세요.

## 6. 종료

터미널에서 실행 중인 Gradle, uvicorn, HTML 서버는 각각 `Ctrl+C`로 종료합니다.
Vue 개발 서버도 실행한 터미널에서 `Ctrl+C`로 종료합니다.

Docker MariaDB 종료:

```bash
cd /Users/u085/Desktop/share/workplace
docker compose stop mariadb
```

Docker로 실행한 음성 AI 서버 종료:

```bash
cd /Users/u085/Desktop/share/voice-ai_code
docker compose --env-file app/.env stop app
```

포트 사용 확인:

```bash
lsof -iTCP:8080 -iTCP:8008 -iTCP:8001 -iTCP:5174 -sTCP:LISTEN
```
