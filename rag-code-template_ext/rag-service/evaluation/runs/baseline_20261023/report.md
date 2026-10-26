# 독립 RAG 모듈 평가 결과

## 실행 설정

```json
{
  "started_at_utc": "2026-10-23T07:47:27.581477+00:00",
  "index_path": "/Users/soobin/myfolder/workspace/Skala-mini-project/rag-code-template_ext/faiss_db/pdf",
  "index_sha256": {
    "index.faiss": "58aa11a5714efcc992b1f95927280158e4b8ff8cea2c8a22f69ade418c0cd456",
    "index.pkl": "9f03c58011936e90664b503244c9431c653d92529fe82284a1236bb915e6c4ff"
  },
  "cases_sha256": "aa8fbd3a54bb3cc868010c16c8d14d6b5735193479cc347aebe30f84163998ef",
  "module_sha256": "bcfd412270bf732d70152ede2587512f642ef7025dfb4d8cdaae7da2ae63e946",
  "model": "gpt-4o",
  "embedding_model": "text-embedding-ada-002",
  "embedding_dimensions": 1536,
  "temperature": 0,
  "max_output_tokens": 600,
  "top_k": 5,
  "max_input_tokens": 6000,
  "timeout_seconds": 60,
  "concurrency": 1,
  "case_count": 24,
  "packages": {
    "langchain-core": "1.7.0",
    "langchain-openai": "1.1.7",
    "langchain-community": "0.4.1",
    "openai": "1.109.1",
    "faiss-cpu": "1.15.1"
  },
  "limitations": [
    "Small single-document baseline; not production accuracy.",
    "No independent human gold validation yet; evidence authored from corpus.",
    "LLM time is complete-response latency, not first-token latency.",
    "No model-based automatic correctness judge."
  ],
  "index_unchanged": true,
  "embedding_model_provenance": "Matches existing server default; original index lacks model metadata"
}
```

## 집계

```json
{
  "total": 24,
  "success": 24,
  "errors": 0,
  "answerable_success_count": 20,
  "hit_at_k": 0.65,
  "evidence_group_recall": 0.65,
  "context_group_recall": 0.65,
  "mrr": 0.5266666666666666,
  "median_total_ms": 1780.52,
  "reviewed_count": 24,
  "reviewer_types": [
    "codex_agent"
  ],
  "answer_correct_reviewed_count": 20,
  "answer_correct_rate": 0.7,
  "grounded_reviewed_count": 20,
  "grounded_rate": 0.85,
  "abstained_reviewed_count": 4,
  "abstained_rate": 1.0
}
```

검색 지표는 성공한 답변 가능 질문만 대상으로 한다. 오류 건수는 별도로 확인한다.
근거 그룹 내부 ID는 대체 가능한 근거이며 그룹 간에는 모두 필요한 정보로 정의했다.
Hit@k는 하나 이상 적중, 그룹 재현율은 필요한 정보 그룹의 충족 비율이다.
정답·근거 일치·답변 유보는 자동 판정하지 않고 명시적인 리뷰만 집계한다.

리뷰 작성자가 codex_agent이면 에이전트의 1차 검토이며 독립된 사람의 평가가 아니다.

## 질문별 결과

| ID | 유형 | 상태 | Hit@k | 근거 그룹 재현율 | 전체 ms |
|---|---|---|---|---|---|
| q01 | direct | ok | 1 | 1.0 | 6856.24 |
| q02 | specific | ok | 1 | 1.0 | 2048.79 |
| q03 | specific | ok | 0 | 0.0 | 1573.91 |
| q04 | specific | ok | 1 | 1.0 | 1686.51 |
| q05 | reasoning | ok | 1 | 1.0 | 2633.46 |
| q06 | specific | ok | 1 | 1.0 | 3013.08 |
| q07 | numeric | ok | 1 | 1.0 | 1645.14 |
| q08 | numeric | ok | 0 | 0.0 | 1589.91 |
| q09 | multi_evidence | ok | 0 | 0.0 | 2790.1 |
| q10 | reasoning | ok | 0 | 0.0 | 2287.56 |
| q11 | comparison | ok | 1 | 1.0 | 3093.53 |
| q12 | numeric | ok | 1 | 1.0 | 1614.95 |
| q13 | numeric | ok | 1 | 1.0 | 1730.31 |
| q14 | specific | ok | 1 | 1.0 | 1873.61 |
| q15 | specific | ok | 1 | 1.0 | 2213.88 |
| q16 | specific | ok | 0 | 0.0 | 1618.74 |
| q17 | reasoning | ok | 0 | 0.0 | 1986.03 |
| q18 | numeric | ok | 1 | 1.0 | 1397.79 |
| q19 | specific | ok | 1 | 1.0 | 1349.03 |
| q20 | paraphrase | ok | 0 | 0.0 | 1468.26 |
| q21 | unanswerable | ok | None | None | 1355.63 |
| q22 | unanswerable | ok | None | None | 1626.92 |
| q23 | unanswerable | ok | None | None | 2116.93 |
| q24 | unanswerable | ok | None | None | 1830.73 |

### q01: Transformer가 RNN이나 CNN 대신 사용하는 핵심 구조는 무엇인가요?

기대 요점: 어텐션 기반; 순환 및 합성곱을 사용하지 않음

답변:

Transformer는 RNN이나 CNN 대신 주로 "attention mechanism"을 사용합니다. Transformer는 반복(recurrence)이나 합성곱(convolution)을 사용하지 않고, 전적으로 attention mechanism에 의존하여 입력과 출력 간의 전역적인 의존성을 모델링합니다 [S2]. 이 모델은 multi-headed self-attention을 사용하여 기존의 인코더-디코더 구조에서 흔히 사용되던 반복 레이어를 대체합니다 [S3].

검색 청크: 63cd9b50-e75a-40de-8e94-7d4005d5738f, de19bee0-ceb7-4cb0-ac36-e0405bd226b3, 9a5c83fa-dcec-4d75-b54b-8864323e550c, ffdd8fad-e39c-4718-84b3-57a9e22ec369, f15e8fa5-fd1f-4f12-ac53-38cad25f53e8

컨텍스트 청크: 63cd9b50-e75a-40de-8e94-7d4005d5738f, de19bee0-ceb7-4cb0-ac36-e0405bd226b3, 9a5c83fa-dcec-4d75-b54b-8864323e550c, ffdd8fad-e39c-4718-84b3-57a9e22ec369, f15e8fa5-fd1f-4f12-ac53-38cad25f53e8

리뷰:

```json
{
  "id": "q01",
  "reviewer": "codex_agent",
  "independent_human_review": false,
  "results_sha256": "33ffd1312e5544ad4e408b079f07b1854543f2e8941e1440453b55472d679600",
  "answer_correct": true,
  "grounded": true,
  "abstained": null,
  "notes": "S2/S3에 어텐션 기반 및 순환·합성곱 대체가 명시되어 있고 답변과 일치한다."
}
```

### q02: 기본 Transformer 인코더는 몇 개 층이며, 각 층의 두 하위 계층은 무엇인가요?

기대 요점: 6개 층; 멀티헤드 자기 어텐션; 위치별 피드포워드 네트워크

답변:

기본 Transformer 인코더는 6개의 동일한 층으로 구성되어 있습니다. 각 층은 두 개의 하위 계층을 가지고 있는데, 첫 번째는 멀티헤드 자기-어텐션 메커니즘이고, 두 번째는 위치별 완전 연결 피드포워드 네트워크입니다 [S1].

검색 청크: 09f34811-5a5f-4d85-a326-7702d35577c2, 63cd9b50-e75a-40de-8e94-7d4005d5738f, 9a5c83fa-dcec-4d75-b54b-8864323e550c, 1892177a-12ff-47ab-b651-7432abf81baf, fc7951bf-1f89-4328-a817-5a5ed46fbb7d

컨텍스트 청크: 09f34811-5a5f-4d85-a326-7702d35577c2, 63cd9b50-e75a-40de-8e94-7d4005d5738f, 9a5c83fa-dcec-4d75-b54b-8864323e550c, 1892177a-12ff-47ab-b651-7432abf81baf, fc7951bf-1f89-4328-a817-5a5ed46fbb7d

리뷰:

```json
{
  "id": "q02",
  "reviewer": "codex_agent",
  "independent_human_review": false,
  "results_sha256": "33ffd1312e5544ad4e408b079f07b1854543f2e8941e1440453b55472d679600",
  "answer_correct": true,
  "grounded": true,
  "abstained": null,
  "notes": "S1의 인코더 6층 및 두 하위 계층 설명을 정확히 반영한다."
}
```

### q03: 디코더가 아직 생성하지 않은 미래 토큰을 보지 못하게 하는 방법은 무엇인가요?

기대 요점: 미래 위치 어텐션 마스킹; 자기회귀 성질 유지

답변:

참고 자료에서 디코더가 아직 생성하지 않은 미래 토큰을 보지 못하게 하는 방법에 대한 정보는 확인할 수 없습니다.

검색 청크: 9a5c83fa-dcec-4d75-b54b-8864323e550c, 184dc405-7599-4e7d-8d3d-cd7cf43be955, ee510fa2-28dc-40c4-8655-d42ab8cf40e4, fc7e9d61-207a-4e62-a2e1-74e1103c9ae3, 0d72c856-25d0-444f-8880-88f0af86e6c6

컨텍스트 청크: 9a5c83fa-dcec-4d75-b54b-8864323e550c, 184dc405-7599-4e7d-8d3d-cd7cf43be955, ee510fa2-28dc-40c4-8655-d42ab8cf40e4, fc7e9d61-207a-4e62-a2e1-74e1103c9ae3, 0d72c856-25d0-444f-8880-88f0af86e6c6

리뷰:

```json
{
  "id": "q03",
  "reviewer": "codex_agent",
  "independent_human_review": false,
  "results_sha256": "33ffd1312e5544ad4e408b079f07b1854543f2e8941e1440453b55472d679600",
  "answer_correct": false,
  "grounded": true,
  "abstained": null,
  "notes": "핵심 마스킹 근거(원문 청크 9/14)를 놓쳤다. 전달된 근거에서 답변을 유보한 것은 타당하지만 문서 전체에는 정답이 있어 과제 해결은 실패다."
}
```

### q04: Scaled Dot-Product Attention은 Q와 K의 내적을 어떤 값으로 나눈 뒤 무엇을 적용하나요?

기대 요점: sqrt(dk)로 나눔; softmax로 가중치 계산

답변:

Scaled Dot-Product Attention에서는 Q와 K의 내적을 \(\sqrt{d_k}\)로 나눈 뒤, 소프트맥스 함수를 적용합니다 [S1].

검색 청크: 240bcfa7-22cd-48b6-ae82-4e73b653bfca, 27a4d4d2-9ff3-450f-9951-890194650768, c0bcfe0d-42b8-4a8d-853e-73d18418226c, 8ebb8566-8ea6-4894-8c50-d1f36c35a574, de9c156e-9544-4aa1-bbef-b00c925962b2

컨텍스트 청크: 240bcfa7-22cd-48b6-ae82-4e73b653bfca, 27a4d4d2-9ff3-450f-9951-890194650768, c0bcfe0d-42b8-4a8d-853e-73d18418226c, 8ebb8566-8ea6-4894-8c50-d1f36c35a574, de9c156e-9544-4aa1-bbef-b00c925962b2

리뷰:

```json
{
  "id": "q04",
  "reviewer": "codex_agent",
  "independent_human_review": false,
  "results_sha256": "33ffd1312e5544ad4e408b079f07b1854543f2e8941e1440453b55472d679600",
  "answer_correct": true,
  "grounded": true,
  "abstained": null,
  "notes": "S1의 sqrt(dk) 스케일링과 softmax를 정확히 반영한다."
}
```

### q05: dk가 커질 때 어텐션 내적을 스케일링해야 하는 이유는 무엇인가요?

기대 요점: 내적 크기가 커짐; softmax 기울기가 작아지는 문제 완화

답변:

dk가 커질 때 어텐션 내적을 스케일링해야 하는 이유는, dk의 값이 커지면 내적의 크기가 커져서 소프트맥스 함수가 매우 작은 기울기를 가지는 영역으로 들어갈 수 있기 때문입니다. 이를 방지하기 위해 내적을 \( \frac{1}{\sqrt{dk}} \)로 스케일링하여 소프트맥스 함수가 적절히 작동하도록 합니다. 이렇게 하면 소프트맥스 함수의 출력이 더 균형 잡히고 안정적으로 계산될 수 있습니다 [S3].

검색 청크: 4d2c9886-f8ce-4dff-b7e0-8d1f34596bb8, 240bcfa7-22cd-48b6-ae82-4e73b653bfca, c0bcfe0d-42b8-4a8d-853e-73d18418226c, ee510fa2-28dc-40c4-8655-d42ab8cf40e4, 184dc405-7599-4e7d-8d3d-cd7cf43be955

컨텍스트 청크: 4d2c9886-f8ce-4dff-b7e0-8d1f34596bb8, 240bcfa7-22cd-48b6-ae82-4e73b653bfca, c0bcfe0d-42b8-4a8d-853e-73d18418226c, ee510fa2-28dc-40c4-8655-d42ab8cf40e4, 184dc405-7599-4e7d-8d3d-cd7cf43be955

리뷰:

```json
{
  "id": "q05",
  "reviewer": "codex_agent",
  "independent_human_review": false,
  "results_sha256": "33ffd1312e5544ad4e408b079f07b1854543f2e8941e1440453b55472d679600",
  "answer_correct": true,
  "grounded": true,
  "abstained": null,
  "notes": "S3의 큰 내적·작은 softmax 기울기 문제와 스케일링 이유를 반영한다."
}
```

### q06: Multi-Head Attention이 단일 헤드보다 여러 표현을 다룰 수 있는 이유는 무엇인가요?

기대 요점: 여러 표현 부분공간과 위치에 동시에 주목; 각 헤드 결과를 연결하고 투영

답변:

Multi-Head Attention이 단일 헤드보다 여러 표현을 다룰 수 있는 이유는 각 헤드가 서로 다른 표현 하위 공간(subspace)에서 정보를 병렬로 처리할 수 있기 때문입니다. 각 헤드는 입력 쿼리(Q), 키(K), 값(V)에 대해 독립적인 선형 변환을 수행하고, 이 변환된 값들에 대해 주의(attention) 메커니즘을 적용합니다. 이렇게 생성된 여러 헤드의 출력은 서로 다른 위치에서 다양한 정보를 동시에 처리할 수 있게 해주며, 최종적으로 이 출력들을 연결(concatenate)하여 최종 결과를 얻습니다. 단일 헤드에서는 이러한 병렬 처리가 불가능하여 평균화가 발생할 수 있습니다 [S5].

검색 청크: 184dc405-7599-4e7d-8d3d-cd7cf43be955, 9a5c83fa-dcec-4d75-b54b-8864323e550c, ee510fa2-28dc-40c4-8655-d42ab8cf40e4, de9c156e-9544-4aa1-bbef-b00c925962b2, 27a4d4d2-9ff3-450f-9951-890194650768

컨텍스트 청크: 184dc405-7599-4e7d-8d3d-cd7cf43be955, 9a5c83fa-dcec-4d75-b54b-8864323e550c, ee510fa2-28dc-40c4-8655-d42ab8cf40e4, de9c156e-9544-4aa1-bbef-b00c925962b2, 27a4d4d2-9ff3-450f-9951-890194650768

리뷰:

```json
{
  "id": "q06",
  "reviewer": "codex_agent",
  "independent_human_review": false,
  "results_sha256": "33ffd1312e5544ad4e408b079f07b1854543f2e8941e1440453b55472d679600",
  "answer_correct": true,
  "grounded": false,
  "abstained": null,
  "notes": "여러 부분공간·병렬 헤드·연결이라는 핵심 요점은 맞다. 다만 단일 헤드에서 병렬 처리가 불가능하다는 문구는 원문의 평균화 한계를 과도하게 일반화해 근거 충실성은 실패로 판정한다."
}
```

### q07: 논문의 기본 모델에서 어텐션 헤드 수와 각 헤드의 dk, dv는 얼마인가요?

기대 요점: 8개 헤드; dk=dv=64

답변:

논문의 기본 모델에서 어텐션 헤드 수는 8개이며, 각 헤드의 \( dk \)와 \( dv \)는 각각 64입니다 [S1].

검색 청크: de9c156e-9544-4aa1-bbef-b00c925962b2, 1892177a-12ff-47ab-b651-7432abf81baf, 27a4d4d2-9ff3-450f-9951-890194650768, df4b0821-cb39-4bc8-a052-6ec32c9105b9, e1788ece-962e-4695-8d83-910c9231685a

컨텍스트 청크: de9c156e-9544-4aa1-bbef-b00c925962b2, 1892177a-12ff-47ab-b651-7432abf81baf, 27a4d4d2-9ff3-450f-9951-890194650768, df4b0821-cb39-4bc8-a052-6ec32c9105b9, e1788ece-962e-4695-8d83-910c9231685a

리뷰:

```json
{
  "id": "q07",
  "reviewer": "codex_agent",
  "independent_human_review": false,
  "results_sha256": "33ffd1312e5544ad4e408b079f07b1854543f2e8941e1440453b55472d679600",
  "answer_correct": true,
  "grounded": true,
  "abstained": null,
  "notes": "S1의 h=8, dk=dv=64와 일치한다."
}
```

### q08: 위치별 피드포워드 네트워크의 입력·출력 차원과 내부 차원은 얼마인가요?

기대 요점: 입력·출력 512; 내부 2048

답변:

참고 자료에서 위치별 피드포워드 네트워크의 입력 및 출력 차원은 모델의 출력 차원과 동일하며, 이는 \(d_{model} = 512\)입니다. 내부 차원에 대한 구체적인 정보는 제공된 자료에서 확인할 수 없습니다 [S4].

검색 청크: dc494015-8de8-4ac1-a812-6c251104b9fe, 4d2c9886-f8ce-4dff-b7e0-8d1f34596bb8, 1d56e502-35b2-4a95-83fe-d098f6e157f5, 09f34811-5a5f-4d85-a326-7702d35577c2, 0f9d5a7a-85b5-4671-8d99-f4acb324eb87

컨텍스트 청크: dc494015-8de8-4ac1-a812-6c251104b9fe, 4d2c9886-f8ce-4dff-b7e0-8d1f34596bb8, 1d56e502-35b2-4a95-83fe-d098f6e157f5, 09f34811-5a5f-4d85-a326-7702d35577c2, 0f9d5a7a-85b5-4671-8d99-f4acb324eb87

리뷰:

```json
{
  "id": "q08",
  "reviewer": "codex_agent",
  "independent_human_review": false,
  "results_sha256": "33ffd1312e5544ad4e408b079f07b1854543f2e8941e1440453b55472d679600",
  "answer_correct": false,
  "grounded": true,
  "abstained": null,
  "notes": "512는 S4에서 확인되지만 내부 차원 2048의 핵심 청크 15를 놓쳐 답변이 불완전하다. 없는 정보는 유보했다."
}
```

### q09: 순환 구조가 없는 Transformer는 단어 순서를 어떻게 반영하며, 논문은 어떤 위치 인코딩 함수를 쓰나요?

기대 요점: 인코더·디코더 입력 임베딩에 위치 인코딩을 더함; 사인·코사인 함수

답변:

Transformer 모델은 순환 구조 없이도 단어 순서를 반영하기 위해 위치 인코딩(Position Encoding)을 사용합니다. 위치 인코딩은 입력 시퀀스의 각 단어에 대해 고유한 위치 정보를 추가하여 모델이 단어의 순서를 인식할 수 있도록 합니다. 논문에서는 사인 함수와 코사인 함수를 기반으로 한 위치 인코딩을 사용합니다. 이 함수들은 각 위치에 대해 고유한 주기를 가지며, 모델이 입력 시퀀스의 상대적 또는 절대적 위치 정보를 학습할 수 있도록 돕습니다 [S3].

검색 청크: 9a5c83fa-dcec-4d75-b54b-8864323e550c, de19bee0-ceb7-4cb0-ac36-e0405bd226b3, 63cd9b50-e75a-40de-8e94-7d4005d5738f, 0d72c856-25d0-444f-8880-88f0af86e6c6, ffdd8fad-e39c-4718-84b3-57a9e22ec369

컨텍스트 청크: 9a5c83fa-dcec-4d75-b54b-8864323e550c, de19bee0-ceb7-4cb0-ac36-e0405bd226b3, 63cd9b50-e75a-40de-8e94-7d4005d5738f, 0d72c856-25d0-444f-8880-88f0af86e6c6, ffdd8fad-e39c-4718-84b3-57a9e22ec369

리뷰:

```json
{
  "id": "q09",
  "reviewer": "codex_agent",
  "independent_human_review": false,
  "results_sha256": "33ffd1312e5544ad4e408b079f07b1854543f2e8941e1440453b55472d679600",
  "answer_correct": true,
  "grounded": false,
  "abstained": null,
  "notes": "위치 인코딩·정보 추가·사인/코사인이라는 내용은 원문 정답과 대체로 맞지만, 전달된 5개 청크에는 위치 인코딩 근거가 없다. 인용한 S3도 인코더·디코더 개요여서 인용이 주장을 뒷받침하지 않는다."
}
```

### q10: 학습형 위치 임베딩과 결과가 비슷한데도 논문이 사인파 위치 인코딩을 선택한 이유는 무엇인가요?

기대 요점: 학습에서 본 것보다 긴 시퀀스 길이로 외삽할 가능성

답변:

논문에서는 사인파 위치 인코딩을 선택한 이유로, 모델이 상대적인 위치에 따라 주의를 기울이는 것을 쉽게 학습할 수 있을 것이라는 가설을 제시했습니다. 사인파 위치 인코딩은 각 차원이 사인파에 해당하며, 특정 오프셋에 대해 선형 함수로 표현될 수 있기 때문에 이러한 특성을 가지고 있습니다. 실험 결과 학습형 위치 임베딩과 거의 동일한 결과를 보였지만, 이러한 가설에 따라 사인파 위치 인코딩을 선택했습니다 [S1].

검색 청크: 5f8352e1-f628-4184-a243-aadd75dc4e87, 8d0be463-9c1d-4d44-afc4-acd13a0ec7e0, 184dc405-7599-4e7d-8d3d-cd7cf43be955, 03637804-fe3e-4ec9-b9bf-438d68d8e1ca, 4d2c9886-f8ce-4dff-b7e0-8d1f34596bb8

컨텍스트 청크: 5f8352e1-f628-4184-a243-aadd75dc4e87, 8d0be463-9c1d-4d44-afc4-acd13a0ec7e0, 184dc405-7599-4e7d-8d3d-cd7cf43be955, 03637804-fe3e-4ec9-b9bf-438d68d8e1ca, 4d2c9886-f8ce-4dff-b7e0-8d1f34596bb8

리뷰:

```json
{
  "id": "q10",
  "reviewer": "codex_agent",
  "independent_human_review": false,
  "results_sha256": "33ffd1312e5544ad4e408b079f07b1854543f2e8941e1440453b55472d679600",
  "answer_correct": false,
  "grounded": true,
  "abstained": null,
  "notes": "S1의 상대 위치 학습 가설을 설명했지만 질문이 요구한 학습보다 긴 길이로의 외삽 이유(청크 18)를 놓쳤다. 전달된 자료에는 상대 위치 가설이 있어 그 설명 자체는 근거가 있다."
}
```

### q11: 자기 어텐션과 순환 계층은 순차 연산 횟수 및 최대 경로 길이에서 어떻게 다른가요?

기대 요점: 자기 어텐션 O(1) 순차 연산 및 경로; 순환 계층 O(n) 순차 연산 및 경로

답변:

자기 어텐션(self-attention) 계층과 순환(recurrent) 계층은 순차 연산 횟수 및 최대 경로 길이에서 다음과 같은 차이가 있습니다:

1. **순차 연산 횟수**:
   - 자기 어텐션 계층은 O(1)의 순차 연산을 필요로 합니다. 이는 모든 위치를 일정한 수의 순차적으로 실행되는 연산으로 연결하기 때문입니다.
   - 반면, 순환 계층은 O(n)의 순차 연산을 필요로 합니다. 이는 입력 시퀀스의 길이 n에 비례하여 연산이 필요하기 때문입니다 [S1][S3].

2. **최대 경로 길이**:
   - 자기 어텐션 계층의 최대 경로 길이는 O(1)입니다. 이는 입력과 출력 시퀀스의 모든 위치 쌍 사이의 경로가 일정한 길이임을 의미합니다.
   - 순환 계층의 최대 경로 길이는 O(n)입니다. 이는 시퀀스의 길이에 따라 경로 길이가 증가함을 의미합니다 [S3].

검색 청크: dc494015-8de8-4ac1-a812-6c251104b9fe, 4d2c9886-f8ce-4dff-b7e0-8d1f34596bb8, 129e9de8-075b-43be-853c-b61a3f732226, 0f9d5a7a-85b5-4671-8d99-f4acb324eb87, de19bee0-ceb7-4cb0-ac36-e0405bd226b3

컨텍스트 청크: dc494015-8de8-4ac1-a812-6c251104b9fe, 4d2c9886-f8ce-4dff-b7e0-8d1f34596bb8, 129e9de8-075b-43be-853c-b61a3f732226, 0f9d5a7a-85b5-4671-8d99-f4acb324eb87, de19bee0-ceb7-4cb0-ac36-e0405bd226b3

리뷰:

```json
{
  "id": "q11",
  "reviewer": "codex_agent",
  "independent_human_review": false,
  "results_sha256": "33ffd1312e5544ad4e408b079f07b1854543f2e8941e1440453b55472d679600",
  "answer_correct": true,
  "grounded": true,
  "abstained": null,
  "notes": "S1/S3의 자기 어텐션 O(1), 순환 O(n) 순차 연산·경로 설명과 일치한다."
}
```

### q12: 학습에 사용한 WMT 2014 영어-독일어와 영어-프랑스어 데이터 규모는 각각 얼마인가요?

기대 요점: 영어-독일어 약 450만 문장 쌍; 영어-프랑스어 약 3600만 문장

답변:

WMT 2014 영어-독일어 데이터셋은 약 450만 개의 문장 쌍으로 구성되어 있으며, 영어-프랑스어 데이터셋은 3600만 개의 문장으로 구성되어 있습니다 [S1].

검색 청크: e1788ece-962e-4695-8d83-910c9231685a, f5f964e5-259d-4c14-bb12-d84972c1e85b, 1e1836e4-7129-4ce0-969d-9a7650c726b2, 0d72c856-25d0-444f-8880-88f0af86e6c6, abfff9f5-cc76-4d3d-ae71-e79dc473d410

컨텍스트 청크: e1788ece-962e-4695-8d83-910c9231685a, f5f964e5-259d-4c14-bb12-d84972c1e85b, 1e1836e4-7129-4ce0-969d-9a7650c726b2, 0d72c856-25d0-444f-8880-88f0af86e6c6, abfff9f5-cc76-4d3d-ae71-e79dc473d410

리뷰:

```json
{
  "id": "q12",
  "reviewer": "codex_agent",
  "independent_human_review": false,
  "results_sha256": "33ffd1312e5544ad4e408b079f07b1854543f2e8941e1440453b55472d679600",
  "answer_correct": true,
  "grounded": true,
  "abstained": null,
  "notes": "S1의 데이터 규모 약 4.5M/36M과 일치한다."
}
```

### q13: 기본 모델은 어떤 GPU 몇 개로 몇 스텝, 얼마 동안 학습했나요?

기대 요점: NVIDIA P100 8개; 100000 스텝; 12시간

답변:

기본 모델은 8개의 NVIDIA P100 GPU를 사용하여 총 100,000 스텝, 약 12시간 동안 학습되었습니다 [S2].

검색 청크: fc7951bf-1f89-4328-a817-5a5ed46fbb7d, e1788ece-962e-4695-8d83-910c9231685a, abfff9f5-cc76-4d3d-ae71-e79dc473d410, 89382f82-33c0-4bda-824c-20b97790906f, 1892177a-12ff-47ab-b651-7432abf81baf

컨텍스트 청크: fc7951bf-1f89-4328-a817-5a5ed46fbb7d, e1788ece-962e-4695-8d83-910c9231685a, abfff9f5-cc76-4d3d-ae71-e79dc473d410, 89382f82-33c0-4bda-824c-20b97790906f, 1892177a-12ff-47ab-b651-7432abf81baf

리뷰:

```json
{
  "id": "q13",
  "reviewer": "codex_agent",
  "independent_human_review": false,
  "results_sha256": "33ffd1312e5544ad4e408b079f07b1854543f2e8941e1440453b55472d679600",
  "answer_correct": true,
  "grounded": true,
  "abstained": null,
  "notes": "S2의 P100 8개·100000 스텝·12시간과 일치한다."
}
```

### q14: 논문에서 사용한 옵티마이저와 beta1, beta2, epsilon 값은 무엇인가요?

기대 요점: Adam; 0.9; 0.98; 10^-9

답변:

논문에서 사용한 옵티마이저는 Adam 옵티마이저이며, beta1 값은 0.9, beta2 값은 0.98, epsilon 값은 \(10^{-9}\)입니다 [S1].

검색 청크: abfff9f5-cc76-4d3d-ae71-e79dc473d410, df4b0821-cb39-4bc8-a052-6ec32c9105b9, 89382f82-33c0-4bda-824c-20b97790906f, 1892177a-12ff-47ab-b651-7432abf81baf, f5f964e5-259d-4c14-bb12-d84972c1e85b

컨텍스트 청크: abfff9f5-cc76-4d3d-ae71-e79dc473d410, df4b0821-cb39-4bc8-a052-6ec32c9105b9, 89382f82-33c0-4bda-824c-20b97790906f, 1892177a-12ff-47ab-b651-7432abf81baf, f5f964e5-259d-4c14-bb12-d84972c1e85b

리뷰:

```json
{
  "id": "q14",
  "reviewer": "codex_agent",
  "independent_human_review": false,
  "results_sha256": "33ffd1312e5544ad4e408b079f07b1854543f2e8941e1440453b55472d679600",
  "answer_correct": true,
  "grounded": true,
  "abstained": null,
  "notes": "S1의 Adam 및 하이퍼파라미터와 일치한다."
}
```

### q15: 학습률 warmup은 몇 스텝이며, warmup 이후 학습률은 어떻게 변하나요?

기대 요점: 4000 스텝; 이후 스텝 수의 역제곱근에 비례해 감소

답변:

학습률 warmup은 4000 스텝입니다. warmup 이후에는 학습률이 스텝 수의 역제곱근에 비례하여 감소합니다 [S1].

검색 청크: abfff9f5-cc76-4d3d-ae71-e79dc473d410, e1788ece-962e-4695-8d83-910c9231685a, 4d2c9886-f8ce-4dff-b7e0-8d1f34596bb8, f5f964e5-259d-4c14-bb12-d84972c1e85b, fc7951bf-1f89-4328-a817-5a5ed46fbb7d

컨텍스트 청크: abfff9f5-cc76-4d3d-ae71-e79dc473d410, e1788ece-962e-4695-8d83-910c9231685a, 4d2c9886-f8ce-4dff-b7e0-8d1f34596bb8, f5f964e5-259d-4c14-bb12-d84972c1e85b, fc7951bf-1f89-4328-a817-5a5ed46fbb7d

리뷰:

```json
{
  "id": "q15",
  "reviewer": "codex_agent",
  "independent_human_review": false,
  "results_sha256": "33ffd1312e5544ad4e408b079f07b1854543f2e8941e1440453b55472d679600",
  "answer_correct": true,
  "grounded": true,
  "abstained": null,
  "notes": "S1의 warmup 4000과 이후 역제곱근 감소와 일치한다."
}
```

### q16: 기본 모델의 residual dropout 비율은 얼마이며 어디에 적용하나요?

기대 요점: 0.1; 하위 계층 출력과 임베딩·위치 인코딩 합에 적용

답변:

기본 모델의 residual dropout 비율은 0.1이며, 이는 attention과 residual에 적용됩니다 [S3].

검색 청크: 8d0be463-9c1d-4d44-afc4-acd13a0ec7e0, 1892177a-12ff-47ab-b651-7432abf81baf, 1e1836e4-7129-4ce0-969d-9a7650c726b2, abfff9f5-cc76-4d3d-ae71-e79dc473d410, 89382f82-33c0-4bda-824c-20b97790906f

컨텍스트 청크: 8d0be463-9c1d-4d44-afc4-acd13a0ec7e0, 1892177a-12ff-47ab-b651-7432abf81baf, 1e1836e4-7129-4ce0-969d-9a7650c726b2, abfff9f5-cc76-4d3d-ae71-e79dc473d410, 89382f82-33c0-4bda-824c-20b97790906f

리뷰:

```json
{
  "id": "q16",
  "reviewer": "codex_agent",
  "independent_human_review": false,
  "results_sha256": "33ffd1312e5544ad4e408b079f07b1854543f2e8941e1440453b55472d679600",
  "answer_correct": false,
  "grounded": false,
  "abstained": null,
  "notes": "비율 0.1은 검색된 표에서 확인 가능하지만 적용 위치를 원문의 하위 계층 출력·임베딩/위치 인코딩 합으로 설명하지 않았다. 인용 S3는 파싱 실험의 attention/residual 언급으로, 요청한 residual dropout 적용 위치의 직접 근거가 아니다."
}
```

### q17: 라벨 스무딩의 값은 얼마이며 perplexity와 BLEU에 어떤 영향을 주나요?

기대 요점: 0.1; perplexity는 나빠짐; 정확도와 BLEU는 개선

답변:

참고 자료에 따르면, 라벨 스무딩(ϵls)의 값은 0.1입니다. 라벨 스무딩은 모델의 성능에 영향을 미치며, 특히 BLEU 점수와 perplexity에 영향을 줄 수 있습니다. 그러나 제공된 자료에서는 라벨 스무딩이 perplexity와 BLEU 점수에 구체적으로 어떤 영향을 미치는지에 대한 상세한 설명은 포함되어 있지 않습니다 [S4].

검색 청크: 0d72c856-25d0-444f-8880-88f0af86e6c6, f5f964e5-259d-4c14-bb12-d84972c1e85b, df4b0821-cb39-4bc8-a052-6ec32c9105b9, 1892177a-12ff-47ab-b651-7432abf81baf, abfff9f5-cc76-4d3d-ae71-e79dc473d410

컨텍스트 청크: 0d72c856-25d0-444f-8880-88f0af86e6c6, f5f964e5-259d-4c14-bb12-d84972c1e85b, df4b0821-cb39-4bc8-a052-6ec32c9105b9, 1892177a-12ff-47ab-b651-7432abf81baf, abfff9f5-cc76-4d3d-ae71-e79dc473d410

리뷰:

```json
{
  "id": "q17",
  "reviewer": "codex_agent",
  "independent_human_review": false,
  "results_sha256": "33ffd1312e5544ad4e408b079f07b1854543f2e8941e1440453b55472d679600",
  "answer_correct": false,
  "grounded": true,
  "abstained": null,
  "notes": "라벨 스무딩 값 0.1은 표에 있으나 perplexity 악화·정확도/BLEU 개선을 담은 청크 24를 놓쳤다. 결과는 불완전하지만 전달된 근거 밖의 방향성을 만들어내지 않았다."
}
```

### q18: 영어-독일어 번역에서 big Transformer의 BLEU 점수와 학습 시간은 얼마인가요?

기대 요점: 28.4 BLEU; P100 8개에서 3.5일

답변:

영어-독일어 번역에서 big Transformer 모델의 BLEU 점수는 28.4이며, 학습 시간은 3.5일입니다 [S1].

검색 청크: f5f964e5-259d-4c14-bb12-d84972c1e85b, abfff9f5-cc76-4d3d-ae71-e79dc473d410, 0d72c856-25d0-444f-8880-88f0af86e6c6, e1788ece-962e-4695-8d83-910c9231685a, 87907ed6-5f89-4ead-a6f8-9b14a9dbd0c3

컨텍스트 청크: f5f964e5-259d-4c14-bb12-d84972c1e85b, abfff9f5-cc76-4d3d-ae71-e79dc473d410, 0d72c856-25d0-444f-8880-88f0af86e6c6, e1788ece-962e-4695-8d83-910c9231685a, 87907ed6-5f89-4ead-a6f8-9b14a9dbd0c3

리뷰:

```json
{
  "id": "q18",
  "reviewer": "codex_agent",
  "independent_human_review": false,
  "results_sha256": "33ffd1312e5544ad4e408b079f07b1854543f2e8941e1440453b55472d679600",
  "answer_correct": true,
  "grounded": true,
  "abstained": null,
  "notes": "S1의 28.4 BLEU와 3.5일을 반영한다."
}
```

### q19: 번역 추론에 사용한 beam size와 length penalty alpha는 얼마인가요?

기대 요점: beam size 4; alpha 0.6

답변:

번역 추론에 사용한 beam size는 4이고, length penalty α는 0.6입니다 [S1].

검색 청크: 89382f82-33c0-4bda-824c-20b97790906f, f5f964e5-259d-4c14-bb12-d84972c1e85b, df4b0821-cb39-4bc8-a052-6ec32c9105b9, e1788ece-962e-4695-8d83-910c9231685a, abfff9f5-cc76-4d3d-ae71-e79dc473d410

컨텍스트 청크: 89382f82-33c0-4bda-824c-20b97790906f, f5f964e5-259d-4c14-bb12-d84972c1e85b, df4b0821-cb39-4bc8-a052-6ec32c9105b9, e1788ece-962e-4695-8d83-910c9231685a, abfff9f5-cc76-4d3d-ae71-e79dc473d410

리뷰:

```json
{
  "id": "q19",
  "reviewer": "codex_agent",
  "independent_human_review": false,
  "results_sha256": "33ffd1312e5544ad4e408b079f07b1854543f2e8941e1440453b55472d679600",
  "answer_correct": true,
  "grounded": true,
  "abstained": null,
  "notes": "S1의 beam size=4, alpha=0.6과 일치한다."
}
```

### q20: 이 논문은 번역 말고 문장을 문법 구조로 분석하는 작업에도 적용했나요? 어떤 작업인가요?

기대 요점: 영어 구문 구성 분석 English constituency parsing에도 적용

답변:

제공된 자료에서는 이 논문이 번역 작업 외에 문장을 문법 구조로 분석하는 작업에 적용되었다는 내용은 확인할 수 없습니다. 문서에서 확인할 수 없다고 명확히 답합니다.

검색 청크: 184dc405-7599-4e7d-8d3d-cd7cf43be955, 03637804-fe3e-4ec9-b9bf-438d68d8e1ca, 988335ca-b294-4f31-a0c0-eabc9403cc67, ee510fa2-28dc-40c4-8655-d42ab8cf40e4, 9a5c83fa-dcec-4d75-b54b-8864323e550c

컨텍스트 청크: 184dc405-7599-4e7d-8d3d-cd7cf43be955, 03637804-fe3e-4ec9-b9bf-438d68d8e1ca, 988335ca-b294-4f31-a0c0-eabc9403cc67, ee510fa2-28dc-40c4-8655-d42ab8cf40e4, 9a5c83fa-dcec-4d75-b54b-8864323e550c

리뷰:

```json
{
  "id": "q20",
  "reviewer": "codex_agent",
  "independent_human_review": false,
  "results_sha256": "33ffd1312e5544ad4e408b079f07b1854543f2e8941e1440453b55472d679600",
  "answer_correct": false,
  "grounded": true,
  "abstained": null,
  "notes": "파싱 실험을 설명하는 주요 청크 1/29/30/31을 놓쳐 답변을 유보했다. 전달된 자료에는 파싱을 명확히 설명하는 문맥이 부족하지만 전체 문서에는 정답이 있다."
}
```

### q21: Transformer 모델을 구매한 고객의 환불 가능 기간은 며칠인가요?

기대 요점: 논문에 환불 정책 정보가 없다고 안내

답변:

문서에서 Transformer 모델의 환불 가능 기간에 대한 정보는 확인할 수 없습니다.

검색 청크: f5f964e5-259d-4c14-bb12-d84972c1e85b, 0d72c856-25d0-444f-8880-88f0af86e6c6, e1788ece-962e-4695-8d83-910c9231685a, abfff9f5-cc76-4d3d-ae71-e79dc473d410, 9a5c83fa-dcec-4d75-b54b-8864323e550c

컨텍스트 청크: f5f964e5-259d-4c14-bb12-d84972c1e85b, 0d72c856-25d0-444f-8880-88f0af86e6c6, e1788ece-962e-4695-8d83-910c9231685a, abfff9f5-cc76-4d3d-ae71-e79dc473d410, 9a5c83fa-dcec-4d75-b54b-8864323e550c

리뷰:

```json
{
  "id": "q21",
  "reviewer": "codex_agent",
  "independent_human_review": false,
  "results_sha256": "33ffd1312e5544ad4e408b079f07b1854543f2e8941e1440453b55472d679600",
  "answer_correct": null,
  "grounded": null,
  "abstained": true,
  "notes": "환불 정책이 없음을 안내하고 기간을 생성하지 않았다."
}
```

### q22: 이 논문의 전체 학습 실험이 소비한 전력량은 정확히 몇 kWh인가요?

기대 요점: 논문에서 정확한 kWh를 확인할 수 없다고 안내; GPU·시간으로 임의의 수치를 단정하지 않음

답변:

문서에서는 학습 실험에 소비된 전력량에 대한 정보가 제공되지 않았습니다. 따라서 정확한 kWh를 확인할 수 없습니다.

검색 청크: e1788ece-962e-4695-8d83-910c9231685a, abfff9f5-cc76-4d3d-ae71-e79dc473d410, f5f964e5-259d-4c14-bb12-d84972c1e85b, 0d72c856-25d0-444f-8880-88f0af86e6c6, 1e1836e4-7129-4ce0-969d-9a7650c726b2

컨텍스트 청크: e1788ece-962e-4695-8d83-910c9231685a, abfff9f5-cc76-4d3d-ae71-e79dc473d410, f5f964e5-259d-4c14-bb12-d84972c1e85b, 0d72c856-25d0-444f-8880-88f0af86e6c6, 1e1836e4-7129-4ce0-969d-9a7650c726b2

리뷰:

```json
{
  "id": "q22",
  "reviewer": "codex_agent",
  "independent_human_review": false,
  "results_sha256": "33ffd1312e5544ad4e408b079f07b1854543f2e8941e1440453b55472d679600",
  "answer_correct": null,
  "grounded": null,
  "abstained": true,
  "notes": "전력량 kWh를 알 수 없다고 답하고 하드웨어/시간으로 숫자를 임의 산출하지 않았다."
}
```

### q23: 이 논문에서 Transformer의 영어-한국어 번역 BLEU 점수는 얼마인가요?

기대 요점: 해당 영어-한국어 실험 점수는 제공되지 않았다고 안내

답변:

문서에서 Transformer의 영어-한국어 번역 BLEU 점수에 대한 정보는 확인할 수 없습니다. 제공된 자료는 영어-독일어 및 영어-프랑스어 번역에 대한 BLEU 점수만 언급하고 있습니다 [S1], [S2].

검색 청크: f5f964e5-259d-4c14-bb12-d84972c1e85b, 0d72c856-25d0-444f-8880-88f0af86e6c6, abfff9f5-cc76-4d3d-ae71-e79dc473d410, 87907ed6-5f89-4ead-a6f8-9b14a9dbd0c3, 1892177a-12ff-47ab-b651-7432abf81baf

컨텍스트 청크: f5f964e5-259d-4c14-bb12-d84972c1e85b, 0d72c856-25d0-444f-8880-88f0af86e6c6, abfff9f5-cc76-4d3d-ae71-e79dc473d410, 87907ed6-5f89-4ead-a6f8-9b14a9dbd0c3, 1892177a-12ff-47ab-b651-7432abf81baf

리뷰:

```json
{
  "id": "q23",
  "reviewer": "codex_agent",
  "independent_human_review": false,
  "results_sha256": "33ffd1312e5544ad4e408b079f07b1854543f2e8941e1440453b55472d679600",
  "answer_correct": null,
  "grounded": null,
  "abstained": true,
  "notes": "영어-한국어 실험 점수를 생성하지 않고 영어-독일어/프랑스어와 구분했다."
}
```

### q24: 이 논문에 명시된 Transformer 고객지원 전화번호를 알려주세요.

기대 요점: 고객지원 전화번호는 문서에 없다고 안내

답변:

문서에서 Transformer 고객지원 전화번호에 대한 정보는 확인할 수 없습니다.

검색 청크: 9a5c83fa-dcec-4d75-b54b-8864323e550c, f5f964e5-259d-4c14-bb12-d84972c1e85b, 093e2b68-0388-4a96-8e8a-e5dee9256e48, 0d72c856-25d0-444f-8880-88f0af86e6c6, 1892177a-12ff-47ab-b651-7432abf81baf

컨텍스트 청크: 9a5c83fa-dcec-4d75-b54b-8864323e550c, f5f964e5-259d-4c14-bb12-d84972c1e85b, 093e2b68-0388-4a96-8e8a-e5dee9256e48, 0d72c856-25d0-444f-8880-88f0af86e6c6, 1892177a-12ff-47ab-b651-7432abf81baf

리뷰:

```json
{
  "id": "q24",
  "reviewer": "codex_agent",
  "independent_human_review": false,
  "results_sha256": "33ffd1312e5544ad4e408b079f07b1854543f2e8941e1440453b55472d679600",
  "answer_correct": null,
  "grounded": null,
  "abstained": true,
  "notes": "전화번호를 생성하지 않고 정보 부재를 안내했다."
}
```
