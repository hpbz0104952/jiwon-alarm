"""
지원사업 알림 자동화 스크립트 v2
- 경기/전국 공고만 필터링
- 마감 3일 이내 공고는 별도 강조
"""
import os
import json
import smtplib
import requests
import re
from email.message import EmailMessage
from datetime import datetime, date
from pathlib import Path

# ============================================================
# 설정 영역
# ============================================================

TO_EMAIL = "jsul8929@gmail.com"

KEYWORDS = [
    "디자인", "수출", "패키지", "박람회", "유통", "플랫폼",
    "마케팅", "컨설팅", "인증", "장비", "스마트",
    "농촌융복합", "농촌자원복합", "푸드", "온라인", "오프라인",
    "디자인개발", "기술개발", "연구개발", "시제품",
    "양조장", "전통주", "주류", "창업",
]

PRIORITY_ORGS = [
    "기업마당",
    "경기도경제과학진흥원", "GBSA",
    "평택산업진흥원",
    "경기기업비서", "경기도",
]

# === 지역 필터 ===
# 허용 지역: 경기 + 전국 대상
# 다른 지역(서울, 부산, 강원 등)은 자동 제외
ALLOWED_REGIONS = ["경기", "전국", "수도권"]

# 명시적으로 제외할 지역 (다른 시/도 단독 공고는 제외)
EXCLUDED_REGIONS = [
    "서울", "부산", "대구", "인천", "광주", "대전", "울산", "세종",
    "강원", "충북", "충남", "전북", "전남", "경북", "경남", "제주",
]

# 마감 임박 기준 (일)
DEADLINE_WARNING_DAYS = 3

BIZINFO_API_KEY = os.environ.get("BIZINFO_API_KEY", "")
GMAIL_USER = os.environ.get("GMAIL_USER", "")
GMAIL_APP_PASSWORD = os.environ.get("GMAIL_APP_PASSWORD", "")

SEEN_FILE = Path("seen.json")
BIZINFO_API_URL = "https://www.bizinfo.go.kr/uss/rss/bizinfoApi.do"


def load_seen():
    if SEEN_FILE.exists():
        try:
            return set(json.loads(SEEN_FILE.read_text(encoding="utf-8")))
        except Exception:
            return set()
    return set()


def save_seen(seen_set):
    seen_list = list(seen_set)[-2000:]
    SEEN_FILE.write_text(json.dumps(seen_list, ensure_ascii=False), encoding="utf-8")


def fetch_bizinfo():
    params = {
        "crtfcKey": BIZINFO_API_KEY,
        "dataType": "json",
        "searchCnt": "100",
        "hashtags": "",
    }
    try:
        r = requests.get(BIZINFO_API_URL, params=params, timeout=30)
        r.raise_for_status()
        data = r.json()
        items = data.get("jsonArray", []) if isinstance(data, dict) else []
        return items
    except Exception as e:
        print(f"기업마당 API 호출 실패: {e}")
        return []


def is_region_allowed(item):
    """경기 또는 전국 대상 공고만 허용"""
    # API에서 지역 정보가 들어오는 필드들 모두 체크
    region_text = " ".join([
        str(item.get("areaNm", "")),
        str(item.get("trgetNm", "")),
        str(item.get("excInsttNm", "")),
        str(item.get("jrsdInsttNm", "")),
        str(item.get("pblancNm", "")),
    ])

    # 허용 지역 키워드가 있으면 통과
    for region in ALLOWED_REGIONS:
        if region in region_text:
            return True

    # 다른 지역명이 명시되어 있으면 제외
    for region in EXCLUDED_REGIONS:
        # "서울특별시", "부산시", "강원도" 같은 패턴
        if region in region_text:
            return False

    # 지역 정보가 명확하지 않으면 일단 통과 (전국 대상으로 추정)
    return True


def parse_deadline(reqstBeginEndDe):
    """접수기간 문자열에서 마감일 추출"""
    if not reqstBeginEndDe or reqstBeginEndDe == "-":
        return None

    # 형식 예: "2026-05-01 ~ 2026-05-15" 또는 "20260501 ~ 20260515"
    # 끝 날짜 추출
    matches = re.findall(r"(\d{4})[.\-/]?(\d{1,2})[.\-/]?(\d{1,2})", reqstBeginEndDe)
    if len(matches) >= 2:
        # 마감일은 두 번째 날짜
        y, m, d = matches[1]
        try:
            return date(int(y), int(m), int(d))
        except ValueError:
            return None
    elif len(matches) == 1:
        y, m, d = matches[0]
        try:
            return date(int(y), int(m), int(d))
        except ValueError:
            return None
    return None


def get_days_until_deadline(item):
    """마감까지 남은 일수 계산 (음수면 이미 마감)"""
    deadline = parse_deadline(item.get("reqstBeginEndDe", ""))
    if deadline is None:
        return None
    today = date.today()
    return (deadline - today).days


def is_relevant(item):
    """공고가 관심사와 매칭되는지 확인"""
    title = (item.get("pblancNm") or "").strip()
    content = (item.get("bsnsSumryCn") or "").strip()
    org = (item.get("excInsttNm") or item.get("jrsdInsttNm") or "").strip()
    text = f"{title} {content} {org}"

    # 1) 우선순위 기관이면 무조건 통과
    for priority_org in PRIORITY_ORGS:
        if priority_org in org:
            return True, f"기관: {priority_org}"

    # 2) 키워드 매칭
    matched = [kw for kw in KEYWORDS if kw in text]
    if matched:
        return True, f"키워드: {', '.join(matched[:3])}"

    return False, ""


def render_card(item, reason, days_left, idx, urgent=False):
    """공고 한 건의 HTML 카드 생성"""
    title = item.get("pblancNm", "(제목 없음)")
    org = item.get("excInsttNm") or item.get("jrsdInsttNm") or "-"
    reqstBeginEndDe = item.get("reqstBeginEndDe", "-")
    pblancUrl = item.get("pblancUrl", "")
    if pblancUrl and not pblancUrl.startswith("http"):
        pblancUrl = "https://www.bizinfo.go.kr" + pblancUrl

    summary = (item.get("bsnsSumryCn") or "").strip()
    if len(summary) > 200:
        summary = summary[:200] + "..."

    # 마감 정보 표시
    if days_left is None:
        deadline_html = f"<b>접수기간:</b> {reqstBeginEndDe}"
    elif days_left < 0:
        deadline_html = f"<b>접수기간:</b> {reqstBeginEndDe} <span style='color:#999;'>(마감)</span>"
    elif urgent:
        deadline_html = f"<b>접수기간:</b> {reqstBeginEndDe} <span style='color:#d9534f; font-weight:bold;'>⏰ D-{days_left}</span>"
    else:
        deadline_html = f"<b>접수기간:</b> {reqstBeginEndDe} <span style='color:#5cb85c;'>(D-{days_left})</span>"

    # 카드 색상 (긴급은 빨강 테두리)
    if urgent:
        border_color = "#d9534f"
        bg_color = "#fff5f5"
    else:
        border_color = "#ddd"
        bg_color = "#fafafa"

    return f"""
    <div style='border:2px solid {border_color}; border-radius:8px; padding:15px; margin:12px 0; background:{bg_color};'>
        <div style='font-size:12px; color:#888;'>#{idx} · 매칭사유: {reason}</div>
        <h3 style='margin:8px 0;'>
            <a href='{pblancUrl}' style='color:#2c5aa0; text-decoration:none;'>{title}</a>
        </h3>
        <div style='font-size:13px; color:#555;'>
            <b>기관:</b> {org}<br/>
            {deadline_html}
        </div>
        <div style='font-size:13px; color:#444; margin-top:8px; line-height:1.5;'>{summary}</div>
        <div style='margin-top:10px;'>
            <a href='{pblancUrl}' style='background:#2c5aa0; color:white; padding:6px 14px;
               text-decoration:none; border-radius:4px; font-size:13px;'>공고 상세보기 →</a>
        </div>
    </div>
    """


def send_email(urgent_items, normal_items):
    """신규 공고를 이메일로 발송 — 마감임박과 일반을 분리해서 표시"""
    total_count = len(urgent_items) + len(normal_items)
    if total_count == 0:
        print("신규 매칭 공고 없음 — 이메일 발송 건너뜀")
        return

    today = datetime.now().strftime("%Y년 %m월 %d일")

    # 제목에 마감임박 건수 강조
    if urgent_items:
        subject = f"[지원사업 알림] {today} ⏰ 마감임박 {len(urgent_items)}건 + 신규 {len(normal_items)}건"
    else:
        subject = f"[지원사업 알림] {today} 신규 공고 {total_count}건"

    html_parts = [
        "<html><body style='font-family: 맑은 고딕, Arial, sans-serif; max-width: 700px;'>",
        f"<h2 style='color:#2c5aa0;'>📢 오늘의 지원사업 공고</h2>",
        f"<p style='color:#666;'>경기/전국 대상 + 관심 키워드 매칭 공고입니다.</p>",
    ]

    idx = 1

    # ⏰ 마감 임박 섹션 (먼저 표시)
    if urgent_items:
        html_parts.append(f"""
        <div style='background:#d9534f; color:white; padding:12px; border-radius:6px; margin:20px 0 10px 0;'>
            <h3 style='margin:0;'>⏰ 마감 임박! ({len(urgent_items)}건) — 3일 이내 마감</h3>
        </div>
        """)
        for item, reason, days_left in urgent_items:
            html_parts.append(render_card(item, reason, days_left, idx, urgent=True))
            idx += 1

    # 📋 일반 신규 공고 섹션
    if normal_items:
        html_parts.append(f"""
        <div style='background:#2c5aa0; color:white; padding:12px; border-radius:6px; margin:20px 0 10px 0;'>
            <h3 style='margin:0;'>📋 신규 공고 ({len(normal_items)}건)</h3>
        </div>
        """)
        for item, reason, days_left in normal_items:
            html_parts.append(render_card(item, reason, days_left, idx, urgent=False))
            idx += 1

    html_parts.append("""
        <hr/>
        <p style='font-size:12px; color:#999;'>
            매일 오전 9시(한국시간) 자동 발송 · 기업마당 공식 API · 경기/전국 필터링
        </p>
        </body></html>
    """)

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = GMAIL_USER
    msg["To"] = TO_EMAIL
    msg.set_content(f"신규 공고 {total_count}건 (마감임박 {len(urgent_items)}건). HTML 메일로 확인하세요.")
    msg.add_alternative("\n".join(html_parts), subtype="html")

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
        smtp.login(GMAIL_USER, GMAIL_APP_PASSWORD)
        smtp.send_message(msg)

    print(f"이메일 발송 완료: 마감임박 {len(urgent_items)}건 + 일반 {len(normal_items)}건")


def main():
    print("=" * 60)
    print(f"실행 시각: {datetime.now()}")
    print("=" * 60)

    if not BIZINFO_API_KEY:
        print("❌ BIZINFO_API_KEY 환경변수가 없습니다.")
        return
    if not GMAIL_USER or not GMAIL_APP_PASSWORD:
        print("❌ GMAIL_USER 또는 GMAIL_APP_PASSWORD 환경변수가 없습니다.")
        return

    seen = load_seen()
    print(f"기존에 본 공고 수: {len(seen)}")

    items = fetch_bizinfo()
    print(f"기업마당에서 가져온 공고 수: {len(items)}")

    if not items:
        print("⚠️ 가져온 공고가 없습니다.")
        return

    urgent_items = []   # 마감 3일 이내
    normal_items = []   # 일반 신규
    filtered_region = 0
    filtered_expired = 0

    for item in items:
        item_id = str(item.get("pblancId") or item.get("pblancNm", ""))
        if not item_id or item_id in seen:
            continue

        # 지역 필터
        if not is_region_allowed(item):
            filtered_region += 1
            seen.add(item_id)
            continue

        # 키워드/기관 매칭
        relevant, reason = is_relevant(item)
        if not relevant:
            seen.add(item_id)
            continue

        # 마감일 확인
        days_left = get_days_until_deadline(item)

        # 이미 마감된 건 제외
        if days_left is not None and days_left < 0:
            filtered_expired += 1
            seen.add(item_id)
            continue

        # 마감임박 vs 일반 분류
        if days_left is not None and days_left <= DEADLINE_WARNING_DAYS:
            urgent_items.append((item, reason, days_left))
        else:
            normal_items.append((item, reason, days_left))

        seen.add(item_id)

    print(f"지역 필터로 제외: {filtered_region}건")
    print(f"이미 마감되어 제외: {filtered_expired}건")
    print(f"마감임박 (D-3 이내): {len(urgent_items)}건")
    print(f"일반 신규 공고: {len(normal_items)}건")

    if urgent_items or normal_items:
        send_email(urgent_items, normal_items)

    save_seen(seen)
    print("완료!")


if __name__ == "__main__":
    main()
