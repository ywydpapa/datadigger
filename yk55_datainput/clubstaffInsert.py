import asyncio
import csv
import os
import re
from pathlib import Path
from urllib.parse import quote_plus

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

# 파일 경로 설정
CSV_FILE_PATH = r"C:\Users\djkim\Desktop\data_input.csv"
ENV_FILE_PATH = "../.env"

# 고정 클럽 번호
CLUB_NO = 10


def load_dotenv_file(env_path: str = ENV_FILE_PATH) -> None:
    path = Path(env_path)
    if not path.exists():
        return

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if not key:
            continue
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        os.environ.setdefault(key, value)


def build_database_url() -> str:
    load_dotenv_file()

    db_host = os.getenv("DB_HOST")
    db_port = os.getenv("DB_PORT", "3306")
    db_user = os.getenv("DB_USER")
    db_password = os.getenv("DB_PASSWORD")
    db_name = os.getenv("DB_NAME")
    db_charset = os.getenv("DB_CHARSET", "utf8mb4")

    missing = [
        name for name, value in {
            "DB_HOST": db_host, "DB_USER": db_user,
            "DB_PASSWORD": db_password, "DB_NAME": db_name,
        }.items() if not value
    ]
    if missing:
        raise RuntimeError(f"필수 DB 환경 변수가 누락되었습니다: {', '.join(missing)}")

    encoded_password = quote_plus(db_password)
    return f"mysql+asyncmy://{db_user}:{encoded_password}@{db_host}:{db_port}/{db_name}?charset={db_charset}"


def normalize_fieldnames(fieldnames: list[str] | None) -> list[str]:
    if not fieldnames:
        return []
    # 띄어쓰기나 특수문자 등으로 인한 오류를 방지하기 위해 공백을 모두 제거하여 키값으로 사용
    return [name.strip().lstrip("\ufeff").replace(" ", "") if name else "" for name in fieldnames]


def open_csv_dict_reader_with_fallback(csv_path: Path):
    encodings_to_try = ["utf-8-sig", "utf-8", "cp949", "euc-kr"]
    last_error = None

    for enc in encodings_to_try:
        try:
            f = csv_path.open("r", encoding=enc, newline="")
            # 탭(\t) 분리 파일일 가능성도 있으므로 쉼표와 탭 모두 확인
            sample = f.read(1024)
            f.seek(0)
            delimiter = "\t" if "\t" in sample else ","

            reader = csv.DictReader(f, delimiter=delimiter)
            if reader.fieldnames is None:
                f.close()
                raise ValueError("CSV 헤더를 읽을 수 없습니다.")

            reader.fieldnames = normalize_fieldnames(reader.fieldnames)
            print(f"[INFO] CSV 인코딩 성공: {enc}, 구분자: {'TAB' if delimiter == chr(9) else 'COMMA'}")
            return f, reader, enc

        except Exception as e:
            last_error = e

    if last_error:
        raise last_error
    raise RuntimeError("CSV 파일을 읽을 수 없습니다.")


async def get_or_create_member(conn, club_no: int, member_name: str):
    """
    회원 이름으로 yk_members 테이블을 조회하여 memberNo를 반환합니다.
    존재하지 않으면 새로 INSERT 한 후 생성된 memberNo를 반환합니다.
    """
    if not member_name:
        return None

    # 이름 정리 및 'L' 제거
    name = member_name.strip()
    if name.endswith("L") or name.endswith("l"):
        name = name[:-1].strip()

    if not name:
        return None

    # 1. 회원 조회
    result = await conn.execute(
        text("SELECT memberNo FROM yk_members WHERE clubNo = :club_no AND memberName = :name LIMIT 1"),
        {"club_no": club_no, "name": name}
    )
    row = result.fetchone()

    if row:
        return row[0]

    # 2. 회원이 없으면 신규 추가
    insert_result = await conn.execute(
        text("INSERT INTO yk_members (clubNo, memberName) VALUES (:club_no, :name)"),
        {"club_no": club_no, "name": name}
    )
    # 새로 생성된 memberNo 반환
    return insert_result.lastrowid


def calculate_period_no(year_str: str) -> int:
    """
    '초대 (1960~1961)' 형태의 문자열에서 시작 연도를 추출하여 periodNo를 계산합니다.
    1971~1972 가 1이므로, 1971년 미만은 0으로 처리합니다.
    """
    if not year_str:
        return 0

    match = re.search(r'(\d{4})\s*~\s*(\d{4})', year_str)
    if match:
        start_year = int(match.group(1))
        if start_year >= 1971:
            return start_year - 1971 + 1
    return 0


async def main() -> None:
    csv_path = Path(CSV_FILE_PATH)
    if not csv_path.exists():
        raise FileNotFoundError(f"CSV 파일을 찾을 수 없습니다: {csv_path}")

    database_url = build_database_url()
    engine = create_async_engine(database_url, future=True)

    inserted = 0
    errors = 0

    try:
        csv_file, reader, detected_encoding = open_csv_dict_reader_with_fallback(csv_path)

        try:
            async with engine.begin() as conn:
                for idx, row in enumerate(reader, start=2):
                    # 헤더의 공백을 모두 제거했으므로 키값도 공백 없이 접근
                    year_str = row.get("년도별", "")

                    # 각 직책별 이름 가져오기
                    chairman_name = row.get("회장", "")
                    vice1_name = row.get("제1부회장", "")
                    vice2_name = row.get("제2부회장", "")
                    vice3_name = row.get("제3부회장", "")
                    sec_name = row.get("총무", "")
                    tre_name = row.get("재무", "")
                    lion_name = row.get("라이온테마", "")  # 공백 제거된 키
                    tail_name = row.get("테일튀스터", "")  # 공백 제거된 키

                    # periodNo 계산
                    period_no = calculate_period_no(year_str)

                    try:
                        # 각 직책별 memberNo 조회 또는 생성
                        chairman_no = await get_or_create_member(conn, CLUB_NO, chairman_name)
                        vice1_no = await get_or_create_member(conn, CLUB_NO, vice1_name)
                        vice2_no = await get_or_create_member(conn, CLUB_NO, vice2_name)
                        vice3_no = await get_or_create_member(conn, CLUB_NO, vice3_name)
                        sec_no = await get_or_create_member(conn, CLUB_NO, sec_name)
                        tre_no = await get_or_create_member(conn, CLUB_NO, tre_name)
                        lion_no = await get_or_create_member(conn, CLUB_NO, lion_name)
                        tail_no = await get_or_create_member(conn, CLUB_NO, tail_name)

                        # yk_clubStaff 테이블에 INSERT
                        await conn.execute(
                            text(
                                """
                                INSERT INTO yk_clubStaff (periodNo, clubNo, chairmanNo, vice1stNo, vice2ndNo, vice3rdNo,
                                                          secretaryNo, treasureNo, lionsteamerNo, tailtNo)
                                VALUES (:period_no, :club_no, :chairman_no, :vice1_no, :vice2_no, :vice3_no,
                                        :sec_no, :tre_no, :lion_no, :tail_no)
                                """
                            ),
                            {
                                "period_no": period_no,
                                "club_no": CLUB_NO,
                                "chairman_no": chairman_no,
                                "vice1_no": vice1_no,
                                "vice2_no": vice2_no,
                                "vice3_no": vice3_no,
                                "sec_no": sec_no,
                                "tre_no": tre_no,
                                "lion_no": lion_no,
                                "tail_no": tail_no,
                            },
                        )
                        inserted += 1
                        print(f"[INSERT] {idx}행: {year_str} (periodNo: {period_no}) 임원진 데이터 추가 완료")

                    except Exception as e:
                        print(f"[ERROR] {idx}행 처리 중 오류 발생: {e}")
                        errors += 1
        finally:
            csv_file.close()

    finally:
        await engine.dispose()

    print("\n===== 처리 완료 =====")
    print(f"INSERT (임원진 추가): {inserted}건")
    print(f"ERROR (오류): {errors}건")


if __name__ == "__main__":
    asyncio.run(main())
