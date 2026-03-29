import os
import urllib.request

# 이미지가 저장될 기준 폴더 경로
save_dir = "my_photos"

# 폴더가 없으면 생성
os.makedirs(save_dir, exist_ok=True)

# 생성할 샘플 데이터 구성
# 형식: (연월일, 이벤트번호, [순번 리스트], 배경색, 글자색)
samples = [
    # 2023년 10월 25일 (사진 3장)
    ("20260311", "01", ["001", "002", "003"], "FF5733", "FFFFFF"),
    # 2023년 11월 05일 (사진 2장)
    ("20260312", "01", ["001", "002"], "33FF57", "000000"),
]

print(f"[{save_dir}] 폴더에 샘플 이미지 생성을 시작합니다...\n")

for date, event, seqs, bg, fg in samples:
    for seq in seqs:
        # 파일명 규칙: gstb-{연월일}-{이벤트번호}-###.jpg
        filename = f"gstb-{date}-{event}-{seq}.jpg"
        filepath = os.path.join(save_dir, filename)

        # 이미지에 표시될 텍스트 (URL에 맞게 공백을 +로 치환)
        display_text = f"{date[:4]}-{date[4:6]}-{date[6:]}+/+{seq}"

        # dummyimage.com API를 사용하여 이미지 생성
        url = f"https://dummyimage.com/800x500/{bg}/{fg}&text={display_text}"

        try:
            urllib.request.urlretrieve(url, filepath)
            print(f"✅ 생성 완료: {filename}")
        except Exception as e:
            print(f"❌ 생성 실패: {filename} ({e})")

print("\n🎉 모든 샘플 이미지 생성이 완료되었습니다!")
print("이제 백엔드 서버를 실행하고 프론트엔드 페이지를 확인해 보세요.")
