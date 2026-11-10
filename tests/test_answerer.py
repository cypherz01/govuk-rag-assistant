import pytest

from govuk_rag.answering.answerer import I_DONT_KNOW, Answerer
from govuk_rag.answering.prompt import NO_ANSWER
from govuk_rag.answering.retrieval import RetrievedChunk
from tests.answering_fakes import FakeChatModel, FakeRetriever, retrieved_chunk

HOLIDAY = retrieved_chunk("Holiday entitlement", relevance=0.7)
SICK_PAY = retrieved_chunk("Statutory Sick Pay", slug="statutory-sick-pay", relevance=0.6)
BANK_HOLIDAYS = retrieved_chunk("Bank holidays", slug="bank-holidays", relevance=0.5)
OFF_TOPIC = retrieved_chunk("Parking", slug="parking", relevance=0.1)


def _answerer(
    chunks: list[RetrievedChunk] | None = None, reply: str = "", threshold: float = 0.4
) -> tuple[Answerer, FakeRetriever, FakeChatModel]:
    retriever = FakeRetriever([HOLIDAY, SICK_PAY, BANK_HOLIDAYS] if chunks is None else chunks)
    model = FakeChatModel(reply)
    return Answerer(retriever, model, relevance_threshold=threshold), retriever, model


def test_says_i_dont_know_without_calling_the_model_when_nothing_is_relevant() -> None:
    answerer, retriever, model = _answerer([OFF_TOPIC], reply="should not be used")

    response = answerer.answer("What's the capital of France?")

    assert response.answered is False
    assert response.answer == I_DONT_KNOW
    assert response.citations == []
    assert retriever.questions == ["What's the capital of France?"]
    assert model.calls == []


def test_says_i_dont_know_when_nothing_is_retrieved() -> None:
    answerer, _, model = _answerer([])

    assert answerer.answer("Anything?").answered is False
    assert model.calls == []


def test_only_relevant_chunks_reach_the_model() -> None:
    answerer, _, model = _answerer([HOLIDAY, OFF_TOPIC], reply="5.6 weeks [1].")

    answerer.answer("How much holiday?")

    [messages] = model.calls
    prompt = messages[-1].content
    assert "Holiday entitlement" in prompt
    assert "Parking" not in prompt


def test_a_chunk_scoring_exactly_the_threshold_counts_as_relevant() -> None:
    answerer, _, model = _answerer([HOLIDAY], reply="Yes [1].", threshold=HOLIDAY.relevance)

    assert answerer.answer("Holiday?").answered is True
    assert len(model.calls) == 1


def test_answers_with_citations_for_the_sources_the_model_used() -> None:
    answerer, _, _ = _answerer(reply="Most workers get 5.6 weeks [1].")

    response = answerer.answer("How much holiday?")

    assert response.answered is True
    assert response.answer == "Most workers get 5.6 weeks [1]."
    assert [c.title for c in response.citations] == ["Holiday entitlement"]
    assert str(response.citations[0].url) == "https://www.gov.uk/holiday-entitlement-rights"
    assert response.citations[0].snippet == HOLIDAY.content


def test_renumbers_citations_in_order_of_first_use() -> None:
    answerer, _, _ = _answerer(reply="Holiday is 5.6 weeks [3]. Bank holidays can count [1][3].")

    response = answerer.answer("Do bank holidays count?")

    assert response.answer == "Holiday is 5.6 weeks [1]. Bank holidays can count [2][1]."
    assert [c.title for c in response.citations] == ["Bank holidays", "Holiday entitlement"]


def test_drops_markers_that_point_at_no_source() -> None:
    answerer, _, _ = _answerer(reply="Holiday is 5.6 weeks [2][7].")

    response = answerer.answer("Holiday?")

    assert response.answer == "Holiday is 5.6 weeks [1]."
    assert [c.title for c in response.citations] == ["Statutory Sick Pay"]


def test_cites_every_source_given_when_the_model_cites_none() -> None:
    answerer, _, _ = _answerer([HOLIDAY, SICK_PAY], reply="Most workers get 5.6 weeks.")

    response = answerer.answer("Holiday?")

    assert response.answered is True
    assert [c.title for c in response.citations] == ["Holiday entitlement", "Statutory Sick Pay"]


@pytest.mark.parametrize(
    "reply",
    [
        NO_ANSWER,
        f"  {NO_ANSWER}\n",
        f"{NO_ANSWER}.",
        # Seen live: the model explains first, then gives the sentinel.
        f"The sources do not say how to ask for a pay rise.\n\n{NO_ANSWER}",
    ],
)
def test_says_i_dont_know_when_the_model_finds_no_answer_in_the_sources(reply: str) -> None:
    answerer, _, _ = _answerer(reply=reply)

    response = answerer.answer("Can I bring my dog to work?")

    assert response.answered is False
    assert response.answer == I_DONT_KNOW
    assert response.citations == []


def test_long_snippets_are_cut_at_a_word_boundary() -> None:
    long_chunk = retrieved_chunk(content="word " * 200, relevance=0.9)
    retriever = FakeRetriever([long_chunk])
    answerer = Answerer(
        retriever, FakeChatModel("Yes [1]."), relevance_threshold=0.4, snippet_chars=50
    )

    [citation] = answerer.answer("q").citations

    assert len(citation.snippet) <= 51
    assert citation.snippet.endswith("…")
    assert citation.snippet.removesuffix("…").split() == ["word"] * 10


def test_reply_is_stripped_of_surrounding_whitespace() -> None:
    answerer, _, _ = _answerer(reply="\n  Yes [1].  \n")

    assert answerer.answer("q").answer == "Yes [1]."
