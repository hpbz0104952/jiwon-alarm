"""
지원사업 알림 자동화 스크립트 v7
- 좋은술양조장 + 김담희창업 정밀 매칭
- 평택/경기 전체/전국 대상만, 미디어/콘텐츠/영상 제외
- 평택 직할 + 농업 + 수출 기관 우선순위 강화
- 마감 3일 이내 별도 강조 + 지원금액 자동 추출
"""
import os
import json
import smtplib
import requests
import re
from email.message import EmailMessage
from datetime import datetime, date
from pathlib import Path

TO_EMAIL = "jsul8929@gmail.com"

CORE_KEYWORDS = {
    "yangjojang": [
        "양조장", "전통주", "막걸리", "탁주", "약주", "증류주",
        "주류", "주조", "지역특산주", "민속주",
        "주류면허", "주류제조", "주세",
        "막걸리축제", "전통주축제", "술축제",
        "시음회", "테이스팅", "페어링",
        "전통식품", "우리술", "한국술", "K-Liquor", "K-Drink",
        "양조", "발효", "효모", "누룩",
        "지역주류", "향토주", "토속주", "지역술",
    ],
    "kimdamhee": [
        "예비창업", "청년창업", "청년농업", "청년농업인", "후계농", "영농창업",
        "여성기업", "여성창업", "1인창조기업", "1인기업",
        "6차산업", "농촌융복합", "농촌자원복합", "농촌체험",
        "농산물가공", "농식품가공", "업사이클", "푸드테크",
        "K-푸드", "K푸드", "K-디저트",
        "농업인", "농가", "농업법인", "농업회사법인", "영농법인",
        "친환경농업", "유기농", "무농약", "친환경인증",
        "스마트팜", "스마트농업", "그린바이오",
        "청년후계농", "농업후계자", "후계농업경영인",
        "농업창업", "귀농귀촌", "귀농인", "귀농",
        "식품제조", "식품가공", "식품안전",
        "농산물브랜드", "지역특산물", "지리적표시",
        "김치", "장류", "발효식품",
        "곡물", "쌀가공", "미곡", "잡곡", "가공곡물",
        "즉석식품", "간편식", "HMR", "밀키트",
        "팜파티", "팜스테이", "농촌관광", "그린투어", "팜투어",
        "마을기업", "공동체기업", "농어촌공동체",
        "농가맛집", "쿠킹클래스", "체험농장", "체험프로그램",
        "평택쌀", "평택농산물", "평택특산",
        "경기미", "경기농산물", "경기특산", "경기쌀",
        "농업정책자금", "농신보", "농업보증",
    ],
}

COMBO_KEYWORDS = [
    "디자인", "패키지", "브랜드", "브랜딩",
    "마케팅", "온라인", "오프라인", "유통", "판로",
    "수출", "해외", "박람회", "전시회", "수출상담",
    "시설", "장비", "스마트공장", "스마트팜",
    "인증", "HACCP", "할랄", "코셔", "FDA", "GMP",
    "시제품", "제품개발", "신제품",
    "컨설팅", "교육", "멘토링",
    "임차료", "사무공간", "공간지원",
    "투자", "투자유치", "IR",
    "체험", "관광", "농촌관광", "팜스테이",
    "비건", "베이킹", "디저트",
    "소상공인", "중소기업", "스타트업", "창업기업",
    "FTA", "통관", "검역", "수출검역",
    "해외시장", "해외판로", "해외바이어", "수출바이어",
    "수출보증", "수출보험", "수출자금",
    "일본수출", "미국수출", "동남아수출", "중국수출",
    "한류",
    "라벨", "라벨디자인", "패키지리뉴얼",
    "굿디자인", "GD마크", "K-디자인",
    "제품사진", "비주얼", "카탈로그",
    "정책자금", "융자", "매칭펀드", "정부매칭",
    "정착지원", "초기자금", "운영자금",
    "판매장", "직거래", "온라인몰", "오픈마켓",
    "청년몰", "청년상인", "청년상가",
]

PRIORITY_ORGS = [
    "한국디자인진흥원",
    "한국쌀가공식품협회",
    "한국전통주연구소",
    # 농식품 수출
    "한국농수산식품유통공사", "aT", "AT",
    "AT수출종합지원시스템", "농식품수출",
    "수출종합지원", "농수산물수출",
    # 농식품부
    "농림축산식품부", "농식품부", "농림부",
    # 농촌진흥청
    "농촌진흥청", "농진청", "국립농업과학원",
    "여성기업종합지원센터",
    "한국여성경제인협회",
    "창업진흥원",
    "K-Startup",
    "농업기술실용화재단", "한국농업기술진흥원",
    "한국농어촌공사",
    # 평택 직할 기관
    "평택시", "평택시청", "평택시농업기술센터", "안중출장소",
    "평택농협", "평택축산농협",
    # 경기 농업 기관
    "경기도농업기술원", "농식품유통과", "경기도농수산진흥원",
    "평택산업진흥원",
    "경기도경제과학진흥원", "GBSA",
    "경기도일자리재단",
    "경기농수산진흥원",
    "경기도주식회사",
    "한국기업가정신재단",
    "중소상공인희망재단",
    "소상공인시장진흥공단",
    "해외규격인증획득지원센터",
    "KOTRA", "코트라",
]

EXCLUDE_KEYWORDS = [
    "대기업", "중견기업",
    "IT개발자", "소프트웨어개발자", "AI개발자", "프로그래머",
    "반도체", "디스플레이", "조선", "해운", "항공",
    "광역버스", "택시운송", "택시기사", "택시업", "물류센터",
    "벤처투자조합", "사모펀드",
    "이공계특성화", "공학교육",
    "장애인기업", "사회적기업",
    "보훈", "다문화",
    # 비대상 그룹
    "신혼부부", "신중년", "여성가장",
    "한부모", "조손가정", "위기청소년",
    "북한이탈주민", "탈북민", "외국인근로자",
    "노인일자리", "시니어",
    # 미디어/콘텐츠/영상
    "미디어", "방송", "라디오", "신문", "언론",
    "콘텐츠", "웹툰", "웹소설", "만화", "애니메이션",
    "영상", "영화", "드라마", "예능", "다큐멘터리",
    "유튜브", "유튜버", "크리에이터", "1인미디어", "MCN",
    "OTT", "넷플릭스", "스트리밍",
    "VR", "AR", "메타버스", "XR",
    "게임", "e스포츠",
    "음악", "뮤직", "공연", "엔터테인먼트",
    "출판", "전자책", "오디오북",
    "광고", "광고제작",
]

ALLOWED_REGIONS = ["경기", "전국", "수도권", "평택"]
EXCLUDED_REGIONS = [
    "서울", "부산", "대구", "인천", "광주", "대전", "울산", "세종",
    "강원", "충북", "충남", "전북", "전남", "경북", "경남", "제주",
]

GYEONGGI_OTHER_CITIES = [
    "수원", "성남", "고양", "용인", "부천", "안산", "안양", "남양주",
    "화성", "의정부", "시흥", "파주", "광명", "김포", "광주시", "군포",
    "하남", "오산", "이천", "양주", "구리", "안성", "포천", "의왕",
    "여주", "동두천", "양평", "과천", "가평", "연천",
]

NATIONWIDE_HINTS = ["전국", "전체", "대한민국", "국가"]
GYEONGGI_WIDE_HINTS = ["경기도 전체", "경기 전체", "도내", "경기지역", "경기도 소재", "경기도 내"]

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
        "searchCnt": "200",
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
    title = str(item.get("pblancNm", ""))
    content = str(item.get("bsnsSumryCn", ""))
    area = str(item.get("areaNm", ""))
    target = str(item.get("trgetNm", ""))
    org = str(item.get("excInsttNm", "") or item.get("jrsdInsttNm", ""))

    all_text = f"{title} {content} {area} {target} {org}"
    region_text = f"{title} {area} {target}"

    # 1) 평택 직접 매칭
    if "평택" in all_text or "오성" in all_text:
        return True

    # 1-2) 평택 직할 기관 발행
    pyeongtaek_orgs = ["평택시", "평택시청", "평택시농업기술센터",
                       "안중출장소", "평택산업진흥원", "평택농협"]
    for po in pyeongtaek_orgs:
        if po in org:
            return True

    # 2) 다른 광역시/도 단독 공고는 제외
    for region in EXCLUDED_REGIONS:
        strong_patterns = [
            f"{region}시", f"{region}도", f"{region}특별시",
            f"{region}광역시", f"{region}특별자치시", f"{region}특별자치도",
        ]
        for pat in strong_patterns:
            if pat in region_text:
                return False
        for limit_pat in [f"{region}시 소재", f"{region}도 소재",
                          f"{region}시 거주", f"{region}도 거주",
                          f"{region}시 소재 기업", f"{region}도 소재 기업"]:
            if limit_pat in all_text:
                return False

    # 3) 평택 외 경기도 시군 단독 공고는 제외
    for city in GYEONGGI_OTHER_CITIES:
        for pat in [f"{city}시 소재", f"{city} 소재",
                    f"{city}시 거주", f"{city} 거주",
                    f"{city}시 관내", f"{city} 관내",
                    f"{city}시 기업", f"{city} 기업"]:
            if pat in all_text:
                return False

    # 4) 명확한 통과 신호: "전국" / "경기 전체"
    for hint in NATIONWIDE_HINTS:
        if hint in region_text:
            return True
    for hint in GYEONGGI_WIDE_HINTS:
        if hint in all_text:
            return True

    # 5) 단순 "경기" 언급
    if "경기" in region_text:
        return True

    # 6) 광역 기관 발행
    nationwide_orgs = [
        "중소벤처기업부", "농림축산식품부", "농식품부", "농림부",
        "문화체육관광부", "산업통상자원부",
        "고용노동부", "환경부", "보건복지부", "교육부", "행정안전부",
        "KOTRA", "코트라", "창업진흥원", "한국디자인진흥원",
        "한국농수산식품유통공사", "aT", "AT", "AT수출종합지원시스템",
        "여성기업종합지원센터",
        "한국기업가정신재단", "소상공인시장진흥공단", "한국쌀가공식품협회",
        "농촌진흥청", "농진청", "국립농업과학원", "기업마당",
        "경기도농업기술원", "농식품유통과", "농업기술실용화재단",
        "한국농어촌공사", "한국농업기술진흥원",
    ]
    for nw_org in nationwide_orgs:
        if nw_org in org:
            return True

    return False


def parse_deadline(reqstBeginEndDe):
    if not reqstBeginEndDe or reqstBeginEndDe == "-":
        return None
    matches = re.findall(r"(\d{4})[.\-/]?(\d{1,2})[.\-/]?(\d{1,2})", reqstBeginEndDe)
    if len(matches) >= 2:
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
    deadline = parse_deadline(item.get("reqstBeginEndDe", ""))
    if deadline is None:
        return None
    today = date.today()
    return (deadline - today).days


def extract_amounts(item):
    title = item.get("pblancNm", "") or ""
    content = item.get("bsnsSumryCn", "") or ""
    text = f"{title}\n{content}"

    patterns = [
        r"(최대|최고)\s*([\d,]+(?:\.\d+)?)\s*(억\s*\d*\s*천?만?|천만|백만|만)\s*원?",
        r"([\d,]+(?:\.\d+)?)\s*(억\s*\d*\s*천?만?|천만|백만|만)\s*원\s*(이내|한도|이하|까지)",
        r"(기업당|건당|사업당|업체당|개사당|과제당)\s*([\d,]+(?:\.\d+)?)\s*(억\s*\d*\s*천?만?|천만|백만|만)\s*원?",
        r"(총\s*사업비|예산|사업규모|총\s*예산|지원금|지원\s*규모|총\s*규모)\s*[:：]?\s*([\d,]+(?:\.\d+)?)\s*(억\s*\d*\s*천?만?|천만|백만|만)\s*원?",
        r"(지원금액|지원\s*금액|보조금|장려금)\s*[:：]?\s*([\d,]+(?:\.\d+)?)\s*(억\s*\d*\s*천?만?|천만|백만|만)\s*원?",
    ]

    found = []
    for pattern in patterns:
        for match in re.finditer(pattern, text):
            full_match = match.group(0).strip()
            if len(full_match) > 30:
                full_match = full_match[:30] + "..."
            if full_match not in found:
                found.append(full_match)

    return found[:3]


def has_excluded(text):
    for kw in EXCLUDE_KEYWORDS:
        if kw in text:
            return True, kw
    return False, ""


def classify_business(item):
    title = (item.get("pblancNm") or "").strip()
    content = (item.get("bsnsSumryCn") or "").strip()
    org = (item.get("excInsttNm") or item.get("jrsdInsttNm") or "").strip()
    text = f"{title} {content} {org}"

    excluded, exc_kw = has_excluded(text)
    if excluded:
        return False, f"제외:{exc_kw}", ""

    for priority_org in PRIORITY_ORGS:
        if priority_org in org:
            if any(k in priority_org for k in ["여성", "창업", "기업가정신"]):
                return True, f"기관: {priority_org}", "kimdamhee"
            elif any(k in priority_org for k in ["농", "쌀", "전통주", "디자인",
                                                  "수출", "KOTRA", "코트라",
                                                  "평택", "안중", "농식품",
                                                  "aT", "AT"]):
                return True, f"기관: {priority_org}", "both"
            else:
                return True, f"기관: {priority_org}", "both"

    yangjojang_matched = [kw for kw in CORE_KEYWORDS["yangjojang"] if kw in text]
    kimdamhee_matched = [kw for kw in CORE_KEYWORDS["kimdamhee"] if kw in text]

    if yangjojang_matched and kimdamhee_matched:
        return True, f"핵심: {yangjojang_matched[0]}, {kimdamhee_matched[0]}", "both"
    elif yangjojang_matched:
        return True, f"양조장 핵심: {', '.join(yangjojang_matched[:2])}", "yangjojang"
    elif kimdamhee_matched:
        return True, f"창업 핵심: {', '.join(kimdamhee_matched[:2])}", "kimdamhee"

    combo_matched = [kw for kw in COMBO_KEYWORDS if kw in text]
    if len(combo_matched) >= 2:
        return True, f"조합: {', '.join(combo_matched[:3])}", "both"

    return False, "", ""


def render_card(item, reason, days_left, idx, urgent=False):
    title = item.get("pblancNm", "(제목 없음)")
    org = item.get("excInsttNm") or item.get("jrsdInsttNm") or "-"
    reqstBeginEndDe = item.get("reqstBeginEndDe", "-")
    pblancUrl = item.get("pblancUrl", "")
    if pblancUrl and not pblancUrl.startswith("http"):
        pblancUrl = "https://www.bizinfo.go.kr" + pblancUrl

    summary = (item.get("bsnsSumryCn") or "").strip()
    if len(summary) > 200:
        summary = summary[:200] + "..."

    if days_left is None:
        deadline_html = f"<b>접수기간:</b> {reqstBeginEndDe}"
    elif days_left < 0:
        deadline_html = f"<b>접수기간:</b> {reqstBeginEndDe} <span style='color:#999;'>(마감)</span>"
    elif urgent:
        deadline_html = f"<b>접수기간:</b> {reqstBeginEndDe} <span style='color:#d9534f; font-weight:bold;'>⏰ D-{days_left}</span>"
    else:
        deadline_html = f"<b>접수기간:</b> {reqstBeginEndDe} <span style='color:#5cb85c;'>(D-{days_left})</span>"

    amounts = extract_amounts(item)
    if amounts:
        amount_text = " · ".join(amounts)
        amount_html = f"""
        <div style='background:#fff8e1; border-left:3px solid #ffa726; padding:6px 10px; margin:8px 0; font-size:13px;'>
            💰 <b>지원금액:</b> {amount_text}
        </div>
        """
    else:
        amount_html = ""

    if urgent:
        border_color = "#d9534f"
        bg_color = "#fff5f5"
    else:
        border_color = "#ddd"
        bg_color = "#fafafa"

    return f"""
    <div style='border:2px solid {border_color}; border-radius:8px; padding:15px; margin:12px 0; background:{bg_color};'>
        <div style='font-size:12px; color:#888;'>#{idx} · {reason}</div>
        <h3 style='margin:8px 0;'>
            <a href='{pblancUrl}' style='color:#2c5aa0; text-decoration:none;'>{title}</a>
        </h3>
        <div style='font-size:13px; color:#555;'>
            <b>기관:</b> {org}<br/>
            {deadline_html}
        </div>
        {amount_html}
        <div style='font-size:13px; color:#444; margin-top:8px; line-height:1.5;'>{summary}</div>
        <div style='margin-top:10px;'>
            <a href='{pblancUrl}' style='background:#2c5aa0; color:white; padding:6px 14px;
               text-decoration:none; border-radius:4px; font-size:13px;'>공고 상세보기 →</a>
        </div>
    </div>
    """


def render_section_header(title, count, color="#2c5aa0"):
    return f"""
    <div style='background:{color}; color:white; padding:12px; border-radius:6px; margin:20px 0 10px 0;'>
        <h3 style='margin:0;'>{title} ({count}건)</h3>
    </div>
    """


def send_email(urgent_items, yangjojang_items, kimdamhee_items, both_items):
    total = len(urgent_items) + len(yangjojang_items) + len(kimdamhee_items) + len(both_items)
    if total == 0:
        print("신규 매칭 공고 없음 — 이메일 발송 건너뜀")
        return

    today = datetime.now().strftime("%Y년 %m월 %d일")

    if urgent_items:
        subject = f"[지원사업 알림] {today} ⏰ 마감임박 {len(urgent_items)}건 + 신규 {total - len(urgent_items)}건"
    else:
        subject = f"[지원사업 알림] {today} 신규 공고 {total}건"

    html_parts = [
        "<html><body style='font-family: 맑은 고딕, Arial, sans-serif; max-width: 700px;'>",
        f"<h2 style='color:#2c5aa0;'>📢 오늘의 지원사업 공고 ({total}건)</h2>",
        f"<p style='color:#666;'>평택/경기전체/전국 대상 · 좋은술양조장 + 김담희창업 맞춤 · 미디어 제외</p>",
    ]

    idx = 1

    if urgent_items:
        html_parts.append(render_section_header(
            f"⏰ 마감 임박! 3일 이내", len(urgent_items), "#d9534f"))
        for item, reason, days_left, _ in urgent_items:
            html_parts.append(render_card(item, reason, days_left, idx, urgent=True))
            idx += 1

    if yangjojang_items:
        html_parts.append(render_section_header(
            f"🍶 좋은술양조장 관련", len(yangjojang_items), "#7a3d2e"))
        for item, reason, days_left, _ in yangjojang_items:
            html_parts.append(render_card(item, reason, days_left, idx))
            idx += 1

    if kimdamhee_items:
        html_parts.append(render_section_header(
            f"🌾 김담희창업 관련", len(kimdamhee_items), "#5cb85c"))
        for item, reason, days_left, _ in kimdamhee_items:
            html_parts.append(render_card(item, reason, days_left, idx))
            idx += 1

    if both_items:
        html_parts.append(render_section_header(
            f"🔀 양쪽 모두 해당", len(both_items), "#5a5a5a"))
        for item, reason, days_left, _ in both_items:
            html_parts.append(render_card(item, reason, days_left, idx))
            idx += 1

    html_parts.append("""
        <hr/>
        <p style='font-size:12px; color:#999;'>
            매일 오전 9시(한국시간) 자동 발송 · v7 (수출/농식품 기관 강화)
        </p>
        </body></html>
    """)

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = GMAIL_USER
    msg["To"] = TO_EMAIL
    msg.set_content(f"신규 공고 {total}건. HTML 메일로 확인하세요.")
    msg.add_alternative("\n".join(html_parts), subtype="html")

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
        smtp.login(GMAIL_USER, GMAIL_APP_PASSWORD)
        smtp.send_message(msg)

    print(f"이메일 발송 완료: 총 {total}건")


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
        return

    urgent_items = []
    yangjojang_items = []
    kimdamhee_items = []
    both_items = []
    stats = {"region_filtered": 0, "expired": 0, "excluded": 0, "no_match": 0}

    for item in items:
        item_id = str(item.get("pblancId") or item.get("pblancNm", ""))
        if not item_id or item_id in seen:
            continue

        if not is_region_allowed(item):
            stats["region_filtered"] += 1
            seen.add(item_id)
            continue

        relevant, reason, business = classify_business(item)
        if not relevant:
            if reason.startswith("제외:"):
                stats["excluded"] += 1
            else:
                stats["no_match"] += 1
            seen.add(item_id)
            continue

        days_left = get_days_until_deadline(item)
        if days_left is not None and days_left < 0:
            stats["expired"] += 1
            seen.add(item_id)
            continue

        entry = (item, reason, days_left, business)
        if days_left is not None and days_left <= DEADLINE_WARNING_DAYS:
            urgent_items.append(entry)
        elif business == "yangjojang":
            yangjojang_items.append(entry)
        elif business == "kimdamhee":
            kimdamhee_items.append(entry)
        else:
            both_items.append(entry)

        seen.add(item_id)

    print(f"📍 지역 필터 제외: {stats['region_filtered']}건")
    print(f"📅 이미 마감 제외: {stats['expired']}건")
    print(f"🚫 제외 키워드 매칭: {stats['excluded']}건")
    print(f"➖ 매칭 안 됨: {stats['no_match']}건")
    print(f"⏰ 마감임박: {len(urgent_items)}건")
    print(f"🍶 좋은술양조장: {len(yangjojang_items)}건")
    print(f"🌾 김담희창업: {len(kimdamhee_items)}건")
    print(f"🔀 양쪽 모두: {len(both_items)}건")

    if urgent_items or yangjojang_items or kimdamhee_items or both_items:
        send_email(urgent_items, yangjojang_items, kimdamhee_items, both_items)

    save_seen(seen)
    print("완료!")


if __name__ == "__main__":
    main()
