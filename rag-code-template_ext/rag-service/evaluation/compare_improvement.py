"""보존된 전후 실행과 별도 에이전트 검토를 비교한다. 외부 API 호출 없음."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import statistics


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def summary(rows):
    results = [row['result'] for row in rows]
    normal = [row['result'] for row in rows if int(row['case']['id'][1:]) <= 28]
    absent = [row['result'] for row in rows if int(row['case']['id'][1:]) >= 29]
    times = sorted(r['elapsed_ms'] for r in results)
    return {'total': len(rows), 'statuses': dict(Counter(r['status'] for r in results)),
            'answerable_answered': sum(r['status'] == 'answered' for r in normal),
            'answerable_total': len(normal), 'unanswerable_abstained': sum(r['status'] == 'no_evidence' for r in absent),
            'unanswerable_total': len(absent), 'median_ms': statistics.median(times),
            'p95_ms_nearest_rank': times[max(0, __import__('math').ceil(.95 * len(times)) - 1)],
            'model_calls': sum(r['model_calls'] for r in results),
            'reported_input_tokens': sum(e.get('usage', {}).get('input_tokens', 0) for r in results for e in r['trace']),
            'reported_output_tokens': sum(e.get('usage', {}).get('output_tokens', 0) for r in results for e in r['trace'])}


def compare(root):
    before, final = [read(root/name/'results.json') for name in ['before_live', 'final_live']]
    manifests = [read(root/name/'manifest.json') for name in ['before_live', 'final_live']]
    for key in ['index_sha256', 'cases_sha256', 'embedding_model', 'model', 'top_k', 'cases_snapshot']:
        if manifests[0][key] != manifests[1][key]:
            raise ValueError('Comparison conditions differ: ' + key)
    if not all(m['index_unchanged'] for m in manifests):
        raise ValueError('Index changed during evaluation')
    if [r['case']['id'] for r in before] != [r['case']['id'] for r in final]:
        raise ValueError('Case IDs differ')
    review = read(root/'agent_review.json')
    for name in ['before_live', 'final_live']:
        if review['results_sha256'][name] != digest(root/name/'results.json'):
            raise ValueError('Review snapshot mismatch')
    by_id = {r['id']: r for r in review['rows']}
    result = {'before': summary(before), 'final': summary(final), 'reviewer': review['reviewer'],
              'limitations': review['limitations']}
    for phase in ['before', 'final']:
        eligible = [r[phase]['primary_answer_correct'] for r in review['rows'] if r[phase]['primary_answer_correct'] is not None]
        result[phase]['agent_primary_correct'] = sum(eligible)
        result[phase]['agent_primary_total'] = len(eligible)
    for phase, folder in [('before', 'before_fixture'), ('final', 'final_fixture')]:
        fixtures = read(root/folder/'results.json')
        result[phase]['fixture_passed'] = sum(r['pass'] for r in fixtures)
        result[phase]['fixture_total'] = len(fixtures)
    (root/'comparison.json').write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    lines = ['# 문항별 전후 결과', '', '상태는 자동 집계이며 핵심 답변 판정은 Codex 에이전트의 1차 검토다. 독립적인 사람의 정확도 평가가 아니다.', '',
             '| ID | 질문 | 개선 전 상태 | 최종 상태 | 핵심 답변 전/후 | 검토 메모 |', '|---|---|---|---|---|---|']
    for a, b in zip(before, final):
        key = a['case']['id']; item = by_id[key]
        lines.append(f"| {key} | {a['case']['질문']} | {a['result']['status']} | {b['result']['status']} | {item['before']['primary_answer_correct']} / {item['final']['primary_answer_correct']} | {item['notes']} |")
    lines.extend(['', '원문 답변과 생성에 사용된 자료는 각 실행 results.json에 보존했다.', ''])
    (root/'case_comparison.md').write_text('\n'.join(lines), encoding='utf-8')
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('run_root', type=Path)
    print(json.dumps(compare(parser.parse_args().run_root), ensure_ascii=False, indent=2))
