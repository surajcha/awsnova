import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()


class Settings:
    # AWS
    AWS_REGION: str = os.getenv("AWS_REGION", "us-east-1")

    # Bedrock Model IDs
    NOVA_TEXT_MODEL_ID: str = os.getenv("NOVA_TEXT_MODEL_ID", "amazon.nova-pro-v1:0")
    NOVA_LITE_MODEL_ID: str = os.getenv("NOVA_LITE_MODEL_ID", "amazon.nova-lite-v1:0")
    NOVA_EMBED_MODEL_ID: str = os.getenv("NOVA_EMBED_MODEL_ID", "amazon.titan-embed-text-v2:0")
    NOVA_MULTIMODAL_EMBED_MODEL_ID: str = os.getenv(
        "NOVA_MULTIMODAL_EMBED_MODEL_ID", "amazon.titan-embed-image-v1:0"
    )

    # App
    UPLOAD_DIR: str = os.getenv("UPLOAD_DIR", "./uploads")
    MAX_UPLOAD_SIZE_MB: int = int(os.getenv("MAX_UPLOAD_SIZE_MB", "50"))
    CORS_ORIGINS: list[str] = os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",")

    # Graph
    GRAPH_BACKEND: str = os.getenv("GRAPH_BACKEND", "networkx")

    # FAISS
    FAISS_INDEX_PATH: str = os.getenv("FAISS_INDEX_PATH", "./faiss_index")
    SIMILARITY_THRESHOLD: float = float(os.getenv("SIMILARITY_THRESHOLD", "0.85"))

    def __init__(self):
        Path(self.UPLOAD_DIR).mkdir(parents=True, exist_ok=True)
        Path(self.FAISS_INDEX_PATH).mkdir(parents=True, exist_ok=True)


settings = Settings()
