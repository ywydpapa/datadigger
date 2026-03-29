import os
import re
import csv
import time
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse, parse_qs, urlencode

START_URL = "http://lc355a.or.kr/bbs/board.php?bo_table=executive&sca=%EB%AA%85%EC%98%88%EC%9C%84%EC%9B%90%EC%9E%A5"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0 Safari/537.36"
}

PHOTO_DIR = "my_photos"
CSV_FILE = "my_list.csv"

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

def get_html(url, session):
    r = session.get(url, headers=HEADERS, timeout=20)
    r.raise_for_status()
    if not r.encoding or r.encoding.lower() == "iso-8859-1":
        r.encoding = r.apparent_encoding
    return r.text

def get_total_pages(soup, current_url):
    pages = [1]
    for a in soup.select("nav.pg_wrap a[href]"):
        href = urljoin(current_url, a.get("href"))
        qs = parse_qs(urlparse(href).query)
        if "page" in qs:
            try:
                pages.append(int(qs["page"][0]))
            except:
                pass
    return max(pages) if pages else 1

def build_page_url(start_url, page_no):
    parsed = urlparse(start_url)
    qs = parse_qs(parsed.query)
    qs["page"] = [str(page_no)]
    new_query = urlencode(qs, doseq=True)
    return parsed._replace(query=new_query).geturl()

def parse_person_box(box, page_url):
    result = {
        "성명": "",
        "소속": "",
        "비고": "",
        "사진URL": "",
        "페이지URL": page_url
    }

    img = box.select_one("div.img img")
    if img and img.get("src"):
        result["사진URL"] = urljoin(page_url, img.get("src"))

    info_dl = box.select_one("dl.info")
    if info_dl:
        dts = info_dl.find_all("dt")
        dds = info_dl.find_all("dd")
        for dt, dd in zip(dts, dds):
            key = clean_text(dt.get_text())
            val = clean_text(dd.get_text())
            if key in ["성명", "소속", "비고"]:
                result[key] = val

    return result

def unique_photo_path(base_name, ext=".jpg"):
    base_name = sanitize_filename(base_name)
    path = os.path.join(PHOTO_DIR, f"{base_name}{ext}")
    if not os.path.exists(path):
        return path

    idx = 2
    while True:
        path = os.path.join(PHOTO_DIR, f"{base_name}_{idx}{ext}")
        if not os.path.exists(path):
            return path
        idx += 1

def download_image(url, name, session):
    if not url:
        return ""

    # 기본 no image는 건너뜀
    if "noimg" in url.lower():
        return ""

    try:
        r = session.get(url, headers=HEADERS, timeout=30)
        r.raise_for_status()

        content_type = r.headers.get("Content-Type", "").lower()
        if "jpeg" in content_type or "jpg" in content_type:
            ext = ".jpg"
        elif "png" in content_type:
            ext = ".png"
        elif "gif" in content_type:
            ext = ".gif"
        else:
            parsed_path = urlparse(url).path.lower()
            if parsed_path.endswith(".png"):
                ext = ".png"
            elif parsed_path.endswith(".gif"):
                ext = ".gif"
            else:
                ext = ".jpg"

        save_path = unique_photo_path(name, ext)
        with open(save_path, "wb") as f:
            f.write(r.content)

        return os.path.basename(save_path)

    except Exception as e:
        print(f"    사진 다운로드 실패: {name} / {url} / {e}")
        return ""

def main():
    os.makedirs(PHOTO_DIR, exist_ok=True)

    session = requests.Session()

    print("첫 페이지 확인 중...")
    first_html = get_html(START_URL, session)
    first_soup = BeautifulSoup(first_html, "html.parser")
    total_pages = get_total_pages(first_soup, START_URL)

    print(f"총 페이지 수: {total_pages}")

    rows = []

    for page_no in range(1, total_pages + 1):
        page_url = build_page_url(START_URL, page_no)
        print(f"[페이지 {page_no}/{total_pages}] {page_url}")

        try:
            html = get_html(page_url, session)
            soup = BeautifulSoup(html, "html.parser")

            boxes = soup.select("div.exe_list div.exe_box")
            print(f"  발견 인원 수: {len(boxes)}")

            for idx, box in enumerate(boxes, start=1):
                data = parse_person_box(box, page_url)

                photo_file = ""
                if data["성명"] and data["사진URL"]:
                    photo_file = download_image(data["사진URL"], data["성명"], session)

                row = {
                    "성명": data["성명"],
                    "소속": data["소속"],
                    "비고": data["비고"],
                    "사진파일명": photo_file,
                    "사진URL": data["사진URL"],
                    "페이지URL": data["페이지URL"]
                }
                rows.append(row)

                print(f"    {idx}. {data['성명']} / {data['소속']} / {data['비고']}")

                time.sleep(0.1)

        except Exception as e:
            print(f"  페이지 처리 실패: {e}")

        time.sleep(0.3)

    with open(CSV_FILE, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["성명", "소속", "비고", "사진파일명", "사진URL", "페이지URL"]
        )
        writer.writeheader()
        writer.writerows(rows)

    print(f"\n완료:")
    print(f"- CSV: {CSV_FILE}")
    print(f"- 사진폴더: {PHOTO_DIR}")

if __name__ == "__main__":
    main()
