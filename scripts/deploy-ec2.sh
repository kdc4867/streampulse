#!/bin/bash
# EC2 배포 스크립트 (프로젝트 루트 또는 infra 기준 실행)
# 사용법: ./scripts/deploy-ec2.sh   또는  cd infra && ../scripts/deploy-ec2.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
INFRA_DIR="$ROOT_DIR/infra"

cd "$ROOT_DIR"

echo "==> 프로젝트 루트: $ROOT_DIR"

# 1. .env 확인
if [ ! -f .env ]; then
  echo "❌ .env 없음. docs/deployment-checklist.md 참고해 프로젝트 루트에 .env 생성 후 재실행하세요."
  exit 1
fi
if ! grep -q "OPENAI_API_KEY=.\+" .env 2>/dev/null; then
  echo "⚠️  .env에 OPENAI_API_KEY가 비어있거나 없을 수 있습니다. 확인하세요."
  read -p "계속하시겠습니까? (y/N) " -n 1 -r
  echo
  [[ ! $REPLY =~ ^[Yy]$ ]] && exit 1
fi

# 2. data 디렉터리 (DuckDB 마운트용)
mkdir -p data

# 3. Docker Compose 실행
echo "==> Docker Compose 빌드 및 시작..."
cd "$INFRA_DIR"
docker compose down 2>/dev/null || true
docker compose up -d --build

echo "==> 컨테이너 상태 대기 (15초)..."
sleep 15

# 4. 상태 확인
echo ""
echo "==> 컨테이너 상태"
docker compose ps

echo ""
echo "==> Health check (API)"
if curl -sf "http://localhost:8081/health" > /dev/null; then
  echo "✅ API /health OK"
else
  echo "❌ API /health 실패. 로그: docker compose logs api"
fi

echo ""
echo "==> Redis"
if docker exec stream_redis redis-cli ping 2>/dev/null | grep -q PONG; then
  echo "✅ Redis PONG"
else
  echo "⚠️  Redis 연결 실패 (stream_redis 확인)"
fi

echo ""
echo "배포 완료. 로그: cd infra && docker compose logs -f"
