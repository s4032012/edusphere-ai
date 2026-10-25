# EduSphere AI — Sprint 5 Implementation Notes

**Date:** 26 October 2026
**Scope:** Communication & Notification System, one-THCS pilot, synthetic records only.
**Base:** working Sprint 4 branch `sprint-4/assignment-homework`, including Expo SDK 58. No change to Django + DRF/PostgreSQL, React Web or three Expo apps.

## Feature coverage

| Capability | Backend | UI | Limitation |
|---|---|---|---|
| Announcement draft / school, grade, class scope / publish | Yes | Admin Web, Teacher Web, Teacher Mobile | No scheduled publishing, no editing published notice |
| Announcement recipient snapshot and read status | Yes | Web + 3 mobile apps | Pilot fanout up to 2,500 users; query not optimized for many tenants |
| Verified parent ↔ assigned teacher conversation | Yes | Teacher Web/Mobile, Parent Mobile | Text only, no real-time socket; users refresh to get updates |
| Message idempotency | Unique key + get_or_create | Client-provided UUID | PostgreSQL concurrent retry tests; load testing remains |
| Parent support tickets | Yes | Parent Mobile; Support Web/Admin Web | Staff assignment is first-response claim; no SLA or escalation automation |
| Ticket replies/status workflow | Yes | Support Web/Admin Web, Parent Mobile | No attachments; parent cannot change state directly |
| Notification inbox, read/unread | Yes (reuses Sprint 2 outbox) | 3 mobile apps, Admin Web | No push, FCM/APNs, email or SMS delivery |
| Authorization & audit | Scoped APIs, entity-level relationships, action audit | UI contextual navigation | Still needs security review and penetration tests |

## Backend modules

- `backend/apps/communications/models.py`: 9 new tables: Announcement, AnnouncementRecipient, AnnouncementRead, Conversation, ConversationMessage, ConversationRead, SupportTicket, TicketReply, NotificationReceipt.
- `views.py`: tenant-specific REST endpoints; relationship checks happen on every conversation read/write.
- `rules.py`: pure validation and state transitions for testability.
- `urls.py`: `/api/v1/comms/` prefixes avoid collision with inherited `/api/v1/notifications/`.
- `backend/config/{urls.py,settings.py}`: module registration and authenticated throttle.
- `backend/apps/identity/management/commands/seed_demo.py`: `support_a`, `support_b` added to synthetic seed.

## Security and privacy decisions

1. **No public teacher directory.** `/students/{id}/contacts/` checks live guardian/teacher relationships.
2. **No arbitrary direct messages.** Conversation key is `(tenant, student, teacher, guardian)`, and authorization is re-evaluated on each request.
3. **No administration backdoor to private messages.** School Admin and Support Staff use ticket workflows; they cannot read conversations by role alone.
4. **Announcements:** `AnnouncementRecipient` snapshots the publication audience; every read also checks current visibility. Newcomers do not automatically see old targeted announcements; revoked guardians lose access.
5. **Notification payload contains metadata only.** No message body or ticket details are copied to the outbox event.
6. **Text only.** Files, external URLs and media are not implemented until private storage, scanning and retention policies exist.
7. **Immutable published notices** in this sprint. Correction/cancellation workflow requires explicit design.
8. **School isolation:** every ORM lookup is scoped to the tenant and target student/class relationship.

## API examples (all require Bearer JWT + X-Tenant-ID)

| Method | Path | Allowed actions |
|---|---|---|
| GET/POST | `/api/v1/comms/announcements/` | List accessible; author creates scoped draft |
| POST | `/api/v1/comms/announcements/{id}/publish/` | School leadership or valid class GVCN |
| POST | `/api/v1/comms/announcements/{id}/read/` | One intended recipient |
| GET | `/api/v1/comms/students/{id}/contacts/` | Verified guardian or assigned teacher only |
| GET/POST | `/api/v1/comms/conversations/` | List own / create eligible conversation |
| GET/POST | `/api/v1/comms/conversations/{id}/messages/` | Read latest 100 / send idempotent text |
| POST | `/api/v1/comms/conversations/{id}/read/` | Mark own conversation read |
| GET/POST | `/api/v1/comms/tickets/` | Staff sees school queue; guardian sees own / creates own |
| GET | `/api/v1/comms/tickets/{id}/` | Requester or school support staff |
| POST | `/api/v1/comms/tickets/{id}/reply/` | Requester or school support staff |
| POST | `/api/v1/comms/tickets/{id}/transition/` | Support/Admin staff only |
| GET | `/api/v1/comms/notifications/` | Current recipient's inbox |
| POST | `/api/v1/comms/notifications/{id}/read/` | Current recipient only |

### Send a teacher message

```http
POST /api/v1/comms/conversations/{conversation_uuid}/messages/
Authorization: Bearer <jwt>
X-Tenant-ID: <school_uuid>
Content-Type: application/json

{"body":"Cô có thể giúp gia đình xem lại bài toán số 3 không?","client_key":"6a0b6db7-c808-4a89-8cb4-962d9dc33b37"}
```

## Ticket state model

`OPEN → IN_PROGRESS → RESOLVED → CLOSED`, with `OPEN → RESOLVED`, `IN_PROGRESS → OPEN` and `RESOLVED → IN_PROGRESS` permitted for authorized staff. `CLOSED` has no reopening in this sprint.

## Verification

```bash
bash scripts/verify_sprint5.sh
# Integration requires installed deps and test DB; example:
cd backend
python manage.py test apps.communications.tests.test_api --verbosity 2
```

Pure tests + executable API client contract tests are not a replacement for Django integration. Full suite status is recorded in delivery manifest.

## Production blockers inherited and newly introduced

- **Versioned migration `communications.0001_initial` is committed with the existing migration chain.** Clean-schema tests and isolated Sprint 4 upgrade/rollback/reapply passed. Never roll back communications on a database whose messages must be retained.
- No production-auth refresh or BFF / mobile token lifecycle; no device enrollment or revoke-all-session UX.
- No real push/email/SMS sending, retries, dead-letter queues, or observability of delivery outcomes; outbox records are not deliveries.
- No attachment storage, virus scanning, moderation/report-abuse process, retention enforcement, consent/guardian dispute management.
- No scalable pagination/cursors, async fan-out, WebSocket/SSE. Pilot fanout currently synchronous in a DB transaction.
- Indexes, per-user/tenant communication throttle and concurrency checks are included. Load tests, distributed throttling, accessibility, background/resume, locale/timezone QA and signed device builds remain.
- No proven regulatory compliance. Conduct local legal/privacy impact assessment and partner-school DPA before processing minors' data.
- Teacher Mobile uses a class selector; all clients save draft and publish separately.

## Recommended next milestone

**Sprint 6: Parent & Student Dashboard + AI Readiness.** Prioritize integrated timeline, read-only parent/student status, verified data contracts, event telemetry and consent gates before connecting any LLM to children's records.


## Run the integrated implementation

```bash
pnpm install --frozen-lockfile
docker compose exec backend python manage.py migrate --noinput
docker compose exec backend python manage.py seed_demo
pnpm dev:support  # 127.0.0.1:5177, support_a / DemoOnly!ChangeMe123
```

`seed_demo` adds support accounts to the two existing synthetic schools without resetting existing passwords or links. Admin Web stays on 5173; Teacher Web on 5174. Launch mobile apps in separate terminals: `pnpm dev:teacher --clear`, `pnpm dev:parent --clear`, `pnpm dev:student --clear`. Keep each app's `.env` and the existing SDK 58 Expo Go.

The backend must pick up CORS for port 5177. If currently using the LAN override, restart **with the same override**, substituting the Mac's current IP:

```bash
DJANGO_BIND_IP=<MAC_LAN_IP> DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1,<MAC_LAN_IP> \
  docker compose -f compose.yaml -f compose.mobile-lan.yaml up -d --no-deps backend
```

For localhost-only development: `docker compose up -d --no-deps backend`. Do not use that command to replace an existing LAN binding needed by phones.

## Contracts and implementation changes from the supplied kit

- Shared `packages/communications-ui` controller and web/native views; each mount is keyed by token + school. Pending requests cannot populate a new session. 401 clears the session; 403/404 clears sensitive communication views. Tokens remain in the existing app auth lifecycle.
- `ConversationRead` advances only through the `last_message_id` actually fetched by the client; `null` does not advance it. Incoming messages after that point remain unread. Message UUIDs are normalized, and the composer retains the retry key until acknowledgement.
- Ticket transitions require `{state, expected_version}`; stale writes return **409**. Replies increment the version. The first staff reply claims an unassigned ticket and moves OPEN to IN_PROGRESS. Every distinct transition has its own outbox deduplication key, including repeated RESOLVED transitions after reopening.
- All communication mutations acquire the existing tenant row lock before validating/writing. The pilot serializes mutations per school. Publication, audience snapshot, outbox and audit are atomic. This is not a scalable fanout worker.
- Relationship policies in `policy.py` match assignment kind to active role, enforce current school year/enrollment, and revalidate linked-student tickets and inbox events. Unknown notification types are hidden. Prior attendance/leave/grade/homework events keep their live authorization checks.
- School announcements include eligible current students, verified guardians, assigned teachers and operational school roles; an active but unverified parent membership alone is insufficient. Published content is immutable; no delete/edit endpoint exists.
- Throttle is limited to communication endpoints: 120 requests/minute/account/school using Django cache. Production requires a shared cache and abuse handling. Other sprint endpoints are unaffected.
- Lists show at most 100 accessible recent items from bounded candidate windows (300 notices/events, 100 conversations/tickets); older items can fall outside the window. Messages show latest 100; ticket replies show latest 150. No history pagination in this sprint.
- Reading a notice or conversation and reading its inbox event are separate receipts. QUEUED is storage state, never proof of external delivery.
