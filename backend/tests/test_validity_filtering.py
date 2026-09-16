from unittest.mock import MagicMock
from backend.app.embedding.vector_store import VectorStore


def test_search_excludes_expired_by_default():
    vs = VectorStore(host="localhost", port=6333, collection_name="test")
    vs.client = MagicMock()
    mock_results = MagicMock()
    mock_results.points = []
    vs.client.query_points.return_value = mock_results

    vs.search(query_vector=[0.1] * 1024, top_k=5)

    # Verify query_points was called
    assert vs.client.query_points.called
    call_kwargs = vs.client.query_points.call_args[1]
    query_filter = call_kwargs["query_filter"]

    # Must contain must_not condition for validity_status == "Hết hiệu lực"
    assert query_filter is not None
    assert query_filter.must_not is not None
    assert len(query_filter.must_not) == 1
    assert query_filter.must_not[0].key == "validity_status"
    assert query_filter.must_not[0].match.value == "Hết hiệu lực"


def test_search_allows_expired_when_flag_false():
    vs = VectorStore(host="localhost", port=6333, collection_name="test")
    vs.client = MagicMock()
    mock_results = MagicMock()
    mock_results.points = []
    vs.client.query_points.return_value = mock_results

    vs.search(query_vector=[0.1] * 1024, top_k=5, exclude_expired=False)

    call_kwargs = vs.client.query_points.call_args[1]
    query_filter = call_kwargs["query_filter"]
    assert query_filter is None


def test_scroll_chunks_excludes_expired():
    vs = VectorStore(host="localhost", port=6333, collection_name="test")
    vs.client = MagicMock()
    vs.client.scroll.return_value = ([], None)

    vs.scroll_chunks(exclude_expired=True)

    assert vs.client.scroll.called
    call_kwargs = vs.client.scroll.call_args[1]
    scroll_filter = call_kwargs["scroll_filter"]
    assert scroll_filter is not None
    assert scroll_filter.must_not is not None
    assert scroll_filter.must_not[0].key == "validity_status"
    assert scroll_filter.must_not[0].match.value == "Hết hiệu lực"
