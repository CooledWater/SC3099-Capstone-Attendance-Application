// Compile module1-frontend/lib/time.ts to /private/tmp/saiv-frontend-time-check first.
const { test } = require('node:test');
const assert = require('node:assert/strict');
const { parseApiDateTime, formatSingaporeDateTime, singaporeGreeting } = require('/private/tmp/saiv-frontend-time-check/time.js');
for (const zone of ['UTC', 'Asia/Singapore', 'America/Los_Angeles']) {
  test(`API UTC parsing and SGT display with browser timezone ${zone}`, () => {
    process.env.TZ = zone;
    const utc = '2026-10-22T01:30:00';
    assert.equal(parseApiDateTime(utc).toISOString(), `${utc}.000Z`);
    assert.equal(parseApiDateTime('2026-10-22T09:30:00+08:00').toISOString(), `${utc}.000Z`);
    assert.equal(formatSingaporeDateTime(utc), formatSingaporeDateTime(`${utc}Z`));
    assert.match(formatSingaporeDateTime(utc, { hour: '2-digit', minute: '2-digit', hourCycle: 'h23' }), /09:30 SGT/);
    assert.match(formatSingaporeDateTime('2026-10-22T20:00:00Z'), /23 Oct 2026/);
    assert.equal(singaporeGreeting(new Date(`${utc}Z`)), 'morning');
    assert.equal(singaporeGreeting(new Date('2026-10-22T05:00:00Z')), 'afternoon');
    assert.equal(singaporeGreeting(new Date('2026-10-22T12:00:00Z')), 'evening');
    assert.equal(formatSingaporeDateTime('invalid'), 'Invalid time');
  });
}
