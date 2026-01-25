# StreamPulse Runbook

## 로컬 작업
- 프론트 실행
```
cd ~/Desktop/devilstream/web
npm run dev
```

- API 실행
```
cd ~/Desktop/devilstream
export POSTGRES_HOST=localhost
uvicorn src.api.main:app --host 0.0.0.0 --port 8080
```

- 로컬 확인
```
curl http://localhost:8080/health
curl http://localhost:8080/api/live
curl http://localhost:8080/api/events
```

## EC2 접속
```
ssh -i /Users/sujeby/Desktop/devilstream/streampulse-key.pem ubuntu@13.124.251.61
```

## EC2 배포/업데이트
```
cd ~/streampulse
git pull
cd infra
docker compose up -d --build
```

- 특정 서비스만
```
docker compose up -d --build web
docker compose up -d --build api
docker compose up -d --build detector
docker compose up -d --build collector
```

## EC2 상태/로그
```
docker compose ps
docker compose logs --tail=100 api
docker compose logs --tail=100 web
docker compose logs --tail=100 collector
docker compose logs --tail=100 detector
```

## DuckDB 락 충돌 시 조치 (Collector "Could not set lock" 에러)
Collector가 `analytics.db` 락 충돌로 SOOP/CHZZK 저장에 실패할 때:

1. DuckDB를 쓰는 서비스를 **순서대로** 재시작 (collector는 마지막에).
2. `dashboard`는 먼저 멈추고, collector 재시작 후 다시 띄우기.

```bash
cd ~/streampulse/infra
docker compose restart detector
docker compose restart api
docker compose stop dashboard
docker compose restart collector
docker compose start dashboard
```

3. 로그 확인:
```bash
docker compose logs --tail=40 collector
```
`[DuckDB] 스냅샷 ...건 저장 완료` 가 보이면 정상.

- **사전 방지**: detector는 DuckDB `read_only` 연결을 `try/finally`로 항상 `close`. Collector 저장은 락 에러 시 최대 3회 재시도.

## EC2 내부 속도 체크
```
curl -w "TOTAL:%{time_total}\n" -o /dev/null -s http://localhost/
curl -w "TOTAL:%{time_total}\n" -o /dev/null -s http://localhost/api/live
curl -w "TOTAL:%{time_total}\n" -o /dev/null -s http://localhost/api/events
```

## 외부 접속 체크 (로컬에서)
```
curl -I http://13.124.251.61/
curl -I http://13.124.251.61/api/live
```

## 생존 로그 확인 (EC2)
```
docker compose logs --tail=100 collector | grep -E "주기|생존|StreamPulse"
```
