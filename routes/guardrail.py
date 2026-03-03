import json
import logging
from fastapi import APIRouter, HTTPException, Request

logger = logging.getLogger("mcp_server")

router = APIRouter()

_guardrail_file_count = 0
_guardrail_input_count = 0
_guardrail_output_count = 0


@router.post("/guardrail")
async def guardrail_endpoint(request: Request):
    """
    Custom API 가드레일 테스트 엔드포인트

    요청 형식:
    - Input:  {"text": "...", "source": "INPUT",  "metadata": {...}}
    - Output: {"text": "...", "source": "OUTPUT", "metadata": {...}}
    - File:   {"text": "", "file": {"filename": "...", "mimetype": "...", "content_base64": "..."}, "source": "FILE", "metadata": {...}}

    차단 규칙:
    - FILE: 2번에 1번 차단
    - INPUT/OUTPUT: 3번에 1번 차단
    - "아이유" 키워드 포함 시 차단
    """
    logger.info("=" * 60)
    logger.info("[GUARDRAIL] POST /guardrail")
    logger.info("=" * 60)
    for key, value in request.headers.items():
        if key.lower() in ("authorization", "x-api-key") and value:
            prefix = value[:20] if len(value) > 20 else value
            logger.info(f"  {key}: {prefix}...({len(value)} chars)")
        else:
            logger.info(f"  {key}: {value}")
    logger.info("-" * 60)

    try:
        body = await request.body()
        payload = json.loads(body)
    except json.JSONDecodeError as e:
        logger.error(f"[GUARDRAIL] JSON parse error: {e}")
        raise HTTPException(status_code=400, detail=f"Invalid JSON: {e}")

    source = payload.get("source", "UNKNOWN")
    text = payload.get("text", "")
    metadata = payload.get("metadata", {})
    file_info = payload.get("file")

    logger.info(f"[GUARDRAIL] source={source}")
    logger.info(f"[GUARDRAIL] text={text[:200]}{'...' if len(text) > 200 else ''}")
    logger.info(f"[GUARDRAIL] metadata={json.dumps(metadata, ensure_ascii=False)}")
    if file_info:
        logger.info(f"[GUARDRAIL] file.filename={file_info.get('filename')}")
        logger.info(f"[GUARDRAIL] file.mimetype={file_info.get('mimetype')}")
        content_b64 = file_info.get("content_base64", "")
        logger.info(f"[GUARDRAIL] file.content_base64=({len(content_b64)} chars)")
    logger.info("=" * 60)

    # FILE 소스: 두 번에 한 번씩 차단
    if source == "FILE":
        global _guardrail_file_count
        _guardrail_file_count += 1
        logger.info(f"[GUARDRAIL] file_call_count={_guardrail_file_count}")

        if _guardrail_file_count % 2 == 0:
            logger.warning(f"[GUARDRAIL] => FILE BLOCKED (count={_guardrail_file_count}, even)")
            return {
                "action": "GUARDRAIL_INTERVENED",
                "is_safe": False,
                "blocked_reasons": {
                    "reason": "파일 가드레일 차단 (simulated failure)",
                },
            }

        logger.info(f"[GUARDRAIL] => FILE PASSED (count={_guardrail_file_count}, odd)")
        return {
            "action": "NONE",
            "is_safe": True,
        }

    # INPUT 소스: 세 번에 한 번씩 차단
    if source == "INPUT":
        global _guardrail_input_count
        _guardrail_input_count += 1
        logger.info(f"[GUARDRAIL] input_call_count={_guardrail_input_count}")

        if _guardrail_input_count % 3 == 0:
            logger.warning(f"[GUARDRAIL] => INPUT BLOCKED (count={_guardrail_input_count}, every 3rd)")
            return {
                "action": "GUARDRAIL_INTERVENED",
                "is_safe": False,
                "blocked_reasons": {
                    "reason": "입력 가드레일 차단 (every 3rd request)",
                },
            }

        logger.info(f"[GUARDRAIL] => INPUT PASSED (count={_guardrail_input_count})")

    # OUTPUT 소스: 세 번에 한 번씩 차단
    if source == "OUTPUT":
        global _guardrail_output_count
        _guardrail_output_count += 1
        logger.info(f"[GUARDRAIL] output_call_count={_guardrail_output_count}")

        if _guardrail_output_count % 3 == 0:
            logger.warning(f"[GUARDRAIL] => OUTPUT BLOCKED (count={_guardrail_output_count}, every 3rd)")
            return {
                "action": "GUARDRAIL_INTERVENED",
                "is_safe": False,
                "blocked_reasons": {
                    "reason": "출력 가드레일 차단 (every 3rd request)",
                },
            }

        logger.info(f"[GUARDRAIL] => OUTPUT PASSED (count={_guardrail_output_count})")

    # "아이유" 포함 여부 검사
    if "아이유" in text:
        logger.warning("[GUARDRAIL] BLOCKED: '아이유' detected")
        return {
            "action": "GUARDRAIL_INTERVENED",
            "is_safe": False,
            "blocked_reasons": {
                "reason": "'아이유' 관련 내용은 허용되지 않습니다.",
            },
        }

    # 안전 응답
    logger.info("[GUARDRAIL] => PASSED")
    return {
        "action": "NONE",
        "is_safe": True,
    }
