import csv
import requests
from bs4 import BeautifulSoup

url = "http://lc355a.or.kr/bbs/board.php?bo_table=executive&sca=%EC%B4%9D%EC%9E%AC%EC%83%81%EC%9E%84%EA%B3%A0%EB%AC%B8"
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

response = requests.get(url, headers=headers)
response.encoding = response.apparent_encoding or "utf-8"

soup = BeautifulSoup(response.text, "html.parser")

# 결과 저장용 리스트
data = []

# 게시판의 목록 행 탐색 (해당 사이트 구조에 맞춤)
# 일반적인 그누보드 테이블 또는 갤러리 구조
items = soup.select(".tbl_head01 tbody tr") or soup.select(".gall_ul li") or soup.select("table tbody tr")

for item in items:
    texts = [t.strip() for t in item.stripped_strings if t.strip()]
    if len(texts) >= 2:
        # 텍스트 중 성명, 소속에 해당하는 필드 매핑
        data.append(texts[:2])

# CSV 파일로 저장 (utf-8-sig로 저장하여 엑셀 한글 깨짐 방지)
output_path = "executive_list.csv"
with open(output_path, "w", encoding="utf-8-sig", newline="") as f:
    writer = csv.writer(f)
    writer.writerow(["성명", "소속"])
    writer.writerows(data)

print(f"총 {len(data)}건 저장 완료: {output_path}")