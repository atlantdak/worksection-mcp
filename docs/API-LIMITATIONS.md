# Worksection API limitations

Behaviour of the upstream Worksection API that shapes how this server works.
Each entry records how it was confirmed, so unverified assumptions are never
mistaken for tested facts. This project has not had access to a live
Worksection account or API credentials, so every entry below is labelled
`not verified — assumed` unless it is a plain fact about the wire format
(request signing, response envelope shape) that follows directly from the
published API documentation rather than from having watched the server
respond.

## Pagination

There is no cursor or offset pagination for task and project listings that
this server relies on; `get_all_tasks`, `get_tasks` and `get_projects` all
call actions that are expected to return the full matching set in one
response. Tools that could plausibly return a very large result set
(`search_tasks`) bound their own output with a `limit` parameter, and any
tool result that turns out to be large regardless is caught by the
response-offload mechanism (`offload.py`) rather than truncated silently.

Verified: not verified — assumed; no live listing has been made against an
account large enough to hit an internal cap, if one exists.

## Status filtering combined with a project scope

The plan for this server documented a report that filtering by status while
also scoping to a project can return rows that do not match the requested
status. Every listing tool (`get_all_tasks`, `get_tasks`, `search_tasks`,
`get_tasks_by_status`, `get_tasks_by_priority`, `get_overdue_tasks`)
therefore re-applies status (and, where relevant, assignee, text, priority
and due-date) filters locally in `filtering.filter_tasks`, so the result is
correct whether or not the server-side filter behaves as requested. The
server-side `status` query parameter is still sent, on the assumption that a
narrower upstream result is a helpful optimisation even if it cannot be
trusted on its own.

Verified: not verified — assumed; this is a documented concern this project
inherited, not a failure this project's own code reproduced against a live
account. The local re-filter (`filtering.py`) is exercised by the unit and
mocked-transport test suite, not by a real mismatching response.

## Dates

Dates are assumed to be exchanged with the API as `DD.MM.YYYY`. Tools accept
`YYYY-MM-DD` as well and normalise before sending
(`validators.normalize_date`). Responses are parsed leniently: an unparsable
date is treated as absent rather than raising, on the theory that a
malformed date should degrade a feature (for example, overdue-task sorting)
rather than break the whole call.

Verified: not verified — assumed; the outbound `DD.MM.YYYY` format and the
lenient inbound parsing are both implemented and covered by
`tests/test_validators.py` against fixed strings, not against a live
request or response.

## Rate limiting

The API is assumed to answer with HTTP 429 under load, optionally with a
`Retry-After` header. `AdaptiveRateLimiter` (`http/rate_limiter.py`) halves
its pace on each 429, honours `Retry-After` when present, and eases back up
after a run of successes. `WorksectionClient` retries a 429 or a 5xx
response up to `max_retries` times with the same backoff.

Verified: not verified — assumed; the limiter and retry logic are unit
tested against a scripted transport that returns manufactured 429 and 5xx
responses, never against real throttling from the live service.

## Request signing (admin API key mode)

Each admin-key request is signed with `md5(page + action + api_key)`
(`auth/admin_key.py::compute_admin_hash`). The key itself is never sent as a
query parameter, only its hash. Every other value is handed to httpx as a
parameter mapping so it is percent-encoded rather than interpolated into the
URL by hand. This scheme is transcribed from Worksection's published admin
API documentation, not reverse-engineered from traffic.

Verified: documentation only; the hash construction has never been checked
against a real admin API response, so a mismatch between this
implementation and the live service (wrong field order, wrong encoding,
case sensitivity of the hex digest) would not have been caught yet.

## Response envelopes

Successful responses are assumed to carry `{"status": "ok", ...}` (a small
set of alternate "ok" spellings is also accepted). The payload may be
nested under a `data` key, or spread across the top level of the same
object (for example `{"status": "ok", "id": 5}` after a create action).
`extract_payload` in `http/client.py` handles both shapes and raises
`WorksectionAPIError` when the status is anything else.

Verified: not verified — assumed; both envelope shapes are exercised by
mocked-transport tests with fabricated JSON bodies, never by a real
response from the API.

## Verification status

Nothing in this document has been checked against a live call to the
Worksection API. Two points in this project's task list called for an
optional manual smoke check against a real account — a `health_check` round
trip after the first project tools were built, and an OAuth browser login
after the auth tools were built — and both were deferred in the absence of
real Worksection credentials in the development environment. Everything
below was implemented from the plan's recorded assumptions and exercised
only against a mocked HTTP transport in the test suite.

| Area | How it was checked |
|---|---|
| Pagination behaviour / internal cap | Not checked. No live listing call has been made. |
| Status + project-scope filtering quirk | Not checked directly; worked around unconditionally by client-side re-filtering, which is covered by mocked-transport and unit tests. |
| Date format on the wire | Not checked; outbound formatting and inbound leniency are unit tested against fixed strings. |
| Rate limiting (429 handling, backoff) | Not checked against real throttling; the limiter and retry path are unit tested against a scripted transport. |
| Admin-key request signing | Not checked against a live response; the hash formula matches the published API documentation. |
| Response envelope shape | Not checked against a live response; both known shapes are covered by mocked-transport tests. |
| `health_check` tool round trip | Deferred manual smoke check (documented in the Task 12 implementation notes); never run against a live account. |
| OAuth browser login | Deferred manual smoke check (documented in the Task 32 implementation notes); never run against a live account. |

If this server is ever run against a real Worksection account, the entries
above are the first things to re-verify, in roughly this order: response
envelope shape and request signing (both would fail loudly and immediately
if wrong), then the status/project-scope filtering quirk and date format
(both would fail quietly, returning wrong data rather than an error), then
pagination and rate limiting (both would only surface under load or with a
large account). Update the `Verified:` line for an entry to `live call on
YYYY-MM-DD` only once it has actually been exercised that way, and describe
what was observed, including anything that turned out to differ from the
assumption recorded here.
