# EduSphere AI — Sprint 1: School Administration Core

**Version:** 1.0 · **Target:** one THCS pilot (grades 6–9) · **Status:** integrated development implementation; automated checks passed, manual acceptance pending.

## Delivery overview

Sprint 1 extends the existing Sprint 0 v2 React + Django + PostgreSQL monorepo; it does **not** merge Teacher, Parent or Student Expo apps. Separate mobile apps remain in `apps/teacher-mobile`, `apps/parent-mobile` and `apps/student-mobile`.

### Implemented user workflows

| Workflow | React Admin Web | REST API | Auth / audit | Status |
|---|---|---|---|---|
| School Admin login + tenant selection | Yes | JWT + `/me/` | role gate | Prototype |
| Dashboard counters | Yes | `admin/dashboard/` | admin only | Implemented |
| Create/list academic year | Yes | `academic-years/` | admin write + audit | Implemented |
| Create/list subject | Yes | `subjects/` | admin write + audit | Implemented |
| Create/list staff account with teacher/academic role | Yes | `staff/` | admin write + audit | **No invitation activation yet** |
| Create/list/update classroom | Create/list | `classrooms/`, `classrooms/{id}/` | admin write + audit | Implemented |
| Create/list/update/archive student | Create/list | `students/`, `students/{id}/edit/`, `students/{id}/archive/` | admin write + audit | Edit/archive API only |
| Create/list/end enrollment | Yes | `enrollments/`, `enrollments/list/`, `enrollments/{id}/end/` | admin write + audit | Implemented |
| Create/list/end teaching assignment | Yes | `teacher-assignments/`, `teacher-assignments/list/`, `teacher-assignments/{id}/end/` | admin write + audit | Implemented |
| Create guardian account; link and verify | Yes | `guardian-accounts/`, `guardian-links/`, `guardian-links/list/`, `guardian-links/{id}/verify/` | admin write + audit | **Verification currently acknowledgement-only** |
| Audit events list | Yes | `audit-events/` | admin only | Implemented |

### Deferred to a subsequent sprint / release gates

- Secure invite/activation/reset flow for newly created accounts. New staff/guardian accounts have **unusable passwords** and **cannot log in**.
- Formal identity/evidence verification and revocation UI for guardians; `evidence_checked=true` is only a **demo acknowledgement** and is insufficient for a real school.
- Data import templates and safe CSV/Excel import with preview, duplicate detection and rollback.
- Server-side search, pagination and filters (list caps 100–500 for current pilot prototype).
- Existing Sprint 0 migrations are preserved and committed. Sprint 1 introduces no schema changes; `makemigrations --check --dry-run` passes.
- Browser refresh token management and production OIDC/BFF authentication; no student personal data yet.
- Hardened database isolation (e.g., PostgreSQL RLS), signed tenant context, cross-tenant FK invariant validation at the model/service level.
- Full TypeScript checks, three React production builds and PostgreSQL integration tests passed. New Admin UI acceptance and device regression remain pending; see Test Plan.
- Accessibility review, load tests and operational observability. Existing CI retains frozen lockfile, pinned Python dependencies and PostgreSQL tests.

## User story highlights

- **US-S1-01** As School Admin, I can see only my school's dashboard; tenant B cannot be viewed using my tenant A token.
- **US-S1-02** As School Admin, I can create a school year with starts_on < ends_on; duplicate label is rejected.
- **US-S1-03** As School Admin, I can create THCS classes 6–9 for an existing year in my school, rejecting foreign-school year IDs.
- **US-S1-04** As School Admin, I can create a student with a unique student_code in my school and update their name safely.
- **US-S1-05** As School Admin, I can create a staff account/role; the account remains unable to sign in until activated.
- **US-S1-06** As School Admin, I can assign students to a class; multiple simultaneously active enrollments must be rejected.
- **US-S1-07** As School Admin, I can assign a homeroom or subject teacher only with a valid matching teacher membership.
- **US-S1-08** As School Admin, I can end an enrollment/teacher assignment, immediately revoking corresponding view rights.
- **US-S1-09** As School Admin, I can create and confirm a guardian link; no academic access before link verification.
- **US-S1-10** As School Admin, I can inspect recent action logs per school, without exposing other schools' logs.

## Authorization model

`JWT identity` → `X-Tenant-ID` → validate membership / tenant status → role-based action permission → scoped queryset → relation check → mutation → audit.

This is a backend rule, not a frontend menu rule. Admin capabilities require `SCHOOL_ADMIN`; parent/student/teacher roles cannot mutate administration records. Cross-tenant failures intentionally return 404. The audit log stores action and object IDs but not before/after snapshots.

## Data model used

Preserves Sprint 0 ORM models:
- `identity.Account`
- `schools.Tenant`, `Membership`, `AuditEvent`
- `academics.AcademicYear`, `Subject`, `Classroom`, `Student`, `Enrollment`, `TeacherAssignment`, `GuardianLink`, `StudentAccount`.

No new ORM tables were introduced in Sprint 1. API workflows use the existing schema. Domain-specific validation is implemented at the API boundary and should also move to services/DB constraints before production.

## UI/UX design decisions

- Admin web: permanent left-side navigation, school context switcher, page headline + primary CRUD action, metric cards, scoped tables.
- Contextual forms with fixed labels and `required` validation, mobile-responsive layout, confirm-to-revoke actions.
- Explicit async loading/errors/success banners; archive/revoke is not mislabeled as physical deletion.
- Color system: ink/navy, blue primary actions, subtle surfaces. Status indicators reserved for meaningful states.
- Session safety: expiry timer, 401 logout and stale response invalidation on logout/school switch are preserved.
- Data safety: only synthetic records. Login demo shows password solely to aid local evaluation; remove before pilot.

## Quick start

```bash
# Requirements: Docker Desktop, Node 22+, Corepack + pnpm 10, Mac or Windows
corepack enable
docker compose up --build -d
docker compose exec backend python manage.py seed_demo
pnpm install --frozen-lockfile
pnpm dev:admin  # http://localhost:5173
```

Demo credentials: `admin_a` / `DemoOnly!ChangeMe123`; tenant `demo-a`. **Never deploy demo credentials or data to a production environment.**

### Smoke checks

```bash
bash scripts/verify_sprint1.sh
# With Django dependencies & a configured test environment:
cd backend && DJANGO_DEBUG=1 python manage.py test apps.academics.tests
# With Node dependencies:
pnpm typecheck && pnpm build:web
```

## Next: Sprint 2 proposal

Prioritize user activation, safe CSV import, parent link evidence/approval/revoke, consistent pagination, stronger isolation invariants. After gates pass, move to Attendance + Leave Requests.

## Integration corrections (2026-10-20)

The ZIP was selectively integrated into the verified Sprint 0 branch. Existing migrations, dependency lockfile, CORS configuration, mobile setup and session controls remain intact.

- Administrative relationship history is restricted to School Admin.
- Enrollments and assignments require a current school year and expire at its end. Teacher read scopes also enforce the year dates.
- Student/class row locks serialize concurrent enrollment and homeroom assignment requests on PostgreSQL. Duplicate requests return 400.
- Classroom year cannot change after any enrollment or assignment history exists.
- Staff/guardian creation rejects malformed input and explicitly reports pending activation.
- Writes and audit events share a transaction; audit failure rolls back the write.

The attached PDF and architecture diagrams are original reference artifacts. This document and the test plan describe the integrated source and actual verification.
