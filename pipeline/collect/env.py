"""프로젝트 루트의 .env 에서 키를 읽는다. 값은 화면이나 로그에 찍지 않는다."""
import os

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def load(path=None):
    """KEY=VALUE 줄을 읽어 dict 로 돌려준다. 이미 환경변수에 있으면 환경변수가 우선."""
    out = {}
    path = path or os.path.join(ROOT, ".env")
    if os.path.exists(path):
        with open(path, encoding="utf-8-sig") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                out[k.strip()] = v.strip().strip('"').strip("'")
    for k in list(out):
        if os.environ.get(k):
            out[k] = os.environ[k]
    return out


def get(name, path=None):
    return os.environ.get(name) or load(path).get(name) or ""
