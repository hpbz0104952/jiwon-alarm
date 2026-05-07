"""
지원사업 알림 자동화 스크립트 v5 (지역 엄격화 + 미디어 제외)
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
    ],
    "kimdamhee": [
        "예비창업", "청년창업", "청년농업", "청년농업인", "후계농", "영농창업",
        "여성기업", "여성창업", "1인창조기업", "1인기업",
        "6차산업", "농촌융복합", "농촌자원복합", "농촌체험",
        "농산물가공", "농식품가공", "업사이클", "푸드테크",
        "K-푸드", "K푸드", "K-디저트",
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
]

PRIORITY_ORGS = [
    "한국디자인진흥원", "한국쌀가공식품협회", "한국전통주연구소",
    "한국농수산식품유통공사", "aT", "농림축산식품부",
    "여성기업종합지원센터", "한국여성경제인협회",
    "창업진흥원", "K-Startup",
    "농업기술실용화재단", "농촌진흥청",
    "평택산업진흥원", "경기도경제과학진흥원", "GBSA",
    "경기도일자리재단", "경기농수산진흥원", "경기도주식회사",
    "한국기업가정신재단", "중소상공인희망재단",
    "소상공인시장진흥공단", "해외규격인증획득지원센터",
    "KOTRA", "코트라",
]

EXCLUDE_KEYWORDS = [
    "대기업", "중견기업",
    "IT개발자", "소프트웨어개발자", "AI개발자", "프로그래머",
    "반도체", "디스플레이", "조선", "해운", "항공",
    "광역버스", "택시", "물류센터",
    "벤처투자조합", "사모펀드",
    "이공계특성화", "공학교육",
    "장애인기업", "사회적기업",
    "보훈", "다문화",
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

    if "평택" in all_text or "오성" in all_text:
        return True

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

    for city in GYEONGGI_OTHER_CITIES:
        for pat in [f"{city}시 소재", f"{city} 소재",
                    f"{city}시 거주", f"{city} 거주",
                    f"{city}시 관내", f"{city} 관내",
                    f"{city}시 기업", f"{city} 기업"]:
            if pat in all_text:
                return False

    for hint in NATIONWIDE_HINTS:
        if hint in region_text:
            return True
    for hint in GYEONGGI_WIDE_HINTS:
        if hint in all_text:
            return True

    if "경기" in region_text:
        return True

    nationwide_orgs = [
        "중소벤처기업부", "농림축산식품부", "문화체육관광부", "산업통상자원부",
        "고용노동부", "환경부", "보건복지부", "교육부", "행정안전부",
        "KOTRA", "코트라", "창업진흥원", "한국디자인진흥원",
        "한국농수산식품유통공사", "aT", "여성기업종합지원센터",
        "한국기업가정신재단", "소상공인시장진흥공단", "한국쌀가공식품협회",
        "농촌진흥청", "기업마당",
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

    excluded, exc_kw = has_excluded
