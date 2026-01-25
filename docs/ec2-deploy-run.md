# EC2 배포 실행 가이드

`deployment-checklist.md` 체크 완료 후, EC2에서 실제 배포할 때 사용하는 단계별 가이드입니다.  
문제 발생 시 **트러블슈팅** 섹션을 참고하세요.

---

## 1. EC2 준비

### 1.1 Docker 설치 (미설치 시)

```bash
# Amazon Linux 2
sudo yum update -y
sudo yum install -y docker
sudo systemctl start docker
sudo systemctl enable docker
sudo usermod -aG docker $USER
# 로그아웃 후 재접속

# Docker Compose v2 (플러그인)
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose
# 또는: Docker Engine 20.10+ 에서 docker compose (플러그인) 사용
```

### 1.2 보안 그룹

아래 포트가 **인바운드**로 열려 있어야 합니다.

| 포트 | 용도 |
|------|------|
| 22 | SSH |
| 80 | Web (프론트) |
| 8000 | Agent (선택) |
| 8081 | API (직접 호출/디버깅) |
| 8501 | Streamlit Dashboard (선택) |

---

## 2. 프로젝트 올리기

### 2.1 코드 배포

```bash
# Git으로 클론 (또는 scp/rsync로 올린 경우 해당 경로로)
git clone <repo-url> devilstream
cd devilstream
git pull origin main
```

### 2.2 환경 변수

- 프로젝트 **루트**에 `.env` 파일 생성.
- `docs/deployment-checklist.md` **1. 환경 변수 확인** 참고.
- **필수**: `OPENAI_API_KEY`, `CHZZK_CLIENT_ID`, `CHZZK_CLIENT_SECRET`, `TELEGRAM_TOKEN`, `TELEGRAM_CHAT_ID`, Postgres 관련(`POSTGRES_*`).
- Docker 내부에서는 `POSTGRES_HOST=postgres` 사용 (기본값이므로 없어도 됨).

```bash
# 예시 확인
grep -E "OPENAI_API_KEY|REDIS_URL|POSTGRES" .env
```

### 2.3 data 디렉터리

- DuckDB·마운트용 `data/` 디렉터리 필요. (`data/`는 .gitignore 됨.)
- 배포 스크립트가 `mkdir -p data` 로 생성함. 수동으로 해도 됨.

```bash
mkdir -p data
```

---

## 3. 배포 실행

### 방법 A: 배포 스크립트 사용 (권장)

```bash
chmod +x scripts/deploy-ec2.sh
./scripts/deploy-ec2.sh
```

- `.env` 확인, `data` 생성, `docker compose up -d --build`, health/Redis 체크까지 수행.

### 방법 B: 수동

```bash
cd infra
docker compose down
docker compose up -d --build
docker compose ps
```

---

## 4. 배포 후 확인

```bash
cd infra

# 모든 컨테이너 Up 확인
docker compose ps

# API Health
curl -s http://localhost:8081/health
# => {"status":"ok"}

# Redis
docker exec stream_redis redis-cli ping
# => PONG

# Web (호스트 80 → nginx → /health, /api)
curl -s http://localhost/health
curl -s http://localhost/api/live
```

- 브라우저: `http://<EC2-퍼블릭-IP>/` 로 접속.
- Dashboard 상태에서 API/DB 체크 항목이 정상이면 OK.

---

## 5. 트러블슈팅

### 5.1 `OPENAI_API_KEY` / `TELEGRAM_*` 관련

- **증상**: Agent·Worker 로그에 API/Telegram 에러.
- **조치**: `.env`에 키 올바르게 설정, `infra`에서 `env_file: ../.env` 로드되는지 확인. 수정 후 `docker compose up -d --build` 재실행.

### 5.2 `DB Init Fail` (Detector)

- **증상**: detector 로그에 `[Detector] DB Init Fail: ...`
- **조치**: Postgres 먼저 기동 확인. `docker compose ps`로 `stream_meta_db` Up 여부 확인.  
  - 필요 시 `docker compose up -d postgres` 후 10초 대기, 그다음 `docker compose up -d`.

### 5.3 Redis 연결 실패

- **증상**: agent/worker/detector에서 Redis 연결 오류.
- **조치**: `REDIS_URL=redis://redis:6379/0` (기본값) 사용 시, `redis` 서비스가 먼저 떠 있어야 함.  
  - `docker compose up -d redis` 후 다른 서비스 재기동.  
  - Redis 없어도 캐싱만 빠지고 동작은 함 (체크리스트 참고).

### 5.4 API 8081 / Web 80 안 열림

- **증상**: `curl localhost:8081` 또는 `curl localhost/health` 실패.
- **조치**:
  - `docker compose ps`로 `stream_api`, `stream_web` Up 확인.
  - EC2 보안 그룹에서 **8081**, **80** 인바운드 허용 확인.
  - `docker compose logs api`, `docker compose logs web` 로 에러 확인.

### 5.5 Web에서 "API/DB 상태" 빨간색

- **증상**: 프론트는 뜨는데 상태 표시만 실패.
- **조치**: nginx가 `/health`, `/api/` 를 API로 프록시해야 함.  
  - `infra/nginx.conf`에 `location /health`와 `location /api/` 가 있는지 확인.  
  - 수정 시 `docker compose up -d --build web` 으로 웹 이미지 재빌드.

### 5.6 포트 충돌 (80, 5432, 6379 등)

- **증상**: `bind: address already in use` 등.
- **조치**: 해당 포트 사용 프로세스 확인 후 중지하거나, `docker-compose.yml`에서 호스트 포트 변경.

### 5.7 `data/analytics.db` 권한

- **증상**: collector/detector에서 DuckDB 파일 쓰기 오류.
- **조치**: `data/` 디렉터리 및 `data/analytics.db` 소유/권한 확인.  
  - `chmod 755 data`, `chmod 644 data/analytics.db` (또는 Docker 사용 UID에 맞게 조정).

### 5.8 롤백

- 체크리스트 **9. 롤백 계획** 참고.  
  - `git checkout origin/main` 후 `docker compose down` → `docker compose up -d --build`.

---

## 6. 로그 모니터링

```bash
cd infra
docker compose logs -f

# 개별 서비스
docker compose logs -f collector
docker compose logs -f detector
docker compose logs -f agent
docker compose logs -f agent-worker
docker compose logs -f api
```

---

**작성일**: 2026-01-25  
**기준**: `deployment-checklist.md` v3 (Redis + Agent Worker)
