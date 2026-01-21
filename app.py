"""
간단한 MCP (Model Context Protocol) 테스트 서버
SSE (Server-Sent Events) 방식으로 MCP 프로토콜 구현

mcp Python 라이브러리의 sse_client가 기대하는 프로토콜 형식:
1. SSE 연결 시 'endpoint' 이벤트로 POST URL 경로 전송
2. 클라이언트는 해당 URL로 JSON-RPC 메시지 POST
3. 서버는 SSE 'message' 이벤트로 응답 전송
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
                    f"'{query}' 검색 시작...",
                    f"키워드 분석 중...",
                    f"데이터베이스 조회 중...",
                    f"결과 필터링 중...",
                    f"결과 정렬 중...",
                    f"최종 결과 준비 중...",
                ]

                total_steps = min(steps, len(progress_messages))
                results = []

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

                    # 더미 결과 추가
                    results.append(f"결과 {i+1}: {query} 관련 항목")

                message = f"검색 완료! '{query}'에 대해 {len(results)}개의 결과를 찾았습니다.\n" + "\n".join(results)

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
        "transport": "SSE",
        "endpoints": {
            "sse": "/sse"
        }
    }


@app.get("/sse")
async def mcp_sse_endpoint(
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
    
    # 인증 로깅
    print(f"[SSE] Connection request")
    print(f"  - Authorization: {authorization}")
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


if __name__ == "__main__":
    print("=" * 60)
    print("🚀 Test MCP Server Starting...")
    print("=" * 60)
    print("📍 SSE Endpoint: http://localhost:8000/sse")
    print("📍 Health Check: http://localhost:8000/health")
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
    print("\nMISO에서 테스트:")
    print('  서버 설정: {"test_mcp": {"url": "http://localhost:8000/sse"}}')
    print("  인증: None")
    print("\n" + "=" * 60)

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        log_level="info"
    )


