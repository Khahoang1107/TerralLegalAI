# -*- coding: utf-8 -*-
from backend.app.api.v1.documents import _index_document_sync
from backend.app.core.config import settings

_index_document_sync(
    document_id="79cd5cb2-c77f-4cf8-bb9e-cf1f19e883e8",
    file_path="data/uploaded/79cd5cb2-c77f-4cf8-bb9e-cf1f19e883e8.pdf",
    source_name="Ban hanh bo TTHC",
    group_type="quyet_dinh",
    procedure_type="all",
    db_url=settings.database_url,
)
