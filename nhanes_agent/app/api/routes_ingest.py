from __future__ import annotations

from fastapi import APIRouter, File, Form, UploadFile

from nhanes_agent.app.core.config import load_agent_settings
from nhanes_agent.app.models.schemas.ingest import IngestPdfResponse
from nhanes_agent.app.services.ingest.service import IngestService

router = APIRouter(tags=["ingest"])


@router.post("/ingest/pdf", response_model=IngestPdfResponse)
async def ingest_pdf(project_name: str = Form(...), auto_index: bool = Form(True), file: UploadFile = File(...)) -> IngestPdfResponse:
    """Upload a PDF and run ingestion plus NHANES extraction."""
    settings = load_agent_settings()
    content = await file.read()
    service = IngestService(settings)
    result = service.ingest_pdf(project_name=project_name, filename=file.filename or "upload.pdf", content=content, auto_index=auto_index)
    return IngestPdfResponse(
        document_id=result["document_id"],
        number_of_chunks=result["number_of_chunks"],
        number_of_validated_cycles=result["number_of_validated_cycles"],
        number_of_validated_components=result["number_of_validated_components"],
        number_of_validated_variables=result["number_of_validated_variables"],
    )
