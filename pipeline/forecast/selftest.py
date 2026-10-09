"""예측 봉인·채점이 이 PC에서 제대로 도는지 임시 폴더에서 확인한다. 실제 장부는 건드리지 않는다.

    python -m pipeline.forecast.selftest
"""
import contextlib
import csv
import io
import json
import os
import sys
import tempfile
from datetime import datetime, timedelta, timezone

from ..ledger import commit as ledger_commit
from ..ledger import core
from ..ledger import verify as ledger_verify
from . import engine, score, seal, selftest_runner


def run(fn, argv, **kw):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        code = fn(argv, **kw)
    return code, buf.getvalue()


def main():
    ok = []

    def check(name, cond, detail=""):
        ok.append(bool(cond))
        print("%s %s%s" % ("  통과" if cond else "**실패", name, "" if cond else " — " + str(detail).strip()[-400:]))

    with tempfile.TemporaryDirectory() as tmp:
        led, prv, eng = (os.path.join(tmp, d) for d in ("ledger", "private", "engines"))
        common = ["--ledger-dir", led, "--private-dir", prv]
        os.makedirs(os.path.join(eng, "alpha", "v1"))
        with open(os.path.join(eng, "alpha", "v1", "recipe.md"), "w", encoding="utf-8") as f:
            f.write("x\n")
        c, out = run(engine.main, ["register", "--name", "alpha", "--version", "1", "--model", "m",
                                   "--dir", os.path.join(eng, "alpha", "v1"), "--no-ots"] + common)
        check("빈 장부에는 엔진 등록 거부(기점 기록이 먼저)", c == 2, out)

        def weekly(asof):
            sig = os.path.join(tmp, "target_%s.json" % asof)
            with open(sig, "w", encoding="utf-8") as f:
                json.dump({"generator": "live_signal_a_selftest", "engine": "A", "params": {}, "asof_week": asof,
                           "generated_at": asof, "orders": {"exit": [], "entry": [{"symbol": "TEST", "group": "G"}]},
                           "model_positions": [{"symbol": "HOLD"}], "context": {}}, f)
            return run(ledger_commit.main, ["--file", sig, "--signals-csv", os.path.join(tmp, "signals.csv"), "--no-ots"] + common)

        c, out = weekly("2098-12-29")
        check("주간 신호 봉인(기점 + 1주차)", c == 0 and len(core.read_ledger(os.path.join(led, "ledger.jsonl"))) == 2, out)
        for name in ("alpha", "beta"):
            os.makedirs(os.path.join(eng, name, "v1"), exist_ok=True)
            with open(os.path.join(eng, name, "v1", "recipe.md"), "w", encoding="utf-8") as f:
                f.write("시험용 레시피 %s\n" % name)
            c, out = run(engine.main, ["register", "--name", name, "--version", "1", "--model", "test-model",
                                       "--dir", os.path.join(eng, name, "v1"), "--no-ots"] + common)
            check("엔진 등록 %s" % name, c == 0, out)
        c, out = run(engine.main, ["register", "--name", "alpha", "--version", "1", "--model", "m",
                                   "--dir", os.path.join(eng, "alpha", "v1"), "--no-ots"] + common)
        check("같은 버전 재등록 거부", c == 2, out)
        c, out = run(engine.main, ["register", "--name", "gpt_engine", "--version", "1", "--model", "m",
                                   "--dir", os.path.join(eng, "alpha", "v1"), "--no-ots"] + common)
        check("모델 회사 이름이 든 엔진 이름 거부", c == 2, out)

        now = datetime(2099, 1, 13, 0, 30, tzinfo=timezone.utc)   # 실제 시계와 무관하게 돌도록 먼 날짜를 쓴다
        doc = {"event": {"kind": "CPI", "ref_period": "2098-12", "release_at_utc": "2099-01-14T13:30:00Z"},
               "data_cutoff_utc": "2099-01-12T15:00:00Z", "bundle_sha256": "a" * 64,
               "forecasts": [
                   {"engine": "alpha", "version": "1", "target": "CPI_MOM", "p10": 0.2, "p50": 0.3, "p90": 0.4, "n_runs": 5},
                   {"engine": "beta", "version": "1", "target": "CPI_MOM", "p10": 0.1, "p50": 0.15, "p90": 0.2},
                   {"engine": "prev", "target": "CPI_MOM", "p50": 0.4}]}
        path = os.path.join(tmp, "fc.json")

        def write(d):
            with open(path, "w", encoding="utf-8") as f:
                json.dump(d, f, ensure_ascii=False)

        sargs = ["--file", path, "--engines-dir", eng, "--no-ots"] + common
        write(doc)
        c, out = run(seal.main, sargs + ["--dry-run"], now=now)
        check("미리 보기(--dry-run)는 쓰지 않음", c == 0 and len(core.read_ledger(os.path.join(led, "ledger.jsonl"))) == 4, out)
        c, out = run(seal.main, sargs, now=now + timedelta(hours=30))
        check("봉인 마감(발표 12시간 전) 뒤 거부", c == 2, out)
        c, out = run(seal.main, sargs, now=now + timedelta(days=3))
        check("발표 뒤 봉인 거부", c == 2, out)
        bad = json.loads(json.dumps(doc)); bad["forecasts"] = bad["forecasts"][:2]
        write(bad)
        c, out = run(seal.main, sargs, now=now)
        check("기준선이 빠지면 거부", c == 2, out)
        bad = json.loads(json.dumps(doc)); bad["forecasts"][0]["p10"] = 0.35
        write(bad)
        c, out = run(seal.main, sargs, now=now)
        check("p10 > p50 이면 거부", c == 2, out)
        bad = json.loads(json.dumps(doc)); bad["forecasts"][0]["version"] = "2"
        write(bad)
        c, out = run(seal.main, sargs, now=now)
        check("등록되지 않은 버전 거부", c == 2, out)
        bad = json.loads(json.dumps(doc)); bad["forecasts"][0]["target"] = "UNRATE"
        write(bad)
        c, out = run(seal.main, sargs, now=now)
        check("다른 발표의 지표 거부", c == 2, out)
        bad = json.loads(json.dumps(doc)); bad["forecasts"][0]["p50"] = 0.312
        write(bad)
        c, out = run(seal.main, sargs, now=now)
        check("자릿수를 너무 잘게 쓴 값 거부", c == 2, out)

        recipe = os.path.join(eng, "alpha", "v1", "recipe.md")
        original = open(recipe, encoding="utf-8").read()
        with open(recipe, "a", encoding="utf-8") as f:
            f.write("몰래 한 줄 추가\n")
        write(doc)
        c, out = run(seal.main, sargs, now=now)
        check("등록 뒤 레시피를 고치면 거부", c == 2, out)
        with open(recipe, "w", encoding="utf-8") as f:
            f.write(original)

        c, out = run(seal.main, sargs, now=now)
        check("정상 봉인", c == 0, out)
        c, out = run(seal.main, sargs, now=now)
        check("같은 발표 두 번째 봉인 거부", c == 2, out)
        os.makedirs(os.path.join(eng, "gamma", "v1"))
        with open(os.path.join(eng, "gamma", "v1", "recipe.md"), "w", encoding="utf-8") as f:
            f.write("나중에 등록한 엔진\n")
        run(engine.main, ["register", "--name", "gamma", "--version", "1", "--model", "m",
                          "--dir", os.path.join(eng, "gamma", "v1"), "--no-ots"] + common)
        more = json.loads(json.dumps(doc))
        more["forecasts"] = [{"engine": "gamma", "version": "1", "target": "CPI_MOM", "p10": 0.2, "p50": 0.25, "p90": 0.5},
                             {"engine": "prev", "target": "CPI_MOM", "p50": 0.5}]
        write(more)
        c, out = run(seal.main, sargs, now=now)
        check("엔진 추가 봉인: 기준선 값이 먼저 것과 다르면 거부", c == 2, out)
        more["forecasts"][1]["p50"] = 0.4
        write(more)
        c, out = run(seal.main, sargs, now=now)
        check("엔진 추가 봉인: 기준선 값이 같으면 허용", c == 0, out)
        c, out = weekly("2099-01-05")
        check("예측 기록 뒤에도 다음 주 신호 봉인이 이어짐", c == 0 and "기록 #" in out, out)
        c, out = run(ledger_verify.main, common)
        check("장부 점검(기존 verify)과 호환", c == 0 and "이상 없음" in out, out)

        public = open(os.path.join(led, "ledger.jsonl"), encoding="utf-8").read()
        check("공개 장부에 예측 값·모델 이름이 없음", "test-model" not in public and '"p50"' not in public, public)

        actuals = os.path.join(tmp, "actuals.csv")
        out_csv = os.path.join(tmp, "scores.csv")
        cargs = common + ["--actuals", actuals, "--out", out_csv]
        c, out = run(score.main, cargs)
        check("발표 전에는 채점 0건", c == 0 and "채점 0개" in out, out)
        with open(actuals, "w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=score.ACTUAL_FIELDS)
            w.writeheader()
            w.writerow({"event_kind": "CPI", "ref_period": "2098-12", "target": "CPI_MOM", "actual": "0.3",
                        "released_at_utc": "2099-01-14T13:30:00Z", "source_url": "x", "known_at_utc": "2099-01-14T13:31:00Z"})
            w.writerow({"event_kind": "CPI", "ref_period": "2098-12", "target": "CPI_MOM", "actual": "0.9",
                        "released_at_utc": "2099-01-14T13:30:00Z", "source_url": "x", "known_at_utc": "2099-02-10T13:31:00Z", "note": "수정치"})
        c, out = run(score.main, cargs)
        rows = list(csv.DictReader(open(out_csv, encoding="utf-8")))
        by = {r["engine"]: r for r in rows}
        check("채점: 수정치가 아니라 처음 발표값(0.3)으로", c == 0 and len(rows) == 5 and all(float(r["actual"]) == 0.3 for r in rows), out)
        late_rows, late = score.score_rows(
            [{"seq": 9, "event_kind": "CPI", "ref_period": "2098-12", "target": "CPI_MOM", "engine": "alpha", "version": "1",
              "p10": 0.2, "p50": 0.3, "p90": 0.4, "sealed_at": "2099-01-14T13:30:01Z", "released_at": "2099-01-14T13:30:00Z"}],
            score.load_actuals(actuals))
        check("발표 뒤에 봉인된 값은 채점에서 제외", late == 1 and not late_rows, str(late_rows))
        check("오차 계산", abs(float(by["alpha"]["abs_error"])) < 1e-9 and abs(float(by["beta"]["abs_error"]) - 0.15) < 1e-9
              and abs(float(by["prev"]["abs_error"]) - 0.1) < 1e-9, str(rows))
        check("구간 적중·구간 점수", by["alpha"]["in_interval"] == "1" and by["beta"]["in_interval"] == "0"
              and abs(float(by["alpha"]["interval_score"]) - 0.2) < 1e-9
              and abs(float(by["beta"]["interval_score"]) - (0.1 + 10 * 0.1)) < 1e-9, str(rows))
        check("요약에 표본 부족 표시", "표본 부족" in out and "alpha@1" in out and "오차가 작음 1 / 같음 0 / 큼 0" in out, out)

    selftest_runner.run_checks(check)   # 엔진 실행기 (가짜 API)

    print("\n시험 %d건 중 %d건 통과" % (len(ok), sum(ok)))
    return 0 if all(ok) else 1


if __name__ == "__main__":
    sys.exit(main())
