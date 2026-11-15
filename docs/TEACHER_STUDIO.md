# Teacher studio and learning analytics

## Teacher workflow

Teachers open **创建课程** to upload a text PDF/PPTX and optionally select the learner's starting level. AI produces a candidate title, objectives, short sections, examples, practice and review suggestions. Nothing is published until the teacher adopts, checks and explicitly publishes the draft. Advanced editing supports resource, video, guided, practice and blended courses.

The review includes source pages, short quote matches, suggested additions and extraction limitations. Quote matching does not establish factual accuracy. Outlines produce orientation material rather than fabricated detailed lessons. Difficulty, duration and exercises are suggestions for the teacher to check. Saved browser drafts contain text/reviews, not file bytes; reselect attachments after restoring.

New authoring code lives in `app/studio/`; frontend modules use the shared `zhixingApi.request` client. Published content is stored in `course_studio` and rendered with the same function in the student lesson and teacher preview. Optimistic revisions prevent stale edits. Existing built-in lessons remain maintained in source code. Practice responses use the existing notebook flow; there is no automatic grading of free-text tasks.

## Configuration and deployment

Install `requirements.txt`, configure the teacher-specific `STUDIO_AI_*` variables documented in `.env.example`, and run `python -m flask --app run migrate`. Migration 005 adds course content without changing existing records. The publish endpoint also creates the table transactionally for older installations. Importing the application and reading pages never initialize data.

The server reads credentials; the browser receives only configuration status, model name and a session CSRF token. Do not commit `.env`, credentials, user files or local settings. Optional `STUDIO_AI_CONFIG_FILE` reads an existing local Claude configuration only when explicitly configured. It is not needed for normal deployments. Set `STUDIO_AI_NETWORK_MODE=direct` only where bypassing the machine's configured HTTP proxy is appropriate; the default preserves normal proxy handling.

`/?preview=studio` disables publishing. AI generation in this preview additionally requires `STUDIO_AI_LOCAL_PREVIEW=1` and a loopback client/host. Leave this flag off on shared deployments. Normal generation requires a teacher/admin session.

AI limits: 20 MB, 60 pages/slides, 45,000 extracted characters; oversized input is rejected, not silently truncated. No OCR, legacy `.ppt` parsing, visual/chart interpretation or speaker-note ingestion. Extracted text is sent to the configured provider and incurs API usage. The adapter requests streaming, accepts compatible complete JSON responses, and validates complete fields and source references before adopting anything. Interrupted or malformed responses preserve the editor's original draft; there is no automatic paid retry.

Generation jobs are session/account scoped, CSRF protected and held in memory in a **single process**. One active job per owner, two globally; six requests per owner/hour and thirty globally. Completed jobs expire after thirty minutes and service restarts lose jobs. A shared queue and distributed limits are required before multi-worker deployment. Cancelling discards the result but cannot guarantee that an already sent provider request stops billing.

## Learning analytics

Course management shows enrollment, started/completed counts, completion rate, search and status filtering. Opening a learner shows that learner's timestamps, progress and fixed-exercise answers/attempts **within this course only**. Access is restricted to the course's teacher owner or an administrator, including direct API requests. It does not expose private notes, chat history, email addresses or unrelated courses.

Opening a lesson or nonzero progress counts as started; 100% counts as completed. These are activity/progress measures, not proof of mastery. `/?preview=analytics` shows clearly labelled example data without database changes.

## Verification

Offline tests cover parser/stream failures, incomplete output, ownership and role guards, session/CSRF isolation, source references and draft generation with a mocked model. Browser checks use mocked API responses to verify search/detail navigation, editing, adoption, source attachment association, failure preservation and narrow layouts. Live provider checks are explicit manual operations, not part of the test suite.
