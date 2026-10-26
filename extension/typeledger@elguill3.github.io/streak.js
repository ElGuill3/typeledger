// Pure summary and streak logic. No gi:// or shell imports, so it also runs
// under plain `gjs -m` for tests.

export const SCHEMA_VERSION = 1;

const ISO_DAY = /^(\d{4})-(\d{2})-(\d{2})$/;
const DAY_MS = 24 * 60 * 60 * 1000;

function isCount(value) {
    return Number.isInteger(value) && value >= 0;
}

function isFiniteNumber(value) {
    return typeof value === 'number' && Number.isFinite(value);
}

// Days are handled as UTC midnights so that day arithmetic never trips over
// daylight saving changes.
function dayToUtc(iso) {
    const match = typeof iso === 'string' ? ISO_DAY.exec(iso) : null;
    if (!match)
        return null;
    const [year, month, day] = match.slice(1).map(Number);
    const time = Date.UTC(year, month - 1, day);
    const check = new Date(time);
    if (check.getUTCFullYear() !== year || check.getUTCMonth() !== month - 1 || check.getUTCDate() !== day)
        return null;
    return time;
}

/**
 * Parse and validate a schema v1 summary.
 *
 * @param {string} text - JSON text of summary.json
 * @returns {object|null} the validated summary, or null when invalid or unsupported
 */
export function parseSummary(text) {
    if (typeof text !== 'string')
        return null;

    let data;
    try {
        data = JSON.parse(text);
    } catch {
        return null;
    }
    if (data === null || typeof data !== 'object' || Array.isArray(data))
        return null;
    if (data.schema !== SCHEMA_VERSION)
        return null;

    if (typeof data.generated_at !== 'string' || Number.isNaN(Date.parse(data.generated_at)))
        return null;
    if (!Array.isArray(data.practiced_days) || !data.practiced_days.every(day => dayToUtc(day) !== null))
        return null;
    for (const key of ['longest_streak', 'total_sessions', 'recent_days', 'recent_sessions']) {
        if (!isCount(data[key]))
            return null;
    }
    if (!isFiniteNumber(data.recent_avg_wpm) || data.recent_avg_wpm < 0)
        return null;
    if (!isFiniteNumber(data.recent_avg_accuracy) || data.recent_avg_accuracy < 0 || data.recent_avg_accuracy > 1)
        return null;

    return {
        schema: data.schema,
        generated_at: data.generated_at,
        practiced_days: [...data.practiced_days],
        longest_streak: data.longest_streak,
        total_sessions: data.total_sessions,
        recent_days: data.recent_days,
        recent_avg_wpm: data.recent_avg_wpm,
        recent_avg_accuracy: data.recent_avg_accuracy,
        recent_sessions: data.recent_sessions,
    };
}

/**
 * @param {Array<object|null>} summaries - parsed summaries, null for missing or invalid files
 * @returns {object|null} the summary with the newest generated_at, or null
 */
export function newestSummary(summaries) {
    let newest = null;
    for (const summary of summaries) {
        if (summary && (!newest || Date.parse(summary.generated_at) > Date.parse(newest.generated_at)))
            newest = summary;
    }
    return newest;
}

/**
 * Current streak as of `todayIso`: consecutive practiced days ending today, or
 * ending yesterday when today has no practice yet (the streak stays alive
 * until the day ends). Duplicates and order do not matter; future days are
 * ignored.
 *
 * @param {string[]} practicedDays - YYYY-MM-DD strings
 * @param {string} todayIso - today's local date as YYYY-MM-DD
 * @returns {{current: number, practicedToday: boolean}}
 */
export function computeStreak(practicedDays, todayIso) {
    const today = dayToUtc(todayIso);
    if (today === null || !Array.isArray(practicedDays))
        return {current: 0, practicedToday: false};

    const practiced = new Set();
    for (const iso of practicedDays) {
        const day = dayToUtc(iso);
        if (day !== null && day <= today)
            practiced.add(day);
    }

    const practicedToday = practiced.has(today);
    let current = 0;
    let day = practicedToday ? today : today - DAY_MS;
    while (practiced.has(day)) {
        current++;
        day -= DAY_MS;
    }
    return {current, practicedToday};
}

/**
 * @param {Date} date
 * @returns {string} the local calendar date as YYYY-MM-DD
 */
export function localIsoDate(date) {
    const pad = n => String(n).padStart(2, '0');
    return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`;
}
