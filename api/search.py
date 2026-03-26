"""
104 VIP recruiter candidate search.

Confirmed endpoint: https://auth.vip.104.com.tw/api/search/searchResult
Auth: cookie-based (paste from browser).

Confirmed query parameters (from network inspection):
  contactPrivacy, kws, workExpTimeType, workExpTimeMin, agemin, agemax,
  sex, empStatus, updateDateType, sortType, readStatus, plastActionDateType,
  autono (recruiter account ID), ec (company code), page

Confirmed response shape:
  { status: "SUCCESS", result: { condition: [...], data: [...] } }

Candidate fields confirmed:
  idNo, userName, age, sex, sexDesc, eduDesc, areaDesc, wcityNoDesc,
  titleCatDesc, expPeriodDesc, expJobArr[{expFirm, expTitle}],
  updateDayDesc, plastActionDateDesc, masterUrl, personalPic, readStatus
"""

import json
import re
import urllib.parse
import httpx
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import Optional
from database import setting_get, setting_set

router = APIRouter()

# ── Confirmed endpoints ───────────────────────────────────────────────────────
SEARCH_URL  = "https://auth.vip.104.com.tw/api/search/searchResult"
DETAIL_BASE = "https://vip.104.com.tw"   # prepend to masterUrl path
REFERER     = "https://vip.104.com.tw/"
RESULTS_PER_PAGE = 10  # 104 default; adjust if confirmed otherwise


# ── Demo / mock data ──────────────────────────────────────────────────────────

_DEMO_CANDIDATES = [
    {"idNo":"DEMO001","userName":"陳大明","age":46,"sexDesc":"男",
     "eduDesc":"碩士畢業 私立大同大學 電機系","areaDesc":"台北市",
     "wcityNoDesc":"台北市、新北市","titleCatDesc":"電力工程師 / SIPI研發工程師",
     "expPeriodDesc":"14~15年工作經驗","updateDayDesc":"2026/03/22","plastActionDateDesc":"2天內",
     "expJobArr":[{"expFirm":"台積電","expTitle":"Senior Signal Integrity Engineer"},
                  {"expFirm":"聯發科","expTitle":"電力工程師"}],"masterUrl":"","personalPic":""},
    {"idNo":"DEMO002","userName":"林小芳","age":29,"sexDesc":"女",
     "eduDesc":"碩士畢業 國立交通大學 電子所","areaDesc":"新竹縣市",
     "wcityNoDesc":"新竹縣市、台北市","titleCatDesc":"電源工程師 / 電力電子工程師",
     "expPeriodDesc":"5~6年工作經驗","updateDayDesc":"2026/03/21","plastActionDateDesc":"1天內",
     "expJobArr":[{"expFirm":"台達電子","expTitle":"電源供應器設計工程師"}],"masterUrl":"","personalPic":""},
    {"idNo":"DEMO003","userName":"王建國","age":41,"sexDesc":"男",
     "eduDesc":"大學畢業 國立成功大學 電機系","areaDesc":"台中市",
     "wcityNoDesc":"台中市","titleCatDesc":"資深電氣工程師",
     "expPeriodDesc":"15~16年工作經驗","updateDayDesc":"2026/03/20","plastActionDateDesc":"3天內",
     "expJobArr":[{"expFirm":"日月光半導體","expTitle":"資深電氣工程師"},
                  {"expFirm":"鴻海精密","expTitle":"電控工程師"}],"masterUrl":"","personalPic":""},
    {"idNo":"DEMO004","userName":"張美玲","age":31,"sexDesc":"女",
     "eduDesc":"碩士畢業 國立清華大學 電機所","areaDesc":"台北市",
     "wcityNoDesc":"台北市、桃園市","titleCatDesc":"韌體工程師 / 嵌入式系統工程師",
     "expPeriodDesc":"5~6年工作經驗","updateDayDesc":"2026/03/19","plastActionDateDesc":"4天內",
     "expJobArr":[{"expFirm":"聯詠科技","expTitle":"韌體工程師"}],"masterUrl":"","personalPic":""},
    {"idNo":"DEMO005","userName":"李志偉","age":35,"sexDesc":"男",
     "eduDesc":"大學畢業 國立台灣大學 電機系","areaDesc":"桃園市",
     "wcityNoDesc":"桃園市、新北市、台北市","titleCatDesc":"電力系統分析師 / Signal Integrity工程師",
     "expPeriodDesc":"10~11年工作經驗","updateDayDesc":"2026/03/18","plastActionDateDesc":"5天內",
     "expJobArr":[{"expFirm":"廣達電腦","expTitle":"Signal Integrity工程師"},
                  {"expFirm":"仁寶電腦","expTitle":"電力系統分析師"}],"masterUrl":"","personalPic":""},
    {"idNo":"DEMO006","userName":"黃雅婷","age":26,"sexDesc":"女",
     "eduDesc":"大學畢業 私立逢甲大學 電機系","areaDesc":"高雄市",
     "wcityNoDesc":"高雄市、台南市","titleCatDesc":"電機工程師",
     "expPeriodDesc":"1~2年工作經驗","updateDayDesc":"2026/03/17","plastActionDateDesc":"本週",
     "expJobArr":[{"expFirm":"台灣電力公司","expTitle":"電機工程師"}],"masterUrl":"","personalPic":""},
    {"idNo":"DEMO007","userName":"吳明哲","age":38,"sexDesc":"男",
     "eduDesc":"碩士畢業 國立台灣科技大學 電機所","areaDesc":"台南市",
     "wcityNoDesc":"台南市、高雄市","titleCatDesc":"高壓電氣主任工程師 / Signal Integrity主管",
     "expPeriodDesc":"12~13年工作經驗","updateDayDesc":"2026/03/16","plastActionDateDesc":"本週",
     "expJobArr":[{"expFirm":"奇美電子","expTitle":"高壓電氣主任工程師"}],"masterUrl":"","personalPic":""},
    {"idNo":"DEMO008","userName":"蔡佳穎","age":33,"sexDesc":"女",
     "eduDesc":"大學畢業 國立台北科技大學 電機系","areaDesc":"新北市",
     "wcityNoDesc":"新北市、台北市","titleCatDesc":"電源模組設計工程師",
     "expPeriodDesc":"7~8年工作經驗","updateDayDesc":"2026/03/15","plastActionDateDesc":"本週",
     "expJobArr":[{"expFirm":"光寶科技","expTitle":"電源模組設計工程師"}],"masterUrl":"","personalPic":""},
    {"idNo":"DEMO009","userName":"鄭俊傑","age":44,"sexDesc":"男",
     "eduDesc":"大學畢業 國立中央大學 電機系","areaDesc":"台北市",
     "wcityNoDesc":"台北市","titleCatDesc":"電力工程部門主管 / 總工程師",
     "expPeriodDesc":"18~19年工作經驗","updateDayDesc":"2026/03/14","plastActionDateDesc":"本週",
     "expJobArr":[{"expFirm":"台達電子","expTitle":"電力工程部門主管"},
                  {"expFirm":"研華科技","expTitle":"資深電力工程師"}],"masterUrl":"","personalPic":""},
    {"idNo":"DEMO010","userName":"許淑惠","age":28,"sexDesc":"女",
     "eduDesc":"碩士畢業 國立成功大學 電機所","areaDesc":"新竹縣市",
     "wcityNoDesc":"新竹縣市","titleCatDesc":"電力電子研究員 / Signal Integrity研究員",
     "expPeriodDesc":"2~3年工作經驗","updateDayDesc":"2026/03/13","plastActionDateDesc":"上週",
     "expJobArr":[{"expFirm":"工業技術研究院","expTitle":"電力電子研究員"}],"masterUrl":"","personalPic":""},
]


def _demo_search(keyword: str, page: int):
    pool = _DEMO_CANDIDATES
    if keyword:
        kw = keyword.strip('"').lower()
        pool = [c for c in pool if
                kw in c["titleCatDesc"].lower() or
                kw in c["userName"].lower() or
                any(kw in j["expTitle"].lower() or kw in j["expFirm"].lower()
                    for j in c["expJobArr"])]
    per_page = RESULTS_PER_PAGE
    total = len(pool)
    total_pages = max(1, -(-total // per_page))
    items = pool[(page-1)*per_page : page*per_page]
    return {
        "ok": True,
        "demo": True,
        "candidates": [_normalise(c) for c in items],
        "totalCount": total,
        "totalPages": total_pages,
        "currentPage": page,
    }


# ── Normalise a raw 104 candidate into our standard shape ────────────────────

def _normalise(raw: dict) -> dict:
    """Map confirmed 104 API fields to our internal schema."""
    exp_jobs = raw.get("expJobArr") or []
    recent_title  = exp_jobs[0].get("expTitle", "") if exp_jobs else ""
    recent_firm   = exp_jobs[0].get("expFirm",  "") if exp_jobs else ""
    # Build a searchable skills/summary string from all available text
    skills_text = " | ".join(
        f"{j.get('expTitle','')} @ {j.get('expFirm','')}"
        for j in exp_jobs if j.get("expTitle") or j.get("expFirm")
    )
    return {
        "candidate_104_id": str(raw.get("idNo", "")),
        "name":             raw.get("userName", ""),
        "age":              raw.get("age"),
        "sex":              raw.get("sexDesc", ""),
        "education":        raw.get("eduDesc", ""),
        "experience":       raw.get("expPeriodDesc", ""),
        "location":         raw.get("areaDesc", ""),
        "preferred_areas":  raw.get("wcityNoDesc", ""),
        "current_title":    raw.get("titleCatDesc", "") or recent_title,
        "recent_firm":      recent_firm,
        "skills":           skills_text,
        "last_update":      raw.get("updateDayDesc", ""),
        "last_active":      raw.get("plastActionDateDesc", ""),
        "pic":              raw.get("personalPic", ""),
        "master_url":       raw.get("masterUrl", ""),
        "exp_jobs":         exp_jobs,
        "raw_data":         raw,
    }


def _extract_total(data_list: list) -> int:
    """Parse total_hit from search_meta embedded in first result's masterUrl."""
    if not data_list:
        return 0
    master = data_list[0].get("masterUrl", "")
    try:
        qs = urllib.parse.parse_qs(urllib.parse.urlparse(master).query)
        meta_str = qs.get("search_meta", ["{}"])[0]
        meta = json.loads(meta_str)
        return int(meta.get("total_hit", 0))
    except Exception:
        return len(data_list)


# ── Headers ───────────────────────────────────────────────────────────────────

def _build_headers(cookie_str: str) -> dict:
    return {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        "Referer":        REFERER,
        "Accept":         "application/json, text/plain, */*",
        "Accept-Language":"zh-TW,zh;q=0.9,en-US;q=0.8,en;q=0.7",
        "Cookie":         cookie_str,
    }


# ── Models ────────────────────────────────────────────────────────────────────

class CookiePayload(BaseModel):
    cookies: str

class AccountConfig(BaseModel):
    autono: str
    ec: str


# ── Cookie / account management ───────────────────────────────────────────────

@router.post("/cookies")
def save_cookies(payload: CookiePayload):
    setting_set("104_cookies", payload.cookies.strip())
    return {"status": "saved"}


@router.get("/account")
def get_account():
    return {
        "autono": setting_get("104_autono", ""),
        "ec":     setting_get("104_ec", ""),
    }


@router.post("/account")
def save_account(body: AccountConfig):
    setting_set("104_autono", body.autono.strip())
    setting_set("104_ec",     body.ec.strip())
    return {"status": "saved"}


# ── Demo mode ─────────────────────────────────────────────────────────────────

@router.get("/demo")
def get_demo_mode():
    return {"enabled": setting_get("demo_mode", "0") == "1"}


@router.post("/demo")
def set_demo_mode(enabled: bool = True):
    setting_set("demo_mode", "1" if enabled else "0")
    return {"enabled": enabled}


# ── Cookie status ─────────────────────────────────────────────────────────────

@router.get("/cookies/status")
async def check_cookies():
    if setting_get("demo_mode", "0") == "1":
        return {"valid": True, "message": "Demo mode active — no cookies needed."}
    cookie_str = setting_get("104_cookies", "")
    if not cookie_str:
        return {"valid": False, "message": "No cookies saved."}
    autono = setting_get("104_autono", "")
    if not autono:
        return {"valid": False, "message": "autono not set. Check Settings → Account Config."}
    headers = _build_headers(cookie_str)
    params  = {"contactPrivacy": "0", "kws": "test", "autono": autono,
               "ec": setting_get("104_ec", ""), "sortType": "RANK",
               "readStatus": "all", "page": 1}
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(SEARCH_URL, headers=headers, params=params)
        if r.status_code == 200:
            d = r.json()
            if d.get("status") == "SUCCESS":
                return {"valid": True, "message": "Connected successfully."}
            return {"valid": False, "message": f"API returned: {d.get('status')} — cookies may have expired."}
        elif r.status_code in (401, 403):
            return {"valid": False, "message": f"Auth failed ({r.status_code}). Refresh cookies."}
        else:
            return {"valid": False, "message": f"HTTP {r.status_code}"}
    except Exception as e:
        return {"valid": False, "message": f"Request error: {str(e)}"}


# ── Candidate search ──────────────────────────────────────────────────────────

@router.get("/candidates")
async def search_candidates(
    keyword:      str = Query(""),
    work_exp_min: str = Query(""),   # e.g. "5"
    age_min:      str = Query(""),
    age_max:      str = Query(""),
    sex:          str = Query(""),   # "" = all, "1" = female, "2" = male
    emp_status:   str = Query("0"),  # 0 = all
    update_date:  str = Query("1"),  # 1 = any date
    sort_type:    str = Query("RANK"),
    read_status:  str = Query("all"),
    page:         int = Query(1),
):
    if setting_get("demo_mode", "0") == "1":
        return _demo_search(keyword, page)

    cookie_str = setting_get("104_cookies", "")
    if not cookie_str:
        raise HTTPException(400, "No cookies saved.")
    autono = setting_get("104_autono", "")
    if not autono:
        raise HTTPException(400, "autono not set. Go to Settings → Account Config.")

    params: dict = {
        "contactPrivacy":    "0",
        "empStatus":         emp_status,
        "updateDateType":    update_date,
        "sortType":          sort_type,
        "readStatus":        read_status,
        "plastActionDateType": "1",
        "autono":            autono,
        "ec":                setting_get("104_ec", ""),
        "page":              page,
    }
    if keyword:      params["kws"]             = keyword
    if work_exp_min: params["workExpTimeType"]  = "up"; params["workExpTimeMin"] = work_exp_min
    if age_min:      params["agemin"]           = age_min
    if age_max:      params["agemax"]           = age_max
    if sex:          params["sex"]              = sex

    headers = _build_headers(cookie_str)
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            r = await client.get(SEARCH_URL, headers=headers, params=params)
        r.raise_for_status()
        data = r.json()
        if data.get("status") != "SUCCESS":
            raise HTTPException(400, f"104 returned status: {data.get('status')} — {data.get('message','')}")

        raw_list   = data.get("result", {}).get("data", [])
        total      = _extract_total(raw_list)
        total_pages = max(1, -(-total // RESULTS_PER_PAGE)) if total else 1

        return {
            "ok":          True,
            "candidates":  [_normalise(c) for c in raw_list],
            "totalCount":  total,
            "totalPages":  total_pages,
            "currentPage": page,
        }
    except httpx.HTTPStatusError as e:
        raise HTTPException(e.response.status_code, f"104 API error: {e.response.text[:300]}")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"Request failed: {str(e)}")


# ── Candidate detail (full resume) ────────────────────────────────────────────
# Confirmed endpoint: https://auth.vip.104.com.tw/vipapi/resume/search/{idNo}?path_for_log=idlist_search

FULL_PROFILE_URL = "https://auth.vip.104.com.tw/vipapi/resume/search/{idno}?path_for_log=idlist_search"

@router.get("/candidates/{resume_id}/detail")
async def get_candidate_detail(resume_id: str, master_url: str = Query("")):
    if setting_get("demo_mode", "0") == "1":
        return {"ok": True, "demo": True, "message": "Full resume not available in demo mode."}

    cookie_str = setting_get("104_cookies", "")
    if not cookie_str:
        raise HTTPException(400, "No cookies saved.")

    url = FULL_PROFILE_URL.format(idno=resume_id)
    headers = _build_headers(cookie_str)
    headers["Referer"] = REFERER

    try:
        async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
            r = await client.get(url, headers=headers)
        r.raise_for_status()
        return {"ok": True, "raw": r.json()}
    except httpx.HTTPStatusError as e:
        raise HTTPException(e.response.status_code, f"Detail fetch error: {e.response.text[:300]}")
    except Exception as e:
        raise HTTPException(500, f"Request failed: {str(e)}")


# ── Area codes reference ──────────────────────────────────────────────────────

AREA_CODES = {
    "台北市":  "6001001000", "新北市": "6001002000", "基隆市": "6001003000",
    "桃園市":  "6001005000", "新竹縣市":"6001006000", "台中市": "6001008000",
    "彰化縣":  "6001010000", "台南市": "6001014000", "高雄市": "6001016000",
}

@router.get("/areas")
def get_areas():
    return AREA_CODES
