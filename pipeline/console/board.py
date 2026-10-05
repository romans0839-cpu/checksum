"""조종판 저장소. 같은 모양의 두 가지: Google 시트(운영)와 CSV 폴더(시험·비상용).

탭과 열 이름은 Nick이 휴대폰에서 보는 그대로 한글로 둔다. 열 이름을 바꾸면 아래 상수도 같이 바꾼다.
"""
import csv
import os

QUEUE, CANDIDATES, STATUS = "게시 대기열", "후보", "오늘 현황"
HEADERS = {
    QUEUE: ["번호", "예약(KST)", "채널", "본문", "셀프 답글", "상태", "검사", "게시 링크", "게시 시각", "처음 문안", "메모"],
    CANDIDATES: ["날짜", "번호", "제목", "무슨 일", "경제와 닿는 지점", "가설 1", "가설 2", "가설 3", "반대로 볼 점", "더 볼 것", "선택"],
    STATUS: ["항목", "마지막 실행(KST)", "결과", "메모"],
}
ST_DRAFT, ST_OK, ST_POSTING, ST_DONE, ST_HOLD, ST_BLOCKED = "초안", "승인", "게시 중", "게시됨", "보류", "막힘"
STATES = [ST_DRAFT, ST_OK, ST_POSTING, ST_DONE, ST_HOLD, ST_BLOCKED]
CH_THREADS, CH_X = "스레드", "X"
CHANNELS = [CH_THREADS, CH_X]


class CsvBoard:
    """폴더 안의 <탭 이름>.csv. 줄 번호는 머리글 다음 줄이 2 (시트와 같게)."""

    def __init__(self, folder):
        self.folder = folder
        os.makedirs(folder, exist_ok=True)

    def _path(self, tab):
        return os.path.join(self.folder, tab + ".csv")

    def ensure(self, tab):
        if not os.path.exists(self._path(tab)):
            self._write(tab, [])

    def _write(self, tab, rows):
        with open(self._path(tab), "w", encoding="utf-8-sig", newline="") as f:
            w = csv.DictWriter(f, fieldnames=HEADERS[tab], lineterminator="\n", extrasaction="ignore")
            w.writeheader()
            for r in rows:
                w.writerow({k: r.get(k, "") for k in HEADERS[tab]})

    def read(self, tab):
        self.ensure(tab)
        with open(self._path(tab), encoding="utf-8-sig", newline="") as f:
            rows = list(csv.DictReader(f))
        for i, r in enumerate(rows, 2):
            r["_row"] = i
        return rows

    def update(self, tab, row, values):
        rows = self.read(tab)
        rows[row - 2].update(values)
        self._write(tab, rows)

    def append(self, tab, new_rows):
        self._write(tab, self.read(tab) + list(new_rows))


class GSheetBoard:
    """Google 시트. 서비스 계정 키 파일과 시트 ID가 필요하다 (pip install gspread). 실제 시트로는 설정 뒤에 시험한다."""

    def __init__(self, key_file, sheet_id):
        import gspread   # 서버에만 깔면 된다
        self._gspread = gspread
        self.sheet = gspread.service_account(filename=key_file).open_by_key(sheet_id)
        self._ws = {}

    def _tab(self, tab):
        if tab not in self._ws:
            try:
                self._ws[tab] = self.sheet.worksheet(tab)
            except self._gspread.WorksheetNotFound:
                self._ws[tab] = self.sheet.add_worksheet(title=tab, rows=200, cols=len(HEADERS[tab]))
        return self._ws[tab]

    def ensure(self, tab):
        ws = self._tab(tab)
        if ws.row_values(1) != HEADERS[tab]:
            ws.update(values=[HEADERS[tab]], range_name="A1", value_input_option="RAW")
        if tab == QUEUE:
            self._dropdowns(ws)

    def _dropdowns(self, ws):
        """상태·채널 열을 고르는 칸으로 만든다. 실패해도 동작에는 지장이 없다."""
        try:
            reqs = []
            for name, options in (("상태", STATES), ("채널", CHANNELS)):
                col = HEADERS[QUEUE].index(name)
                reqs.append({"setDataValidation": {
                    "range": {"sheetId": ws.id, "startRowIndex": 1, "startColumnIndex": col, "endColumnIndex": col + 1},
                    "rule": {"condition": {"type": "ONE_OF_LIST", "values": [{"userEnteredValue": o} for o in options]},
                             "showCustomUi": True, "strict": False}}})
            self.sheet.batch_update({"requests": reqs})
        except Exception:
            pass

    def read(self, tab):
        values = self._tab(tab).get_all_values()
        if not values:
            return []
        head, out = values[0], []
        for i, line in enumerate(values[1:], 2):
            if not any(c.strip() for c in line):
                continue
            r = {h: (line[j] if j < len(line) else "") for j, h in enumerate(head)}
            r["_row"] = i
            out.append(r)
        return out

    def update(self, tab, row, values):
        ws = self._tab(tab)
        cells = [{"range": self._gspread.utils.rowcol_to_a1(row, HEADERS[tab].index(k) + 1), "values": [[v]]} for k, v in values.items()]
        ws.batch_update(cells, value_input_option="RAW")   # RAW: 수식으로 해석되지 않게

    def append(self, tab, new_rows):
        rows = [[r.get(k, "") for k in HEADERS[tab]] for r in new_rows]
        if rows:
            self._tab(tab).append_rows(rows, value_input_option="RAW")


def open_board(env):
    """환경에 시트 설정이 있으면 Google 시트, CONSOLE_CSV_DIR 이 있으면 CSV 폴더."""
    if env.get("CONSOLE_CSV_DIR"):
        return CsvBoard(env["CONSOLE_CSV_DIR"])
    key, sid = env.get("GOOGLE_SERVICE_ACCOUNT_FILE"), env.get("CONSOLE_SHEET_ID")
    if not (key and sid):
        raise SystemExit("[중단] .env 에 GOOGLE_SERVICE_ACCOUNT_FILE 과 CONSOLE_SHEET_ID 가 필요합니다 (docs/15 §6).")
    return GSheetBoard(key, sid)
