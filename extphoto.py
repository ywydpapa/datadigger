import os
import pymysql
from dotenv import load_dotenv

# 1. .env 파일 로드
load_dotenv()

# 2. 저장할 디렉토리 생성 (현재 폴더 내 'photos' 폴더)
SAVE_DIR = "./r15_photos"
if not os.path.exists(SAVE_DIR):
    os.makedirs(SAVE_DIR)

def extract_and_save_photos():
    # 3. DB 연결 설정
    try:
        connection = pymysql.connect(
            host=os.getenv("DB_HOST"),
            port=int(os.getenv("DB_PORT", 3306)),
            user=os.getenv("DB_USER"),
            password=os.getenv("DB_PASSWORD"),
            database=os.getenv("DB_NAME"),
            charset=os.getenv("DB_CHARSET", "utf8mb4")
        )
        print("✅ DB 연결 성공!")
    except Exception as e:
        print(f"❌ DB 연결 실패: {e}")
        return

    try:
        with connection.cursor() as cursor:
            # 4. memberNo와 mPhoto 데이터 가져오기 (사진이 있는 데이터만)
            sql = "SELECT memberNo, mPhoto FROM memberPhoto WHERE mPhoto IS NOT NULL"
            cursor.execute(sql)
            results = cursor.fetchall()

            print(f"총 {len(results)}개의 사진 데이터를 찾았습니다. 저장을 시작합니다...")

            success_count = 0
            for row in results:
                member_no = row[0]
                photo_data = row[1]

                # 데이터가 비어있지 않은 경우에만 파일로 저장
                if photo_data:
                    file_name = f"mphoto_{member_no}.png"
                    file_path = os.path.join(SAVE_DIR, file_name)

                    try:
                        # 💡 mPhoto가 BLOB(바이너리) 타입인 경우 바로 파일로 씁니다.
                        # 만약 DB에 Base64 문자열로 저장되어 있다면 디코딩 과정이 필요할 수 있습니다.
                        with open(file_path, "wb") as f:
                            f.write(photo_data)
                        success_count += 1
                        print(f"저장 완료: {file_name}")
                    except Exception as e:
                        print(f"저장 실패 ({member_no}): {e}")

            print(f"🎉 작업 완료! 총 {success_count}개의 이미지가 '{SAVE_DIR}' 폴더에 저장되었습니다.")

    finally:
        connection.close()

if __name__ == "__main__":
    extract_and_save_photos()
