# Test MCP Server

MCP 도구 및 Custom API 가드레일 테스트를 위한 서버

## 프로젝트 구조

```
test_mcp_server/
  app.py                  # 메인 (로거, FastAPI 앱, 라우터 등록)
  routes/
    mcp.py                # MCP 프로토콜 (/mcp, /mcp2, /sse, /message)
    guardrail.py          # Custom API 가드레일 (/guardrail)
    files.py              # 파일 전처리 (/files)
  requirements.txt
```

## 설치 및 실행

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python app.py
```

서버: `http://localhost:8000`

## 엔드포인트

| 엔드포인트 | 메서드 | 설명 |
|---|---|---|
| `/mcp`, `/mcp2` | POST | Streamable HTTP (권장) |
| `/sse` | GET | SSE 연결 (레거시) |
| `/message/{session_id}` | POST | SSE 메시지 수신 |
| `/guardrail` | POST | Custom API 가드레일 |
| `/files` | POST | 파일 업로드/반환 |
| `/health` | GET | 헬스체크 |
| `/` | GET | 서버 정보 |

## MCP 도구

| 도구 | 설명 | 필수 파라미터 |
|---|---|---|
| `add_numbers` | 두 숫자를 더합니다 | `a`, `b` (number) |
| `multiply_numbers` | 두 숫자를 곱합니다 | `x`, `y` (number) |
| `get_greeting` | 인사말 생성 | `name` (string), `language` (optional, ko/en) |
| `search_with_progress` | 검색 + Progress Notification | `query` (string), `steps` (optional, 기본 5) |

## 가드레일 차단 규칙

| 소스 | 규칙 |
|---|---|
| `INPUT` | 3번에 1번 차단 |
| `OUTPUT` | 3번에 1번 차단 |
| `FILE` | 2번에 1번 차단 |
| 키워드 | "아이유" 포함 시 차단 |

요청/응답 형식:

```jsonc
// 요청
{"text": "...", "source": "INPUT", "metadata": {}}

// 통과
{"action": "NONE", "is_safe": true}

// 차단
{"action": "GUARDRAIL_INTERVENED", "is_safe": false, "blocked_reasons": {"reason": "..."}}
```

## MISO 연동

### Streamable HTTP (권장)

```json
{"test_mcp": {"url": "http://localhost:8000/mcp"}}
```

### SSE (레거시)

```json
{"test_mcp": {"url": "http://localhost:8000/sse"}}
```

### Docker 환경

```json
{"test_mcp": {"url": "http://host.docker.internal:8000/mcp"}}
```

## 트러블슈팅

```bash
# 헬스체크
curl http://localhost:8000/health

# 포트 충돌 시
lsof -ti:8000 | xargs kill -9
```
