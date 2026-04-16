import asyncio
import csv
import os
from pathlib import Path
from urllib.parse import quote_plus

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

# 파일 경로 설정
CSV_FILE_PATH = "C:\\Users\\djkim\\Desktop\\data_input.csv"
ENV_FILE_PATH = "./.env"


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

            # 성명(또는 회원명), 전화번호 컬럼이 있는지 확인
            has_name = any(col in reader.fieldnames for col in ["성명", "회원명", "이름"])
            has_phone = any(col in reader.fieldnames for col in ["전화번호", "연락처", "휴대폰", "핸드폰"])

            if not has_name or not has_phone:
                f.close()
                raise ValueError(
                    f"필수 컬럼('성명' 관련, '전화번호' 관련)이 없습니다. "
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

    processed = 0
    skipped = 0
    not_found_member = 0
    errors = 0

    try:
        csv_file, reader, detected_encoding = open_csv_dict_reader_with_fallback(csv_path)
        print(f"[INFO] 사용된 CSV 인코딩: {detected_encoding}")

        try:
            async with engine.begin() as conn:
                for idx, row in enumerate(reader, start=2):
                    # 컬럼명 유연하게 가져오기
                    member_name = (row.get("성명") or row.get("회원명") or row.get("이름") or "").strip()
                    phone_number = (row.get("전화번호") or row.get("연락처") or row.get("휴대폰") or row.get("핸드폰") or "").strip()

                    # 이름 끝에 'L' 또는 'l'이 있으면 제거
                    if member_name.endswith("L") or member_name.endswith("l"):
                        member_name = member_name[:-1].strip()

                    if not member_name:
                        print(f"[SKIP] {idx}행: 회원명이 비어 있습니다.")
                        skipped += 1
                        continue

                    if not phone_number:
                        print(f"[SKIP] {idx}행: '{member_name}' 회원의 전화번호가 비어 있습니다.")
                        skipped += 1
                        continue

                    try:
                        # 1. chyMember에서 이름으로 memberNo 찾기
                        member_result = await conn.execute(
                            text(
                                """
                                SELECT memberNo
                                FROM chyMember
                                WHERE memberName = :member_name LIMIT 1
                                """
                            ),
                            {"member_name": member_name},
                        )
                        member_row = member_result.fetchone()

                        if not member_row:
                            print(f"[SKIP] {idx}행: '{member_name}' 회원을 chyMember에서 찾을 수 없습니다.")
                            not_found_member += 1
                            continue

                        member_no = member_row[0]

                        # 2. 기존 전화번호 정보(catNo=1) 업데이트 (이력 남기기)
                        # 이전에 있던 동일한 memberNo, catNo=1 데이터의 attrib와 modDate를 수정
                        await conn.execute(
                            text(
                                """
                                UPDATE chyMemberInfo
                                SET attrib  = 'XXXUPXXXUP',
                                    modDate = NOW()
                                WHERE memberNo = :member_no
                                  AND catNo = 1
                                  AND (attrib IS NULL OR attrib != 'XXXUPXXXUP')
                                """
                            ),
                            {"member_no": member_no},
                        )

                        # 3. 새로운 전화번호 정보 인서트
                        # 테이블 스키마에 따라 regDate나 다른 필수 컬럼이 있다면 추가해주세요.
                        await conn.execute(
                            text(
                                """
                                INSERT INTO chyMemberInfo (memberNo, catNo, infoContents)
                                VALUES (:member_no, 1, :phone_number)
                                """
                            ),
                            {
                                "member_no": member_no,
                                "phone_number": phone_number,
                            },
                        )

                        processed += 1
                        print(f"[SUCCESS] {idx}행: {member_name} 전화번호 업데이트 완료 ({phone_number})")

                    except Exception as e:
                        print(f"[ERROR] {idx}행 처리 중 오류 발생: {e}")
                        errors += 1
        finally:
            csv_file.close()

    finally:
        await engine.dispose()

    print("\n===== 처리 완료 =====")
    print(f"SUCCESS (전화번호 갱신 완료): {processed}건")
    print(f"SKIP (이름/전화번호 없음): {skipped}건")
    print(f"NOT FOUND (회원 정보 없음): {not_found_member}건")
    print(f"ERROR (오류): {errors}건")


if __name__ == "__main__":
    asyncio.run(main())
