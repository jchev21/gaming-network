# Deferred: event date/time entry — offline design and acceptance contract

Status: **DESIGN ONLY / NOT IMPLEMENTED / NOT DEPLOYED**. Prepared 2026-11-07. No live Discord command, calendar data, Railway service, X workflow, or authentication is modified.

## Why this is separate

The master checklist asks for clearer Discord dashboard date entry. Current Discord `/hubview`, `/dashboard`, existing calendar events, and server permissions must continue unchanged during the friends/family preview. This document defines an isolated, reviewable future enhancement rather than patching live bot handlers.

## Input contract

An event editor should capture a **calendar date**, **local wall-clock time**, and an explicit **IANA timezone** (e.g. `America/Chicago`) as separate fields. Avoid guessing the timezone from a browser, guild locale, or Railway server. Use strict `YYYY-MM-DD` and 24-hour `HH:mm` parsing; reject invalid dates (e.g. February 30), leap-day errors, malformed times, and empty timezone.

At save, convert the selected wall-clock value into an unambiguous UTC instant and persist both the UTC instant and the original IANA timezone, so users can view it in their chosen zone later. DST gaps (nonexistent local times) must be rejected with a clear correction prompt; DST folds (two possible UTC instants) require an explicit earlier/later choice. Never silently shift a user-selected time by an hour.

A proposed event payload (not a live API) is:

```json
{
  "title": "Sample game night",
  "localDate": "2026-11-14",
  "localTime": "19:30",
  "timeZone": "America/Chicago",
  "startsAtUtc": "2026-11-15T01:30:00.000Z",
  "visibility": "guild"
}
```

Treat title as untrusted text: length limits, escaping, no mentions by default, and no sensitive access codes in event descriptions. Server must authorize the editor against guild permissions and prevent cross-guild edits. Revalidate all fields server-side even when a UI picker is used.

## UX and backwards compatibility

1. Date picker, time picker, timezone selector, and confirmation preview should be visible together before save; keyboard and mobile input must work.
2. Display the local time with timezone abbreviation **and** UTC offset in confirmation, especially near DST transitions.
3. Existing event records should remain readable; migration should be additive and reversible, never overwrite unknown legacy date formats automatically.
4. Keep `/hubview`, `/dashboard`, refresh buttons, calendar displays and existing event creation working until an explicit feature-flagged integration is reviewed.
5. Do not broadcast announcements, alter Discord roles, write calendar entries or notify members from this prototype.

## Offline acceptance matrix (not executed)

| Case | Expected result |
| --- | --- |
| `2026-11-14` at `19:30` in `America/Chicago` | `2026-11-15T01:30:00.000Z` |
| `2028-02-29` | Accepted leap day |
| `2027-02-29` | Rejected invalid day |
| `2026-04-31` | Rejected invalid day |
| `2026-11-01 01:30 America/New_York` | Explicit ambiguous DST choice required |
| `2027-03-14 02:30 America/New_York` | Rejected nonexistent DST time |
| `2026-11-14 24:00` | Rejected invalid time |
| `2026-11-14 19:60` | Rejected invalid minute |
| Empty or unknown timezone | Rejected |
| Event created in guild A, edited by guild B | Rejected authorization |
| Existing legacy event | Display preserved, no implicit migration |
| Attempt to include `@everyone` or a join secret in title | Safe text rendering; no ping or secret disclosure |

## Future implementation gate

Build a pure date/time conversion function with deterministic offline unit tests, including DST disambiguation and strict round trips; then integrate a **feature-flagged** editor behind the existing authorized event flow. Validate with real repo CI and Discord UI manual acceptance. No automatic production deployment or migration. **Issue #46 remains DEFERRED**: secure X-to-Discord account linking and Member-role gating must not be enabled or conflated with standalone X sign-in while preview approval is unsettled.
