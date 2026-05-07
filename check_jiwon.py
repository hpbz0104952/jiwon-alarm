"""
지원사업 알림 자동화 스크립트
"""
import os
import json
import smtplib
import requests
from email.message import EmailMessage
from datetime import datetime
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


def is_relevant(item):
    title = (item.get("pblancNm") or "").strip()
    content = (item.get("bsnsSumryCn") or "").strip()
    org = (item.get("excInsttNm") or item.get("jrsdInsttNm") or "").strip()
    text = f"{title} {content} {org}"

    for priority_org in PRIORITY_ORGS:
        if priority_org in org:
            return True, f"기관: {priority_org}"

    matched = [kw for kw in KEYWORDS if kw in text]
    if matched:
        return True, f"키워드: {', '.join(matched[:3])}"

    return False, ""


def send_email(new_items):
    if not new_items:
        print("신규 매칭 공고 없음 — 이메일 발송 건너뜀")
        return

    today = datetime.now().strftime("%Y년 %m월 %d일")
    subject = f"[지원사업 알림] {today} 신규 공고 {len(new_items)}건"

    html_parts = [
        "<html><body style='font-family: 맑은 고딕, Arial, sans-serif; max-width: 700px;'>",
        f"<h2 style='color:#2c5aa0;'>📢 오늘의 신규 지원사업 공고 ({len(new_items)}건)</h2>",
        "<p style='color:#666;'>관심 키워드/기관과 매칭된 신규 공고입니다.</p>",
        "<hr/>",
    ]

    for idx, (item, reason) in enumerate(new_items, 1):
        title = item.get("pblancNm", "(제목 없음)")
        org = item.get("excInsttNm") or item.get("jrsdInsttNm") or "-"
        reqstBeginEndDe = item.get("reqstBeginEndDe", "-")
        pblancUrl = item.get("pblancUrl", "")
        if pblancUrl and not pblancUrl.startswith("http"):
            pblancUrl = "https://www.bizinfo.go.kr" + pblancUrl

        summary = (item.get("bsnsSumryCn") or "").strip()
        if len(summary) > 200:
            summary = summary[:200] + "..."

        html_parts.append(f"""
        <div style='border:1px solid #ddd; border-radius:8px; padding:15px; margin:12px 0; background:#fafafa;'>
            <div style='font-size:12px; color:#888;'>#{idx} · 매칭사유: {reason}</div>
            <h3 style='margin:8px 0;'>
                <a href='{pblancUrl}' style='color:#2c5aa0; text-decoration:none;'>{title}</a>
            </h3>
            <div style='font-size:13px; color:#555;'>
                <b>기관:</b> {org}<br/>
                <b>접수기간:</b> {reqstBeginEndDe}
            </div>
            <div style='font-size:13px; color:#444; margin-top:8px; line-height:1.5;'>{summary}</div>
            <div style='margin-top:10px;'>
                <a href='{pblancUrl}' style='background:#2c5aa0; color:white; padding:6px 14px;
                   text-decoration:none; border-radius:4px; font-size:13px;'>공고 상세보기 →</a>
            </div>
        </div>
        """)

    html_parts.append("""
        <hr/>
        <p style='font-size:12px; color:#999;'>
            매일 오전 9시(한국시간) 자동 발송 · 기업마당 공식 API 기반
        </p>
        </body></html>
    """)

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = GMAIL_USER
    msg["To"] = TO_EMAIL
    msg.set_content(f"신규 공고 {len(new_items)}건이 있습니다. HTML 메일로 확인하세요.")
    msg.add_alternative("\n".join(html_parts), subtype="html")

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
        smtp.login(GMAIL_USER, GMAIL_APP_PASSWORD)
        smtp.send_message(msg)

    print(f"이메일 발송 완료: {len(new_items)}건")


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
        print("⚠️ 가져온 공고가 없습니다. API 키 또는 네트워크를 확인하세요.")
        return

    new_relevant = []
    for item in items:
        item_id = str(item.get("pblancId") or item.get("pblancNm", ""))
        if not item_id or item_id in seen:
            continue

        relevant, reason = is_relevant(item)
        if relevant:
            new_relevant.append((item, reason))

        seen.add(item_id)

    print(f"신규 매칭 공고 수: {len(new_relevant)}")

    if new_relevant:
        send_email(new_relevant)

    save_seen(seen)
    print("완료!")


if __name__ == "__main__":
    main()
