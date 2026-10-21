import asyncio
import csv
import os
import re
from pathlib import Path
from urllib.parse import quote_plus

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

# ==========================================
# 설정
# ==========================================
CSV_FILE_PATH = "C:\\Users\\djkim\\Desktop\\data_input.csv"
ENV_FILE_PATH = "./.env"
TARGET_CIRCLE_NO = 2
TARGET_RANK_NO = 51


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
            if not has_name:
                f.close()
                raise ValueError(
                    f"필수 컬럼('성명')이 없습니다. 현재 컬럼: {reader.fieldnames}"
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

    inserted_count = 0
    not_found_count = 0
    skipped_count = 0
    error_count = 0

    try:
        csv_file, reader, detected_encoding = open_csv_dict_reader_with_fallback(csv_path)
        print(f"[INFO] 사용 인코딩: {detected_encoding}\n")
        print(f"{'행':<4} | {'클럽명(번호)':<16} | {'성명':<6} | {'직책(addRemark)':<15} | {'결과'}")
        print("-" * 70)

        try:
            # 트랜잭션 시작 (begin)
            async with engine.begin() as conn:
                for idx, row in enumerate(reader, start=2):
                    position = (row.get("직책") or "").strip()
                    club_no = (row.get("클럽번호") or "").strip()
                    club_name = (row.get("클럽명") or "").strip()
                    member_name = (row.get("성명") or row.get("회원명") or row.get("이름") or "").strip()

                    # 이름 끝 'L' 또는 'l' 제거
                    if member_name.endswith("L") or member_name.endswith("l"):
                        member_name = member_name[:-1].strip()

                    if not member_name:
                        print(f"[{idx:>2}행] 성명 누락으로 건너뜀")
                        skipped_count += 1
                        continue

                    # 1. lionsMember 테이블에서 회원번호(memberNo) 조회
                    find_query = text(
                        """
                        SELECT memberNo, memberName, clubNo
                        FROM lionsMember
                        WHERE memberName = :member_name
                          AND (clubNo = :club_no OR :club_no = '')
                        LIMIT 1
                        """
                    )
                    result = await conn.execute(
                        find_query,
                        {
                            "member_name": member_name,
                            "club_no": club_no,
                        },
                    )
                    record = result.mappings().fetchone()

                    # 클럽번호로 못 찾은 경우 이름만으로 2차 조회
                    if not record:
                        fallback_query = text(
                            """
                            SELECT memberNo, memberName, clubNo
                            FROM lionsMember
                            WHERE memberName = :member_name
                            LIMIT 1
                            """
                        )
                        result_fb = await conn.execute(fallback_query, {"member_name": member_name})
                        record = result_fb.mappings().fetchone()

                    if not record:
                        print(f"[{idx:>2}행] {club_name}({club_no}) | {member_name} | {position} | [회원정보 미발견]")
                        not_found_count += 1
                        continue

                    member_no = record["memberNo"]

                    # 2. circleMember 테이블에 INSERT 실행
                    # 중복(circleNo, memberNo) 시 addRemark와 rankNo를 최신값으로 갱신
                    insert_query = text(
                        """
                        INSERT INTO circleMember (
                            circleNo,
                            memberNo,
                            rankNo,
                            addRemark
                        ) VALUES (
                            :circle_no,
                            :member_no,
                            :rank_no,
                            :add_remark
                        )
                        ON DUPLICATE KEY UPDATE
                            rankNo = VALUES(rankNo),
                            addRemark = VALUES(addRemark)
                        """
                    )

                    try:
                        await conn.execute(
                            insert_query,
                            {
                                "circle_no": TARGET_CIRCLE_NO,
                                "member_no": member_no,
                                "rank_no": TARGET_RANK_NO,
                                "add_remark": position if position else None,
                            },
                        )
                        inserted_count += 1
                        print(f"[{idx:>2}행] {club_name}({club_no}) | {member_name} | {position} | [등록완료: memberNo={member_no}]")
                    except Exception as e:
                        print(f"[{idx:>2}행] {member_name} INSERT 에러: {e}")
                        error_count += 1

        finally:
            csv_file.close()

    finally:
        await engine.dispose()

    print("\n" + "=" * 40)
    print(f"circleMember 입력/갱신 완료: {inserted_count}건")
    print(f"lionsMember 미발견 (입력제외): {not_found_count}건")
    print(f"데이터 누락 건너뜀: {skipped_count}건")
    if error_count > 0:
        print(f"DB 오류 발생: {error_count}건")
    print("=" * 40)


if __name__ == "__main__":
    asyncio.run(main())