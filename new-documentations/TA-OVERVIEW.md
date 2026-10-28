# TA overview integration

The TA overview reuses `GET /api/v1/courses/my-courses`, paginated
`GET /api/v1/sessions/?course_id=...`, `GET /api/v1/stats/sessions/{session_id}`,
`GET /api/v1/sessions/{session_id}/attendance`, `GET /api/v1/checkins/flagged`,
`GET /api/v1/checkins/{checkin_id}`, `GET /api/v1/checkins/session/{session_id}`,
and `POST /api/v1/checkins/{checkin_id}/review`.

No new endpoint, table, or permission is introduced. Instructor-only overview,
course/student analytics, exports, and the admin audit API are not called.
The existing TA assignment checks apply before any statistics or review summaries
are returned. `/docs` remains unchanged.

## Additive session-statistics fields

`GET /stats/sessions/{session_id}` retains its existing fields and adds:

| Field | Meaning |
|---|---|
| `submitted_count` | Alias of `checked_in`; all five verification statuses count |
| `expected_count` | Alias of `total_enrolled`; current active course enrollments |
| `scored_count` | Number of non-null risk scores, including valid zero scores |
| `timezone` | Effective `APP_TIMEZONE`, default `Asia/Singapore` |
| `server_time` | UTC timestamp with `Z`, captured for this response |
| `checkin_opens_at`, `checkin_closes_at` | Configured UTC check-in window, with `Z` |
| `scheduled_end`, `actual_end` | Session end metadata; actual end is nullable |
| `timeline_bucket_minutes` | `5`, preserving the existing bucket width |
| `pre_opening_count` | Records clamped to minute-zero because they predate opening |
| `today` | Selected course's local-day session total and lifecycle breakdown |
| `recent_review_activity` | At most five real, selected-session manual review events |

Example extension fields (illustrative; not preview data in the application):

```json
{
  "submitted_count": 5,
  "expected_count": 6,
  "scored_count": 5,
  "timezone": "Asia/Singapore",
  "server_time": "2026-10-28T02:02:00Z",
  "checkin_opens_at": "2026-10-28T01:45:00Z",
  "checkin_closes_at": "2026-10-28T02:30:00Z",
  "scheduled_end": "2026-10-28T03:00:00",
  "actual_end": null,
  "timeline_bucket_minutes": 5,
  "pre_opening_count": 1,
  "today": {
    "date": "2026-10-28",
    "total": 2,
    "breakdown": { "active": 1, "scheduled": 1, "closed": 0, "cancelled": 0 }
  },
  "recent_review_activity": [
    {
      "id": "event-uuid",
      "session_id": "session-uuid",
      "session_name": "Lecture 9",
      "action": "checkin_reviewed",
      "decision": "approved",
      "previous_status": "appealed",
      "timestamp": "2026-10-28T02:00:00Z"
    }
  ]
}
```

## Calculations and boundaries

- The unique `checkins(session_id, student_id)` index enforces one effective record
  per student/session. Failed attempts are not separate attendance records. All
  cards, status counts, and timeline use those same stored check-in rows.
- Check-in rate is submitted / current active enrollments. With no denominator,
  the UI shows `Unavailable`. This is distinct from the historical enrollment and
  in-window presence policy of the full attendance roster. The overview displays
  only its submitted rows, including retained early/out-of-window submissions.
- Needs review is flagged + appealed; pending does not count. The same five status
  counts form the donut and reconcile with submitted total, independent of filters.
- Risk average and risk distribution now exclude missing scores. Existing
  `average_risk_score=0` is retained when none exist for compatibility; the UI uses
  `scored_count=0` to show `No scored check-ins`. Current schema requires a non-null
  risk score; a legacy zero/default cannot be distinguished from a measured zero.
- Today's sessions are course-scoped and include all four lifecycle statuses.
  Sessions whose scheduled start is in local `[midnight, next midnight)` count.
- Timeline counts are per five-minute half-open interval anchored at
  `checkin_opens_at`, never cumulative. Pre-opening records are counted in bucket
  zero and identified by the tooltip. The display ends at the earlier configured
  check-in close, scheduled end, or actual end, but extends to retain any returned
  out-of-window record. Omitted elapsed buckets inside the window become zero;
  future buckets remain null. The current active bucket is marked `In progress`.
- Review activity comes only from `checkin_reviewed` audit entries joined to
  check-ins in this authorised session, filtered before the five-event limit.
  Only event/session identity, decision, previous status, and timestamp are exposed;
  no IP, reviewer identity, notes, or unrelated audit events are returned. Missing
  historical audit events are not reconstructed from current statuses.
- Active session statistics/rosters poll every 15 seconds; other sessions every
  60 seconds, with React Query's default pause when hidden. Selected-resource query
  keys and abort signals prevent obsolete results appearing under a new selection.
  A successful review invalidates both session statistics and the shared roster.

## Limitations

Assigned courses currently use the existing `/courses/my-courses` extension, which
is not listed in the main API specification. The main specification also predates
the existing `course_assistants` relation and describes global/fail-closed TA rules
in some roster sections; the implementation continues to enforce the established
assigned-course rules. None of those permissions are broadened here.
