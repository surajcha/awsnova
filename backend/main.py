"""Nova Multimodal Knowledge Graph Builder — FastAPI Backend."""

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import settings
from api.routes import router

# Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

app = FastAPI(
    title="Nova MKG — Multimodal Knowledge Graph Builder",
    description=(
        "Ingest PDFs, images, and text to automatically extract entities & relationships, "
        "build a queryable knowledge graph, and answer natural-language questions with citations. "
        "Powered by Amazon Nova via Bedrock."
    ),
    version="1.0.0",
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routes
app.include_router(router)


@app.get("/health")
async def health():
    return {"status": "healthy", "service": "nova-mkg"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
