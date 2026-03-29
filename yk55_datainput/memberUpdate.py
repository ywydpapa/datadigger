import asyncio
import csv
import os
import re  # 숫자 추출을 위한 정규표현식 모듈 추가
from pathlib import Path
from urllib.parse import quote_plus

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

# 파일 경로 설정
CSV_FILE_PATH = "C:\\Users\\djkim\\Desktop\\data_input.csv"
ENV_FILE_PATH = "../.env"

# 고정 클럽 번호
CLUB_NO = 8


def load_dotenv_file(env_path: str = ENV_FILE_PATH) -> None:
    path = Path(env_path)
    if not path.exists():
        return

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()

        if not line or line.startswith("#"):
            continue

        if "=" not in line:
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
    normalized = []
    for name in fieldnames:
        if name is None:
            normalized.append("")
        else:
            normalized.append(name.strip().lstrip("\ufeff"))
    return normalized


def open_csv_dict_reader_with_fallback(csv_path: Path):
    encodings_to_try = ["utf-8-sig", "utf-8", "cp949", "euc-kr"]
    last_error = None

    for enc in encodings_to_try:
        try:
            f = csv_path.open("r", encoding=enc, newline="")
            reader = csv.DictReader(f)

            if reader.fieldnames is None:
                f.close()
                raise ValueError("CSV 헤더를 읽을 수 없습니다.")

            reader.fieldnames = normalize_fieldnames(reader.fieldnames)

            # 성명(또는 회원명), 입회 일자(또는 입회일자) 컬럼이 있는지 확인
            has_name = any(col in reader.fieldnames for col in ["성명", "회원명"])
            has_date = any(col in reader.fieldnames for col in ["입회 일자", "입회일자"])

            if not has_name or not has_date:
                f.close()
                raise ValueError(
                    f"필수 컬럼('성명' 또는 '회원명', '입회 일자' 또는 '입회일자')이 없습니다. "
                    f"현재 컬럼: {reader.fieldnames}"
                )

            print(f"[INFO] CSV 인코딩 성공: {enc}")
            return f, reader, enc

        except UnicodeDecodeError as e:
            last_error = e
            print(f"[WARN] CSV 인코딩 실패: {enc} -> {e}")
        except ValueError:
            raise
        except Exception as e:
            last_error = e
            print(f"[WARN] CSV 읽기 실패: {enc} -> {e}")

    if last_error:
        raise last_error
    raise RuntimeError("CSV 파일을 읽을 수 없습니다.")


def format_date(date_str: str) -> str:
    """
    다양한 형태의 날짜 문자열을 'YYYY-MM-DD' 형태로 변환합니다.
    연, 월만 있는 경우 해당 월의 1일로 자동 설정합니다.
    """
    if not date_str:
        return None

    # 정규표현식을 사용하여 문자열에서 숫자 덩어리만 추출
    # 예: "1982. 12." -> ['1982', '12']
    # 예: "1988-02" -> ['1988', '02']
    numbers = re.findall(r'\d+', date_str)

    try:
        if len(numbers) >= 3:
            # 연, 월, 일 모두 존재하는 경우
            return f"{numbers[0]}-{int(numbers[1]):02d}-{int(numbers[2]):02d}"
        elif len(numbers) == 2:
            # 연, 월만 존재하는 경우 -> 무조건 1일로 설정
            return f"{numbers[0]}-{int(numbers[1]):02d}-01"
        elif len(numbers) == 1 and len(numbers[0]) == 8:
            # "19821201" 처럼 붙어있는 경우
            return f"{numbers[0][:4]}-{numbers[0][4:6]}-{numbers[0][6:]}"
        elif len(numbers) == 1 and len(numbers[0]) == 6:
            # "198212" 처럼 연월만 붙어있는 경우 -> 1일로 설정
            return f"{numbers[0][:4]}-{numbers[0][4:]}-01"
    except ValueError:
        pass

    return date_str  # 변환 실패 시 원본 반환


async def main() -> None:
    csv_path = Path(CSV_FILE_PATH)
    if not csv_path.exists():
        raise FileNotFoundError(f"CSV 파일을 찾을 수 없습니다: {csv_path}")

    database_url = build_database_url()
    engine = create_async_engine(database_url, future=True)

    updated = 0
    inserted = 0
    skipped = 0
    errors = 0

    try:
        csv_file, reader, detected_encoding = open_csv_dict_reader_with_fallback(csv_path)
        print(f"[INFO] 사용된 CSV 인코딩: {detected_encoding}")

        try:
            async with engine.begin() as conn:
                for idx, row in enumerate(reader, start=2):
                    # 컬럼명 유연하게 가져오기
                    member_name = (row.get("성명") or row.get("회원명") or "").strip()
                    raw_date = (row.get("입회 일자") or row.get("입회일자") or "").strip()

                    # 이름 끝에 'L' 또는 'l'이 있으면 제거
                    if member_name.endswith("L") or member_name.endswith("l"):
                        member_name = member_name[:-1].strip()

                    if not member_name:
                        print(f"[SKIP] {idx}행: 회원명이 비어 있습니다.")
                        skipped += 1
                        continue

                    ent_date = format_date(raw_date)

                    try:
                        # 1. 회원 존재 여부 확인 (clubNo=6 이고 이름이 같은 회원)
                        member_result = await conn.execute(
                            text(
                                """
                                SELECT memberNo
                                FROM yk_members
                                WHERE clubNo = :club_no
                                  AND memberName = :member_name LIMIT 1
                                """
                            ),
                            {
                                "club_no": CLUB_NO,
                                "member_name": member_name,
                            },
                        )
                        member_row = member_result.fetchone()

                        if member_row:
                            # 2-A. 회원이 존재하면 입회일자 업데이트
                            member_no = member_row[0]
                            await conn.execute(
                                text(
                                    """
                                    UPDATE yk_members
                                    SET memberEntdate = :ent_date
                                    WHERE memberNo = :member_no
                                    """
                                ),
                                {
                                    "ent_date": ent_date,
                                    "member_no": member_no,
                                },
                            )
                            updated += 1
                            print(f"[UPDATE] {idx}행: {member_name} (No.{member_no}) 입회일자 업데이트 완료 ({ent_date})")
                        else:
                            # 2-B. 회원이 없으면 신규 추가
                            await conn.execute(
                                text(
                                    """
                                    INSERT INTO yk_members (clubNo, memberName, memberEntdate)
                                    VALUES (:club_no, :member_name, :ent_date)
                                    """
                                ),
                                {
                                    "club_no": CLUB_NO,
                                    "member_name": member_name,
                                    "ent_date": ent_date,
                                },
                            )
                            inserted += 1
                            print(f"[INSERT] {idx}행: {member_name} 신규 회원 추가 완료 ({ent_date})")

                    except Exception as e:
                        print(f"[ERROR] {idx}행 처리 중 오류 발생: {e}")
                        errors += 1
        finally:
            csv_file.close()

    finally:
        await engine.dispose()

    print("\n===== 처리 완료 =====")
    print(f"UPDATE (기존회원 수정): {updated}건")
    print(f"INSERT (신규회원 추가): {inserted}건")
    print(f"SKIP (건너뜀): {skipped}건")
    print(f"ERROR (오류): {errors}건")


if __name__ == "__main__":
    asyncio.run(main())
