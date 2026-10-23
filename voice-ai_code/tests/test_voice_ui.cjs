// UI flow tests with a simulated DOM and fake API responses. No paid calls.
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const test = require('node:test');
const assert = require('node:assert/strict');

function harness(options = {}) {
  const html = fs.readFileSync(path.join(__dirname, '../app/static/voice-query.html'), 'utf8');
  const elements = {};
  for (const match of html.matchAll(/<[^>]*\bid="([^"]+)"[^>]*>/g)) {
    elements[match[1]] = {
      value: '', textContent: '', hidden: /\bhidden\b/.test(match[0]),
      checked: /\bchecked\b/.test(match[0]), disabled: false, readOnly: false,
      pause() {}, removeAttribute() {}, replaceChildren() {}, append() {},
    };
  }
  const calls = [];
  const review = {raw_transcript: '유가 휴직 신청', corrected_question: '육아휴직 신청',
                  changed: true, ...options.review};
  const sandbox = {
    document: {
      getElementById(id) { assert.ok(elements[id], 'Missing element: ' + id); return elements[id]; },
      createElement() { return {}; },
    },
    window: {addEventListener() {}},
    URL: {createObjectURL() { return 'blob:test'; }, revokeObjectURL() {}},
    FormData: class { append() {} },
    setTimeout, clearTimeout,
    async fetch(url, request) {
      calls.push({url, request});
      if (url === '/voice-config') return {ok: true, status: 200, async json() {return {mode: 'demo'};}};
      if (url === '/voice-transcribe') {
        if (options.waitReview) await options.waitReview;
        if (options.transcriptionFails) return {ok: false, status: 422, async json() {return {detail: '음성 인식 실패'};}};
        return {ok: true, status: 200, async json() {return review;}};
      }
      assert.equal(url, '/voice-query-text');
      if (options.answerFails) return {ok: false, status: 503, async json() {return {detail: '검색 연결 실패'};}};
      return {ok: true, status: 200, async json() {
        return {mode: 'demo', transcript: JSON.parse(request.body).question,
          answer: '테스트 답변', sources: [], needs_review: true, handoff: true,
          latency_ms: 1, audio_url: null};
      }};
    },
  };
  vm.createContext(sandbox);
  vm.runInContext(html.match(/<script>([\s\S]*?)<\/script>/)[1], sandbox);
  return {elements, calls, sandbox,
    answers: () => calls.filter(c => c.url === '/voice-query-text'),
    transcriptions: () => calls.filter(c => c.url === '/voice-transcribe')};
}

test('ON defaults to waiting; original and editable suggestion are visible', async () => {
  const h = harness();
  assert.equal(h.elements.requireConfirmation.checked, true);
  await h.sandbox.send({}, 'test.webm');
  assert.equal(h.answers().length, 0);
  assert.equal(h.elements.rawTranscript.textContent, '유가 휴직 신청');
  assert.equal(h.elements.question.value, '육아휴직 신청');
  assert.equal(h.elements.question.readOnly, false);
  assert.equal(h.elements.confirmationActions.hidden, false);
  assert.equal(h.elements.result.hidden, true);
});

test('ON submits edited text only on click and does not repeat correction', async () => {
  const h = harness();
  await h.sandbox.send({}, 'test.webm');
  h.elements.question.value = '재택근무는 주 몇 회인가요?';
  await h.elements.confirmQuestion.onclick();
  assert.equal(h.answers().length, 1);
  assert.equal(h.transcriptions().length, 1);
  assert.equal(JSON.parse(h.answers()[0].request.body).question, h.elements.question.value);
  assert.equal(h.elements.transcript.textContent, '재택근무는 주 몇 회인가요?');
  assert.equal(h.elements.rawTranscript.textContent, '유가 휴직 신청');
});

test('OFF displays recognized text and automatically submits corrected question once', async () => {
  const h = harness();
  h.elements.requireConfirmation.checked = false;
  h.elements.requireConfirmation.onchange();
  assert.equal(h.elements.confirmationState.textContent, 'OFF');
  assert.equal(h.answers().length, 0); // Changing the switch alone does not call APIs.
  await h.sandbox.send({}, 'test.webm');
  assert.equal(h.answers().length, 1);
  assert.equal(h.transcriptions().length, 1);
  assert.equal(JSON.parse(h.answers()[0].request.body).question, '육아휴직 신청');
  assert.equal(h.elements.rawTranscript.textContent, '유가 휴직 신청');
  assert.equal(h.elements.transcript.textContent, '육아휴직 신청');
  assert.equal(h.elements.question.readOnly, true);
  assert.equal(h.elements.confirmationActions.hidden, true);
  assert.equal(h.elements.result.hidden, false);
  assert.equal(h.elements.requireConfirmation.disabled, false);
});

test('OFF uses fallback original while keeping correction warning visible', async () => {
  const h = harness({review: {corrected_question: '유가 휴직 신청', changed: false,
                             warning: '교정 실패: 원문을 확인하세요.'}});
  h.elements.requireConfirmation.checked = false;
  await h.sandbox.send({}, 'test.webm');
  assert.equal(JSON.parse(h.answers()[0].request.body).question, '유가 휴직 신청');
  assert.match(h.elements.correctionWarning.textContent, /교정 실패/);
});

test('automatic answer failure preserves question and releases controls', async () => {
  const h = harness({answerFails: true});
  h.elements.requireConfirmation.checked = false;
  await h.sandbox.send({}, 'test.webm');
  assert.equal(h.elements.rawTranscript.textContent, '유가 휴직 신청');
  assert.equal(h.elements.questionReview.hidden, false);
  assert.equal(h.elements.result.hidden, true);
  assert.equal(h.elements.status.textContent, '검색 연결 실패');
  for (const id of ['record', 'send', 'file', 'requireConfirmation']) {
    assert.equal(h.elements[id].disabled, false);
  }
});

test('transcription failure never requests an answer', async () => {
  const h = harness({transcriptionFails: true});
  h.elements.requireConfirmation.checked = false;
  await h.sandbox.send({}, 'test.webm');
  assert.equal(h.answers().length, 0);
  assert.equal(h.elements.questionReview.hidden, true);
  assert.equal(h.elements.requireConfirmation.disabled, false);
});

test('mode is captured per request and switch stays disabled during processing', async () => {
  let release;
  const waitReview = new Promise(resolve => { release = resolve; });
  const h = harness({waitReview});
  const pending = h.sandbox.send({}, 'test.webm');
  assert.equal(h.elements.requireConfirmation.disabled, true);
  h.elements.requireConfirmation.checked = false; // Simulate a programmatic change.
  release();
  await pending;
  assert.equal(h.answers().length, 0); // This request began in ON mode.
  assert.equal(h.elements.question.readOnly, false);
});
