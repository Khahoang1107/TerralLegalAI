from backend.app.document_processing.article_mapper import ArticleMapper


def test_extracts_explicit_amendment_reference():
    changes = ArticleMapper().extract_changes(
        "Sửa đổi, bổ sung khoản 2 Điều 5 như sau: nội dung mới."
    )
    assert len(changes) == 1
    assert changes[0].action == "amend"
    assert changes[0].article == "Điều 5"
    assert changes[0].clause == "Khoản 2"


def test_extracts_repeal_and_deduplicates():
    changes = ArticleMapper().extract_changes(
        "Bãi bỏ khoản 1 Điều 7. Bãi bỏ khoản 1 Điều 7."
    )
    assert len(changes) == 1
    assert changes[0].action == "repeal"


def test_ignores_text_without_explicit_article_reference():
    assert ArticleMapper().extract_changes("Quy định này có hiệu lực kể từ ngày ký.") == []


def test_phrase_replacement_does_not_replace_whole_provision():
    changes = ArticleMapper().extract_changes(
        'Thay thế cụm từ "Sở Tài nguyên" bằng "Sở Nông nghiệp" tại khoản 1 Điều 8.'
    )
    assert changes[0].action == "replace_text"
