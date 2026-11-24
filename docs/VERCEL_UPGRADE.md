# Vercel upgrade: teacher access, attachments and AI

## What changes

- Registration no longer sends or requires a verification email. Historical verification flags do not block existing users. A new teacher still submits a teaching purpose and needs administrator approval; sign in again after approval.
- Vercel defaults to `UPLOAD_STORAGE=database`. New course attachments and avatars are stored in PostgreSQL in the same transaction as the course/profile. Replacing or deleting a course removes its stored attachment. Existing local development keeps local files.
- Hosted file uploads are limited to **3 MB**, with a 4 MB request limit to leave multipart overhead below Vercel's default 4.5 MB request limit. The editor displays the limit and returns a useful error. Split/compress larger handouts; large video hosting requires a separate object-storage design.
- Hosted AI generation runs within its invocation, with shared PostgreSQL status, recovery and rate limits. It does not rely on a background thread surviving after a response. Drafts are never automatically published. The browser can recover a job by its saved request identifier.
- Student questions can reuse the teacher's Claude configuration and read the currently published PDF/PPTX from durable storage. Independent tutor configuration remains supported. Existing learning, analytics and Iterative Ark behavior is retained.

## Release steps for the project owner

1. Merge the repair PR into the branch used by the Vercel **production** project. Approve the deployment in Vercel if the contribution requires team authorization; keep deployment protection enabled.
2. Confirm `DATABASE_URL` and a stable random `ZHIXING_SECRET_KEY` in the target Vercel environment. Keep the existing values; do not reset accounts. Set `PUBLIC_BASE_URL` to the actual production HTTPS origin. Preview and Production variables are configured separately.
3. Set `STUDIO_AI_BASE_URL`, `STUDIO_AI_API_KEY`, and `STUDIO_AI_MODEL` in Vercel. The provider must support the Claude Messages API and the selected model. A local `.env` or Claude settings file is not transferred by Git. Never commit those files. For student reuse set `TUTOR_USE_STUDIO_AI=1`; otherwise retain the independent tutor variables. `MAIL_BACKEND=disabled` is sufficient for registration and teacher review; real password-reset delivery still needs SMTP.
4. With the target database configured, run `python -m flask --app run migrate` once. Migration `008_hosted_uploads.sql` only adds attachment/job tables. It does not reseed accounts, reset passwords or clear courses/progress. The two new tables also have transactional first-write bootstrap for existing installs with schema permissions.
5. Deploy with the repository's `api/index.py` entry point and `vercel.json`, which enables **Fluid compute** and sets a 300-second function duration. The legacy `builds` configuration has been replaced by the documented `functions` configuration. Frontend assets, SQL migrations and the extraction worker are explicitly included. Catch-all routing continues through Flask, rather than exposing the repository as public files.
6. Share the project's **production domain** shown in Vercel, not an old deployment-specific URL. An existing snapshot such as `zhixing-mp019mm9d-yxl28hk.vercel.app` does not automatically become the newly deployed build. Confirm the deployment commit matches the merged PR before testing.

## Existing missing attachments

Previous database records may point to files that were only on a developer's machine or an old ephemeral deployment. This release cannot recreate missing file contents. The teacher opens **课程管理 → 编辑课程 → 课程附件**, reselects the original file, and saves. The course ID, enrollments and learning progress remain unchanged. Missing attachment URLs now explain that the teacher must re-upload. Do not put private course files into Git as a workaround.

## Post-deployment check

Use a dedicated test account and a small non-sensitive text PDF/PPTX:

1. Register; no verification email is requested. Submit a teacher application; an administrator reviews it. Sign in again and open Create Course.
2. Upload the file, adopt an AI draft, review and publish. Refresh, sign in on another device and open the attachment. Replacing the attachment must serve the new file.
3. As a student, join the course and ask a question whose answer appears in the handout. Confirm the answer uses that course and reports readable source pages. The original text fallback remains explicitly non-AI.
4. Restore an AI job after refreshing the editor; restore queries must not generate a second paid request. Another account must not read the job or edit the teacher's course.

Local regression tests use isolated PostgreSQL schemas and mocked model responses; they do not verify the production provider key, team authorization or a deployment's environment values.

References: [Vercel function duration](https://vercel.com/docs/functions/configuring-functions/duration), [function configuration](https://vercel.com/docs/project-configuration/vercel-json#functions), [payload limit](https://vercel.com/docs/errors/function_payload_too_large).
