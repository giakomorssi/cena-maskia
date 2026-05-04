"""Content endpoints — serves static markdown files from /api/content/"""

from pathlib import Path

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

router = APIRouter(prefix="/content", tags=["Content"])

# Resolve the content directory relative to this file:
# api/app/api/v1/content.py -> parents[3] = api/ -> api/content/
_CONTENT_DIR = Path(__file__).resolve().parents[3] / "content"


class ContentResponse(BaseModel):
    body_md: str


@router.get("/{content_id}", response_model=ContentResponse)
def get_content(content_id: str):
    """
    Return the markdown body of a static content file.

    Args:
        content_id: Identifier for the content document (e.g. "regolamento").
                    Maps to ``/api/content/<content_id>.md``.

    Returns:
        ``{ body_md: <file_content> }``

    Raises:
        HTTPException 404: if the requested content file does not exist.
    """
    content_file = _CONTENT_DIR / f"{content_id}.md"

    if not content_file.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Content '{content_id}' not found",
        )

    return ContentResponse(body_md=content_file.read_text(encoding="utf-8"))
