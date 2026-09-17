"""Download and verify the embedding model before accepting real chat traffic.

Run inside the backend container after a deploy.  The model files are kept in
``/app/data/huggingface`` by docker-compose.prod.yml, so subsequent rebuilds
reuse them instead of timing out a user's first request.
"""

from backend.app.core.config import settings
from backend.app.embedding.embedding_model import EmbeddingModel


def main() -> None:
    model = EmbeddingModel(
        model_name=settings.embedding_model_name,
        batch_size=settings.embedding_batch_size,
        cpu_threads=settings.embedding_cpu_threads,
    )
    vector = model.encode_single("Kiểm tra mô hình tìm kiếm văn bản pháp luật")
    if not vector:
        raise RuntimeError("Không tạo được embedding trong bước làm nóng")
    print(
        f"Embedding ready: model={settings.embedding_model_name}, "
        f"dimension={len(vector)}"
    )


if __name__ == "__main__":
    main()
