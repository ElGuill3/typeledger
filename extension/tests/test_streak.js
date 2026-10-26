// Pure-logic tests for streak.js. Run with: gjs -m extension/tests/test_streak.js
// Exits non-zero when any test fails.

import {computeStreak, localIsoDate, newestSummary, parseSummary} from '../typeledger@elguill3.github.io/streak.js';

import System from 'system';

const tests = [];
function test(name, fn) {
    tests.push([name, fn]);
}

function assert(condition, message) {
    if (!condition)
        throw new Error(message ?? 'assertion failed');
}

function assertEqual(actual, expected, message) {
    const a = JSON.stringify(actual);
    const e = JSON.stringify(expected);
    if (a !== e)
        throw new Error(`${message ?? 'not equal'}: expected ${e}, got ${a}`);
}

function validSummary(overrides = {}) {
    return {
        schema: 1,
        generated_at: '2026-10-25T10:00:00-06:00',
        practiced_days: ['2026-10-23', '2026-10-24', '2026-10-25'],
        longest_streak: 5,
        total_sessions: 12,
        recent_days: 7,
        recent_avg_wpm: 42.5,
        recent_avg_accuracy: 0.97,
        recent_sessions: 4,
        ...overrides,
    };
}

// parseSummary

test('parseSummary accepts a valid v1 summary', () => {
    const parsed = parseSummary(JSON.stringify(validSummary()));
    assert(parsed !== null, 'expected an object');
    assertEqual(parsed.practiced_days, ['2026-10-23', '2026-10-24', '2026-10-25']);
    assertEqual(parsed.longest_streak, 5);
    assertEqual(parsed.total_sessions, 12);
    assertEqual(parsed.recent_avg_wpm, 42.5);
    assertEqual(parsed.recent_avg_accuracy, 0.97);
    assertEqual(parsed.recent_sessions, 4);
    assertEqual(parsed.recent_days, 7);
    assertEqual(parsed.generated_at, '2026-10-25T10:00:00-06:00');
});

test('parseSummary accepts integer averages', () => {
    const parsed = parseSummary(JSON.stringify(validSummary({recent_avg_wpm: 0, recent_avg_accuracy: 1})));
    assert(parsed !== null, 'expected an object');
});

test('parseSummary rejects invalid JSON', () => {
    assertEqual(parseSummary('{not json'), null);
    assertEqual(parseSummary(''), null);
});

test('parseSummary rejects non-string and non-object input', () => {
    assertEqual(parseSummary(null), null);
    assertEqual(parseSummary(undefined), null);
    assertEqual(parseSummary('[]'), null);
    assertEqual(parseSummary('42'), null);
    assertEqual(parseSummary('null'), null);
});

test('parseSummary rejects unsupported schema versions', () => {
    assertEqual(parseSummary(JSON.stringify(validSummary({schema: 2}))), null);
    assertEqual(parseSummary(JSON.stringify(validSummary({schema: '1'}))), null);
});

test('parseSummary rejects missing fields', () => {
    for (const key of Object.keys(validSummary())) {
        const data = validSummary();
        delete data[key];
        assertEqual(parseSummary(JSON.stringify(data)), null, `missing ${key}`);
    }
});

test('parseSummary rejects wrong types', () => {
    const bad = {
        generated_at: 123,
        practiced_days: '2026-10-25',
        longest_streak: 1.5,
        total_sessions: '3',
        recent_days: null,
        recent_avg_wpm: '40',
        recent_avg_accuracy: 1.5,
        recent_sessions: -1,
    };
    for (const [key, value] of Object.entries(bad)) {
        assertEqual(parseSummary(JSON.stringify(validSummary({[key]: value}))), null, `bad ${key}`);
    }
});

test('parseSummary rejects malformed practiced days', () => {
    for (const days of [['2026-1-5'], [20261025], ['2026-13-01'], ['yesterday']]) {
        assertEqual(parseSummary(JSON.stringify(validSummary({practiced_days: days}))), null,
            `days ${JSON.stringify(days)}`);
    }
});

test('parseSummary rejects an unparseable generated_at', () => {
    assertEqual(parseSummary(JSON.stringify(validSummary({generated_at: 'soon'}))), null);
});

// computeStreak

test('computeStreak with no days', () => {
    assertEqual(computeStreak([], '2026-10-25'), {current: 0, practicedToday: false});
});

test('computeStreak counts a run ending today', () => {
    assertEqual(computeStreak(['2026-10-23', '2026-10-24', '2026-10-25'], '2026-10-25'),
        {current: 3, practicedToday: true});
});

test('computeStreak stays alive when only yesterday is practiced', () => {
    assertEqual(computeStreak(['2026-10-22', '2026-10-23', '2026-10-24'], '2026-10-25'),
        {current: 3, practicedToday: false});
});

test('computeStreak is broken by a gap', () => {
    assertEqual(computeStreak(['2026-10-20', '2026-10-21', '2026-10-23'], '2026-10-25'),
        {current: 0, practicedToday: false});
    assertEqual(computeStreak(['2026-10-20', '2026-10-21', '2026-10-23', '2026-10-25'], '2026-10-25'),
        {current: 1, practicedToday: true});
});

test('computeStreak tolerates duplicates and unsorted input', () => {
    assertEqual(computeStreak(['2026-10-25', '2026-10-23', '2026-10-24', '2026-10-25', '2026-10-23'], '2026-10-25'),
        {current: 3, practicedToday: true});
});

test('computeStreak ignores future dates', () => {
    assertEqual(computeStreak(['2026-10-26', '2026-10-27'], '2026-10-25'),
        {current: 0, practicedToday: false});
    assertEqual(computeStreak(['2026-10-24', '2026-10-26'], '2026-10-25'),
        {current: 1, practicedToday: false});
});

test('computeStreak crosses month and year boundaries', () => {
    assertEqual(computeStreak(['2025-12-30', '2025-12-31', '2026-01-01'], '2026-01-01'),
        {current: 3, practicedToday: true});
    assertEqual(computeStreak(['2024-02-28', '2024-02-29', '2024-03-01'], '2024-03-01'),
        {current: 3, practicedToday: true});
});

// newestSummary

test('newestSummary picks the latest generated_at and skips nulls', () => {
    const older = validSummary({generated_at: '2026-10-25T10:00:00-06:00'});
    const newer = validSummary({generated_at: '2026-10-25T17:00:00Z'});
    assertEqual(newestSummary([older, null, newer]), newer);
    assertEqual(newestSummary([newer, older]), newer);
    assertEqual(newestSummary([null, null]), null);
    assertEqual(newestSummary([]), null);
});

// localIsoDate

test('localIsoDate pads month and day', () => {
    assertEqual(localIsoDate(new Date(2026, 0, 5, 12, 0, 0)), '2026-01-05');
    assertEqual(localIsoDate(new Date(2026, 11, 31, 23, 59, 59)), '2026-12-31');
});

let failures = 0;
for (const [name, fn] of tests) {
    try {
        fn();
        print(`ok - ${name}`);
    } catch (e) {
        failures++;
        print(`FAIL - ${name}: ${e.message}`);
    }
}
print(`${tests.length - failures}/${tests.length} passed`);
System.exit(failures ? 1 : 0);
