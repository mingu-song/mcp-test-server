import asyncio
import json
import logging
import uuid
from typing import Optional, Dict, Any
from fastapi import APIRouter, Header, HTTPException, Request
from fastapi.responses import StreamingResponse
from sse_starlette.sse import EventSourceResponse

logger = logging.getLogger("mcp_server")

router = APIRouter()

# 세션별 큐 관리
session_queues: Dict[str, asyncio.Queue] = {}
session_response_queues: Dict[str, asyncio.Queue] = {}
session_sse_queues: Dict[str, asyncio.Queue] = {}


class MCPServer:
    """MCP 프로토콜 핸들러"""

    def __init__(self):
        self.tools = [
            {
                "name": "add_numbers",
                "description": "두 숫자를 더합니다",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "a": {
                            "type": "number",
                            "description": "첫 번째 숫자",
                            "title": "숫자 A"
                        },
                        "b": {
                            "type": "number",
                            "description": "두 번째 숫자",
                            "title": "숫자 B"
                        }
                    },
                    "required": ["a", "b"]
                }
            },
            {
                "name": "multiply_numbers",
                "description": "두 숫자를 곱합니다",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "x": {
                            "type": "number",
                            "description": "첫 번째 숫자",
                            "title": "숫자 X"
                        },
                        "y": {
                            "type": "number",
                            "description": "두 번째 숫자",
                            "title": "숫자 Y"
                        }
                    },
                    "required": ["x", "y"]
                }
            },
            {
                "name": "get_greeting",
                "description": "인사말을 생성합니다",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "name": {
                            "type": "string",
                            "description": "이름",
                            "title": "이름"
                        },
                        "language": {
                            "type": "string",
                            "description": "언어 (ko, en)",
                            "title": "언어",
                            "default": "ko"
                        }
                    },
                    "required": ["name"]
                }
            },
            {
                "name": "search_with_progress",
                "description": "검색을 수행하며 진행 상황을 알립니다 (Progress Notification 테스트용)",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "검색어",
                            "title": "검색어"
                        },
                        "steps": {
                            "type": "integer",
                            "description": "진행 단계 수 (기본: 5)",
                            "title": "단계 수",
                            "default": 5
                        }
                    },
                    "required": ["query"]
                }
            }
        ]

    def handle_initialize(self, request_id: Any) -> dict:
        """초기화 응답"""
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {
                    "tools": {}
                },
                "serverInfo": {
                    "name": "test-mcp-server",
                    "version": "1.0.0"
                }
            }
        }

    async def handle_list_tools(self, request_id: Any) -> dict:
        """도구 목록 응답"""
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "tools": self.tools
            }
        }

    async def handle_call_tool(
        self,
        request_id: Any,
        tool_name: str,
        arguments: dict,
        progress_callback=None,
        progress_token=None
    ) -> dict:
        """도구 실행 응답"""
        logger.info(f"[TOOL] handle_call_tool: tool={tool_name}, progress_token={progress_token}, has_callback={progress_callback is not None}")
        try:
            if tool_name == "add_numbers":
                a = arguments.get("a", 0)
                b = arguments.get("b", 0)
                result = a + b
                message = f"{a} + {b} = {result}"

            elif tool_name == "multiply_numbers":
                x = arguments.get("x", 0)
                y = arguments.get("y", 0)
                result = x * y
                message = f"{x} × {y} = {result}"

            elif tool_name == "get_greeting":
                name = arguments.get("name", "Guest")
                language = arguments.get("language", "ko")

                if language == "ko":
                    message = f"안녕하세요, {name}님!"
                else:
                    message = f"Hello, {name}!"

            elif tool_name == "search_with_progress":
                query = arguments.get("query", "")
                steps = arguments.get("steps", 5)
                logger.info(f"[TOOL] search_with_progress: query='{query}', steps={steps}, progress_token={progress_token}")

                progress_messages = [
                    f"검색 시작 - `{query}` 키워드 수신",
                    f"키워드 분석 중 - 형태소 분석 및 토큰화 진행",
                    f"데이터베이스 조회 중 - 인덱스 탐색 수행",
                    f"결과 필터링 중 - 관련도 기반 필터 적용",
                    f"결과 정렬 중 - 스코어링 및 랭킹 처리",
                    f"최종 결과 준비 중 - 응답 포맷팅 완료 단계",
                ]

                total_steps = min(steps, len(progress_messages))

                dummy_results = [
                    {
                        "title": f"{query} 개요 및 핵심 개념 정리",
                        "url": f"https://example.com/docs/{query.replace(' ', '-')}-overview",
                        "snippet": f"{query}의 기본 개념부터 심화 내용까지 체계적으로 정리한 문서입니다.",
                        "relevance": 98,
                        "category": "문서",
                    },
                    {
                        "title": f"{query} 실전 활용 가이드 (2024)",
                        "url": f"https://example.com/guide/{query.replace(' ', '-')}-practical",
                        "snippet": f"실무에서 {query}를 효과적으로 활용하는 방법을 단계별로 설명합니다.",
                        "relevance": 95,
                        "category": "가이드",
                    },
                    {
                        "title": f"{query} 관련 자주 묻는 질문 (FAQ)",
                        "url": f"https://example.com/faq/{query.replace(' ', '-')}",
                        "snippet": f"{query}에 대해 가장 많이 질문되는 항목들을 모아 답변한 FAQ 모음입니다.",
                        "relevance": 89,
                        "category": "FAQ",
                    },
                    {
                        "title": f"{query} 성능 벤치마크 및 비교 분석",
                        "url": f"https://example.com/benchmark/{query.replace(' ', '-')}",
                        "snippet": f"다양한 환경에서 {query}의 성능을 측정하고 비교 분석한 리포트입니다.",
                        "relevance": 82,
                        "category": "분석",
                    },
                    {
                        "title": f"{query} 최신 업데이트 및 변경사항",
                        "url": f"https://example.com/changelog/{query.replace(' ', '-')}",
                        "snippet": f"{query}의 최신 버전 릴리즈 노트와 주요 변경사항을 제공합니다.",
                        "relevance": 76,
                        "category": "릴리즈",
                    },
                    {
                        "title": f"{query} 커뮤니티 토론 및 베스트 프랙티스",
                        "url": f"https://example.com/community/{query.replace(' ', '-')}",
                        "snippet": f"개발자 커뮤니티에서 공유된 {query} 관련 팁과 베스트 프랙티스를 정리했습니다.",
                        "relevance": 71,
                        "category": "커뮤니티",
                    },
                ]

                for i in range(total_steps):
                    if progress_callback:
                        logger.info(f"[PROGRESS] Sending with token={progress_token}: {i+1}/{total_steps+1}")
                        await progress_callback(
                            progress=i + 1,
                            total=total_steps + 1,
                            message=progress_messages[i],
                            progress_token=progress_token
                        )
                    logger.info(f"[PROGRESS] {i+1}/{total_steps+1}: {progress_messages[i]}")
                    await asyncio.sleep(1)

                result_count = min(total_steps, len(dummy_results))
                result_entries = []
                for i in range(result_count):
                    r = dummy_results[i]
                    result_entries.append(
                        f"#### {i+1}. {r['title']}\n"
                        f"- **카테고리**: `{r['category']}` | **관련도**: {r['relevance']}%\n"
                        f"- **URL**: [{r['url']}]({r['url']})\n"
                        f"- {r['snippet']}"
                    )

                elapsed = total_steps
                message = (
                    f"## 검색 완료\n\n"
                    f"> **`{query}`** 키워드에 대해 **{result_count}건**의 결과를 찾았습니다.\n\n"
                    f"| 항목 | 값 |\n"
                    f"|------|----|\n"
                    f"| 검색어 | `{query}` |\n"
                    f"| 결과 수 | **{result_count}건** |\n"
                    f"| 소요 시간 | **{elapsed}초** |\n"
                    f"| 최고 관련도 | **{dummy_results[0]['relevance']}%** |\n\n"
                    f"---\n\n"
                    f"### 검색 결과\n\n"
                    + "\n\n".join(result_entries) +
                    f"\n\n---\n\n"
                    f"*더 정확한 결과를 위해 검색어를 구체적으로 입력해 보세요.*"
                )

            else:
                return {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "error": {
                        "code": -32601,
                        "message": f"Unknown tool: {tool_name}"
                    }
                }

            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {
                    "content": [
                        {
                            "type": "text",
                            "text": message
                        }
                    ]
                }
            }

        except Exception as e:
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {
                    "code": -32603,
                    "message": f"Tool execution error: {str(e)}"
                }
            }

    async def handle_request(self, message: dict, progress_callback=None) -> dict:
        """MCP 요청 처리"""
        method = message.get("method")
        request_id = message.get("id")
        params = message.get("params", {})

        meta = params.get("_meta", {})
        progress_token = meta.get("progressToken")

        logger.info(f"[MCP] Received: method={method}, id={request_id}, progressToken={progress_token}")

        if method == "initialize":
            return self.handle_initialize(request_id)
        elif method == "tools/list":
            return await self.handle_list_tools(request_id)
        elif method == "tools/call":
            tool_name = params.get("name")
            arguments = params.get("arguments", {})
            return await self.handle_call_tool(
                request_id, tool_name, arguments, progress_callback, progress_token
            )
        elif method == "notifications/initialized":
            return None
        else:
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {
                    "code": -32601,
                    "message": f"Method not found: {method}"
                }
            }


mcp_server = MCPServer()


# --- Streamable HTTP 엔드포인트 (/mcp, /mcp2) ---

@router.post("/mcp")
@router.post("/mcp2")
async def mcp_streamable_http_endpoint(request: Request):
    """Streamable HTTP 엔드포인트 - MCP 2025-11 스펙 권장 방식"""
    logger.info("=" * 60)
    logger.info("[MCP] POST /mcp - Streamable HTTP Request")
    logger.info("=" * 60)
    for key, value in request.headers.items():
        if key.lower() == "authorization" and value:
            prefix = value[:20] if len(value) > 20 else value
            logger.info(f"  {key}: {prefix}...({len(value)} chars)")
        else:
            logger.info(f"  {key}: {value}")
    logger.info("=" * 60)

    try:
        body = await request.body()
        message = json.loads(body)
    except json.JSONDecodeError as e:
        logger.error(f"[MCP] JSON parse error: {e}")
        raise HTTPException(status_code=400, detail=f"Invalid JSON: {e}")

    logger.info(f"[MCP] Received: {json.dumps(message, ensure_ascii=False)[:200]}...")

    if "params" in message and "_meta" in message.get("params", {}):
        logger.info(f"[MCP] _meta found: {message['params']['_meta']}")

    async def stream_response():
        sse_queue = asyncio.Queue()

        async def progress_callback(progress: float, total: float, message: str, progress_token=None):
            logger.info(f"[MCP PROGRESS] token={progress_token}, {progress}/{total}: {message}")
            notification = {
                "jsonrpc": "2.0",
                "method": "notifications/progress",
                "params": {
                    "progress": progress,
                    "total": total,
                    "message": message
                }
            }
            if progress_token is not None:
                notification["params"]["progressToken"] = progress_token
            await sse_queue.put(notification)

        async def process_request():
            return await mcp_server.handle_request(message, progress_callback)

        task = asyncio.create_task(process_request())

        while True:
            try:
                notification = await asyncio.wait_for(sse_queue.get(), timeout=0.1)
                notification_json = json.dumps(notification, ensure_ascii=False)
                logger.info(f"[MCP] Streaming progress: {notification_json}")
                yield f"event: message\ndata: {notification_json}\n\n"
            except asyncio.TimeoutError:
                pass

            if task.done():
                while not sse_queue.empty():
                    notification = await sse_queue.get()
                    notification_json = json.dumps(notification, ensure_ascii=False)
                    logger.info(f"[MCP] Streaming progress: {notification_json}")
                    yield f"event: message\ndata: {notification_json}\n\n"

                response = await task
                if response is not None:
                    response_json = json.dumps(response, ensure_ascii=False)
                    logger.info(f"[MCP] Streaming response: {response_json[:200]}...")
                    yield f"event: message\ndata: {response_json}\n\n"
                break

    return StreamingResponse(
        stream_response(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


# --- SSE 엔드포인트 (레거시) ---

@router.get("/sse")
async def mcp_sse_endpoint(
    request: Request,
    authorization: Optional[str] = Header(None),
    auth_type: Optional[str] = Header(None),
    api_key_header: Optional[str] = Header(None),
    api_key_header_prefix: Optional[str] = Header(None)
):
    """SSE 엔드포인트 - MCP 클라이언트 연결 (레거시)"""
    logger.info("=" * 60)
    logger.info("[SSE] Connection request - HEADERS:")
    logger.info("=" * 60)
    for key, value in request.headers.items():
        if key.lower() == "authorization" and value:
            prefix = value[:20] if len(value) > 20 else value
            logger.info(f"  {key}: {prefix}...({len(value)} chars)")
        else:
            logger.info(f"  {key}: {value}")
    logger.info("=" * 60)

    logger.info(f"[SSE] Parsed headers:")
    logger.info(f"  - Authorization: {'Bearer token (' + str(len(authorization)) + ' chars)' if authorization else 'None'}")
    logger.info(f"  - auth_type: {auth_type}")

    async def event_generator():
        session_id = str(uuid.uuid4())

        request_queue = asyncio.Queue()
        sse_queue = asyncio.Queue()
        session_queues[session_id] = request_queue
        session_sse_queues[session_id] = sse_queue

        logger.info(f"[SSE] Session started: {session_id}")

        try:
            yield {
                "event": "endpoint",
                "data": f"/message/{session_id}"
            }
            logger.info(f"[SSE] Sent endpoint: /message/{session_id}")

            while True:
                try:
                    request_data = await asyncio.wait_for(
                        request_queue.get(),
                        timeout=30.0
                    )

                    logger.info(f"[SSE] Processing request: {request_data}")

                    async def progress_callback(progress: float, total: float, message: str, progress_token=None):
                        logger.info(f"[CALLBACK] progress_callback called: token={progress_token}, progress={progress}/{total}, message={message}")
                        notification = {
                            "jsonrpc": "2.0",
                            "method": "notifications/progress",
                            "params": {
                                "progressToken": progress_token,
                                "progress": progress,
                                "total": total,
                                "message": message
                            }
                        }
                        if progress_token is None:
                            logger.warning(f"[CALLBACK] progressToken is None! Client may not receive progress.")
                            del notification["params"]["progressToken"]
                        else:
                            logger.info(f"[CALLBACK] Notification with progressToken: {notification}")
                        await sse_queue.put(notification)

                    async def process_request():
                        return await mcp_server.handle_request(request_data, progress_callback)

                    task = asyncio.create_task(process_request())

                    while True:
                        try:
                            notification = await asyncio.wait_for(
                                sse_queue.get(),
                                timeout=0.1
                            )
                            notification_json = json.dumps(notification)
                            logger.info(f"[SSE] Sending progress: {notification_json}")
                            yield {
                                "event": "message",
                                "data": notification_json
                            }
                        except asyncio.TimeoutError:
                            pass

                        if task.done():
                            while not sse_queue.empty():
                                notification = await sse_queue.get()
                                notification_json = json.dumps(notification)
                                logger.info(f"[SSE] Sending progress: {notification_json}")
                                yield {
                                    "event": "message",
                                    "data": notification_json
                                }

                            response = await task
                            if response is not None:
                                response_json = json.dumps(response)
                                logger.info(f"[SSE] Sending response: {response_json[:200]}...")
                                yield {
                                    "event": "message",
                                    "data": response_json
                                }
                            break

                except asyncio.TimeoutError:
                    yield {
                        "comment": "keep-alive"
                    }

        except asyncio.CancelledError:
            logger.info(f"[SSE] Session cancelled: {session_id}")
        except Exception as e:
            logger.error(f"[SSE] Session error: {session_id}, error: {e}")
        finally:
            if session_id in session_queues:
                del session_queues[session_id]
            if session_id in session_sse_queues:
                del session_sse_queues[session_id]
            logger.info(f"[SSE] Session closed: {session_id}")

    return EventSourceResponse(event_generator())


# --- SSE 메시지 수신 엔드포인트 ---

@router.post("/message/{session_id}")
async def receive_message(session_id: str, request: Request):
    """클라이언트로부터 MCP JSON-RPC 메시지 수신"""
    auth_header = request.headers.get("authorization")
    logger.info("-" * 60)
    logger.info(f"[MESSAGE] POST /message/{session_id} - HEADERS:")
    for key, value in request.headers.items():
        if key.lower() == "authorization" and value:
            prefix = value[:20] if len(value) > 20 else value
            logger.info(f"  {key}: {prefix}...({len(value)} chars)")
        else:
            logger.info(f"  {key}: {value}")
    logger.info("-" * 60)

    try:
        body = await request.body()
        message = json.loads(body)
    except json.JSONDecodeError as e:
        logger.error(f"[MESSAGE] JSON parse error: {e}")
        raise HTTPException(status_code=400, detail=f"Invalid JSON: {e}")

    logger.info(f"[MESSAGE] Received for session {session_id}: {json.dumps(message)[:200]}...")
    if "params" in message and "_meta" in message.get("params", {}):
        logger.info(f"[MESSAGE] _meta found: {message['params']['_meta']}")
    else:
        logger.info(f"[MESSAGE] _meta NOT found in params. Full params: {message.get('params', {})}")

    if session_id not in session_queues:
        logger.warning(f"[MESSAGE] Session not found: {session_id}")
        logger.warning(f"[MESSAGE] Active sessions: {list(session_queues.keys())}")
        raise HTTPException(status_code=404, detail="Session not found")

    await session_queues[session_id].put(message)

    return {"status": "accepted"}
