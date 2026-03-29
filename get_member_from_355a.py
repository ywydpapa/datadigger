import os
import re
import csv
import time
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse, parse_qs, urlencode
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

START_URL = "http://lc355a.or.kr/bbs/content.php?co_id=ready01"
LOGIN_URL = "http://lc355a.or.kr/bbs/login.php"
PHOTO_DIR = "355a_member_photos"
CSV_FILE = "355a_members.csv"
USERNAME = "김동진"
PASSWORD = "4290642"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/146.0 Safari/537.36"
    ),
    "Referer": START_URL,
}


def clean_text(text):
    if text is None:
        return ""
    text = text.replace("\xa0", " ")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def sanitize_filename(name):
    name = clean_text(name)
    name = re.sub(r'[\\/:*?"<>|]', "_", name)
    return name


def create_driver():
    options = webdriver.ChromeOptions()
    options.add_argument("--start-maximized")
    options.add_argument("--disable-blink-features=AutomationControlled")
    return webdriver.Chrome(options=options)


def transfer_cookies_to_session(driver, session):
    for cookie in driver.get_cookies():
        session.cookies.set(
            cookie["name"],
            cookie["value"],
            domain=cookie.get("domain"),
            path=cookie.get("path", "/"),
        )


def login(driver):
    driver.get(LOGIN_URL)
    wait = WebDriverWait(driver, 15)
    try:
        user_input = wait.until(EC.presence_of_element_located((By.ID, "login_id")))
        pw_input = wait.until(EC.presence_of_element_located((By.ID, "login_pw")))
    except TimeoutException:
        print("로그인 폼을 찾지 못했습니다. 사이트 구조가 변경되었을 가능성이 있습니다.")
        return False
    user_input.clear()
    user_input.send_keys(USERNAME)
    pw_input.clear()
    pw_input.send_keys(PASSWORD)
    clicked = False
    submit_selectors = [
        "button[type='submit']",
        "input[type='submit']",
        "button.btn_submit",
        "input.btn_submit",
        "button",
    ]
    for selector in submit_selectors:
        try:
            elements = driver.find_elements(By.CSS_SELECTOR, selector)
            for element in elements:
                text = clean_text(element.text or element.get_attribute("value") or "")
                if not text or any(keyword in text for keyword in ["로그인", "LOGIN", "확인"]):
                    element.click()
                    clicked = True
                    break
            if clicked:
                break
        except Exception:
            pass
    if not clicked:
        try:
            pw_input.send_keys(Keys.ENTER)
            clicked = True
        except Exception:
            pass
    if not clicked:
        print("로그인 제출을 수행하지 못했습니다.")
        return False
    try:
        wait.until(lambda d: "로그아웃" in d.page_source or "logout" in d.page_source.lower())
        print("로그인 완료.")
        driver.get(START_URL)
        return True
    except TimeoutException:
        print("로그인 실패 또는 로그인 완료 확인 불가.")
        return False


def build_page_url(start_url, page_no, club_id):
    parsed = urlparse(start_url)
    qs = parse_qs(parsed.query)
    qs["page"] = [str(page_no)]
    qs["club_sch"] = [str(club_id)]  # 전달받은 클럽 ID 적용
    new_query = urlencode(qs, doseq=True)
    return parsed._replace(query=new_query).geturl()


def parse_member_row(row, club_name):
    cols = row.find_all("td")
    if len(cols) < 7:
        return None
    name_cell = cols[1]
    detail_link = name_cell.find("a")
    member_no = ""
    detail_url = ""
    if detail_link and detail_link.get("href"):
        href = detail_link.get("href")
        detail_url = urljoin(START_URL, href)
        parsed_url = urlparse(detail_url)
        query_params = parse_qs(parsed_url.query)
        if "mb_no" in query_params:
            member_no = query_params["mb_no"][0]
        elif "wr_id" in query_params:
            member_no = query_params["wr_id"][0]
    member = {
        "클럽명": club_name,  # 동적으로 전달받은 클럽명 적용
        "성명": clean_text(name_cell.get_text()),
        "직장": clean_text(cols[2].get_text()),
        "직위": clean_text(cols[3].get_text()),
        "주소": clean_text(cols[4].get_text()),
        "휴대폰번호": clean_text(cols[5].get_text()),
        "자택전화": clean_text(cols[6].get_text()),
        "회원번호": member_no,
        "사진URL": detail_url,
    }
    return member

def extract_image_url_from_member_page(session, detail_url):
    if not detail_url:
        return ""
    try:
        r = session.get(detail_url, headers=HEADERS, timeout=30)
        r.raise_for_status()
        if not r.encoding or r.encoding.lower() == "iso-8859-1":
            r.encoding = r.apparent_encoding
        soup = BeautifulSoup(r.text, "html.parser")
        exclude_words = ['logo', 'icon', 'btn', 'button', 'no_img', 'no_profile', 'blank', 'default', 'bg_', 'title',
                         'common']
        image_candidates = []
        target_areas = soup.select("#bo_v_atc, #bo_v_img, #bo_v_con, .profile-image, .member-img, td img")
        for area in target_areas:
            for img in area.select("img[src]"):
                src = img.get("src", "").strip()
                if not src: continue
                lower_src = src.lower()
                if any(word in lower_src for word in exclude_words):
                    continue
                abs_url = urljoin(detail_url, src)
                image_candidates.append(abs_url)
        if not image_candidates:
            for img in soup.select("img[src]"):
                src = img.get("src", "").strip()
                if not src: continue
                lower_src = src.lower()
                if any(word in lower_src for word in exclude_words):
                    continue
                if any(ext in lower_src for ext in [".jpg", ".jpeg", ".png", ".gif", "/data/file/", "thumb-"]):
                    abs_url = urljoin(detail_url, src)
                    image_candidates.append(abs_url)
        return image_candidates[0] if image_candidates else ""
    except Exception as e:
        print(f"    상세 페이지 이미지 추출 실패: {detail_url} / {e}")
        return ""


def download_image(url, member, session, referer_url):
    if not url:
        return ""
    headers = HEADERS.copy()
    if referer_url:
        headers["Referer"] = referer_url
    try:
        r = session.get(url, headers=headers, timeout=30)
        r.raise_for_status()
        content_type = r.headers.get("Content-Type", "").lower()
        if "jpeg" in content_type or "jpg" in content_type:
            ext = ".jpg"
        elif "png" in content_type:
            ext = ".png"
        elif "gif" in content_type:
            ext = ".gif"
        else:
            parsed_path = urlparse(r.url).path.lower()
            if parsed_path.endswith(".png"):
                ext = ".png"
            elif parsed_path.endswith(".gif"):
                ext = ".gif"
            elif parsed_path.endswith(".jpeg"):
                ext = ".jpeg"
            else:
                ext = ".jpg"
        club_name = sanitize_filename(member.get("클럽명", ""))
        name = sanitize_filename(member.get("성명", ""))
        member_no = sanitize_filename(member.get("회원번호", ""))
        if member_no:
            file_name = f"{club_name}_{name}_{member_no}{ext}"
        else:
            file_name = f"{club_name}_{name}{ext}"
        save_path = os.path.join(PHOTO_DIR, file_name)
        with open(save_path, "wb") as f:
            f.write(r.content)
        return file_name
    except Exception as e:
        print(f"    사진 다운로드 실패: {member.get('성명')} / {url} / {e}")
        return ""


def main():
    os.makedirs(PHOTO_DIR, exist_ok=True)
    driver = create_driver()
    session = requests.Session()
    try:
        if not login(driver):
            return
        transfer_cookies_to_session(driver, session)
        print("클럽 목록을 가져오는 중...")
        driver.get(START_URL)
        WebDriverWait(driver, 15).until(EC.presence_of_element_located((By.ID, "club_sch")))
        soup = BeautifulSoup(driver.page_source, "html.parser")
        select_element = soup.find("select", {"id": "club_sch"})
        clubs = []
        if select_element:
            for option in select_element.find_all("option"):
                val = option.get("value", "").strip()
                name = clean_text(option.text)
                # value 값이 있는 경우만 (전체클럽 제외)
                if val:
                    clubs.append({"id": val, "name": name})
        print(f"총 {len(clubs)}개의 클럽을 발견했습니다. 데이터 수집을 시작합니다.\n")
        rows = []
        total_members_all_clubs = 0
        for club in clubs:
            club_id = club["id"]
            club_name = club["name"]
            print(f"==================================")
            print(f"▶ [{club_name}] 데이터 수집 시작 (고유번호: {club_id})")
            page_no = 1
            club_members_count = 0
            while True:
                page_url = build_page_url(START_URL, page_no, club_id)
                print(f"  [페이지 {page_no}] {page_url}")
                try:
                    driver.get(page_url)
                    WebDriverWait(driver, 15).until(EC.presence_of_element_located((By.CSS_SELECTOR, "table tr")))
                    soup = BeautifulSoup(driver.page_source, "html.parser")
                    member_rows = soup.select("table tr")
                    data_rows = member_rows[1:] if len(member_rows) > 1 else []
                    if len(data_rows) == 0:
                        print("    더 이상 데이터가 없습니다.")
                        break
                    for idx, row in enumerate(data_rows, start=1):
                        member = parse_member_row(row, club_name)
                        if not member:
                            continue
                        image_url = extract_image_url_from_member_page(session, member["사진URL"])
                        photo_file = download_image(image_url, member, session, member["사진URL"]) if image_url else ""
                        member["사진URL"] = image_url
                        member["사진파일명"] = photo_file
                        rows.append(member)
                        print(f"      {idx}. {member['성명']} / {member['회원번호']} / {member['직위']}")
                        time.sleep(0.05)
                    club_members_count += len(data_rows)
                    if len(data_rows) < 20:
                        print(f"    마지막 페이지로 인식됨 (현재 클럽 수집 인원: {club_members_count}명)")
                        break
                    page_no += 1
                except TimeoutException:
                    print("    페이지 로딩 시간 초과. 다음 클럽으로 넘어갑니다.")
                    break
                except Exception as e:
                    print(f"    페이지 처리 실패: {e}")
                    break
                time.sleep(0.2)
            total_members_all_clubs += club_members_count
            print(f"▶ [{club_name}] 수집 완료\n")
        with open(CSV_FILE, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(
                f,
                fieldnames=[
                    "클럽명",
                    "성명",
                    "직장",
                    "직위",
                    "주소",
                    "휴대폰번호",
                    "자택전화",
                    "회원번호",
                    "사진파일명",
                    "사진URL",
                ],
            )
            writer.writeheader()
            writer.writerows(rows)
        print("\n==================================")
        print(f"전체 수집 완료: 총 {len(clubs)}개 클럽, {total_members_all_clubs}명의 데이터를 수집했습니다.")
        print(f"- CSV: {CSV_FILE}")
        print(f"- 사진폴더: {PHOTO_DIR}")
        print("==================================")
    finally:
        driver.quit()

if __name__ == "__main__":
    main()
