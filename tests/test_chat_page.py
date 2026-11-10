import re

from fastapi.testclient import TestClient

from govuk_rag.config import Settings
from govuk_rag.main import create_app


def test_home_page_is_the_chat_page(client: TestClient) -> None:
    response = client.get("/")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    html = response.text
    assert "<form" in html
    assert 'src="/static/app.js"' in html
    assert 'href="/static/styles.css"' in html


def test_page_needs_no_key_so_visitors_can_enter_one(settings: Settings) -> None:
    with TestClient(create_app(settings)) as anonymous:
        assert anonymous.get("/").status_code == 200


def test_page_has_no_inline_script_or_style(client: TestClient) -> None:
    html = client.get("/").text

    assert "<script>" not in html
    assert "<style" not in html
    assert " style=" not in html
    assert not re.search(r"\son[a-z]+\s*=", html), "inline event handler"


def test_page_is_served_with_a_strict_content_security_policy(client: TestClient) -> None:
    headers = client.get("/").headers

    csp = headers["content-security-policy"]
    assert "default-src 'self'" in csp
    assert "frame-ancestors 'none'" in csp
    assert "unsafe-inline" not in csp
    assert headers["x-content-type-options"] == "nosniff"
    assert headers["referrer-policy"] == "no-referrer"


def test_script_and_stylesheet_are_served(client: TestClient) -> None:
    script = client.get("/static/app.js")
    styles = client.get("/static/styles.css")

    assert script.status_code == 200
    assert "javascript" in script.headers["content-type"]
    assert "/chat" in script.text
    assert "X-Demo-Key" in script.text
    assert styles.status_code == 200
    assert styles.headers["content-type"].startswith("text/css")


def test_script_never_writes_untrusted_text_as_html(client: TestClient) -> None:
    script = client.get("/static/app.js").text

    assert "innerHTML" not in script
    assert "outerHTML" not in script
    assert "insertAdjacentHTML" not in script
    assert "document.write" not in script


def test_page_is_not_in_the_api_schema(client: TestClient) -> None:
    assert "/" not in client.get("/openapi.json").json()["paths"]
