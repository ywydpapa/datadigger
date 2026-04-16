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

# 고정 직급 번호 (rankNo)
RANK_NO = 5


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
    return [name.strip().lstrip("\ufeff").replace(" ", "") if name else "" for name in fieldnames]


def open_csv_dict_reader_with_fallback(csv_path: Path):
    encodings_to_try = ["utf-8-sig", "utf-8", "cp949", "euc-kr"]
    last_error = None
    for enc in encodings_to_try:
        try:
            f = csv_path.open("r", encoding=enc, newline="")
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


def calculate_period_no(year_str: str) -> int:
    if not year_str:
        return 0
    match = re.search(r'(\d{4})\s*~\s*(\d{4})', year_str)
    if match:
        start_year = int(match.group(1))
        if start_year >= 1971:
            return start_year - 1971 + 1
    return 0


async def get_club(conn, club_name: str):
    if not club_name:
        return None
    name = club_name.strip()
    result = await conn.execute(
        text("SELECT clubNo FROM yk_club WHERE clubName = :name LIMIT 1"),
        {"name": name}
    )
    row = result.fetchone()
    if row:
        return row[0]
    return None


async def get_or_create_member(conn, club_no: int, member_name: str):
    if not member_name or not club_no:
        return None
    name = member_name.strip()
    if name.endswith("L") or name.endswith("l"):
        name = name[:-1].strip()
    if not name:
        return None
    result = await conn.execute(
        text("SELECT memberNo FROM yk_members WHERE clubNo = :club_no AND memberName = :name LIMIT 1"),
        {"club_no": club_no, "name": name}
    )
    row = result.fetchone()
    if row:
        return row[0]
    insert_result = await conn.execute(
        text("INSERT INTO yk_members (clubNo, memberName) VALUES (:club_no, :name)"),
        {"club_no": club_no, "name": name}
    )
    return insert_result.lastrowid


async def main() -> None:
    csv_path = Path(CSV_FILE_PATH)
    if not csv_path.exists():
        raise FileNotFoundError(f"CSV 파일을 찾을 수 없습니다: {csv_path}")
    database_url = build_database_url()
    engine = create_async_engine(database_url, future=True)
    inserted = 0
    updated = 0
    skipped = 0
    errors = 0
    try:
        csv_file, reader, detected_encoding = open_csv_dict_reader_with_fallback(csv_path)
        try:
            async with engine.begin() as conn:
                for idx, row in enumerate(reader, start=2):
                    role_str = row.get("직책", "")
                    period_str = row.get("임기", "")
                    member_name = row.get("성명", "")
                    club_name = row.get("소속", "")
                    period_no = calculate_period_no(period_str)
                    try:
                        club_no = await get_club(conn, club_name)
                        if club_no is None:
                            print(f"[SKIP] {idx}행: '{club_name}' 클럽이 존재하지 않아 건너뜁니다.")
                            skipped += 1
                            continue
                        member_no = await get_or_create_member(conn, club_no, member_name)

                        # 이미 같은 데이터(periodNo, rankNo 기준)가 있는지 확인
                        check_result = await conn.execute(
                            text(
                                "SELECT dstaffNo FROM yk_distStaff WHERE periodNo = :period_no AND rankNo = :rank_no LIMIT 1"),
                            {"period_no": period_no, "rank_no": RANK_NO}
                        )
                        existing_row = check_result.fetchone()
                        if existing_row:
                            dist_staff_no = existing_row[0]
                            await conn.execute(
                                text(
                                    """
                                    UPDATE yk_distStaff
                                    SET clubNo   = :club_no,
                                        memberNo = :member_no,
                                        memo1    = :memo1
                                    WHERE dstaffNo = :dist_staff_no
                                    """
                                ),
                                {
                                    "club_no": club_no,
                                    "member_no": member_no,
                                    "memo1": role_str,
                                    "dist_staff_no": dist_staff_no
                                }
                            )
                            updated += 1
                            print(f"[UPDATE] {idx}행: {period_str} (periodNo: {period_no}) 데이터 업데이트 완료")
                        else:
                            await conn.execute(
                                text(
                                    """
                                    INSERT INTO yk_distStaff (periodNo, clubNo, rankNo, memberNo, memo1)
                                    VALUES (:period_no, :club_no, :rank_no, :member_no, :memo1)
                                    """
                                ),
                                {
                                    "period_no": period_no,
                                    "club_no": club_no,
                                    "rank_no": RANK_NO,
                                    "member_no": member_no,
                                    "memo1": role_str
                                }
                            )
                            inserted += 1
                            print(f"[INSERT] {idx}행: {period_str} (periodNo: {period_no}) 데이터 추가 완료")
                    except Exception as e:
                        print(f"[ERROR] {idx}행 처리 중 오류 발생: {e}")
                        errors += 1
        finally:
            csv_file.close()

    finally:
        await engine.dispose()

    print("\n===== 처리 완료 =====")
    print(f"INSERT (신규 추가): {inserted}건")
    print(f"UPDATE (기존 수정): {updated}건")
    print(f"SKIP (클럽 없음): {skipped}건")
    print(f"ERROR (오류): {errors}건")


if __name__ == "__main__":
    asyncio.run(main())
