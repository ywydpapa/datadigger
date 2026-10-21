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


def clean_phone_number(raw_phone: str) -> str:
    """전화번호에서 하이픈 및 공백 등 특수문자 제거 후 숫자만 추출"""
    return re.sub(r"\D", "", raw_phone)


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

    circle_inserted_count = 0
    phone_updated_count = 0
    address_updated_count = 0
    not_found_count = 0
    skipped_count = 0
    error_count = 0

    try:
        csv_file, reader, detected_encoding = open_csv_dict_reader_with_fallback(csv_path)
        print(f"[INFO] 사용 인코딩: {detected_encoding}\n")

        try:
            async with engine.begin() as conn:
                for idx, row in enumerate(reader, start=2):
                    position = (row.get("직책") or "").strip()
                    club_no = (row.get("클럽번호") or "").strip()
                    club_name = (row.get("클럽명") or "").strip()
                    member_name = (row.get("성명") or row.get("회원명") or row.get("이름") or "").strip()
                    phone = (row.get("전화번호") or row.get("연락처") or "").strip()
                    address = (row.get("주소") or "").strip()

                    # 이름 끝 'L' 또는 'l' 제거
                    if member_name.endswith("L") or member_name.endswith("l"):
                        member_name = member_name[:-1].strip()

                    if not member_name:
                        print(f"[{idx:>2}행] 성명 누락으로 건너뜀")
                        skipped_count += 1
                        continue

                    # 1. lionsMember 테이블에서 회원 정보 조회
                    find_query = text(
                        """
                        SELECT memberNo, memberName, clubNo, memberPhone, memberAddress, memberSeccode
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
                            SELECT memberNo, memberName, clubNo, memberPhone, memberAddress, memberSeccode
                            FROM lionsMember
                            WHERE memberName = :member_name
                            LIMIT 1
                            """
                        )
                        result_fb = await conn.execute(fallback_query, {"member_name": member_name})
                        record = result_fb.mappings().fetchone()

                    if not record:
                        print(f"[{idx:>2}행] {club_name}({club_no}) | {member_name} | [회원정보 미발견]")
                        not_found_count += 1
                        continue

                    member_no = record["memberNo"]
                    current_phone = record["memberPhone"]
                    current_address = record["memberAddress"]

                    try:
                        # 2. lionsMember 테이블 업데이트 대상 판별
                        # 전화번호 갱신 조건: 기존 번호가 NULL, 빈 문자열, 또는 0000이 포함된 경우
                        phone_needs_update = False
                        digits_phone = clean_phone_number(phone)

                        if phone:
                            if current_phone is None or not str(current_phone).strip():
                                phone_needs_update = True
                            elif "0000" in str(current_phone):
                                phone_needs_update = True

                        # 주소 갱신 조건: 기존 주소가 NULL 또는 빈 문자열인 경우
                        address_needs_update = False
                        if address:
                            if current_address is None or not str(current_address).strip():
                                address_needs_update = True

                        update_fields = []
                        update_params = {"member_no": member_no}

                        # 전화번호 및 memberSeccode 동시 업데이트
                        if phone_needs_update:
                            update_fields.append("memberPhone = :new_phone")
                            update_params["new_phone"] = phone

                            if digits_phone:
                                update_fields.append("memberSeccode = :new_seccode")
                                update_params["new_seccode"] = digits_phone

                        if address_needs_update:
                            update_fields.append("memberAddress = :new_address")
                            update_params["new_address"] = address

                        update_msg = []
                        if update_fields:
                            update_query = text(
                                f"""
                                UPDATE lionsMember
                                SET {', '.join(update_fields)}
                                WHERE memberNo = :member_no
                                """
                            )
                            await conn.execute(update_query, update_params)

                            if phone_needs_update:
                                phone_updated_count += 1
                                update_msg.append(f"전화/Seccode({phone} / {digits_phone})")
                            if address_needs_update:
                                address_updated_count += 1
                                update_msg.append("주소등록")

                        # 3. circleMember 테이블에 INSERT / UPDATE
                        insert_circle_query = text(
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
                        await conn.execute(
                            insert_circle_query,
                            {
                                "circle_no": TARGET_CIRCLE_NO,
                                "member_no": member_no,
                                "rank_no": TARGET_RANK_NO,
                                "add_remark": position if position else None,
                            },
                        )
                        circle_inserted_count += 1

                        status_text = ", ".join(update_msg) if update_msg else "기존정보 유지"
                        print(f"[{idx:>2}행] {club_name}({club_no}) | {member_name:<4} (No.{member_no}) | 써클등록 | {status_text}")

                    except Exception as e:
                        print(f"[{idx:>2}행] {member_name} 처리 중 에러: {e}")
                        error_count += 1

        finally:
            csv_file.close()

    finally:
        await engine.dispose()

    print("\n" + "=" * 45)
    print(f"circleMember 등록/갱신: {circle_inserted_count}건")
    print(f"lionsMember 전화번호 및 Seccode 갱신: {phone_updated_count}건")
    print(f"lionsMember 주소 신규등록: {address_updated_count}건")
    print(f"회원정보 미발견 건너뜀: {not_found_count}건")
    print(f"데이터 누락 건너뜀: {skipped_count}건")
    if error_count > 0:
        print(f"처리 오류: {error_count}건")
    print("=" * 45)


if __name__ == "__main__":
    asyncio.run(main())