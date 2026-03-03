"""
MCP (Model Context Protocol) 테스트 서버

전송 방식:
  - Streamable HTTP: /mcp, /mcp2 (권장)
  - SSE: /sse (레거시)

부가 엔드포인트:
  - /guardrail  Custom API 가드레일 테스트
  - /files      파일 전처리 테스트
  - /health     헬스체크
"""
import logging
import datetime
from zoneinfo import ZoneInfo
from fastapi import FastAPI
import uvicorn

from routes.mcp import router as mcp_router, mcp_server, session_queues
from routes.guardrail import router as guardrail_router
from routes.files import router as files_router


# 한국시간(KST) 로거 설정
class KSTFormatter(logging.Formatter):
    def formatTime(self, record, datefmt=None):
        ct = datetime.datetime.fromtimestamp(record.created, tz=ZoneInfo("Asia/Seoul"))
        if datefmt:
            return ct.strftime(datefmt)
        return ct.strftime("%Y-%m-%d %H:%M:%S")

logger = logging.getLogger("mcp_server")
logger.setLevel(logging.INFO)
_handler = logging.StreamHandler()
_handler.setFormatter(KSTFormatter("[%(asctime)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S"))
logger.addHandler(_handler)
logger.propagate = False


app = FastAPI(title="Test MCP Server")

# 라우터 등록
app.include_router(mcp_router)
app.include_router(guardrail_router)
app.include_router(files_router)


@app.get("/")
async def root():
    """서버 정보"""
    return {
        "name": "Test MCP Server",
        "version": "1.0.0",
        "protocol": "MCP 2024-11-05",
        "transport": ["Streamable HTTP", "SSE"],
        "endpoints": {
            "mcp": "/mcp (권장)",
            "mcp2": "/mcp2 (/mcp와 동일)",
            "sse": "/sse (레거시)",
            "guardrail": "/guardrail",
            "files": "/files",
            "health": "/health",
        }
    }


@app.get("/health")
async def health_check():
    """헬스체크"""
    return {
        "status": "healthy",
        "active_sessions": len(session_queues),
        "sessions": list(session_queues.keys())
    }


if __name__ == "__main__":
    logger.info("=" * 60)
    logger.info("Test MCP Server - http://localhost:8000")
    logger.info("=" * 60)
    logger.info("Endpoints:")
    logger.info("  /mcp, /mcp2  Streamable HTTP (권장)")
    logger.info("  /sse         SSE (레거시)")
    logger.info("  /guardrail   Custom API 가드레일")
    logger.info("  /files       파일 전처리")
    logger.info("  /health      헬스체크")
    logger.info("-" * 60)
    logger.info("Tools:")
    for tool in mcp_server.tools:
        logger.info(f"  - {tool['name']}: {tool['description']}")
    logger.info("=" * 60)

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        log_level="info"
    )
