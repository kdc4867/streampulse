#!/usr/bin/env bash
# EC2/로컬 Docker 환경에서 급등 텔레그램 알람이 안 올 때 진단용.
# 사용: 프로젝트 루트에서 ./scripts/check-telegram-alerts.sh
#       또는 infra에서 ../scripts/check-telegram-alerts.sh

set -e
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
ENV_FILE="${ENV_FILE:-.env}"
INFRA="${INFRA:-infra}"

echo "=== 1. .env 알림 관련 설정 ==="
if [[ ! -f "$ENV_FILE" ]]; then
  echo "⚠ .env 없음 (경로: $ROOT/$ENV_FILE)"
else
  for key in TELEGRAM_TOKEN TELEGRAM_CHAT_ID DETECTOR_ALERT_MODE AGENT_ALERT_MODE; do
    val=$(grep -E "^${key}=" "$ENV_FILE" 2>/dev/null | sed -n "s/^${key}=//p" | tr -d '"' | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')
    if [[ -z "$val" ]]; then
      echo "  $key: (미설정)"
    else
      if [[ "$key" == "TELEGRAM_TOKEN" ]]; then
        echo "  $key: ${val:0:8}... (길이 ${#val})"
      else
        echo "  $key: $val"
      fi
    fi
  done
fi

echo ""
echo "=== 2. Detector 로그 (Telegram/Alert Fail, 최근 200줄) ==="
if [[ -d "$INFRA" ]] && command -v docker >/dev/null 2>&1; then
  (cd "$INFRA" && docker compose logs --tail=200 detector 2>/dev/null) | grep -E "\[Telegram\]|알림 전송 완료|Alert Fail|Error|감지 완료|특이사항 없음" || echo "  (해당 로그 없음)"
else
  echo "  (Docker 없음 또는 infra 없음, 스킵)"
fi

echo ""
echo "=== 3. Agent Worker 로그 (알림/에러, 최근 200줄) ==="
if [[ -d "$INFRA" ]] && command -v docker >/dev/null 2>&1; then
  (cd "$INFRA" && docker compose logs --tail=200 agent-worker 2>/dev/null) | grep -E "\[Agent Alert\]|알림 전송 완료|처리 실패|Error|시작" || echo "  (해당 로그 없음)"
else
  echo "  (스킵)"
fi

echo ""
echo "=== 4. DB: analysis_status / analysis_verdict 집계 ==="
if [[ -d "$INFRA" ]] && command -v docker >/dev/null 2>&1; then
  docker exec stream_meta_db psql -U user -d streampulse_meta -t -c \
    "SELECT analysis_status, analysis_verdict, COUNT(*) FROM signal_events GROUP BY 1,2 ORDER BY 1,2;" 2>/dev/null || echo "  (DB 쿼리 실패)"
else
  echo "  (스킵)"
fi

echo ""
echo "=== 5. 조치 체크리스트 ==="
echo "  • 헬스체크(8h)는 오는데 급등만 안 오면:"
echo "    - DETECTOR_ALERT_MODE=immediate → Detector가 SPIKE 감지 시 즉시 알림"
echo "    - AGENT_ALERT_MODE=all → Agent가 분석 후 passes_alert_gate만 만족해도 알림"
echo "  • .env 수정 후 반드시 재시작:"
echo "    cd $INFRA && docker compose up -d --build detector agent-worker"
echo "  • PENDING만 쌓이면 agent-worker 미동작 가능: 로그에 '처리 실패' 확인"
