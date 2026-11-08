// Castle Siege 3D - safe in-browser code runner for challenges.
// Adapted from the proven Web Worker pattern in the Syntax Sprint code
// challenge (logicstack src/components/CodeChallenge.jsx): the player code
// runs in a Blob Web Worker, so an infinite loop cannot hang the page.
// A 3 second timeout terminates the worker. Results compare with deepEqual
// and report actual vs expected per test, plus clear syntax/runtime errors.

export const RUN_TIMEOUT_MS = 3000;

const WORKER_SRC = `
function deepEqual(a, b) {
  if (a === b || Object.is(a, b)) return true;
  if (typeof a !== typeof b) return false;
  if (a && b && typeof a === 'object') {
    if (Array.isArray(a) !== Array.isArray(b)) return false;
    var ka = Object.keys(a), kb = Object.keys(b);
    if (ka.length !== kb.length) return false;
    return ka.every(function (k) { return deepEqual(a[k], b[k]); });
  }
  return false;
}
onmessage = function (e) {
  var data = e.data;
  var fn;
  try {
    fn = new Function(data.code + '\\n; return ' + data.functionName + ';')();
  } catch (err) {
    postMessage({ ok: false, error: 'Syntax error: ' + err.message, results: [] });
    return;
  }
  if (typeof fn !== 'function') {
    postMessage({ ok: false, error: data.functionName + ' is not a function. Check the function name.', results: [] });
    return;
  }
  var results = data.tests.map(function (t) {
    var actual;
    try {
      var args = JSON.parse(JSON.stringify(t.args));
      actual = fn.apply(null, args);
    } catch (err) {
      return { passed: false, actual: null, expected: t.expected, error: err.message };
    }
    return { passed: deepEqual(actual, t.expected), actual: actual, expected: t.expected, error: null };
  });
  postMessage({ ok: true, error: null, results: results });
};
`;

// Run player code against a list of tests.
// tests: [{ args: [...], expected: any }]
// Returns a promise of { ok, error, results: [{ passed, actual, expected, error }] }.
// ok is false for syntax errors, a missing function, a runner crash, or a
// timeout (including infinite loops). Per-test runtime errors set
// results[i].error and passed false, with ok still true.
export function runChallenge(code, functionName, tests) {
  return new Promise((resolve) => {
    let settled = false;
    let worker = null;
    const finish = (payload) => {
      if (settled) return;
      settled = true;
      try {
        if (worker) worker.terminate();
      } catch (err) {
        // Worker already gone.
      }
      resolve(payload);
    };
    const blob = new Blob([WORKER_SRC], { type: 'application/javascript' });
    const url = URL.createObjectURL(blob);
    try {
      worker = new Worker(url);
    } catch (err) {
      URL.revokeObjectURL(url);
      resolve({ ok: false, error: 'Your browser blocked the code runner. Try another browser.', results: [] });
      return;
    }
    URL.revokeObjectURL(url);
    const timer = window.setTimeout(() => {
      finish({ ok: false, error: 'Time limit exceeded (' + RUN_TIMEOUT_MS / 1000 + 's). Infinite loop?', results: [] });
    }, RUN_TIMEOUT_MS);
    worker.onmessage = (event) => {
      window.clearTimeout(timer);
      finish(event.data);
    };
    worker.onerror = () => {
      window.clearTimeout(timer);
      finish({ ok: false, error: 'The runner crashed. Check the code and try again.', results: [] });
    };
    worker.postMessage({ code, functionName, tests });
  });
}
