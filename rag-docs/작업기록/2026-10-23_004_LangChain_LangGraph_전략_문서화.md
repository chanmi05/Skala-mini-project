# LangChain·LangGraph RAG 전략 문서화

- 작업일: 2026-10-23 (Asia/Seoul)
- 브랜치: `dev-rag`
- 상태: 문서 작성 완료, 라우터·그래프 구현 전

## 요청과 목적

LangChain 입력 분기와 LangGraph 문서 질의·제한적 재검색을 결합하는 구체적인 개발 전략을 기록한다.

## 수행 내용 및 변경 파일

- `soobin-docs/LANGCHAIN_LANGGRAPH_RAG_STRATEGY.md` 생성.
- 입력 유형·LangChain 구성, 그래프 상태·노드·전이, 공통 응답, 기존 함수 재사용 경계 기록.
- 재검색 기본 1회·설정 최대 2회, 중복 질의·무진전·시간 및 토큰 예산 종료 정책 기록.
- 구현 순서, 상황별 오프라인 테스트·실제 데이터 평가·완료 조건 기록.
- 이 작업 로그 생성.
- 기존 실행 코드·패키지·서버·저장소는 변경하지 않음.

## 검증 결과

- LangChain 모델 및 LangGraph Graph API 공식 문서를 확인해 구조화 출력과 그래프 개념을 검토.
- 로컬 패키지 버전과 RunnableBranch·RunnableLambda·ChatPromptTemplate,
  모델의 with_structured_output, StateGraph 노드·조건 전이·compile 인터페이스 존재 확인.
- 문서의 코드 블록과 로컬 참조 경로 확인.
- 문서 작성 작업이므로 전체 RAG 테스트·실제 외부 모델 호출은 수행하지 않음.

## 남은 작업 및 제약

- 문서의 라우터·그래프·공통 응답은 계획이며 구현된 기능이 아님.
- 실제 데이터 담당자와 입력·메타데이터·저장소 계약 합의 필요.
- 근거 충분성·의도 분류의 정확도와 추가 호출 지연은 구현 후 실제 평가 필요.
- 현재 설치 버전과 최신 문서의 API 차이를 구현 시 확인해야 함.
