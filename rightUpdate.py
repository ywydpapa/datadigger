import asyncio
import csv
import os
from pathlib import Path
from urllib.parse import quote_plus

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

CSV_FILE_PATH = "input/right.csv"
ENV_FILE_PATH = ".env"


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
            + ". .env 파일 또는 PyCharm 실행 설정의 환경 변수를 확인하세요."
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

            required_columns = {"클럽명", "회원명"}
            missing_columns = required_columns - set(reader.fieldnames)
            if missing_columns:
                f.close()
                raise ValueError(
                    f"필수 컬럼이 없습니다: {', '.join(sorted(missing_columns))}. "
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


async def main() -> None:
    csv_path = Path(CSV_FILE_PATH)
    if not csv_path.exists():
        raise FileNotFoundError(f"CSV 파일을 찾을 수 없습니다: {csv_path}")

    database_url = build_database_url()
    engine = create_async_engine(database_url, future=True)

    inserted = 0
    skipped = 0
    errors = 0

    try:
        csv_file, reader, detected_encoding = open_csv_dict_reader_with_fallback(csv_path)
        print(f"[INFO] 사용된 CSV 인코딩: {detected_encoding}")

        try:
            async with engine.begin() as conn:
                for idx, row in enumerate(reader, start=2):
                    club_name = (row.get("클럽명") or "").strip()
                    member_name = (row.get("회원명") or "").strip()

                    if not any((value or "").strip() for value in row.values()):
                        print(f"[SKIP] {idx}행: 빈 행입니다.")
                        skipped += 1
                        continue

                    if not club_name or not member_name:
                        print(f"[SKIP] {idx}행: 클럽명 또는 회원명이 비어 있습니다.")
                        skipped += 1
                        continue

                    try:
                        club_result = await conn.execute(
                            text(
                                """
                                SELECT clubNo
                                FROM lionsClub
                                WHERE clubName = :club_name
                                LIMIT 1
                                """
                            ),
                            {"club_name": club_name},
                        )
                        club_row = club_result.fetchone()

                        if not club_row:
                            print(f"[SKIP] {idx}행: 클럽을 찾을 수 없습니다. clubName={club_name}")
                            skipped += 1
                            continue

                        club_no = club_row[0]

                        member_result = await conn.execute(
                            text(
                                """
                                SELECT memberNo
                                FROM lionsMember
                                WHERE memberName = :member_name
                                  AND clubNo = :club_no
                                LIMIT 1
                                """
                            ),
                            {
                                "member_name": member_name,
                                "club_no": club_no,
                            },
                        )
                        member_row = member_result.fetchone()

                        if not member_row:
                            print(
                                f"[SKIP] {idx}행: 회원을 찾을 수 없습니다. "
                                f"clubName={club_name}, memberName={member_name}"
                            )
                            skipped += 1
                            continue

                        member_no = member_row[0]

                        exists_result = await conn.execute(
                            text(
                                """
                                SELECT 1
                                FROM voteRight
                                WHERE clubNo = :club_no
                                  AND memberNo = :member_no
                                LIMIT 1
                                """
                            ),
                            {
                                "club_no": club_no,
                                "member_no": member_no,
                            },
                        )
                        exists_row = exists_result.fetchone()

                        if exists_row:
                            print(f"[SKIP] {idx}행: 이미 존재합니다. clubNo={club_no}, memberNo={member_no}")
                            skipped += 1
                            continue

                        await conn.execute(
                            text(
                                """
                                INSERT INTO voteRight (clubNo, memberNo)
                                VALUES (:club_no, :member_no)
                                """
                            ),
                            {
                                "club_no": club_no,
                                "member_no": member_no,
                            },
                        )

                        inserted += 1
                        print(f"[OK] {idx}행: clubNo={club_no}, memberNo={member_no} 삽입 완료")

                    except Exception as e:
                        print(f"[ERROR] {idx}행: {e}")
                        errors += 1
        finally:
            csv_file.close()

    finally:
        await engine.dispose()

    print("\n===== 처리 완료 =====")
    print(f"INSERT: {inserted}")
    print(f"SKIP: {skipped}")
    print(f"ERROR: {errors}")


if __name__ == "__main__":
    asyncio.run(main())
