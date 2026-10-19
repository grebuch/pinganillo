import pytest

from pinganillo.llm.knowledge import KnowledgeBase, split_passages, tokenize

DOC = """Backups

Our recovery time objective (RTO) is four hours for the ERP and one day for the intranet.

Recovery point objective (RPO): snapshots every 15 minutes, replicated to a second site.

Holidays

The office closes in August. Requests go to human resources before May."""


def test_tokenize_folds_accents_and_drops_stopwords():
    assert tokenize("¿Cuál es la Política de COPIAS?") == ["cual", "politica", "copias"]


def test_passages_respect_size_and_keep_all_text():
    long = "word " * 400
    passages = split_passages(long, size=300)
    assert all(len(p) <= 300 for p in passages)
    assert sum(len(p.split()) for p in passages) == 400


def test_only_matching_passages_are_returned():
    kb = KnowledgeBase(DOC, passage_chars=150)
    context = kb.relevant("What is the recovery time objective for the ERP?", budget_chars=2000)
    assert "four hours" in context
    assert "August" not in context


def test_nothing_is_sent_when_nothing_matches():
    assert KnowledgeBase(DOC, passage_chars=150).relevant("football results yesterday") == ""


def test_budget_is_respected():
    kb = KnowledgeBase("\n\n".join(f"Paragraph {i} about servers and storage." * 5 for i in range(50)))
    assert len(kb.relevant("servers storage", budget_chars=1000)) <= 1000


def test_empty_and_oversized_documents():
    assert not KnowledgeBase("")
    assert KnowledgeBase("").relevant("anything") == ""
    with pytest.raises(ValueError):
        KnowledgeBase("x" * 200_001)
