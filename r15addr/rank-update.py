import asyncio
import csv
import os
from pathlib import Path
from urllib.parse import quote_plus

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

# ==========================================
# 설정
# ==========================================
CSV_FILE_PATH = "C:\\Users\\djkim\\Desktop\\data_input.csv"  # 실제 CSV 파일 경로
ENV_FILE_PATH = "./.env"
TARGET_RANK_NO = 16


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
        name
        for name, value in {
            "DB_HOST": db_host,
            "DB_USER": db_user,
            "DB_PASSWORD": db_password,
            "DB_NAME": db_name,
        }.items()
        if not value
    ]
    if missing:
        raise RuntimeError(
            "필수 DB 환경 변수가 누락되었습니다: "
            + ", ".join(missing)
            + ". .env 파일 또는 환경 변수를 확인하세요."
        )

    encoded_password = quote_plus(db_password)
    return (
        f"mysql+asyncmy://{db_user}:{encoded_password}@{db_host}:{db_port}/{db_name}"
        f"?charset={db_charset}"
    )


def normalize_fieldnames(fieldnames: list[str] | None) -> list[str]:
    if not fieldnames:
        return []
    return [name.strip().lstrip("\ufeff") if name else "" for name in fieldnames]


def open_csv_dict_reader_with_fallback(csv_path: Path):
    encodings_to_try = ["utf-8-sig", "cp949", "euc-kr", "utf-8"]
    last_error = None

    for enc in encodings_to_try:
        try:
            f = csv_path.open("r", encoding=enc, newline="")
            reader = csv.DictReader(f)

            if reader.fieldnames is None:
                f.close()
                raise ValueError("CSV 헤더를 읽을 수 없습니다.")

            reader.fieldnames = normalize_fieldnames(reader.fieldnames)

            has_name = any(col in reader.fieldnames for col in ["성명", "회원명", "이름"])
            has_club = any(col in reader.fieldnames for col in ["소속", "클럽명", "클럽"])

            if not has_name or not has_club:
                f.close()
                raise ValueError(
                    f"필수 컬럼('성명', '소속')이 없습니다. 현재 컬럼: {reader.fieldnames}"
                )

            print(f"[INFO] CSV 인코딩 확인 성공: {enc}")
            return f, reader, enc

        except UnicodeDecodeError as e:
            last_error = e
        except ValueError:
            raise
        except Exception as e:
            last_error = e

    if last_error:
        raise last_error
    raise RuntimeError("CSV 파일을 읽을 수 없습니다.")


async def main() -> None:
    csv_path = Path(CSV_FILE_PATH)
    if not csv_path.exists():
        raise FileNotFoundError(f"CSV 파일을 찾을 수 없습니다: {csv_path}")

    database_url = build_database_url()
    engine = create_async_engine(database_url, future=True)

    updated_count = 0
    not_found_club = 0
    not_found_member = 0
    skipped_count = 0
    error_count = 0

    try:
        csv_file, reader, detected_encoding = open_csv_dict_reader_with_fallback(csv_path)
        print(f"[INFO] 사용 인코딩: {detected_encoding}\n")
        print(f"{'행':<4} | {'클럽명(변환)':<15} | {'성명':<6} | {'회원번호':<8} | {'결과'}")
        print("-" * 65)

        try:
            async with engine.begin() as conn:
                for idx, row in enumerate(reader, start=2):
                    member_name = (row.get("성명") or row.get("회원명") or row.get("이름") or "").strip()
                    club_raw = (row.get("소속") or row.get("클럽명") or row.get("클럽") or "").strip()

                    # 이름 끝 'L' 또는 'l' 제거
                    if member_name.endswith("L") or member_name.endswith("l"):
                        member_name = member_name[:-1].strip()

                    if not member_name or not club_raw:
                        print(f"[{idx:>2}행] 성명 또는 소속 데이터 누락으로 건너뜀")
                        skipped_count += 1
                        continue

                    # 소속 끝에 '클럽'이 없으면 붙여줌 (예: '서면' -> '서면클럽')
                    target_club_name = club_raw if club_raw.endswith("클럽") else f"{club_raw}클럽"

                    try:
                        # 1. lionsClub 테이블에서 clubNo 조회
                        club_query = text(
                            """
                            SELECT clubNo, clubName
                            FROM lionsClub
                            WHERE clubName = :club_name OR clubName = :raw_name
                            LIMIT 1
                            """
                        )
                        club_res = await conn.execute(
                            club_query,
                            {"club_name": target_club_name, "raw_name": club_raw},
                        )
                        club_row = club_res.mappings().fetchone()

                        if not club_row:
                            print(f"[{idx:>2}행] {target_club_name:<15} | {member_name:<6} | {'-':<8} | [클럽 미발견]")
                            not_found_club += 1
                            continue

                        club_no = club_row["clubNo"]

                        # 2. lionsMember 테이블에서 clubNo와 memberName으로 memberNo 조회
                        member_query = text(
                            """
                            SELECT memberNo, memberName, rankNo
                            FROM lionsMember
                            WHERE clubNo = :club_no AND memberName = :member_name
                            LIMIT 1
                            """
                        )
                        mem_res = await conn.execute(
                            member_query,
                            {"club_no": club_no, "member_name": member_name},
                        )
                        member_row = mem_res.mappings().fetchone()

                        if not member_row:
                            print(f"[{idx:>2}행] {target_club_name:<15} | {member_name:<6} | {'-':<8} | [회원 미발견(클럽내 없음)]")
                            not_found_member += 1
                            continue

                        member_no = member_row["memberNo"]
                        old_rank = member_row["rankNo"]

                        # 3. rankNo = 34 로 업데이트
                        update_query = text(
                            """
                            UPDATE lionsMember
                            SET rankNo = :target_rank
                            WHERE memberNo = :member_no
                            """
                        )
                        await conn.execute(
                            update_query,
                            {"target_rank": TARGET_RANK_NO, "member_no": member_no},
                        )

                        updated_count += 1
                        print(f"[{idx:>2}행] {target_club_name:<15} | {member_name:<6} | {member_no:<8} | [업데이트 완료: rank {old_rank}->{TARGET_RANK_NO}]")

                    except Exception as e:
                        print(f"[{idx:>2}행] {member_name} 처리 중 에러: {e}")
                        error_count += 1

        finally:
            csv_file.close()

    finally:
        await engine.dispose()

    print("\n" + "=" * 45)
    print(f"rankNo 업데이트 완료: {updated_count}건")
    print(f"클럽정보 미발견: {not_found_club}건")
    print(f"회원정보 미발견: {not_found_member}건")
    print(f"데이터 누락 건너뜀: {skipped_count}건")
    if error_count > 0:
        print(f"DB 오류 발생: {error_count}건")
    print("=" * 45)


if __name__ == "__main__":
    asyncio.run(main())