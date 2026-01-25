# 배포 전 체크리스트 (EC2 배포용)

## 📋 주요 변경사항 요약

### 🆕 새로 추가된 기능
1. **Redis 캐싱 시스템** - 중복 분석 방지
2. **Agent Worker** - 백그라운드 이벤트 처리 워커
3. **개선된 LangGraph 워크플로우** - Watcher → Cache → Searcher → Analyst → Editor
4. **향상된 Detector 로직** - 더 정교한 급등 감지

### 🔄 수정된 주요 파일
- `src/agent/graph.py` - 완전히 재작성 (LangGraph 워크플로우)
- `src/detector/signal_detector.py` - 감지 로직 개선, 환경변수 추가
- `src/agent/worker.py` - **새 파일** (이벤트 처리 워커)
- `src/agent/cache.py` - **새 파일** (Redis 캐싱)
- `infra/docker-compose.yml` - Redis, agent-worker 서비스 추가
- `requirements.txt` - redis, tavily-python 추가

### ⚠️ 주의사항
- **API 포트 변경**: 8080 → 8081 (포트 충돌 방지)
- **새 서비스 추가**: Redis, agent-worker

---

## ✅ 배포 전 필수 체크리스트

### 1. 환경 변수 확인

#### 필수 환경변수 (기존)
```bash
# 플랫폼 API
CHZZK_CLIENT_ID=xxx
CHZZK_CLIENT_SECRET=xxx

# 알림
TELEGRAM_TOKEN=xxx
TELEGRAM_CHAT_ID=xxx

# 데이터베이스
POSTGRES_DB=streampulse_meta
POSTGRES_USER=user
POSTGRES_PASSWORD=password
POSTGRES_HOST=postgres  # Docker 내부에서는 postgres
POSTGRES_PORT=5432

# DuckDB
DB_PATH=/app/data/analytics.db

# OpenAI (필수!)
OPENAI_API_KEY=sk-xxx
```

#### 새로 추가된 환경변수 (선택)
```bash
# Redis (기본값 있음, 선택사항)
REDIS_URL=redis://redis:6379/0

# 검색 API (선택사항 - 없으면 DuckDuckGo 사용)
BRAVE_API_KEY=xxx        # Brave Search API (우선순위 1)
TAVILY_API_KEY=xxx       # Tavily Search API (우선순위 2)

# Agent Worker 설정 (선택사항)
AGENT_ALERT_MODE=confirmed  # all | confirmed
ALERT_KEYWORDS=패치,업데이트

# Detector 설정 (선택사항)
CANDIDATE_COOLDOWN_MINUTES=120
INTEREST_GROWTH=1.2
INTEREST_DELTA=500
INTEREST_TOP_N=10
MAJOR_TOP_N=12
DETECTOR_ALERT_MODE=post_research  # immediate | post_research
```

**체크**: EC2의 `.env` 파일에 `OPENAI_API_KEY`가 있는지 확인!

---

### 2. Docker Compose 변경사항 확인

#### 새로 추가된 서비스
- ✅ **redis**: Redis 캐싱 서버
- ✅ **agent-worker**: 백그라운드 이벤트 처리 워커

#### 변경된 설정
- API 포트: `8080` → `8081` (외부 포트)
- detector에 `redis` 의존성 추가
- agent, agent-worker에 `REDIS_URL` 환경변수 추가

**체크**: EC2에서 `docker compose up -d --build` 실행 시 모든 서비스가 정상 시작되는지 확인

---

### 3. 데이터베이스 마이그레이션

#### Postgres 테이블 스키마 변경
`signal_events` 테이블에 새 컬럼이 추가됩니다:
- `analysis_status` (VARCHAR)
- `analysis_tier` (VARCHAR)
- `spike_reason` (TEXT)
- `entity_keywords` (JSONB)
- `context_cache_key` (TEXT)

**자동 마이그레이션**: `signal_detector.py`의 `init_db()` 함수가 자동으로 컬럼을 추가합니다.

**체크**: 배포 후 detector 로그에서 "DB Init Fail" 메시지가 없는지 확인

---

### 4. 의존성 확인

#### 새로 추가된 Python 패키지
```txt
redis
tavily-python
```

**체크**: 
- `requirements.txt`에 포함되어 있는지 확인 ✅
- Docker 이미지 빌드 시 정상 설치되는지 확인

---

### 5. 서비스 시작 순서

배포 시 권장 순서:
1. `postgres` - 데이터베이스
2. `redis` - 캐시 서버
3. `collector` - 데이터 수집
4. `detector` - 급등 감지
5. `agent` - 분석 API 서버
6. `agent-worker` - 백그라운드 워커
7. `api` - REST API
8. `web` - 프론트엔드

**체크**: `docker compose up -d` 실행 후 모든 컨테이너가 `Up` 상태인지 확인
```bash
docker compose ps
```

---

### 6. 포트 확인

변경된 포트:
- API: `8081` (기존 8080에서 변경)

기존 포트:
- Web: `80`
- Dashboard: `8501`
- Agent: `8000`
- Postgres: `5432`
- Redis: `6379`

**체크**: EC2 보안 그룹에서 포트 8081이 열려있는지 확인

---

### 7. 기능 테스트

배포 후 다음을 테스트:

#### ✅ 기본 기능
```bash
# Health check
curl http://localhost:8081/health

# 실시간 데이터
curl http://localhost:8081/api/live

# 이벤트 목록
curl http://localhost:8081/api/events
```

#### ✅ Agent Worker 동작 확인
```bash
# agent-worker 로그 확인
docker logs stream_agent_worker

# Postgres에서 PENDING 이벤트 확인
docker exec -it stream_meta_db psql -U user -d streampulse_meta -c "SELECT event_id, platform, category_name, analysis_status FROM signal_events ORDER BY created_at DESC LIMIT 5;"
```

#### ✅ Redis 연결 확인
```bash
# Redis 연결 테스트
docker exec -it stream_redis redis-cli ping
# 응답: PONG
```

---

### 8. 로그 모니터링

배포 후 다음 로그를 모니터링:

```bash
# Collector
docker logs -f stream_collector

# Detector
docker logs -f stream_detector

# Agent Worker
docker logs -f stream_agent_worker

# Agent API
docker logs -f stream_agent
```

**체크 포인트**:
- ❌ 에러 메시지가 없는지
- ✅ "시작" 메시지가 있는지
- ✅ 정상적인 작업 로그가 출력되는지

---

### 9. 롤백 계획

문제 발생 시 롤백 방법:

```bash
# 1. 현재 버전으로 롤백
cd /path/to/ec2/project
git checkout origin/main

# 2. 서비스 재시작
cd infra
docker compose down
docker compose up -d --build
```

---

### 10. 알려진 이슈 및 주의사항

#### ⚠️ 주의사항
1. **Redis가 없어도 동작**: Redis 연결 실패 시 캐싱 없이 동작 (성능 저하 가능)
2. **Agent Worker는 선택사항**: 없어도 동작하지만, 이벤트 분석이 자동으로 처리되지 않음
3. **검색 API**: Brave/Tavily 없어도 DuckDuckGo로 동작 (품질 차이 가능)

#### 🔍 확인할 사항
- OpenAI API 키가 유효한지
- EC2 메모리/CPU가 충분한지 (새 서비스 추가로 리소스 사용 증가)
- DuckDB 파일 권한 (`data/analytics.db`)

---

## 🚀 배포 명령어

**실제 EC2 배포 절차·트러블슈팅**: → **[docs/ec2-deploy-run.md](ec2-deploy-run.md)** 참고.

```bash
# 1. 코드 업데이트
cd /path/to/project
git pull origin main  # 또는 로컬에서 push 후

# 2. 환경변수 확인
cat .env | grep -E "OPENAI_API_KEY|REDIS_URL"

# 3. Docker Compose 재빌드 및 시작 (또는 ./scripts/deploy-ec2.sh)
cd infra
docker compose down
docker compose up -d --build

# 4. 서비스 상태 확인
docker compose ps

# 5. 로그 확인
docker compose logs -f
```

---

## ✅ 최종 체크리스트

배포 전:
- [ ] `.env` 파일에 `OPENAI_API_KEY` 확인
- [ ] `requirements.txt`에 `redis`, `tavily-python` 포함 확인
- [ ] `docker-compose.yml`에 `redis`, `agent-worker` 서비스 확인
- [ ] EC2 포트 8081 열려있는지 확인
- [ ] 데이터 백업 (선택사항)

배포 후:
- [ ] 모든 컨테이너가 `Up` 상태인지 확인
- [ ] Health check API 응답 확인
- [ ] Agent Worker 로그에서 에러 없는지 확인
- [ ] Redis 연결 확인
- [ ] 실제 이벤트가 처리되는지 확인

---

**작성일**: 2026-01-XX  
**버전**: v3 (Redis + Agent Worker 추가)
