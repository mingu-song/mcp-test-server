"""
간단한 MCP (Model Context Protocol) 테스트 서버

두 가지 전송 방식 지원:
1. SSE (Server-Sent Events) - /sse 엔드포인트 (레거시)
2. Streamable HTTP - /mcp 엔드포인트 (권장, MCP 2025-11 스펙)

Streamable HTTP 프로토콜:
- POST /mcp로 JSON-RPC 메시지 전송
- 응답은 SSE 스트림으로 반환 (progress notification 포함)
- 세션 관리가 필요 없는 stateless 방식
"""
import asyncio
import json
import uuid
from typing import Optional, Dict, Any
from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import StreamingResponse
from sse_starlette.sse import EventSourceResponse
import uvicorn

app = FastAPI(title="Test MCP Server")

# 세션별 응답 큐 관리
session_queues: Dict[str, asyncio.Queue] = {}
# 세션별 응답 대기 큐 (POST 요청이 SSE 응답을 기다림)
session_response_queues: Dict[str, asyncio.Queue] = {}
# 세션별 SSE 출력 큐 (progress notification 등)
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
        """도구 목록 응답 - 지연 추가로 이벤트 루프 충돌 유발"""
        # 5초 지연으로 anyio 이벤트 루프 충돌 유발
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
        print(f"[TOOL] handle_call_tool: tool={tool_name}, progress_token={progress_token}, has_callback={progress_callback is not None}")
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
                # Progress Notification 테스트용 도구
                query = arguments.get("query", "")
                steps = arguments.get("steps", 5)
                print(f"[TOOL] search_with_progress: query='{query}', steps={steps}, progress_token={progress_token}")

                progress_messages = [
                    f"🔍 **검색 시작** - `{query}` 키워드 수신",
                    f"📝 **키워드 분석 중** - 형태소 분석 및 토큰화 진행",
                    f"🗄️ **데이터베이스 조회 중** - 인덱스 탐색 수행",
                    f"⚙️ **결과 필터링 중** - 관련도 기반 필터 적용",
                    f"📊 **결과 정렬 중** - 스코어링 및 랭킹 처리",
                    f"✅ **최종 결과 준비 중** - 응답 포맷팅 완료 단계",
                ]

                total_steps = min(steps, len(progress_messages))

                # 더미 검색 결과 데이터
                dummy_results = [
                    {
                        "title": f"{query} 개요 및 핵심 개념 정리",
                        "url": f"https://example.com/docs/{query.replace(' ', '-')}-overview",
                        "snippet": f"{query}의 기본 개념부터 심화 내용까지 체계적으로 정리한 문서입니다. 입문자부터 숙련자까지 참고할 수 있습니다.",
                        "relevance": 98,
                        "category": "문서",
                    },
                    {
                        "title": f"{query} 실전 활용 가이드 (2024)",
                        "url": f"https://example.com/guide/{query.replace(' ', '-')}-practical",
                        "snippet": f"실무에서 {query}를 효과적으로 활용하는 방법을 단계별로 설명합니다. 다양한 사례와 코드 예제를 포함합니다.",
                        "relevance": 95,
                        "category": "가이드",
                    },
                    {
                        "title": f"{query} 관련 자주 묻는 질문 (FAQ)",
                        "url": f"https://example.com/faq/{query.replace(' ', '-')}",
                        "snippet": f"{query}에 대해 가장 많이 질문되는 항목들을 모아 명확하게 답변한 FAQ 모음입니다.",
                        "relevance": 89,
                        "category": "FAQ",
                    },
                    {
                        "title": f"{query} 성능 벤치마크 및 비교 분석",
                        "url": f"https://example.com/benchmark/{query.replace(' ', '-')}",
                        "snippet": f"다양한 환경에서 {query}의 성능을 측정하고 대안 솔루션과 비교 분석한 리포트입니다.",
                        "relevance": 82,
                        "category": "분석",
                    },
                    {
                        "title": f"{query} 최신 업데이트 및 변경사항",
                        "url": f"https://example.com/changelog/{query.replace(' ', '-')}",
                        "snippet": f"{query}의 최신 버전 릴리즈 노트와 주요 변경사항, 마이그레이션 가이드를 제공합니다.",
                        "relevance": 76,
                        "category": "릴리즈",
                    },
                    {
                        "title": f"{query} 커뮤니티 토론 및 베스트 프랙티스",
                        "url": f"https://example.com/community/{query.replace(' ', '-')}",
                        "snippet": f"개발자 커뮤니티에서 공유된 {query} 관련 팁, 트릭, 베스트 프랙티스를 정리했습니다.",
                        "relevance": 71,
                        "category": "커뮤니티",
                    },
                ]

                for i in range(total_steps):
                    # Progress notification 전송 (progressToken 포함)
                    if progress_callback:
                        print(f"[PROGRESS] Sending with token={progress_token}: {i+1}/{total_steps+1}")
                        await progress_callback(
                            progress=i + 1,
                            total=total_steps + 1,
                            message=progress_messages[i],
                            progress_token=progress_token
                        )
                    print(f"[PROGRESS] {i+1}/{total_steps+1}: {progress_messages[i]}")

                    # 각 단계마다 1초 대기 (실제 작업 시뮬레이션)
                    await asyncio.sleep(1)

                # 결과 조립
                result_count = min(total_steps, len(dummy_results))
                result_entries = []
                for i in range(result_count):
                    r = dummy_results[i]
                    result_entries.append(
                        f"#### {i+1}. {r['title']}\n"
                        f"- 🏷️ **카테고리**: `{r['category']}` | 📈 **관련도**: {r['relevance']}%\n"
                        f"- 🔗 **URL**: [{r['url']}]({r['url']})\n"
                        f"- 💬 {r['snippet']}"
                    )

                elapsed = total_steps  # 1초 × 단계 수
                message = (
                    f"## 🎉 검색 완료\n\n"
                    f"> **`{query}`** 키워드에 대해 **{result_count}건**의 결과를 찾았습니다.\n\n"
                    f"| 항목 | 값 |\n"
                    f"|------|----|\n"
                    f"| 🔎 검색어 | `{query}` |\n"
                    f"| 📄 결과 수 | **{result_count}건** |\n"
                    f"| ⏱️ 소요 시간 | **{elapsed}초** |\n"
                    f"| 📊 최고 관련도 | **{dummy_results[0]['relevance']}%** |\n\n"
                    f"---\n\n"
                    f"### 📋 검색 결과\n\n"
                    + "\n\n".join(result_entries) +
                    f"\n\n---\n\n"
                    f"*💡 더 정확한 결과를 위해 검색어를 구체적으로 입력해 보세요.*"
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

        # _meta에서 progressToken 추출
        meta = params.get("_meta", {})
        progress_token = meta.get("progressToken")

        print(f"[MCP] Received: method={method}, id={request_id}, progressToken={progress_token}")

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
            # 클라이언트 초기화 완료 알림 - 응답 불필요
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
            "sse": "/sse (레거시)"
        }
    }


@app.post("/mcp")
async def mcp_streamable_http_endpoint(request: Request):
    """
    Streamable HTTP 엔드포인트 - MCP 2025-11 스펙 권장 방식

    - POST 요청으로 JSON-RPC 메시지 수신
    - SSE 스트림으로 응답 (progress notification + 최종 결과)
    - Stateless: 각 요청이 독립적으로 처리됨
    """
    # 인증 헤더 로깅
    print("\n" + "=" * 60)
    print("[MCP] 🔐 POST /mcp - Streamable HTTP Request")
    print("=" * 60)
    for key, value in request.headers.items():
        if key.lower() == "authorization" and value:
            prefix = value[:20] if len(value) > 20 else value
            print(f"  {key}: {prefix}...({len(value)} chars)")
        else:
            print(f"  {key}: {value}")
    print("=" * 60)

    # Request body 파싱
    try:
        body = await request.body()
        message = json.loads(body)
    except json.JSONDecodeError as e:
        print(f"[MCP] JSON parse error: {e}")
        raise HTTPException(status_code=400, detail=f"Invalid JSON: {e}")

    print(f"[MCP] Received: {json.dumps(message, ensure_ascii=False)[:200]}...")

    # _meta 확인
    if "params" in message and "_meta" in message.get("params", {}):
        print(f"[MCP] _meta found: {message['params']['_meta']}")

    async def stream_response():
        """SSE 스트림으로 응답 생성"""
        sse_queue = asyncio.Queue()

        # Progress callback - SSE 큐에 notification 추가
        async def progress_callback(progress: float, total: float, message: str, progress_token=None):
            print(f"[MCP PROGRESS] token={progress_token}, {progress}/{total}: {message}")
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

        # 요청 처리 태스크
        async def process_request():
            return await mcp_server.handle_request(message, progress_callback)

        task = asyncio.create_task(process_request())

        # Progress notification과 최종 응답 스트리밍
        while True:
            # SSE 큐에서 progress notification 확인
            try:
                notification = await asyncio.wait_for(sse_queue.get(), timeout=0.1)
                notification_json = json.dumps(notification, ensure_ascii=False)
                print(f"[MCP] Streaming progress: {notification_json}")
                yield f"event: message\ndata: {notification_json}\n\n"
            except asyncio.TimeoutError:
                pass

            # 요청 처리 완료 확인
            if task.done():
                # 남은 progress notification 전송
                while not sse_queue.empty():
                    notification = await sse_queue.get()
                    notification_json = json.dumps(notification, ensure_ascii=False)
                    print(f"[MCP] Streaming progress: {notification_json}")
                    yield f"event: message\ndata: {notification_json}\n\n"

                # 최종 응답 전송
                response = await task
                if response is not None:
                    response_json = json.dumps(response, ensure_ascii=False)
                    print(f"[MCP] Streaming response: {response_json[:200]}...")
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


@app.get("/sse")
async def mcp_sse_endpoint(
    request: Request,
    authorization: Optional[str] = Header(None),
    auth_type: Optional[str] = Header(None),
    api_key_header: Optional[str] = Header(None),
    api_key_header_prefix: Optional[str] = Header(None)
):
    """
    SSE 엔드포인트 - MCP 클라이언트 연결

    mcp 라이브러리의 sse_client 프로토콜:
    1. 연결 시 'endpoint' 이벤트로 POST URL 전송 (순수 경로만)
    2. 클라이언트가 해당 URL로 JSON-RPC 메시지 POST
    3. 서버는 'message' 이벤트로 JSON-RPC 응답 전송
    """

    # 인증 로깅 - 상세
    print("\n" + "=" * 60)
    print("[SSE] 🔐 Connection request - HEADERS:")
    print("=" * 60)
    for key, value in request.headers.items():
        # Authorization 헤더는 토큰 마스킹
        if key.lower() == "authorization" and value:
            prefix = value[:20] if len(value) > 20 else value
            print(f"  {key}: {prefix}...({len(value)} chars)")
        else:
            print(f"  {key}: {value}")
    print("=" * 60)

    # 파싱된 값 출력
    print(f"[SSE] Parsed headers:")
    print(f"  - Authorization: {'Bearer token (' + str(len(authorization)) + ' chars)' if authorization else 'None'}")
    print(f"  - auth_type: {auth_type}")
    
    async def event_generator():
        """SSE 이벤트 생성기"""
        session_id = str(uuid.uuid4())

        # 세션 큐 생성
        request_queue = asyncio.Queue()
        sse_queue = asyncio.Queue()  # Progress notification 등 SSE 출력용
        session_queues[session_id] = request_queue
        session_sse_queues[session_id] = sse_queue

        print(f"[SSE] Session started: {session_id}")

        try:
            # 1. endpoint 이벤트 전송 - mcp 라이브러리가 기대하는 형식
            # 순수 URL 경로만 전송해야 함!
            yield {
                "event": "endpoint",
                "data": f"/message/{session_id}"
            }
            print(f"[SSE] Sent endpoint: /message/{session_id}")

            # 2. 클라이언트 요청 대기 및 응답
            while True:
                try:
                    # 큐에서 요청 대기 (타임아웃 30초)
                    request_data = await asyncio.wait_for(
                        request_queue.get(),
                        timeout=30.0
                    )

                    print(f"[SSE] Processing request: {request_data}")

                    # Progress callback 정의 - SSE 큐에 progress notification 추가
                    async def progress_callback(progress: float, total: float, message: str, progress_token=None):
                        print(f"[CALLBACK] progress_callback called: token={progress_token}, progress={progress}/{total}, message={message}")
                        notification = {
                            "jsonrpc": "2.0",
                            "method": "notifications/progress",
                            "params": {
                                "progressToken": progress_token,  # MCP 스펙 필수 필드
                                "progress": progress,
                                "total": total,
                                "message": message
                            }
                        }
                        # progressToken이 없으면 params에서 제거 (클라이언트가 토큰 안 보낸 경우)
                        if progress_token is None:
                            print(f"[CALLBACK] WARNING: progressToken is None! Client may not receive progress.")
                            del notification["params"]["progressToken"]
                        else:
                            print(f"[CALLBACK] Notification with progressToken: {notification}")
                        await sse_queue.put(notification)

                    # MCP 요청 처리 (백그라운드 태스크로 실행하여 progress를 실시간 전송)
                    async def process_request():
                        return await mcp_server.handle_request(request_data, progress_callback)

                    # 요청 처리 태스크 시작
                    task = asyncio.create_task(process_request())

                    # 요청 처리 중 progress notification과 최종 응답 전송
                    while True:
                        # SSE 큐에서 progress notification 확인 (짧은 타임아웃)
                        try:
                            notification = await asyncio.wait_for(
                                sse_queue.get(),
                                timeout=0.1
                            )
                            notification_json = json.dumps(notification)
                            print(f"[SSE] Sending progress: {notification_json}")
                            yield {
                                "event": "message",
                                "data": notification_json
                            }
                        except asyncio.TimeoutError:
                            pass

                        # 요청 처리 완료 확인
                        if task.done():
                            # 남은 progress notification 모두 전송
                            while not sse_queue.empty():
                                notification = await sse_queue.get()
                                notification_json = json.dumps(notification)
                                print(f"[SSE] Sending progress: {notification_json}")
                                yield {
                                    "event": "message",
                                    "data": notification_json
                                }

                            # 최종 응답 전송
                            response = await task
                            if response is not None:
                                response_json = json.dumps(response)
                                print(f"[SSE] Sending response: {response_json[:200]}...")
                                yield {
                                    "event": "message",
                                    "data": response_json
                                }
                            break

                except asyncio.TimeoutError:
                    # Keep-alive: 빈 코멘트 전송
                    yield {
                        "comment": "keep-alive"
                    }

        except asyncio.CancelledError:
            print(f"[SSE] Session cancelled: {session_id}")
        except Exception as e:
            print(f"[SSE] Session error: {session_id}, error: {e}")
        finally:
            # 세션 정리
            if session_id in session_queues:
                del session_queues[session_id]
            if session_id in session_sse_queues:
                del session_sse_queues[session_id]
            print(f"[SSE] Session closed: {session_id}")
    
    return EventSourceResponse(event_generator())


@app.post("/message/{session_id}")
async def receive_message(session_id: str, request: Request):
    """
    클라이언트로부터 MCP JSON-RPC 메시지 수신

    mcp 라이브러리는 이 엔드포인트로 JSON-RPC 요청을 POST하고,
    SSE 스트림을 통해 응답을 받음
    """
    # 헤더 로깅
    auth_header = request.headers.get("authorization")
    print("\n" + "-" * 60)
    print(f"[MESSAGE] 🔐 POST /message/{session_id} - HEADERS:")
    for key, value in request.headers.items():
        if key.lower() == "authorization" and value:
            prefix = value[:20] if len(value) > 20 else value
            print(f"  {key}: {prefix}...({len(value)} chars)")
        else:
            print(f"  {key}: {value}")
    print("-" * 60)

    # Request body 파싱
    try:
        body = await request.body()
        message = json.loads(body)
    except json.JSONDecodeError as e:
        print(f"[MESSAGE] JSON parse error: {e}")
        raise HTTPException(status_code=400, detail=f"Invalid JSON: {e}")

    print(f"[MESSAGE] Received for session {session_id}: {json.dumps(message)[:200]}...")
    # _meta 확인을 위한 상세 로그
    if "params" in message and "_meta" in message.get("params", {}):
        print(f"[MESSAGE] _meta found: {message['params']['_meta']}")
    else:
        print(f"[MESSAGE] _meta NOT found in params. Full params: {message.get('params', {})}")
    
    if session_id not in session_queues:
        print(f"[MESSAGE] Session not found: {session_id}")
        print(f"[MESSAGE] Active sessions: {list(session_queues.keys())}")
        raise HTTPException(status_code=404, detail="Session not found")
    
    # 요청을 SSE 처리 큐에 추가
    await session_queues[session_id].put(message)
    
    # 202 Accepted 반환 (응답은 SSE로 전송됨)
    return {"status": "accepted"}


@app.get("/health")
async def health_check():
    """헬스체크"""
    return {
        "status": "healthy",
        "active_sessions": len(session_queues),
        "sessions": list(session_queues.keys())
    }


# ============================================================
# Custom API Guardrail 테스트 엔드포인트
# ============================================================

_guardrail_file_count = 0

@app.post("/guardrail")
async def guardrail_endpoint(request: Request):
    """
    Custom API 가드레일 테스트 엔드포인트

    MISO CustomApiGuardrailEngine이 호출하는 형식:
    - Input:  {"text": "...", "source": "INPUT",  "metadata": {...}}
    - Output: {"text": "...", "source": "OUTPUT", "metadata": {...}}
    - File:   {"text": "", "file": {"filename": "...", "mimetype": "...", "content_base64": "..."}, "source": "FILE", "metadata": {...}}

    응답:
    - 안전: {"action": "NONE", "is_safe": true}
    - 차단: {"action": "GUARDRAIL_INTERVENED", "is_safe": false, "blocked_reasons": {...}}
    """
    # 헤더 로깅
    print("\n" + "=" * 60)
    print("[GUARDRAIL] POST /guardrail")
    print("=" * 60)
    for key, value in request.headers.items():
        if key.lower() in ("authorization", "x-api-key") and value:
            prefix = value[:20] if len(value) > 20 else value
            print(f"  {key}: {prefix}...({len(value)} chars)")
        else:
            print(f"  {key}: {value}")
    print("-" * 60)

    # Body 파싱
    try:
        body = await request.body()
        payload = json.loads(body)
    except json.JSONDecodeError as e:
        print(f"[GUARDRAIL] JSON parse error: {e}")
        raise HTTPException(status_code=400, detail=f"Invalid JSON: {e}")

    source = payload.get("source", "UNKNOWN")
    text = payload.get("text", "")
    metadata = payload.get("metadata", {})
    file_info = payload.get("file")

    print(f"[GUARDRAIL] source={source}")
    print(f"[GUARDRAIL] text={text[:200]}{'...' if len(text) > 200 else ''}")
    print(f"[GUARDRAIL] metadata={json.dumps(metadata, ensure_ascii=False)}")
    if file_info:
        print(f"[GUARDRAIL] file.filename={file_info.get('filename')}")
        print(f"[GUARDRAIL] file.mimetype={file_info.get('mimetype')}")
        content_b64 = file_info.get("content_base64", "")
        print(f"[GUARDRAIL] file.content_base64=({len(content_b64)} chars)")
    print("=" * 60)

    # FILE 소스: 두 번에 한 번씩 차단
    if source == "FILE":
        global _guardrail_file_count
        _guardrail_file_count += 1
        print(f"[GUARDRAIL] file_call_count={_guardrail_file_count}")

        if _guardrail_file_count % 2 == 0:
            print(f"[GUARDRAIL] => FILE BLOCKED (count={_guardrail_file_count}, even)")
            print("=" * 60)
            return {
                "action": "GUARDRAIL_INTERVENED",
                "is_safe": False,
                "blocked_reasons": {
                    "reason": "파일 가드레일 차단 (simulated failure)",
                },
            }

        print(f"[GUARDRAIL] => FILE PASSED (count={_guardrail_file_count}, odd)")
        print("=" * 60)
        return {
            "action": "NONE",
            "is_safe": True,
        }

    # "아이유" 포함 여부 검사 (INPUT/OUTPUT)
    if "아이유" in text:
        print("[GUARDRAIL] BLOCKED: '아이유' detected")
        print("=" * 60)
        return {
            "action": "GUARDRAIL_INTERVENED",
            "is_safe": False,
            "blocked_reasons": {
                "reason": "'아이유' 관련 내용은 허용되지 않습니다.",
            },
        }

    # 안전 응답
    print("[GUARDRAIL] => PASSED")
    print("=" * 60)
    return {
        "action": "NONE",
        "is_safe": True,
    }


@app.post("/files")
async def files_endpoint(request: Request):
    """
    파일 전처리 테스트 엔드포인트

    호출 방식:
        client.post(url, files={"file": (filename, content)}, headers={"X-API-KEY": api_key})

    동작: 받은 파일을 로깅하고 파일 내용을 그대로 반환
    """
    from fastapi.responses import Response

    # 헤더 로깅
    print("\n" + "=" * 60)
    print("[FILES] POST /files")
    print("=" * 60)
    for key, value in request.headers.items():
        if key.lower() in ("x-api-key", "authorization") and value:
            prefix = value[:20] if len(value) > 20 else value
            print(f"  {key}: {prefix}...({len(value)} chars)")
        else:
            print(f"  {key}: {value}")
    print("-" * 60)

    # multipart/form-data 에서 파일 추출
    form = await request.form()
    file = form.get("file")

    if file is None:
        print("[FILES] ERROR: 'file' field not found in form data")
        raise HTTPException(status_code=400, detail="'file' field is required")

    filename = file.filename
    content = await file.read()
    content_type = file.content_type or "application/octet-stream"

    print(f"[FILES] filename={filename}")
    print(f"[FILES] content_type={content_type}")
    print(f"[FILES] content_size={len(content)} bytes")
    print(f"[FILES] content_preview={content[:200]}")
    print("=" * 60)

    # 받은 파일 내용을 그대로 반환
    return Response(
        content=content,
        media_type=content_type,
        headers={"X-Filename": filename},
    )


if __name__ == "__main__":
    print("=" * 60)
    print("🚀 Test MCP Server Starting...")
    print("=" * 60)
    print("📍 Streamable HTTP (권장): http://localhost:8000/mcp")
    print("📍 SSE (레거시):          http://localhost:8000/sse")
    print("📍 Custom API Guardrail:  http://localhost:8000/guardrail")
    print("📍 Health Check:          http://localhost:8000/health")
    print("=" * 60)
    print("\n사용 가능한 도구:")
    for tool in mcp_server.tools:
        print(f"  - {tool['name']}: {tool['description']}")
    print("\n" + "=" * 60)
    print("\n⭐ Progress Notification 테스트:")
    print("  도구: search_with_progress")
    print("  파라미터: query (검색어), steps (단계 수, 기본 5)")
    print("  동작: 각 단계마다 1초 대기 + Progress Notification 전송")
    print("\n" + "=" * 60)
    print("\n🛡️ Custom API 가드레일 테스트:")
    print("  엔드포인트: http://localhost:8000/guardrail")
    print("  인증: 헤더 로깅만 (X-API-Key, Authorization)")
    print("  동작: 모든 요청에 안전 응답 반환 + 로깅")
    print("  MISO 설정:")
    print("    - API Endpoint: http://localhost:8000/guardrail")
    print("    - Auth Type: api_key (또는 bearer/none)")
    print("    - API Key: test-key-12345 (아무 값)")
    print("\n" + "=" * 60)
    print("\n📋 MISO에서 테스트:")
    print("")
    print("  [Streamable HTTP - 권장]")
    print('  서버 설정: {"test_mcp": {"url": "http://localhost:8000/mcp"}}')
    print("")
    print("  [SSE - 레거시]")
    print('  서버 설정: {"test_mcp": {"url": "http://localhost:8000/sse"}}')
    print("")
    print("  인증: 없음")
    print("\n" + "=" * 60)

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        log_level="info"
    )


