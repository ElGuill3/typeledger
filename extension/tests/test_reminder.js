// Pure-logic tests for reminder.js. Run with: gjs -m extension/tests/test_reminder.js
// Exits non-zero when any test fails.

import {
    REMINDER_HOUR, parseState, secondsUntilReminder, serializeState, shouldRemind,
} from '../typeledger@elguill3.github.io/reminder.js';

import System from 'system';

const tests = [];
function test(name, fn) {
    tests.push([name, fn]);
}

function assertEqual(actual, expected, message) {
    const a = JSON.stringify(actual);
    const e = JSON.stringify(expected);
    if (a !== e)
        throw new Error(`${message ?? 'not equal'}: expected ${e}, got ${a}`);
}

function remind(overrides = {}) {
    return shouldRemind({
        todayIso: '2026-10-25',
        nowHour: 21,
        practicedToday: false,
        lastRemindedIso: null,
        reminderHour: 20,
        ...overrides,
    });
}

// shouldRemind

test('reminder hour is 20:00', () => {
    assertEqual(REMINDER_HOUR, 20);
});

test('no reminder before the reminder hour', () => {
    assertEqual(remind({nowHour: 19}), false);
    assertEqual(remind({nowHour: 0}), false);
});

test('reminder at or after the hour when today has no practice', () => {
    assertEqual(remind({nowHour: 20}), true);
    assertEqual(remind({nowHour: 23}), true);
});

test('no reminder when practiced today', () => {
    assertEqual(remind({practicedToday: true}), false);
});

test('no second reminder on the same day', () => {
    assertEqual(remind({lastRemindedIso: '2026-10-25'}), false);
});

test('reminded yesterday still reminds today', () => {
    assertEqual(remind({lastRemindedIso: '2026-10-24'}), true);
});

test('reminder hour defaults to REMINDER_HOUR', () => {
    const base = {todayIso: '2026-10-25', practicedToday: false, lastRemindedIso: null};
    assertEqual(shouldRemind({...base, nowHour: REMINDER_HOUR - 1}), false);
    assertEqual(shouldRemind({...base, nowHour: REMINDER_HOUR}), true);
});

test('invalid inputs never remind', () => {
    assertEqual(remind({todayIso: ''}), false);
    assertEqual(remind({nowHour: Number.NaN}), false);
});

// secondsUntilReminder

const H = 60 * 60;

test('seconds until the reminder later today', () => {
    assertEqual(secondsUntilReminder({secondsSinceMidnight: 8 * H, reminderHour: 20}), 12 * H);
    assertEqual(secondsUntilReminder({secondsSinceMidnight: 20 * H - 1, reminderHour: 20}), 1);
});

test('at or after the hour the next reminder is tomorrow', () => {
    assertEqual(secondsUntilReminder({secondsSinceMidnight: 20 * H, reminderHour: 20}), 24 * H);
    assertEqual(secondsUntilReminder({secondsSinceMidnight: 21 * H + 30 * 60, reminderHour: 20}), 22 * H + 30 * 60);
});

test('across midnight', () => {
    assertEqual(secondsUntilReminder({secondsSinceMidnight: 24 * H - 1, reminderHour: 20}), 20 * H + 1);
    assertEqual(secondsUntilReminder({secondsSinceMidnight: 0, reminderHour: 20}), 20 * H);
});

test('reminder hour defaults to REMINDER_HOUR for the schedule', () => {
    assertEqual(secondsUntilReminder({secondsSinceMidnight: 0}), REMINDER_HOUR * H);
});

// state file

test('state round trip', () => {
    assertEqual(parseState(serializeState({lastRemindedIso: '2026-10-25'})), {lastRemindedIso: '2026-10-25'});
});

test('missing or invalid state means never reminded', () => {
    for (const text of [null, '', 'not json', '[]', 'null', '{}', '{"last_reminded":42}', '{"last_reminded":"2026-13-40"}'])
        assertEqual(parseState(text), {lastRemindedIso: null}, `for ${text}`);
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
