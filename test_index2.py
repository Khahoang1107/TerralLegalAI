from backend.app.api.v1.documents import _index_document_sync
from backend.app.core.config import settings

_index_document_sync(
    document_id='91253b58-b2ef-44ba-9f3e-7859a7dbdb08',
    file_path='data/uploaded/91253b58-b2ef-44ba-9f3e-7859a7dbdb08.pdf',
    source_name='Ban hanh bo TTHC',
    group_type='quyet_dinh',
    procedure_type='all',
    db_url=settings.database_url
)
