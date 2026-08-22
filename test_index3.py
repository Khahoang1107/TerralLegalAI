from backend.app.api.v1.documents import _index_document_sync
from backend.app.core.config import settings

_index_document_sync(
    document_id='8fb6e410-5ed2-41e2-98fc-e45582c7b72c',
    file_path='data/uploaded/8fb6e410-5ed2-41e2-98fc-e45582c7b72c.pdf',
    source_name='Quy trinh noi bo',
    group_type='quyet_dinh',
    procedure_type='all',
    db_url=settings.database_url
)
