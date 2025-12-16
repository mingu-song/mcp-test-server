# Test MCP Server

MISO MCP 도구 테스트를 위한 간단한 MCP 서버

## 설치

```bash
cd /Users/kade/project/test_mcp_server
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## 실행

```bash
python app.py
```

서버가 `http://localhost:8000`에서 실행됩니다.

## 엔드포인트

- `GET /` - 서버 정보
- `GET /sse` - MCP SSE 연결
- `POST /message/{session_id}` - MCP 메시지 수신
- `GET /health` - 헬스체크

## MISO에서 테스트

### 1. 로컬 환경 테스트

1. MISO 웹 접속 (http://localhost:3000)
2. 도구 > MCP 도구 생성
3. 서버 설정 입력:
   ```json
   {
     "test_mcp": {
       "url": "http://localhost:8000/sse"
     }
   }
   ```
4. 인증 방식: "None" 선택
5. "MCP Tools 가져오기" 클릭

### 2. 컨테이너 환경 테스트

Docker 컨테이너에서 로컬 MCP 서버 접근:

```json
{
  "test_mcp": {
    "url": "http://host.docker.internal:8000/sse"
  }
}
```

### 3. ngrok으로 외부 노출 (선택)

```bash
# 다른 터미널에서
ngrok http 8000
```

ngrok URL을 MISO 서버 설정에 사용:
```json
{
  "test_mcp": {
    "url": "https://xxxx-xxx-xxx-xxx.ngrok.io/sse"
  }
}
```

## 사용 가능한 도구

### 1. add_numbers
두 숫자를 더합니다.

**파라미터:**
- `a` (number, required) - 첫 번째 숫자
- `b` (number, required) - 두 번째 숫자

**예시:**
```json
{
  "a": 10,
  "b": 20
}
```

**결과:** `"10 + 20 = 30"`

### 2. multiply_numbers
두 숫자를 곱합니다.

**파라미터:**
- `x` (number, required) - 첫 번째 숫자
- `y` (number, required) - 두 번째 숫자

**예시:**
```json
{
  "x": 5,
  "y": 7
}
```

**결과:** `"5 × 7 = 35"`

### 3. get_greeting
인사말을 생성합니다.

**파라미터:**
- `name` (string, required) - 이름
- `language` (string, optional) - 언어 (ko, en), 기본값: "ko"

**예시:**
```json
{
  "name": "홍길동",
  "language": "ko"
}
```

**결과:** `"안녕하세요, 홍길동님!"`

## 테스트 시나리오

### 시나리오 1: 로컬 환경에서 asyncio 동작 확인

```bash
# Terminal 1: MCP 서버 실행
cd /Users/kade/project/test_mcp_server
source venv/bin/activate
python app.py

# Terminal 2: MISO API 실행 (Flask dev server)
cd /Users/kade/project/miso/api
poetry run python app.py

# 웹 브라우저: MISO 웹 접속
# http://localhost:3000
# 도구 > MCP 도구 생성 > "MCP Tools 가져오기" 클릭
```

**예상 결과:** 정상 동작 (RuntimeError 분기)

### 시나리오 2: 컨테이너 환경에서 gevent 동작 확인

```bash
# Terminal 1: MCP 서버 실행
cd /Users/kade/project/test_mcp_server
source venv/bin/activate
python app.py

# Terminal 2: MISO 컨테이너 실행
cd /Users/kade/project/miso
docker-compose up api

# 웹 브라우저: MISO 웹 접속
# 서버 설정: http://host.docker.internal:8000/sse
```

**예상 결과:** 정상 동작 (ThreadPoolExecutor 분기)

### 시나리오 3: 에러 재현 (수정 전 코드)

```bash
# 1. 수정 전 커밋으로 이동
cd /Users/kade/project/miso
git checkout 430535e09b9cc2ae670b2b76dd72111af27762d8^

# 2. 컨테이너 재시작
docker-compose restart api

# 3. "MCP Tools 가져오기" 클릭
```

**예상 결과:** `RuntimeError: asyncio.run() cannot be called from a running event loop`

## 로그 확인

### MCP 서버 로그

```
[SSE] Connection request
  - Authorization: None
  - auth_type: None
  - api_key_header: None
  - api_key_header_prefix: None
[SSE] Session started: abc-123-def-456
[MCP] Received: method=initialize, id=1
[MCP] Received: method=tools/list, id=2
[SSE] Session closed: abc-123-def-456
```

### MISO API 로그

```
2025-12-16 09:16:19 INFO - POST /console/api/workspaces/current/tool-provider/mcp/tools
2025-12-16 09:16:19 INFO - Fetching MCP tools from http://localhost:8000/sse
2025-12-16 09:16:20 INFO - Successfully fetched 3 tools
```

## 트러블슈팅

### 1. 포트 충돌

```bash
# 8000번 포트가 사용 중인 경우
lsof -ti:8000 | xargs kill -9
```

### 2. 연결 실패

```bash
# MCP 서버 상태 확인
curl http://localhost:8000/health

# 예상 응답:
# {"status":"healthy","active_sessions":0}
```

### 3. CORS 에러

FastAPI는 기본적으로 CORS를 허용하지 않습니다. 필요시 `app.py`에 추가:

```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

## 참고 자료

- [MCP Protocol Specification](https://modelcontextprotocol.io/)
- [SSE (Server-Sent Events)](https://developer.mozilla.org/en-US/docs/Web/API/Server-sent_events)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
