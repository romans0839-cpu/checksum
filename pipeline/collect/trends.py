"""뜨는 검색어 수집: Google 트렌드 '지금 뜨는 검색어' 피드(한국·미국)를 받아 DB에 쌓는다. 표준 라이브러리만 사용.

    python -m pipeline.collect.trends              받아서 저장하고 목록을 보여 준다
    python -m pipeline.collect.trends --dry-run    받아서 보여 주기만 한다

- 트렌디 체크(docs/14)의 후보 재료다. 여기서는 모으고 규칙으로 표시만 붙인다.
  "경제와 닿는 지점이 있는가"를 가려 후보 5개를 내는 일은 다음 단계(LLM)이고, 고르는 것은 Nick이다.
- 기사는 제목·출처·링크만 저장한다. 본문은 받지도 저장하지도 않는다.
- 검색량은 피드가 주는 어림값이다("2000+"). 발행물에 순위·검색량을 쓰면 "자료: Google 트렌드"를 단다.
- 재난·인명 사고, 정치 공방으로 보이는 검색어에는 표시(flag)를 붙인다. 지우지는 않는다.
"""
import argparse
import os
import re
import sys
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

from . import store

FEED = "https://trends.google.com/trending/rss?geo=%s"
GEOS = ("KR", "US")
FLAG_WORDS = {
    "disaster": ("사망", "숨져", "숨진", "실종", "전복", "참사", "추락", "화재", "지진", "침몰", "피살", "살인", "성폭", "유족", "폭발", "가정폭력",
                 "killed", "dead", "dies", "death", "shooting", "crash", "missing", "earthquake", "wildfire", "victim"),
    "politics": ("제명", "탄핵", "내란", "여야", "민주당", "국민의힘", "대선", "총선", "선거",
                 "election", "senate", "republican", "democrat", "impeach", "campaign", "ballot"),
}


def setup_console():
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(errors="replace")
        except Exception:
            pass


def local(tag):
    return tag.rsplit("}", 1)[-1]


def parse(xml_bytes):
    """피드 -> [{"term", "approx_traffic", "pub_at", "news": [{"title", "source", "url"}]}]. 이름공간은 꼬리 이름으로만 본다."""
    root = ET.fromstring(xml_bytes)
    out = []
    for item in root.iter():
        if local(item.tag) != "item":
            continue
        rec = {"term": "", "approx_traffic": None, "pub_at": None, "news": []}
        for child in item:
            name = local(child.tag)
            text = (child.text or "").strip()
            if name == "title":
                rec["term"] = text
            elif name == "approx_traffic":
                digits = re.sub(r"[^0-9]", "", text)
                rec["approx_traffic"] = int(digits) if digits else None
            elif name == "pubDate" and text:
                try:
                    rec["pub_at"] = parsedate_to_datetime(text).astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
                except (TypeError, ValueError):
                    pass
            elif name == "news_item":
                news = {"title": "", "source": "", "url": ""}
                for sub in child:
                    key = {"news_item_title": "title", "news_item_source": "source", "news_item_url": "url"}.get(local(sub.tag))
                    if key:
                        news[key] = (sub.text or "").strip()
                if news["url"].startswith("http") and news["title"]:
                    rec["news"].append(news)
        if rec["term"]:
            out.append(rec)
    return out


def _hit(word, text):
    """영어 낱말은 낱말 단위로만 본다('deadline' 안의 'dead'를 잡지 않는다). 한글은 포함 여부로 본다."""
    if word.isascii():
        return re.search(r"\b" + re.escape(word) + r"\b", text) is not None
    return word in text


def flag_of(rec):
    text = (rec["term"] + " " + " ".join(n["title"] for n in rec["news"])).lower()
    for flag, words in FLAG_WORDS.items():
        if any(_hit(w, text) for w in words):
            return flag
    return ""


def ingest(con, geo, records, seen_at):
    """DB에 넣고 (새 검색어 수, 다시 본 검색어 수, 새 기사 링크 수)를 돌려준다."""
    new = again = docs = 0
    for rec in records:
        row = con.execute("SELECT trend_id FROM trend WHERE geo=? AND term=? AND pub_at IS ?", (geo, rec["term"], rec["pub_at"])).fetchone()
        if row:
            con.execute("UPDATE trend SET last_seen_at=?, approx_traffic=COALESCE(?, approx_traffic) WHERE trend_id=?",
                        (seen_at, rec["approx_traffic"], row[0]))
            trend_id = row[0]
            again += 1
        else:
            cur = con.execute("INSERT INTO trend(geo,term,approx_traffic,pub_at,first_seen_at,last_seen_at,flag,source_id) VALUES (?,?,?,?,?,?,?,'gtrends')",
                              (geo, rec["term"], rec["approx_traffic"], rec["pub_at"], seen_at, seen_at, flag_of(rec)))
            trend_id = cur.lastrowid
            new += 1
        for n in rec["news"]:
            got = con.execute("SELECT doc_id FROM document WHERE url=?", (n["url"],)).fetchone()
            if got:
                doc_id = got[0]
            else:
                cur = con.execute("INSERT INTO document(source_id,kind,url,title,lang,fetched_at,summary_own) VALUES ('press','press',?,?,?,?,?)",
                                  (n["url"], n["title"], "ko" if geo == "KR" else "en", seen_at, n["source"]))
                doc_id = cur.lastrowid
                docs += 1
            con.execute("INSERT OR IGNORE INTO doc_link(doc_id,ref_type,ref_id) VALUES (?,'tag',?)", (doc_id, "trend:%d" % trend_id))
    return new, again, docs


def fetch(geo, timeout=30):
    req = urllib.request.Request(FEED % geo, headers={"User-Agent": "checksumlab-collector/0.1 (hello@checksumlab.com)"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def main(argv=None):
    setup_console()
    ap = argparse.ArgumentParser(description="뜨는 검색어 수집")
    ap.add_argument("--db", default=store.DEFAULT_DB)
    ap.add_argument("--geo", action="append", help="KR, US (기본: 둘 다)")
    ap.add_argument("--from-file", default=None, help="시험용: 저장된 피드 파일(geo 하나에만 쓴다)")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)

    seen_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    con = None if a.dry_run else store.connect(a.db)
    failed = 0
    for geo in (a.geo or list(GEOS)):
        try:
            if a.from_file:
                with open(a.from_file, "rb") as f:
                    raw = f.read()
            else:
                raw = fetch(geo)
            records = parse(raw)
        except (urllib.error.URLError, OSError, ET.ParseError) as e:
            print("[실패] %s 피드를 받지 못했습니다: %s" % (geo, e))
            failed += 1
            continue
        print("[%s] 검색어 %d개" % (geo, len(records)))
        for rec in records:
            flag = flag_of(rec)
            head = rec["news"][0]["title"] if rec["news"] else ""
            print("   %-6s %-22s %s%s" % ("%s+" % rec["approx_traffic"] if rec["approx_traffic"] else "", rec["term"][:22],
                                           ("(" + flag + ") ") if flag else "", head[:60]))
        if con is not None:
            new, again, docs = ingest(con, geo, records, seen_at)
            print("   저장: 새 검색어 %d / 다시 본 것 %d / 새 기사 링크 %d" % (new, again, docs))
    if con is not None:
        con.execute("INSERT INTO job_run(job_id,started_at,finished_at,status,detail) VALUES ('collect_trends',?,?,?,?)",
                    (seen_at, store.utc_now(), "ok" if not failed else "fail", "failed_geo=%d" % failed))
        con.commit()
        con.close()
    else:
        print("--dry-run: 저장하지 않았습니다.")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
