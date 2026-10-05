"""DB에 값을 쌓는 공통 함수. 원칙: 덮어쓰지 않는다. 값이 바뀌면 새 줄을 쌓고 '알게 된 시각'을 남긴다."""
import os
from datetime import datetime, timezone

from ..db import init as dbinit

ROOT = dbinit.ROOT
DEFAULT_DB = os.path.join(ROOT, "data", "db", "checksum.db")


def utc_now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def connect(db_path=None):
    """없으면 만들고(표·기본 행 포함) 연결을 돌려준다."""
    return dbinit.init(db_path or DEFAULT_DB)


def add_fetch(con, source_id, url, fetched_at, http_status, sha256, path):
    cur = con.execute("INSERT INTO raw_fetch(source_id,url,fetched_at,http_status,sha256,path) VALUES (?,?,?,?,?,?)",
                      (source_id, url, fetched_at, http_status, sha256, path))
    return cur.lastrowid


def ensure_series(con, series_id, name_ko, unit, freq, source_id, stale_after_days=45, note=""):
    con.execute("INSERT OR IGNORE INTO series(series_id,name_ko,unit,freq,source_id,stale_after_days,note) VALUES (?,?,?,?,?,?,?)",
                (series_id, name_ko, unit, freq, source_id, stale_after_days, note))


def put(con, series_id, obs_date, value, known_at, fetch_id=None, released_at=None):
    """최신값과 다를 때만 새 줄을 넣는다. 돌려주는 값: 'new' / 'revised' / 'same'."""
    row = con.execute("SELECT value FROM observation WHERE series_id=? AND obs_date=? ORDER BY known_at DESC LIMIT 1",
                      (series_id, obs_date)).fetchone()
    if row is not None and abs(row[0] - float(value)) < 1e-9:
        return "same"
    con.execute("INSERT INTO observation(series_id,obs_date,value,known_at,released_at,fetch_id) VALUES (?,?,?,?,?,?)",
                (series_id, obs_date, float(value), known_at, released_at, fetch_id))
    return "new" if row is None else "revised"


def asof(con, series_id, cutoff):
    """cutoff 시각까지 알려진 값만으로 본 계열. [(obs_date, value)] 날짜순."""
    return con.execute(
        "SELECT o.obs_date, o.value FROM observation o WHERE o.series_id=? AND o.known_at<=? AND o.known_at=("
        " SELECT MAX(x.known_at) FROM observation x WHERE x.series_id=o.series_id AND x.obs_date=o.obs_date AND x.known_at<=?)"
        " ORDER BY o.obs_date", (series_id, cutoff, cutoff)).fetchall()


def first_known(con, series_id, obs_date):
    """그 날짜의 값을 처음 알게 된 줄. (value, known_at) 또는 None."""
    return con.execute("SELECT value, known_at FROM observation WHERE series_id=? AND obs_date=? ORDER BY known_at LIMIT 1",
                       (series_id, obs_date)).fetchone()


def set_meta(con, key, value):
    con.execute("INSERT INTO meta(key,value) VALUES (?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key, value))


def get_meta(con, key):
    row = con.execute("SELECT value FROM meta WHERE key=?", (key,)).fetchone()
    return row[0] if row else None
