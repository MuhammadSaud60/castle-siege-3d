// Castle Siege 3D - challenge panel UI.
// Modal overlay: problem on the left, code editor on the right. Run checks
// the visible tests first; when they all pass, the hidden tests run too.
// All tests passing shows the success state with a "Place building" button
// that calls the onSolved callback given to openChallenge. Wrong attempts
// cost nothing: the player can retry or close freely. While the panel is
// open the game simulation is paused through window.__castle.

import { pickChallenge } from './challenges.js';
import { runChallenge } from './challengeRunner.js';

let current = null;
let onSolved = null;
let running = false;

function $(id) {
  return document.getElementById(id);
}

function formatValue(value) {
  let text;
  try {
    text = JSON.stringify(value) ?? String(value);
  } catch (err) {
    text = String(value);
  }
  return text.length > 220 ? text.slice(0, 220) + '...' : text;
}

function setPaused(paused) {
  try {
    if (window.__castle && typeof window.__castle.setChallengeOpen === 'function') {
      window.__castle.setChallengeOpen(paused);
    }
  } catch (err) {
    // Pause flag unavailable; the panel still works.
  }
}

function escapeHtml(text) {
  return String(text)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');
}

function renderTestRow(label, result, args) {
  const cls = result.passed ? 'challenge-test-pass' : 'challenge-test-fail';
  const mark = result.passed ? '✓' : '✗';
  let detail;
  if (result.error) {
    detail = 'Error: ' + escapeHtml(result.error);
  } else if (!result.passed) {
    detail = 'Expected ' + escapeHtml(formatValue(result.expected)) + ', got ' + escapeHtml(formatValue(result.actual));
  } else {
    detail = 'Got ' + escapeHtml(formatValue(result.actual));
  }
  return '<div class="challenge-test ' + cls + '"><span class="challenge-test-mark">' + mark + '</span>'
    + '<span class="challenge-test-body"><b>' + escapeHtml(label) + '</b>'
    + '<span class="challenge-test-args">Input: ' + escapeHtml(formatValue(args)) + '</span>'
    + '<span class="challenge-test-detail">' + detail + '</span></span></div>';
}

export function getCurrentChallenge() {
  return current;
}

export function closeChallenge() {
  const overlay = $('challenge-overlay');
  if (overlay) overlay.classList.add('hidden');
  current = null;
  onSolved = null;
  running = false;
  setPaused(false);
}

export function openChallenge(kind, callback) {
  const challenge = pickChallenge(kind);
  if (!challenge) return false;
  current = challenge;
  onSolved = typeof callback === 'function' ? callback : null;

  $('challenge-title').textContent = challenge.title;
  const badge = $('challenge-difficulty');
  badge.textContent = challenge.difficulty;
  badge.className = 'challenge-badge challenge-badge-' + challenge.difficulty.toLowerCase().replace(/[^a-z]/g, '');
  $('challenge-kind').textContent = 'Build: ' + kind;
  $('challenge-story').textContent = challenge.story;
  $('challenge-description').textContent = challenge.description;

  $('challenge-examples').innerHTML = challenge.examples.map((ex) => (
    '<div class="challenge-example"><p><b>Input:</b> ' + escapeHtml(ex.input) + '</p>'
    + '<p><b>Output:</b> ' + escapeHtml(ex.output) + '</p>'
    + (ex.explanation ? '<p class="challenge-example-note">' + escapeHtml(ex.explanation) + '</p>' : '')
    + '</div>'
  )).join('');

  $('challenge-constraints').innerHTML = challenge.constraints.map((c) => (
    '<li>' + escapeHtml(c) + '</li>'
  )).join('');

  const editor = $('challenge-editor');
  editor.value = challenge.starterCode;
  editor.disabled = false;

  $('challenge-hint').classList.add('hidden');
  $('challenge-hint').textContent = '';
  $('challenge-hint-btn').disabled = false;
  $('challenge-error').classList.add('hidden');
  $('challenge-error').textContent = '';
  $('challenge-results').innerHTML = '';
  $('challenge-summary').textContent = '';
  $('challenge-success').classList.add('hidden');
  $('challenge-run').disabled = false;
  $('challenge-run').textContent = 'Run tests';

  $('challenge-overlay').classList.remove('hidden');
  setPaused(true);
  return true;
}

async function handleRun() {
  if (!current || running) return;
  running = true;
  const runBtn = $('challenge-run');
  runBtn.disabled = true;
  runBtn.textContent = 'Running...';
  $('challenge-error').classList.add('hidden');
  $('challenge-success').classList.add('hidden');
  $('challenge-summary').textContent = '';

  const challenge = current;
  // One worker run for all tests (visible + hidden together): a single
  // spawn and a single timeout window. Only the visible rows are shown;
  // the hidden tests appear as one summary row, never with their inputs.
  const allTests = [...challenge.visibleTests, ...challenge.hiddenTests];
  const run = await runChallenge($('challenge-editor').value, challenge.functionName, allTests);
  if (!current || current.id !== challenge.id) {
    running = false;
    return;
  }
  if (!run.ok) {
    $('challenge-error').textContent = run.error;
    $('challenge-error').classList.remove('hidden');
    $('challenge-results').innerHTML = '';
    $('challenge-summary').textContent = 'Run failed. Fix the error and try again, there is no penalty.';
    runBtn.disabled = false;
    runBtn.textContent = 'Run tests';
    running = false;
    return;
  }

  const visibleResults = run.results.slice(0, challenge.visibleTests.length);
  const hiddenResults = run.results.slice(challenge.visibleTests.length);
  let html = visibleResults.map((result, i) => renderTestRow(
    'Test ' + (i + 1),
    result,
    challenge.visibleTests[i].args,
  )).join('');
  const visiblePassed = visibleResults.filter((r) => r.passed).length;
  let summary = visiblePassed + ' / ' + visibleResults.length + ' visible tests passed.';
  let allPassed = false;

  if (visiblePassed === visibleResults.length) {
    const hiddenPassed = hiddenResults.filter((r) => r.passed).length;
    if (hiddenPassed === hiddenResults.length) {
      allPassed = true;
      summary = 'All tests passed, including 2 hidden tests. Well done.';
      html += '<div class="challenge-test challenge-test-pass"><span class="challenge-test-mark">✓</span>'
        + '<span class="challenge-test-body"><b>Hidden tests</b>'
        + '<span class="challenge-test-detail">2 / 2 passed</span></span></div>';
    } else {
      summary = 'Visible tests pass, but a hidden test failed. Keep going, there is no penalty.';
      html += '<div class="challenge-test challenge-test-fail"><span class="challenge-test-mark">✗</span>'
        + '<span class="challenge-test-body"><b>Hidden tests</b>'
        + '<span class="challenge-test-detail">' + hiddenPassed + ' / 2 passed</span></span></div>';
    }
  }

  $('challenge-results').innerHTML = html;
  $('challenge-summary').textContent = summary;
  if (allPassed) {
    $('challenge-success').classList.remove('hidden');
  }
  runBtn.disabled = false;
  runBtn.textContent = 'Run tests';
  running = false;
}

function handleHint() {
  if (!current) return;
  const hintEl = $('challenge-hint');
  hintEl.textContent = 'Hint: ' + current.hint;
  hintEl.classList.remove('hidden');
}

function handlePlace() {
  if (!current) return;
  const cb = onSolved;
  const solvedKind = current.kind;
  closeChallenge();
  if (cb) cb(solvedKind);
}

function wirePanel() {
  $('challenge-run').addEventListener('click', handleRun);
  $('challenge-hint-btn').addEventListener('click', handleHint);
  $('challenge-close').addEventListener('click', closeChallenge);
  $('challenge-cancel').addEventListener('click', closeChallenge);
  $('challenge-place-btn').addEventListener('click', handlePlace);
  $('challenge-reset').addEventListener('click', () => {
    if (!current) return;
    $('challenge-editor').value = current.starterCode;
    $('challenge-results').innerHTML = '';
    $('challenge-summary').textContent = '';
    $('challenge-error').classList.add('hidden');
    $('challenge-success').classList.add('hidden');
  });
  const editor = $('challenge-editor');
  editor.addEventListener('keydown', (event) => {
    if (event.key !== 'Tab') return;
    event.preventDefault();
    const start = editor.selectionStart;
    const end = editor.selectionEnd;
    editor.value = editor.value.slice(0, start) + '  ' + editor.value.slice(end);
    editor.selectionStart = start + 2;
    editor.selectionEnd = start + 2;
  });
}

wirePanel();
