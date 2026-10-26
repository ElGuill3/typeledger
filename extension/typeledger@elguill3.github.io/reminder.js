// Pure daily reminder logic. No gi:// or shell imports, so it also runs
// under plain `gjs -m` for tests.

// Local hour (0-23) from which an unpracticed day gets its reminder.
export const REMINDER_HOUR = 20;

const ISO_DAY = /^(\d{4})-(\d{2})-(\d{2})$/;
const DAY_S = 24 * 60 * 60;

function isIsoDay(iso) {
    const match = typeof iso === 'string' ? ISO_DAY.exec(iso) : null;
    if (!match)
        return false;
    const [year, month, day] = match.slice(1).map(Number);
    const check = new Date(Date.UTC(year, month - 1, day));
    return check.getUTCFullYear() === year && check.getUTCMonth() === month - 1 && check.getUTCDate() === day;
}

/**
 * At most one reminder per local day, at or after the reminder hour, and only
 * while today has no practice.
 *
 * @param {object} params
 * @param {string} params.todayIso - today's local date as YYYY-MM-DD
 * @param {number} params.nowHour - current local hour, 0-23
 * @param {boolean} params.practicedToday
 * @param {string|null} params.lastRemindedIso - local date of the last reminder, if any
 * @param {number} [params.reminderHour]
 * @returns {boolean}
 */
export function shouldRemind({todayIso, nowHour, practicedToday, lastRemindedIso, reminderHour = REMINDER_HOUR}) {
    if (!isIsoDay(todayIso) || !Number.isFinite(nowHour))
        return false;
    return nowHour >= reminderHour && !practicedToday && lastRemindedIso !== todayIso;
}

/**
 * Seconds until the next reminder hour: later today, or tomorrow once it has
 * passed. Assumes 24-hour days; callers cap the wait so a daylight saving
 * change or a suspend only delays the check briefly.
 *
 * @param {object} params
 * @param {number} params.secondsSinceMidnight - local time of day in seconds
 * @param {number} [params.reminderHour]
 * @returns {number}
 */
export function secondsUntilReminder({secondsSinceMidnight, reminderHour = REMINDER_HOUR}) {
    const target = reminderHour * 60 * 60;
    if (secondsSinceMidnight < target)
        return target - secondsSinceMidnight;
    return DAY_S - secondsSinceMidnight + target;
}

/**
 * @param {string|null} text - JSON text of the state file
 * @returns {{lastRemindedIso: string|null}} never throws; invalid means never reminded
 */
export function parseState(text) {
    let data = null;
    try {
        data = typeof text === 'string' ? JSON.parse(text) : null;
    } catch {
        data = null;
    }
    const last = data !== null && typeof data === 'object' ? data.last_reminded : null;
    return {lastRemindedIso: isIsoDay(last) ? last : null};
}

/**
 * @param {{lastRemindedIso: string|null}} state
 * @returns {string} JSON text for the state file
 */
export function serializeState({lastRemindedIso}) {
    return JSON.stringify({last_reminded: lastRemindedIso});
}
