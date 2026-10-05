"""스레드에 글 올리기 (Threads API, 공식). 표준 라이브러리만 사용.

    python -m pipeline.publish.threads whoami      .env 의 토큰이 어느 계정 것인지 확인하고 THREADS_USER_ID 를 .env 에 적는다
    python -m pipeline.publish.threads exchange    1시간짜리 토큰을 60일짜리로 바꿔 .env 에 다시 적는다 (THREADS_APP_SECRET 필요)
    python -m pipeline.publish.threads refresh     토큰을 60일 더 쓰게 갱신해 .env 에 다시 적는다 (월 1회)

글 하나 = 두 번의 요청: 그릇을 만들고(/threads) → 게시한다(/threads_publish). 답글은 reply_to_id 로 단다.
토큰은 요청 본문에만 넣고 화면·로그·오류 문구에 찍지 않는다. 한도: 500자, 하루 250건.
"""
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

HOST = "https://graph.threads.net"
MAX_CHARS = 500


class PostError(Exception):
    pass


def _call(method, url, data=None, timeout=30):
    body = urllib.parse.urlencode(data).encode("utf-8") if data else None
    req = urllib.request.Request(url, data=body, method=method, headers={"User-Agent": "checksumlab-console/0.1"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        try:
            msg = (json.loads(e.read().decode("utf-8")).get("error") or {}).get("message", "")
        except Exception:
            msg = ""
        raise PostError("스레드 API 오류 %s: %s" % (e.code, msg[:200]))
    except (urllib.error.URLError, OSError) as e:
        raise PostError("스레드에 닿지 못했습니다: %s" % getattr(e, "reason", e))


def post(text, env, reply_to=None, wait=15, call=_call, sleep=time.sleep):
    """(글 ID, 링크). 실패하면 PostError."""
    user, token = env.get("THREADS_USER_ID"), env.get("THREADS_ACCESS_TOKEN")
    if not (user and token):
        raise PostError(".env 에 THREADS_USER_ID 와 THREADS_ACCESS_TOKEN 이 없습니다")
    data = {"media_type": "TEXT", "text": text, "access_token": token}
    if reply_to:
        data["reply_to_id"] = reply_to
    box = call("POST", "%s/v1.0/%s/threads" % (HOST, user), data)
    if not box.get("id"):
        raise PostError("그릇을 만들지 못했습니다")
    sleep(wait)   # 공식 안내: 게시 전에 잠시 기다린다
    done = call("POST", "%s/v1.0/%s/threads_publish" % (HOST, user), {"creation_id": box["id"], "access_token": token})
    if not done.get("id"):
        raise PostError("게시 응답에 ID가 없습니다")
    link = ""
    try:
        info = call("GET", "%s/v1.0/%s?%s" % (HOST, done["id"], urllib.parse.urlencode({"fields": "permalink", "access_token": token})))
        link = info.get("permalink", "")
    except PostError:
        pass   # 글은 올라갔다. 링크만 못 받은 것
    return done["id"], link


def _set_env(env_path, key, value):
    """.env 의 한 줄을 바꾸거나 없으면 덧붙인다. 값은 찍지 않는다."""
    with open(env_path, encoding="utf-8-sig") as f:
        lines = f.read().splitlines()
    hit = False
    for i, ln in enumerate(lines):
        if ln.strip().startswith(key + "="):
            lines[i], hit = key + "=" + value, True
    if not hit:
        lines.append(key + "=" + value)
    with open(env_path, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines) + "\n")


def whoami(env_path, call=_call):
    """토큰의 주인을 확인하고 THREADS_USER_ID 를 .env 에 적는다. (계정 이름, ID)"""
    from ..collect import env as envmod
    token = envmod.load(env_path).get("THREADS_ACCESS_TOKEN")
    if not token:
        raise PostError(".env 에 THREADS_ACCESS_TOKEN 이 없습니다")
    me = call("GET", "%s/v1.0/me?%s" % (HOST, urllib.parse.urlencode({"fields": "id,username", "access_token": token})))
    if not me.get("id"):
        raise PostError("응답에 ID가 없습니다")
    _set_env(env_path, "THREADS_USER_ID", str(me["id"]))
    return me.get("username", ""), str(me["id"])


def exchange(env_path, call=_call):
    """1시간짜리 토큰을 60일짜리로 바꾼다. 앱 시크릿이 필요하다."""
    from ..collect import env as envmod
    env = envmod.load(env_path)
    token, secret = env.get("THREADS_ACCESS_TOKEN"), env.get("THREADS_APP_SECRET")
    if not (token and secret):
        raise PostError(".env 에 THREADS_ACCESS_TOKEN 과 THREADS_APP_SECRET 이 필요합니다")
    got = call("GET", "%s/access_token?%s" % (HOST, urllib.parse.urlencode({"grant_type": "th_exchange_token", "client_secret": secret, "access_token": token})))
    if not got.get("access_token"):
        raise PostError("교환 응답에 토큰이 없습니다")
    _set_env(env_path, "THREADS_ACCESS_TOKEN", got["access_token"])
    return int(got.get("expires_in", 0)) // 86400


def refresh(env_path, call=_call):
    """긴 토큰을 갱신하고 .env 의 THREADS_ACCESS_TOKEN 줄을 바꿔 쓴다. 토큰 값은 찍지 않는다."""
    from ..collect import env as envmod
    token = envmod.load(env_path).get("THREADS_ACCESS_TOKEN")
    if not token:
        raise PostError(".env 에 THREADS_ACCESS_TOKEN 이 없습니다")
    got = call("GET", "%s/refresh_access_token?%s" % (HOST, urllib.parse.urlencode({"grant_type": "th_refresh_token", "access_token": token})))
    new = got.get("access_token")
    if not new:
        raise PostError("갱신 응답에 토큰이 없습니다")
    _set_env(env_path, "THREADS_ACCESS_TOKEN", new)
    return int(got.get("expires_in", 0)) // 86400


if __name__ == "__main__":
    root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    path = os.path.join(root, ".env")
    try:
        if sys.argv[1:] == ["refresh"]:
            print("스레드 토큰 갱신 완료. 남은 기간 약 %d일" % refresh(path))
        elif sys.argv[1:] == ["exchange"]:
            print("60일짜리 토큰으로 바꿨습니다. 남은 기간 약 %d일" % exchange(path))
        elif sys.argv[1:] == ["whoami"]:
            name, uid = whoami(path)
            print("계정 @%s (ID %s). THREADS_USER_ID 를 .env 에 적었습니다." % (name, uid))
        else:
            print(__doc__)
    except PostError as e:
        print("[실패] %s" % e)
        sys.exit(1)
