# Sprint 4 — delivery and verification

Date: 2026-10-24. Branch: `sprint-4/assignment-homework`, based on accepted Sprint 3 main.

## Delivered

- `apps.homework`: Assignment/Submission models, committed `0001_initial` migration, 11 REST operations, strict validation, audit and return-notification outbox.
- Teacher Web/Mobile: create/edit/publish/close, roster, feedback and optional formative score; GVCN read-only. Native mobile date/time picker matched to Expo 58.
- Student Mobile: list/detail, draft save, submit/resubmit, stale-version recovery, returned feedback. Parent Mobile: child switcher, reload, progress/feedback without answers.
- Shared typed API client, role-aware controls, session/selection guards and expiry handling.
- Hardening: tenant-serialized state changes including first creation, expected version for submission and grading, current-year/relationship checks, per-assignment multi-role privacy, revoked notification filtering. Prior sprint fixes and deployment settings preserved.
- Source report, diagrams, implementation/API/acceptance docs and verification script.

## Verified results

| Check | Result |
|---|---|
| PostgreSQL migration and drift check | Applied `homework.0001_initial`; no pending model changes |
| PostgreSQL full regression | **173/173 PASS**, including all 132 previous tests |
| Homework tests | 23 API/security + 12 rule + 6 PostgreSQL concurrency = **41 PASS** |
| API client executable contracts | **18 PASS** |
| TypeScript | **6 apps PASS** |
| React/Vite production builds | **3 web apps PASS** |
| Expo dependency compatibility | **3 apps PASS** |
| iOS + Android JS/Hermes exports | **3 apps, both platforms PASS** |
| Chrome headless workflow | **PASS**: web create/edit/publish, student HTTP submit, web feedback/close, parent HTTP redaction, logout to GVCN read-only; no JS page errors |

Native signed builds and real-device acceptance are not implied by bundle export. Full physical-phone acceptance remains pending user verification. Report/ZIP validation tables reflect their original artifact environment; this manifest records actual integrated-project checks.

## Expo Go compatibility update — SDK 58

All three mobile apps now use Expo ~58.0.19 / React Native 0.88.0 / React 19.3.0, with SDK-aligned Router, Reanimated/Worklets, SecureStore, date/time picker and React types. Metro runtime and DOM webview peers are explicit to avoid retaining SDK 57 transitive dependencies. Web apps retain their existing React version.

After the upgrade: `expo install --check` passes for all three apps; full `expo-doctor` passes **20/20 per app**; typecheck (6), contracts (18), web builds (3) and iOS/Android exports (3 apps) pass. A temporary Metro server returned `sdkVersion: 58.0.0` and `runtimeVersion: exposdk:58.0.0`; it was stopped after verification. Existing user Metro servers must be restarted with `--clear`, then scanned using the new QR. Physical-phone validation remains pending.
