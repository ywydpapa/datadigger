import asyncio
import os
import re
from datetime import datetime, date
from pathlib import Path
from urllib.parse import quote_plus

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from korean_lunar_calendar import KoreanLunarCalendar

# .env 파일 경로 설정
ENV_FILE_PATH = "./.env"


def load_dotenv_file(env_path: str = ENV_FILE_PATH) -> None:
    path = Path(env_path)
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key, value = key.strip(), value.strip()
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

    encoded_password = quote_plus(db_password)
    return f"mysql+asyncmy://{db_user}:{encoded_password}@{db_host}:{db_port}/{db_name}?charset={db_charset}"


async def get_birthdays_in_range(start_date_str: str, end_date_str: str):
    # 검색할 날짜 범위 설정
    start_date = datetime.strptime(start_date_str, "%Y-%m-%d").date()
    end_date = datetime.strptime(end_date_str, "%Y-%m-%d").date()
    target_year = start_date.year
    database_url = build_database_url()
    engine = create_async_engine(database_url, future=True)
    calendar = KoreanLunarCalendar()
    upcoming_birthdays = []
    try:
        async with engine.begin() as conn:
            result = await conn.execute(
                text(
                    """
                    SELECT m.memberName, i.infoContents
                    FROM chyMember m
                             JOIN chyMemberInfo i ON m.memberNo = i.memberNo
                    WHERE i.catNo = 6
                      AND (i.attrib IS NULL OR i.attrib != 'XXXUPXXXUP')
                    """
                )
            )
            rows = result.fetchall()

            for row in rows:
                member_name = row[0]
                birth_info = row[1].strip()
                match = re.match(r"(\d{4})-(\d{2})-(\d{2})\s*\(([\+\-])\)", birth_info)
                if not match:
                    continue  # 형식이 맞지 않는 데이터는 건너뜀
                _, birth_month, birth_day, is_solar = match.groups()
                birth_month = int(birth_month)
                birth_day = int(birth_day)
                this_year_birthday = None
                if is_solar == '+':
                    try:
                        this_year_birthday = date(target_year, birth_month, birth_day)
                    except ValueError:
                        # 윤달(2월 29일) 생일자가 평년일 경우 3월 1일로 처리
                        this_year_birthday = date(target_year, 3, 1)
                else:
                    # 음력 생일 처리: 올해(target_year)의 해당 음력 날짜를 양력으로 변환
                    # 윤달 생일(isIntercalation=True) 여부는 기본적으로 False로 가정하여 계산
                    is_valid = calendar.setLunarDate(target_year, birth_month, birth_day, False)
                    if is_valid:
                        this_year_birthday = date(calendar.solarYear, calendar.solarMonth, calendar.solarDay)

                # 계산된 올해의 생일이 검색 기간 내에 포함되는지 확인
                if this_year_birthday and start_date <= this_year_birthday <= end_date:
                    upcoming_birthdays.append({
                        "name": member_name,
                        "original_birth": birth_info,
                        "this_year_date": this_year_birthday,
                        "type": "양력" if is_solar == '+' else "음력"
                    })

    finally:
        await engine.dispose()
    # 날짜순으로 정렬
    upcoming_birthdays.sort(key=lambda x: x["this_year_date"])
    # 결과 출력
    print(f"\n===== 🎂 생일자 목록 ({start_date_str} ~ {end_date_str}) =====")
    if not upcoming_birthdays:
        print("해당 기간에 생일인 회원이 없습니다.")
    else:
        for b in upcoming_birthdays:
            # 출력 예시: 2026-09-14 | 홍길동 (원래 생일: 1960-08-04 (-) [음력])
            print(f"{b['this_year_date']} | {b['name']} (원래 생일: {b['original_birth']} [{b['type']}])")
    print("========================================================\n")


async def main():
    # 💡 여기서 검색하고 싶은 기간을 설정하세요 (YYYY-MM-DD 형식)
    search_start = "2026-02-13"
    search_end = "2026-05-19"

    await get_birthdays_in_range(search_start, search_end)


if __name__ == "__main__":
    asyncio.run(main())
