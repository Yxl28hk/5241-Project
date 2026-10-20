"""Opt-in browser regressions for XSS and legacy HTML script compatibility.

Run with RUN_BROWSER_TESTS=1 and requirements-browser.txt installed. Uses only
local static files and mocked API responses, never a database.
"""

import json
import os
import re
import sys
import threading
from urllib.parse import urlsplit

import pytest
from werkzeug.serving import make_server

from app import create_app

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_BROWSER_TESTS") != "1",
    reason="Set RUN_BROWSER_TESTS=1 to run optional browser regressions",
)


@pytest.fixture
def browser_page():
    playwright = pytest.importorskip("playwright.sync_api")
    application = create_app({"TESTING": True, "DATABASE_URL": ""})
    server = make_server("127.0.0.1", 0, application, threaded=True)
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    try:
        with playwright.sync_playwright() as runtime:
            channel = os.environ.get(
                "BROWSER_CHANNEL", "msedge" if sys.platform == "win32" else ""
            )
            browser = runtime.chromium.launch(
                headless=True, **({"channel": channel} if channel else {})
            )
            try:
                page = browser.new_page()
                page.set_default_timeout(10000)
                yield page, f"http://127.0.0.1:{server.server_port}", application
            finally:
                browser.close()
    finally:
        server.shutdown()
        worker.join(timeout=5)
        server.server_close()


@pytest.mark.parametrize(
    "legacy_scripts",
    [
        None,
        ("app.js", "prototype.js", "study.js"),
        ("api.js", "app.js", "prototype.js", "study.js"),
    ],
    ids=["current-html", "original-html-without-api", "html-with-separate-api"],
)
def test_user_content_is_text_and_legacy_pages_initialize(browser_page, legacy_scripts):
    page, root, application = browser_page
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    title = '<img src="/missing" onerror="window.__xssExecuted = true">'
    description = '<svg onload="window.__xssExecuted = true"></svg>'
    author = '<img src="/missing" onerror="window.__xssExecuted = true"> & "author"'
    course = {
        "id": 1,
        "title": title,
        "description": description,
        "author": author,
        "cover": 'tech" onmouseover="window.__xssExecuted = true',
        "badge": description,
        "duration": title,
        "type": "pdf",
        "resource_type": "pdf",
        "category": description,
        "learner_count": 1,
        "file_url": None,
        "progress": '0"><img src="/missing" onerror="window.__xssExecuted = true">',
    }
    user = {
        "id": 2,
        "name": author,
        "email": description,
        "role": "student",
        "courses": [course],
        "learning_records": [{**course, "updated_at": None}],
    }
    responses = {
        "/api/auth/me": {"user": None},
        "/api/prototype/config": {
            "database": "postgresql",
            "tutor_mode": "guided-demo",
        },
        "/api/courses": {"courses": [course]},
        "/api/profile/courses": {"courses": [course]},
        "/api/profile/learning": {"courses": [course]},
        "/api/courses/1/learners": {
            "learners": [{"id": 2, "name": author, "progress": 50}]
        },
        "/api/admin/users": {"users": [user]},
    }

    def api_response(route):
        path = urlsplit(route.request.url).path
        assert path in responses, path
        route.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps(responses[path]),
        )

    page.route(f"{root}/api/**", api_response)
    if legacy_scripts:
        html = application.test_client().get("/").get_data(as_text=True)
        html = re.sub(r'\s*<script src="[^"]+"></script>', "", html)
        scripts = "\n".join(
            f'<script src="/{name}"></script>' for name in legacy_scripts
        )
        html = html.replace("</body>", scripts + "\n</body>")
        page.route(
            f"{root}/",
            lambda route: route.fulfill(
                status=200, content_type="text/html", body=html
            ),
        )

    def assert_safe(container):
        assert (
            page.locator(
                f"{container} img, {container} svg, {container} script"
            ).count()
            == 0
        )
        assert (
            page.locator(
                f"{container} [onerror], {container} [onload], {container} [onmouseover]"
            ).count()
            == 0
        )
        assert page.evaluate("window.__xssExecuted !== true")

    page.goto(root)
    page.wait_for_function("state.courses.length === 1")
    assert page.locator(".course-title").text_content() == title
    assert page.locator(".course-description").text_content() == description
    assert page.locator(".course-author").text_content().endswith(author)
    assert (
        page.locator(".course-cover").first.get_attribute("class")
        == "course-cover cover-design"
    )
    assert_safe("#course-grid")

    # Exercise every other HTML view that renders course or account fields.
    page.evaluate(
        "state.user = {id: 42, role: 'admin', is_admin: true, can_upload: true}"
    )
    page.evaluate("openSpace('uploads')")
    assert page.locator("#space-list strong").text_content() == title
    assert_safe("#space-list")
    page.evaluate("openSpace('learning')")
    assert (
        page.locator("#space-list .progress-track span").evaluate(
            "el => el.style.width"
        )
        == "0%"
    )
    assert_safe("#space-list")
    page.evaluate("openLearners(1)")
    assert page.locator("#learners-list strong").text_content() == author
    assert_safe("#learners-list")
    page.evaluate("openAdminUsers()")
    assert (
        page.locator("#admin-users-list .space-item-info strong").text_content()
        == author
    )
    assert (
        page.locator("#admin-users-list .admin-data-row span").first.text_content()
        == title
    )
    assert_safe("#admin-users-list")
    assert not errors, errors
