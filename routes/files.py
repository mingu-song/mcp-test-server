import logging
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import Response

logger = logging.getLogger("mcp_server")

router = APIRouter()


@router.post("/files")
async def files_endpoint(request: Request):
    """
    파일 전처리 테스트 엔드포인트

    호출 방식:
        client.post(url, files={"file": (filename, content)}, headers={"X-API-KEY": api_key})

    동작: 받은 파일을 로깅하고 파일 내용을 그대로 반환
    """
    logger.info("=" * 60)
    logger.info("[FILES] POST /files")
    logger.info("=" * 60)
    for key, value in request.headers.items():
        if key.lower() in ("x-api-key", "authorization") and value:
            prefix = value[:20] if len(value) > 20 else value
            logger.info(f"  {key}: {prefix}...({len(value)} chars)")
        else:
            logger.info(f"  {key}: {value}")
    logger.info("-" * 60)

    form = await request.form()
    file = form.get("file")

    if file is None:
        logger.error("[FILES] 'file' field not found in form data")
        raise HTTPException(status_code=400, detail="'file' field is required")

    filename = file.filename
    content = await file.read()
    content_type = file.content_type or "application/octet-stream"

    logger.info(f"[FILES] filename={filename}")
    logger.info(f"[FILES] content_type={content_type}")
    logger.info(f"[FILES] content_size={len(content)} bytes")
    logger.info(f"[FILES] content_preview={content[:200]}")
    logger.info("=" * 60)

    return Response(
        content=content,
        media_type=content_type,
        headers={"X-Filename": filename},
    )
