#!/usr/bin/env bash
# 서버의 코드 반영 (D24, docs/15 §5-1). 서버에서 10분마다 돈다.
#   새 커밋이 있으면 받는다 → 자체 시험 4종 → 통과하면 그대로 쓰고, 하나라도 실패하면 직전 커밋으로 되돌린다.
#   결과는 logs/sync.log 와 조종판 "오늘 현황"의 "코드 반영" 줄에 남는다.
#   반영하는 동안 게시 일꾼이 돌지 않게 같은 잠금 파일(logs/worker.lock)을 잡는다.
# 등록 (checksum 계정의 crontab):
#   */10 * * * * bash /home/checksum/checksum/scripts/server_sync.sh >> /home/checksum/logs/sync.log 2>&1
# 서버에서 추적 중인 파일을 직접 고치지 않는다. 고치면 받기가 멈추고 [주의]가 남는다.
set -u

main() {
  local repo="${CHECKSUM_REPO:-$HOME/checksum}"
  local py="${CHECKSUM_PY:-$HOME/venv/bin/python}"
  local logs="${CHECKSUM_LOGS:-$HOME/logs}"
  local branch="${CHECKSUM_BRANCH:-main}"
  local old new m out failed="" reqs=0

  stamp() { date '+%F %T'; }
  note() {   # 조종판에 한 줄. 실패해도 반영 결과에는 영향을 주지 않는다
    "$py" -m pipeline.console.worker note --item "코드 반영" --result "$1" >/dev/null 2>&1 || true
  }

  mkdir -p "$logs"
  cd "$repo" || { echo "$(stamp) [중단] 저장소 폴더가 없음: $repo"; return 1; }

  git fetch -q origin "$branch" || { echo "$(stamp) [주의] 받기 실패 (네트워크 또는 읽기 키)"; return 1; }
  old=$(git rev-parse HEAD) || return 1
  new=$(git rev-parse "origin/$branch") || return 1
  [ "$old" = "$new" ] && return 0
  # 이미 시험에 떨어져 되돌린 커밋이면 새 커밋이 올 때까지 다시 시도하지 않는다
  if [ -f "$logs/sync_failed" ] && [ "$(cat "$logs/sync_failed")" = "$new" ]; then
    return 0
  fi

  exec 9>"$logs/worker.lock"
  flock -w 240 9 || { echo "$(stamp) [주의] 잠금을 잡지 못함 (게시 일꾼이 오래 도는 중). 다음 바퀴에 다시"; return 1; }

  if ! git merge -q --ff-only "origin/$branch"; then
    echo "$(stamp) [주의] 받은 코드를 합칠 수 없음 (서버에서 고친 파일이 있는지 확인): ${old:0:7} → ${new:0:7}"
    note "받지 못함: 서버에 고친 파일이 있음 (${new:0:7})"
    echo "$new" > "$logs/sync_failed"
    return 1
  fi

  if git diff --name-only "$old" "$new" | grep -qx 'requirements-server.txt'; then
    reqs=1
    "$py" -m pip install -q -r requirements-server.txt || failed="pip"
  fi

  if [ -z "$failed" ]; then
    for m in forecast collect content console; do
      if ! out=$("$py" -m "pipeline.$m.selftest" 2>&1); then
        failed="$m"
        echo "$(stamp) 자체 시험 실패: $m"
        echo "$out" | grep -v '^  통과' | tail -12
        break
      fi
    done
  fi

  if [ -n "$failed" ]; then
    git reset -q --hard "$old"
    [ "$reqs" = 1 ] && "$py" -m pip install -q -r requirements-server.txt
    echo "$new" > "$logs/sync_failed"
    echo "$(stamp) [되돌림] ${new:0:7} 은 반영하지 않음 ($failed). 지금 코드: ${old:0:7}"
    note "실패: $failed 시험 → 이전 코드로 되돌림 (받은 것 ${new:0:7}, 쓰는 것 ${old:0:7})"
    return 1
  fi

  rm -f "$logs/sync_failed"
  echo "$(stamp) 반영 ${old:0:7} → ${new:0:7} (자체 시험 4종 통과)"
  note "반영 ${old:0:7} → ${new:0:7}, 자체 시험 통과"
  return 0
}

main "$@"
exit $?
