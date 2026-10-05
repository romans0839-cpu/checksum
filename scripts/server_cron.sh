#!/usr/bin/env bash
# 서버 예약(crontab)을 이 저장소의 기준 세 줄로 맞춘다 (docs/15 §5-1). 서버의 checksum 계정에서 한 번:
#   cd ~/checksum && git pull && bash scripts/server_cron.sh
# - 게시 일꾼(5분) · 코드 반영(10분) · 예약 작업 일꾼(5분, 2분 어긋나게) 세 줄만 넣고 고친다. 다른 줄은 그대로 둔다.
# - 여러 번 돌려도 결과가 같다. 이미 손으로 넣어 둔 같은 줄은 기준 줄로 바뀐다.
# - 끝에 지표 수집에 필요한 키가 서버에 있는지(값은 보지 않는다) 알려 주고, 지표 수집을 한 번 돌려 결과를 화면에 보여 준다.
#   키를 넣었거나 무엇을 고친 뒤 바로 확인하고 싶을 때도 이 스크립트를 다시 돌리면 된다.
#   bash scripts/server_cron.sh --show   넣을 줄만 보여 주고 아무것도 바꾸지 않는다
# 예약 작업을 더하거나 시각을 바꿀 때는 이 스크립트를 다시 돌릴 필요가 없다. 예정은 pipeline/console/jobs.py 가 정한다.
set -u

main() {
  local repo="${CHECKSUM_REPO:-$HOME/checksum}"
  local py="${CHECKSUM_PY:-$HOME/venv/bin/python}"
  local logs="${CHECKSUM_LOGS:-$HOME/logs}"
  local mark="# checksum: 아래 세 줄은 scripts/server_cron.sh 가 넣는다. 손으로 고치지 않는다"
  local ours cur rest

  ours=$(cat <<EOF
$mark
*/5 * * * * cd $repo && flock -n $logs/worker.lock $py -m pipeline.console.worker run >> $logs/worker.log 2>&1
*/10 * * * * bash $repo/scripts/server_sync.sh >> $logs/sync.log 2>&1
2-59/5 * * * * cd $repo && flock -w 100 $logs/worker.lock $py -m pipeline.console.jobs tick >> $logs/jobs.log 2>&1
EOF
)
  if [ "${1:-}" = "--show" ]; then
    echo "$ours"
    return 0
  fi

  [ -d "$repo/pipeline" ] || { echo "[중단] 저장소 폴더가 없음: $repo"; return 1; }
  [ -x "$py" ] || { echo "[중단] 가상환경의 파이썬이 없음: $py"; return 1; }
  command -v flock >/dev/null 2>&1 || { echo "[중단] flock 명령이 없음 (util-linux)"; return 1; }
  mkdir -p "$logs"

  cur=$(crontab -l 2>/dev/null || true)
  rest=$(printf '%s\n' "$cur" | grep -v -F -e 'pipeline.console.worker run' -e 'scripts/server_sync.sh' -e 'pipeline.console.jobs tick' -e '# checksum: ' || true)
  if ! { [ -n "$rest" ] && printf '%s\n' "$rest"; printf '%s\n' "$ours"; } | crontab -; then
    echo "[중단] crontab 을 바꾸지 못했습니다. 예약은 그대로입니다."
    return 1
  fi
  echo "예약을 맞췄습니다. 지금 이 계정의 예약:"
  crontab -l | sed 's/^/   /'

  echo
  if grep -q -E '^[[:space:]]*BLS_API_KEY=[^[:space:]]' "$repo/.env" 2>/dev/null; then
    echo "지표 수집 키(BLS_API_KEY): 서버 .env 에 있음"
  else
    echo "[할 일] 서버 .env 에 BLS_API_KEY 가 없습니다. $repo/.env 에 PC .env 의 BLS_API_KEY= 줄을 그대로 한 줄 넣으세요."
    echo "        넣은 뒤 이 스크립트를 다시 돌리면 바로 확인됩니다(그냥 두어도 한 시간 안에 다시 시도합니다)."
  fi

  echo
  echo "지표 수집을 한 번 돌립니다 (결과는 조종판 '오늘 현황'의 '지표 수집' 줄에도 적힙니다):"
  cd "$repo" && flock -w 100 "$logs/worker.lock" "$py" -m pipeline.console.jobs run collect_indicators 2>&1 | tee -a "$logs/jobs.log" | sed 's/^/   /'
  echo "끝. 화면에 [주의]나 '실패'가 있으면 그 줄을 그대로 Claude에게 알려 주세요."
  return 0
}

main "$@"
exit $?
