import json
from pathlib import Path
from typing import Any

from govuk_rag.govuk.fetch import (
    documents_from_content_item,
    fetch_pages,
    html_to_text,
    read_page_list,
)


def test_html_to_text_keeps_structure_and_drops_markup() -> None:
    html = """
    <h2>Entitlement</h2>
    <p>Almost all workers get <a href="/x">5.6 weeks&rsquo;</a> paid holiday.</p>
    <ul><li>agency workers</li><li>zero-hours   workers</li></ul>
    <script>alert('x')</script>
    <table><tr><th>Days worked</th><th>Holiday</th></tr><tr><td>5</td><td>28 days</td></tr></table>
    """

    assert html_to_text(html) == (
        "Entitlement\n\n"
        "Almost all workers get 5.6 weeks\u2019 paid holiday.\n\n"
        "- agency workers\n"
        "- zero-hours workers\n\n"
        "Days worked | Holiday\n"
        "5 | 28 days"
    )


def guide_item() -> dict[str, Any]:
    return {
        "title": "Holiday entitlement",
        "base_path": "/holiday-entitlement-rights",
        "details": {
            "parts": [
                {"slug": "entitlement", "title": "Entitlement", "body": "<p>5.6 weeks.</p>"},
                {"slug": "holiday-pay", "title": "Holiday pay", "body": "<p>Normal pay.</p>"},
            ]
        },
    }


def test_guide_parts_become_separate_documents() -> None:
    documents = documents_from_content_item(guide_item())

    assert [d.id for d in documents] == [
        "holiday-entitlement-rights/entitlement",
        "holiday-entitlement-rights/holiday-pay",
    ]
    assert documents[0].title == "Holiday entitlement: Entitlement"
    assert str(documents[0].url) == "https://www.gov.uk/holiday-entitlement-rights/entitlement"
    assert documents[1].text == "Normal pay."


def test_single_body_page_becomes_one_document() -> None:
    item = {
        "title": "Carer's Leave",
        "base_path": "/carers-leave",
        "details": {"body": "<p>One week a year.</p>"},
    }

    [document] = documents_from_content_item(item)

    assert document.id == "carers-leave"
    assert document.title == "Carer's Leave"
    assert str(document.url) == "https://www.gov.uk/carers-leave"
    assert document.text == "One week a year."


def test_page_without_body_text_gives_no_documents() -> None:
    assert documents_from_content_item({"title": "T", "base_path": "/t", "details": {}}) == []


def test_fetch_pages_writes_one_json_file_per_document(tmp_path: Path) -> None:
    requested: list[str] = []

    def get_json(url: str) -> Any:  # noqa: ANN401
        requested.append(url)
        return guide_item()

    written = fetch_pages(["/holiday-entitlement-rights"], get_json, tmp_path)

    assert requested == ["https://www.gov.uk/api/content/holiday-entitlement-rights"]
    assert written == 2
    stored = json.loads(
        (tmp_path / "holiday-entitlement-rights" / "entitlement.json").read_text(encoding="utf-8")
    )
    assert stored == {
        "title": "Holiday entitlement: Entitlement",
        "url": "https://www.gov.uk/holiday-entitlement-rights/entitlement",
        "text": "5.6 weeks.",
    }


def test_read_page_list_skips_comments_and_blank_lines(tmp_path: Path) -> None:
    pages = tmp_path / "pages.txt"
    pages.write_text(
        "# Leave\n/holiday-entitlement-rights\n\nstatutory-sick-pay  \n", encoding="utf-8"
    )

    assert read_page_list(pages) == ["/holiday-entitlement-rights", "/statutory-sick-pay"]


def test_redirect_items_give_no_documents() -> None:
    # The Content API returns redirect stubs with a null title and empty details.
    item = {
        "title": None,
        "base_path": "/redundant-your-rights",
        "document_type": "redirect",
        "details": {},
    }

    assert documents_from_content_item(item) == []
