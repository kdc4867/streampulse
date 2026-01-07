# StreamPulse

SOOP/CHZZK 라이브 트래픽을 수집하고 급등 신호를 감지해 대시보드로 보여주는 모니터링 프로젝트입니다.

## 구성
- 데이터 수집: SOOP/CHZZK 카테고리 스냅샷 수집
- 급등 감지: 기준선/단기 추세 비교로 스파이크 이벤트 기록
- API: FastAPI 기반 데이터 제공
- 대시보드: 웹(Vite) + Streamlit
- 에이전트: 이벤트 원인 분석 보조

## 디렉터리
- `src/collectors`: 수집기
- `src/detector`: 급등 감지
- `src/api`: API 서버
- `src/dashboard`: Streamlit 대시보드
- `src/agent`: 분석 에이전트
- `web`: Vite 프론트엔드
- `infra`: Docker/배포 구성
- `docs`: 운영 가이드

## 로컬 실행
### Web
```
cd web
npm run dev
```

### API
```
export POSTGRES_HOST=localhost
uvicorn src.api.main:app --host 0.0.0.0 --port 8080
```

### 간단 확인
```
curl http://localhost:8080/health
curl http://localhost:8080/api/live
curl http://localhost:8080/api/events
```

## Docker (EC2/로컬)
```
cd infra
docker compose up -d --build
```

## 환경 변수
필수 키/접속 정보는 `.env`로 관리합니다.
- `CHZZK_CLIENT_ID`, `CHZZK_CLIENT_SECRET`
- `TELEGRAM_TOKEN`, `TELEGRAM_CHAT_ID`
- `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_HOST`, `POSTGRES_PORT`
- `DB_PATH` (DuckDB 파일 경로)

## 문서
- 운영/배포 절차: `docs/runbook.md`
