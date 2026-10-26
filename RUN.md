# 프로젝트 실행 방법

아래에서 **Docker로 전체 실행** 또는 **로컬 실행** 중 하나를 선택합니다. 명령어는 macOS의 zsh/bash 기준이며, 별도 안내가 없으면 저장소 루트에서 시작합니다.

| 프로젝트                  | 역할                    | 포트 | 접속 주소                        |
| ------------------------- | ----------------------- | ---- | -------------------------------- |
| `workplace`             | Java 인증 서버          | 8080 | http://localhost:8080/login      |
| `voice-ai_code`         | 음성 인식·합성·통번역 | 8008 | http://localhost:8008/index.html |
| `rag-code-template_ext` | 외부 웹·PDF RAG API    | 8001 | http://localhost:8001/docs       |
| `frontend`              | Vue 3 프런트엔드        | 5173 | http://localhost:5173            |

## Docker로 전체 실행

Docker Desktop을 실행합니다. 로컬 JDK·Python·Node.js 설치 없이 네 서버와 MariaDB를 함께 실행합니다.

### 1. 환경 설정

각 프로젝트의 기존 `.env`를 그대로 사용합니다. 루트 `.env`를 만들거나 비밀값을 복사할 필요가 없습니다.

| 환경 파일 | 사용하는 서비스 | 필수 설정 |
| --- | --- | --- |
| `workplace/.env` | Java, MariaDB | `DB_PASSWORD`, `JWT_SECRET` |
| `voice-ai_code/.env` | 음성 AI | `OPENAI_API_KEY`, `JWT_SECRET` |
| `rag-code-template_ext/.env` | RAG | `OPENAI_API_KEY` |

파일이 없다면 해당 폴더의 `.env.example`을 복사해 설정합니다. Java와 음성 서버의 `JWT_SECRET`은 같아야 합니다. 기존 음성 설정이 `app/.env`에 있다면 `voice-ai_code/.env`로 통일합니다.

RAG 모델·임베딩 모델은 `rag-code-template_ext/.env`, Whisper 모델·언어는 `voice-ai_code/.env`에서 조정합니다. 임베딩 모델은 기존 FAISS 인덱스를 생성한 모델과 같아야 합니다.

Compose의 `env_file`이 각 환경 파일을 컨테이너 환경변수로 전달합니다. 환경 파일 자체는 이미지에 포함하지 않습니다. 컨테이너 사이의 주소와 음성 서버의 `VOICE_RAG_MODE=live`는 Compose에서 지정합니다. MariaDB는 기존 `DB_PASSWORD`를 이미지가 요구하는 `MARIADB_PASSWORD`로 변환해 사용합니다.

```bash
docker compose config --quiet
```

### 2. 한 번에 실행

기존 로컬 서버는 각 터미널에서 `Ctrl+C`로 종료합니다. 개별 Docker 구성을 사용 중이면 먼저 중지해 포트 충돌을 해소합니다.

```bash
docker compose -f workplace/docker-compose.yml --env-file workplace/.env stop
docker compose -f voice-ai_code/docker-compose.yml --env-file voice-ai_code/.env stop
```

개별 구성을 사용하지 않았다면 위 중지 명령은 생략합니다. 저장소 루트에서 실행합니다.

```bash
docker compose up -d --build
```

Docker Desktop에 **mini-project**라는 그룹과 아래 항목이 표시됩니다. 각 항목의 실제 컨테이너 이름에는 `mini-project-` 접두사와 번호가 붙습니다.

| 항목 | 호스트 포트 | 역할 |
| --- | --- | --- |
| `workplace` | 8080 | Java 인증 서버 |
| `voice-ai` | 8008 | 음성 인식·합성 및 RAG 연결 |
| `rag` | 8001 | 외부 웹·PDF RAG API |
| `frontend` | 5173 | Vue 화면 |
| `mariadb` | 53301 | 인증 DB |

MariaDB의 상태 확인 후 Java가 시작되고, RAG의 `/health` 확인 후 음성 서버가 시작됩니다. Vue는 Vite 개발 서버로 제공됩니다. 첫 빌드와 음성 서버의 최초 Whisper 모델 다운로드에는 시간이 걸릴 수 있습니다. `up -d`가 끝나도 모델을 로드하는 동안 8008은 아직 준비 중일 수 있으므로 로그를 확인합니다.

```bash
docker compose ps
docker compose logs -f
# 특정 서버만 확인
docker compose logs -f voice-ai
```

http://localhost:5173 에서 가입·로그인하고 질문합니다. 기존 음성 HTML 화면을 사용하려면 http://localhost:8080/login 에서 로그인한 뒤 8008로 이동합니다. Vue는 `localhost:5173` 또는 `127.0.0.1:5173` 중 하나를 선택해 가입·로그인·질의까지 같은 주소에서 사용합니다. 기존 8080·8008 HTML 화면은 모두 `localhost`를 사용합니다.

컨테이너 내부 연결은 Java → `mariadb:3306`, Vue 프록시 → `workplace:8080` 및 `voice-ai:8008`, 음성 서버 → `rag:8001`을 사용합니다. 브라우저의 음성 요청은 현재 화면 주소의 `/voice-api` 프록시를 거쳐 8008로 전달되어 로그인 쿠키를 함께 사용합니다. Docker에서는 `VOICE_RAG_MODE=live`로 실제 RAG에 연결합니다.

DB는 `mini-project_mariadb_data`, Whisper 모델은 `mini-project_whisper_cache` 볼륨에 보관됩니다. 기존 `workplace` 개별 Compose DB와 별도의 볼륨이므로 통합 구성에서는 처음에 새로 가입해야 하며 기존 계정이 자동 이전되지는 않습니다. DB 볼륨 생성 후에는 `workplace/.env`의 비밀번호만 바꿔도 DB 사용자 비밀번호가 변경되지 않습니다.

RAG의 `faiss_db`는 저장소 폴더를 마운트하므로 현재 인덱스를 사용하고 PDF 업로드 결과도 해당 폴더에 보관됩니다. 새 코드를 적용할 때는 `docker compose up -d --build`를 다시 실행합니다.

### 3. 종료 및 재시작

```bash
# 전체 종료: 컨테이너와 네트워크를 제거하고 데이터 볼륨은 유지
docker compose down

# 다시 실행
docker compose up -d
```

`docker compose down -v`는 DB와 모델 볼륨까지 삭제하므로 데이터를 초기화하려는 경우에만 사용합니다.

## 로컬 실행

서버마다 별도의 터미널을 사용하며 Python 프로젝트는 각각의 가상환경을 사용합니다. 먼저 루트의 통합 Docker 구성을 `docker compose down`으로 종료해 포트를 확보합니다. 로컬 실행에서는 MariaDB만 Docker로 실행합니다.

실행 순서: **MariaDB → Java 인증 서버 → RAG API → 음성 AI 서버 → Vue**. 로컬용 환경 파일은 각 프로젝트에 따로 설정합니다.

### 1. Java 인증 서버 (`workplace`)

#### 최초 준비

JDK 17 이상과 Docker Desktop이 필요합니다. Docker Desktop을 먼저 실행합니다.

`workplace/.env`에 다음 항목을 설정합니다. 기존 파일이 있으면 필요한 항목만 확인·수정합니다.

```dotenv
DB_PASSWORD=사용할_DB_비밀번호
JWT_SECRET=충분히_긴_임의의_비밀키
```

Java 서버는 실행 위치를 기준으로 `workplace/.env`, 현재 디렉터리의 `.env`, 상위 디렉터리의 `.env` 순서로 설정 파일을 찾습니다. Gradle로 실행할 때 `workplace/.env`를 사용하며, 같은 키의 프로세스 환경변수가 있으면 우선합니다.

#### 실행

```bash
cd workplace
docker compose up -d --wait mariadb
./gradlew :app:run --no-configuration-cache
```

MariaDB는 호스트 포트 `53301`, DB `sql_db`, 사용자 `user`를 사용합니다. 새 DB 볼륨을 처음 생성할 때 `docker/mariadb/init.sql`이 실행되어 `users` 테이블을 생성합니다.

Java 서버를 시작하면 기존 테이블에도 이름을 저장할 `name` 컬럼을 추가합니다. 기존 계정과 DB 볼륨은 유지되며, 기존 `username` 컬럼을 사원번호 저장에 사용합니다. 새 회원가입은 **이름·사원번호·비밀번호**, 로그인은 **사원번호·비밀번호**를 사용합니다.

Gradle 실행 권한 오류가 나면 `chmod +x gradlew`를 한 번 실행합니다.

접속: http://localhost:8080/login

### 2. 음성 AI 서버 (`voice-ai_code`)

#### 최초 준비

Python 3.11과 ffmpeg가 필요합니다.

```bash
cd voice-ai_code
brew install ffmpeg
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip setuptools wheel
python -m pip install -r requirements.txt
```

`voice-ai_code/.env`에 다음 항목을 설정합니다. `.env.example`을 복사해 시작할 수 있습니다. 기존 `app/.env`가 있다면 중복 설정을 제거하고 이 파일로 통일합니다(`app/.env`가 우선 로드됩니다).

```dotenv
OPENAI_API_KEY=발급받은_OpenAI_API_키
JWT_SECRET=workplace와_동일한_JWT_SECRET
VOICE_RAG_MODE=live
RAG_BASE_URL=http://localhost:8001
```

로컬에서는 `JWT_SECRET`이 없으면 `workplace/.env`에서도 읽지만, 명시할 경우 반드시 Java 서버와 같은 값을 사용합니다.

#### 실행

```bash
cd voice-ai_code
source .venv/bin/activate
python -m uvicorn app.main:app --host 127.0.0.1 --port 8008 --reload --env-file .env
```

`--env-file`은 서비스 모듈을 불러오기 전에 API 키를 로드하기 위해 지정합니다.

먼저 http://localhost:8080/login 에서 로그인합니다. 로그인 성공 시 http://localhost:8008/index.html 로 이동합니다. 로그인 없이 8008의 HTML 또는 음성 API에 접근하면 401을 반환합니다. 두 서버 모두 `localhost`로 접속해 인증 쿠키가 공유되도록 합니다.

음성 페이지:

- 음성 인식: http://localhost:8008/stt.html
- 음성 합성: http://localhost:8008/tts.html
- 음성 통번역: http://localhost:8008/stt-tts.html

### 3. 외부 웹·PDF RAG API (`rag-code-template_ext`)

RAG 모듈은 `rag-code-template_ext/rag-service/`에 있다. 기존 uvicorn 진입점에서 새 세션 API를 실행한다. [RAG 모듈 안내](rag-code-template_ext/rag-service/README.md)와 [API·업로드·세션 계약](rag-docs/HR_RAG_API_USAGE.md)을 참고한다.

#### 최초 준비

```bash
cd rag-code-template_ext
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip setuptools wheel
python -m pip install -r rag-service/requirements-rag-workflow.txt
```

`rag-code-template_ext/.env`에 다음 항목을 설정합니다.

```dotenv
OPENAI_API_KEY=발급받은_OpenAI_API_키
RAG_MODEL=gpt-4o
OPENAI_EMBEDDING_MODEL=text-embedding-ada-002
```

PDF 기반 세션 RAG에는 네이버 키나 관계형 DB가 필요하지 않습니다. `.env.example`에서 선택 설정을 확인할 수 있습니다.

#### 실행

```bash
cd rag-code-template_ext
source .venv/bin/activate
python -m uvicorn rag_external-web_pdf_closed_llm:app --host 127.0.0.1 --port 8001 --reload
```

API 문서: http://localhost:8001/docs

PDF 업로드·질의 콘솔: http://localhost:8001/console

현재 저장소의 인사규정 인덱스를 사용하거나 PDF를 등록한 뒤 질문합니다. 재업로드는 같은 파일명의 문서만 교체하며 다른 문서는 유지합니다. 문서가 바뀌면 새 대화가 필요합니다. 현재 콘솔은 새 대화와 업로드 후 초기화를 지원합니다.

### 4. Vue 프런트엔드 (`frontend`)

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

메인은 사내 지침 챗봇 화면입니다. 휴가·근태, 출장·경비, 보안·업무에 관한 예시 질문을 제공하며 텍스트와 음성으로 질문할 수 있습니다. 개발 환경에서 텍스트는 `/voice-api/voice-query-text`, 음성은 `/voice-api/voice-query` 프록시를 통해 8008에 연결되어 서버의 답변과 출처를 표시합니다. 실제 지침 답변은 음성 서버의 RAG 연결이 준비되어야 합니다. 대화 목록·검색·저장 기능 없이 현재 대화만 표시하며, 상단 **대화 초기화**, 페이지 이동 또는 새로고침 시 초기화됩니다.

음성 질문은 위 2번의 음성 서버(8008)도 실행해야 합니다. Vue에서 로그인한 뒤 입력창을 비우고 **음성 질문 → 녹음 종료**를 누르면 `/voice-api/voice-query`로 녹음을 전송하며 개발 서버가 8008로 전달합니다. 서버가 반환한 인식 문장과 지침 답변을 표시하고 `audio_url` 음성을 자동 재생합니다. 음성이 없으면 브라우저 한국어 음성을 사용합니다. 답변 아래 **다시 듣기 / 중지**를 사용할 수 있습니다. 질문은 2,000자 이내이며, API 호환성과 RAG 응답 계약에 대한 주의사항은 [프런트엔드 README](frontend/README.md)를 참고하세요.

마이크 권한과 WebM 녹음을 지원하는 브라우저가 필요하며, 녹음은 최대 60초입니다. 녹음·변환 중 취소할 수 있고, **대화 초기화**를 누르거나 페이지를 떠나면 녹음과 재생을 중지합니다. 자동 재생이 차단되면 **다시 듣기**를 누릅니다. 기존 음성 HTML 화면은 8080에서 로그인한 뒤 8008에서 사용할 수 있습니다.

프로덕션 빌드: `npm run build`. 자세한 설정은 [frontend/README.md](frontend/README.md)를 참고하세요.

### 5. 로컬 종료

터미널에서 실행 중인 Gradle, uvicorn 서버는 각각 `Ctrl+C`로 종료합니다.
Vue 개발 서버도 실행한 터미널에서 `Ctrl+C`로 종료합니다.

Docker MariaDB 종료:

```bash
cd workplace
docker compose stop mariadb
```

포트 사용 확인:

```bash
lsof -iTCP:8080 -iTCP:8008 -iTCP:8001 -iTCP:5173 -sTCP:LISTEN
```
