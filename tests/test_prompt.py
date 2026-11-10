from govuk_rag.answering.prompt import NO_ANSWER, SYSTEM_PROMPT, build_messages
from tests.answering_fakes import retrieved_chunk


def test_system_prompt_restricts_answers_to_the_sources() -> None:
    assert "only" in SYSTEM_PROMPT.lower()
    assert NO_ANSWER in SYSTEM_PROMPT
    assert "[1]" in SYSTEM_PROMPT


def test_builds_a_system_message_then_numbered_sources_and_the_question() -> None:
    chunks = [
        retrieved_chunk("Holiday entitlement", content="5.6 weeks' paid holiday."),
        retrieved_chunk("Statutory Sick Pay", slug="statutory-sick-pay", content="SSP is paid."),
    ]

    messages = build_messages("How much holiday do I get?", chunks)

    assert [m.role for m in messages] == ["system", "user"]
    assert messages[0].content == SYSTEM_PROMPT
    user = messages[1].content
    assert "[1] Holiday entitlement" in user
    assert "https://www.gov.uk/holiday-entitlement-rights" in user
    assert "5.6 weeks' paid holiday." in user
    assert "[2] Statutory Sick Pay" in user
    assert user.index("[1]") < user.index("[2]") < user.index("How much holiday do I get?")
