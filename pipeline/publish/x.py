"""X에 글 올리기 (X API v2, OAuth 1.0a 사용자 인증). 표준 라이브러리만 사용.

    python -m pipeline.publish.x whoami      .env 의 키 4개가 맞는지, 어느 계정 것인지 확인한다 (글을 올리지 않는다)

.env: X_API_KEY, X_API_SECRET, X_ACCESS_TOKEN, X_ACCESS_SECRET (개발자 화면의 Keys and tokens, 쓰기 권한 필요)
한도: 기본 계정은 가중 길이 280 (한글 한 글자 = 2, 링크 = 23). 종량제: 글마다 요금이 붙고 링크가 든 글은 훨씬 비싸다.
키와 서명은 화면·로그·오류 문구에 찍지 않는다.
"""
import base64
import hashlib
import hmac
import json
import re
import secrets
import time
import urllib.error
import urllib.parse
import urllib.request

URL = "https://api.x.com/2/tweets"
MAX_WEIGHT = 280
_LIGHT = ((0x0000, 0x10FF), (0x2000, 0x200D), (0x2010, 0x201F), (0x2032, 0x2037))


class PostError(Exception):
    pass


def weighted_length(text):
    """X가 세는 길이. 링크는 23, 라틴 문자 등은 1, 한글·이모지 등은 2."""
    total = 0
    for part in re.split(r"(https?://\S+)", text):
        if re.match(r"https?://\S+", part):
            total += 23
            continue
        for ch in part:
            cp = ord(ch)
            total += 1 if any(a <= cp <= b for a, b in _LIGHT) else 2
    return total


def _enc(s):
    return urllib.parse.quote(str(s), safe="-._~")


def sign(method, url, params, consumer_secret, token_secret):
    """OAuth 1.0a HMAC-SHA1 서명. JSON 본문은 서명에 들어가지 않는다."""
    base_params = "&".join("%s=%s" % (_enc(k), _enc(v)) for k, v in sorted(params.items()))
    base = "&".join([method.upper(), _enc(url), _enc(base_params)])
    key = "%s&%s" % (_enc(consumer_secret), _enc(token_secret))
    return base64.b64encode(hmac.new(key.encode(), base.encode(), hashlib.sha1).digest()).decode()


def auth_header(env, method="POST", url=URL, nonce=None, timestamp=None):
    oauth = {"oauth_consumer_key": env["X_API_KEY"], "oauth_nonce": nonce or secrets.token_hex(16),
             "oauth_signature_method": "HMAC-SHA1", "oauth_timestamp": str(timestamp or int(time.time())),
             "oauth_token": env["X_ACCESS_TOKEN"], "oauth_version": "1.0"}
    oauth["oauth_signature"] = sign(method, url, oauth, env["X_API_SECRET"], env["X_ACCESS_SECRET"])
    return "OAuth " + ", ".join('%s="%s"' % (_enc(k), _enc(v)) for k, v in sorted(oauth.items()))


def _send(body, header, timeout=30):
    req = urllib.request.Request(URL, data=json.dumps(body).encode("utf-8"), method="POST",
                                 headers={"Authorization": header, "Content-Type": "application/json", "User-Agent": "checksumlab-console/0.1"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        try:
            doc = json.loads(e.read().decode("utf-8"))
            msg = doc.get("detail") or doc.get("title") or ""
        except Exception:
            msg = ""
        raise PostError("X API 오류 %s: %s" % (e.code, str(msg)[:200]))
    except (urllib.error.URLError, OSError) as e:
        raise PostError("X에 닿지 못했습니다: %s" % getattr(e, "reason", e))


def post(text, env, reply_to=None, send=_send):
    """(글 ID, 링크). 실패하면 PostError."""
    for k in ("X_API_KEY", "X_API_SECRET", "X_ACCESS_TOKEN", "X_ACCESS_SECRET"):
        if not env.get(k):
            raise PostError(".env 에 %s 가 없습니다" % k)
    body = {"text": text}
    if reply_to:
        body["reply"] = {"in_reply_to_tweet_id": str(reply_to)}
    doc = send(body, auth_header(env))
    pid = (doc.get("data") or {}).get("id")
    if not pid:
        raise PostError("응답에 글 ID가 없습니다")
    return pid, "https://x.com/i/web/status/%s" % pid


ME_URL = "https://api.x.com/2/users/me"


def whoami(env, timeout=30):
    """키 4개로 내 계정 정보를 받아 본다. (계정 이름, ID). 글을 올리지 않는다."""
    for k in ("X_API_KEY", "X_API_SECRET", "X_ACCESS_TOKEN", "X_ACCESS_SECRET"):
        if not env.get(k):
            raise PostError(".env 에 %s 가 없습니다" % k)
    req = urllib.request.Request(ME_URL, method="GET", headers={"Authorization": auth_header(env, "GET", ME_URL), "User-Agent": "checksumlab-console/0.1"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            data = (json.loads(r.read().decode("utf-8")).get("data") or {})
    except urllib.error.HTTPError as e:
        try:
            doc = json.loads(e.read().decode("utf-8"))
            msg = doc.get("detail") or doc.get("title") or ""
        except Exception:
            msg = ""
        raise PostError("X API 오류 %s: %s" % (e.code, str(msg)[:200]))
    except (urllib.error.URLError, OSError) as e:
        raise PostError("X에 닿지 못했습니다: %s" % getattr(e, "reason", e))
    return data.get("username", ""), data.get("id", "")


if __name__ == "__main__":
    import sys
    from ..collect import env as envmod
    if sys.argv[1:] == ["whoami"]:
        try:
            name, uid = whoami(envmod.load())
            print("계정 @%s (ID %s). 키 4개가 맞습니다." % (name, uid))
        except PostError as e:
            print("[실패] %s" % e)
            sys.exit(1)
    else:
        print(__doc__)
