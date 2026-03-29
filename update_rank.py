import os
import csv
import sys
import argparse
import traceback
from datetime import datetime

import pandas as pd
import pymysql
from dotenv import load_dotenv


load_dotenv()

DB_CONFIG = {
    "host": os.getenv("DB_HOST", "127.0.0.1"),
    "port": int(os.getenv("DB_PORT", "3306")),
    "user": os.getenv("DB_USER", ""),
    "password": os.getenv("DB_PASSWORD", ""),
    "database": os.getenv("DB_NAME", ""),
    "charset": os.getenv("DB_CHARSET", "utf8mb4"),
    "autocommit": False,
    "cursorclass": pymysql.cursors.DictCursor,
}

REQUIRED_COLUMNS = ["memberName", "clubName", "clubRank", "rankNo"]
PHOTO_EXTENSIONS = [".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp"]


def now_str():
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def ensure_output_dir(path: str):
    os.makedirs(path, exist_ok=True)


def normalize_text(value):
    if pd.isna(value):
        return ""
    return str(value).strip()


def normalize_rank_no(value):
    if pd.isna(value):
        return None
    s = str(value).strip()
    if s == "":
        return None
    try:
        return int(float(s))
    except ValueError:
        return None


def validate_dataframe(df: pd.DataFrame):
    missing = [col for col in REQUIRED_COLUMNS if col not in df.columns]
    if missing:
        raise ValueError(f"CSV에 필요한 컬럼이 없습니다: {missing}")

    for col in ["memberName", "clubName", "clubRank"]:
        df[col] = df[col].apply(normalize_text)

    df["rankNo"] = df["rankNo"].apply(normalize_rank_no)
    return df


def write_csv(file_path, rows, fieldnames):
    with open(file_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def get_connection():
    return pymysql.connect(**DB_CONFIG)


def read_csv_with_fallback(csv_path):
    encodings_to_try = ["utf-8-sig", "utf-8", "cp949", "euc-kr"]

    last_error = None
    for enc in encodings_to_try:
        try:
            print(f"[INFO] CSV 인코딩 시도: {enc}")
            df = pd.read_csv(csv_path, dtype=str, encoding=enc)
            print(f"[INFO] CSV 인코딩 성공: {enc}")
            return df, enc
        except UnicodeDecodeError as e:
            last_error = e
            print(f"[WARN] CSV 인코딩 실패: {enc} -> {e}")

    raise last_error


def find_club(cursor, club_name):
    sql = """
        SELECT clubNo, clubName
        FROM lionsClub
        WHERE TRIM(clubName) = %s
    """
    cursor.execute(sql, (club_name,))
    return cursor.fetchall()


def find_member(cursor, member_name, club_no):
    sql = """
        SELECT memberNo, memberName, clubNo, clubRank, rankNo
        FROM lionsMember
        WHERE TRIM(memberName) = %s
          AND clubNo = %s
    """
    cursor.execute(sql, (member_name, club_no))
    return cursor.fetchall()


def update_member_info(cursor, member_no, new_club_rank, new_rank_no):
    sql = """
        UPDATE lionsMember
        SET clubRank = %s,
            rankNo = %s
        WHERE memberNo = %s
    """
    cursor.execute(sql, (new_club_rank, new_rank_no, member_no))


def init_photo_result(base_result):
    base_result["photoSource"] = ""
    base_result["photoTarget"] = ""
    base_result["photoStatus"] = ""
    base_result["photoMessage"] = ""


def find_matching_photo_files(photos_dir, member_name):
    matched = []
    for ext in PHOTO_EXTENSIONS:
        candidate = os.path.join(photos_dir, f"{member_name}{ext}")
        if os.path.isfile(candidate):
            matched.append(candidate)
    return matched


def rename_photo_file(photos_dir, member_name, member_no, renamed_sources):
    result = {
        "photoSource": "",
        "photoTarget": "",
        "photoStatus": "",
        "photoMessage": "",
    }

    if not photos_dir:
        result["photoStatus"] = "PHOTO_SKIPPED"
        result["photoMessage"] = "photos_dir 미지정"
        return result

    if not os.path.isdir(photos_dir):
        result["photoStatus"] = "PHOTO_ERROR"
        result["photoMessage"] = f"사진 폴더가 존재하지 않습니다: {photos_dir}"
        return result

    matched_files = find_matching_photo_files(photos_dir, member_name)

    if len(matched_files) == 0:
        result["photoStatus"] = "PHOTO_NOT_FOUND"
        result["photoMessage"] = f"이름과 일치하는 사진이 없습니다: {member_name}"
        return result

    if len(matched_files) > 1:
        result["photoStatus"] = "PHOTO_DUPLICATED"
        result["photoMessage"] = f"동일 이름 사진이 여러 개 있습니다: {len(matched_files)}건"
        return result

    source_path = matched_files[0]
    source_name = os.path.basename(source_path)

    if source_path in renamed_sources:
        result["photoSource"] = source_name
        result["photoStatus"] = "PHOTO_ALREADY_RENAMED"
        result["photoMessage"] = "같은 원본 사진이 이미 처리되었습니다."
        return result

    ext = os.path.splitext(source_name)[1]
    target_name = f"mphoto_{member_no}{ext}"
    target_path = os.path.join(photos_dir, target_name)

    result["photoSource"] = source_name
    result["photoTarget"] = target_name

    if os.path.exists(target_path):
        result["photoStatus"] = "PHOTO_TARGET_EXISTS"
        result["photoMessage"] = f"대상 파일이 이미 존재합니다: {target_name}"
        return result

    os.rename(source_path, target_path)
    renamed_sources.add(source_path)

    result["photoStatus"] = "PHOTO_RENAMED"
    result["photoMessage"] = "사진 파일명 변경 성공"
    return result


def make_enriched_row(base_result):
    return {
        "lineNo": base_result["lineNo"],
        "memberName": base_result["memberName"],
        "clubName": base_result["clubName"],
        "inputClubRank": base_result["inputClubRank"],
        "inputRankNo": base_result["inputRankNo"],
        "memberNo": base_result["memberNo"],
        "clubNo": base_result["clubNo"],
        "oldClubRank": base_result["oldClubRank"],
        "newClubRank": base_result["newClubRank"],
        "oldRankNo": base_result["oldRankNo"],
        "newRankNo": base_result["newRankNo"],
        "status": base_result["status"],
        "message": base_result["message"],
        "photoSource": base_result["photoSource"],
        "photoTarget": base_result["photoTarget"],
        "photoStatus": base_result["photoStatus"],
        "photoMessage": base_result["photoMessage"],
    }


def process_csv(csv_path, output_dir, dry_run=False, skip_same=True, rename_photos=False, photos_dir=None):
    ensure_output_dir(output_dir)

    timestamp = now_str()
    result_log_path = os.path.join(output_dir, f"result_{timestamp}.csv")
    enriched_csv_path = os.path.join(output_dir, f"enriched_{timestamp}.csv")
    summary_path = os.path.join(output_dir, f"summary_{timestamp}.txt")

    print(f"[INFO] CSV 읽는 중: {csv_path}")
    df, detected_encoding = read_csv_with_fallback(csv_path)
    df = validate_dataframe(df)
    print(f"[INFO] 사용된 CSV 인코딩: {detected_encoding}")

    total_count = len(df)
    updated_count = 0
    skipped_same_count = 0
    not_found_count = 0
    duplicate_count = 0
    invalid_count = 0
    error_count = 0

    photo_renamed_count = 0
    photo_not_found_count = 0
    photo_duplicate_count = 0
    photo_exists_count = 0
    photo_error_count = 0

    result_rows = []
    enriched_rows = []
    renamed_sources = set()

    conn = None

    try:
        conn = get_connection()
        print("[INFO] DB 연결 성공")

        with conn.cursor() as cursor:
            for index, row in df.iterrows():
                line_no = index + 2
                member_name = row["memberName"]
                club_name = row["clubName"]
                club_rank = row["clubRank"]
                rank_no = row["rankNo"]

                base_result = {
                    "lineNo": line_no,
                    "memberName": member_name,
                    "clubName": club_name,
                    "inputClubRank": club_rank,
                    "inputRankNo": rank_no,
                    "status": "",
                    "message": "",
                    "memberNo": "",
                    "clubNo": "",
                    "oldClubRank": "",
                    "newClubRank": club_rank,
                    "oldRankNo": "",
                    "newRankNo": rank_no,
                }
                init_photo_result(base_result)

                try:
                    if not member_name or not club_name or not club_rank:
                        invalid_count += 1
                        base_result["status"] = "INVALID"
                        base_result["message"] = "memberName, clubName, clubRank 중 빈 값이 있습니다."
                        result_rows.append(base_result)
                        enriched_rows.append(make_enriched_row(base_result))
                        print(f"[INVALID] line={line_no} 필수값 누락")
                        continue

                    if rank_no is None:
                        invalid_count += 1
                        base_result["status"] = "INVALID"
                        base_result["message"] = "rankNo가 비어있거나 숫자가 아닙니다."
                        result_rows.append(base_result)
                        enriched_rows.append(make_enriched_row(base_result))
                        print(f"[INVALID] line={line_no} rankNo 오류")
                        continue

                    clubs = find_club(cursor, club_name)

                    if len(clubs) == 0:
                        not_found_count += 1
                        base_result["status"] = "CLUB_NOT_FOUND"
                        base_result["message"] = "일치하는 clubName이 없습니다."
                        result_rows.append(base_result)
                        enriched_rows.append(make_enriched_row(base_result))
                        print(f"[NOT_FOUND] line={line_no} clubName={club_name}")
                        continue

                    if len(clubs) > 1:
                        duplicate_count += 1
                        base_result["status"] = "CLUB_DUPLICATED"
                        base_result["message"] = f"동일 clubName이 {len(clubs)}건 존재합니다."
                        result_rows.append(base_result)
                        enriched_rows.append(make_enriched_row(base_result))
                        print(f"[DUPLICATE] line={line_no} clubName={club_name}")
                        continue

                    club_no = clubs[0]["clubNo"]
                    base_result["clubNo"] = club_no

                    members = find_member(cursor, member_name, club_no)

                    if len(members) == 0:
                        not_found_count += 1
                        base_result["status"] = "MEMBER_NOT_FOUND"
                        base_result["message"] = "memberName + clubName 기준 일치하는 회원이 없습니다."
                        result_rows.append(base_result)
                        enriched_rows.append(make_enriched_row(base_result))
                        print(f"[NOT_FOUND] line={line_no} memberName={member_name}, clubName={club_name}")
                        continue

                    if len(members) > 1:
                        duplicate_count += 1
                        base_result["status"] = "MEMBER_DUPLICATED"
                        base_result["message"] = f"memberName + clubName 기준 일치하는 회원이 {len(members)}건 존재합니다."
                        result_rows.append(base_result)
                        enriched_rows.append(make_enriched_row(base_result))
                        print(f"[DUPLICATE] line={line_no} memberName={member_name}, clubName={club_name}")
                        continue

                    member = members[0]
                    member_no = member["memberNo"]
                    old_club_rank = normalize_text(member["clubRank"])
                    old_rank_no = member["rankNo"]

                    base_result["memberNo"] = member_no
                    base_result["oldClubRank"] = old_club_rank
                    base_result["oldRankNo"] = old_rank_no

                    if (
                        skip_same
                        and old_rank_no == rank_no
                        and normalize_text(old_club_rank) == normalize_text(club_rank)
                    ):
                        skipped_same_count += 1
                        base_result["status"] = "SKIPPED_SAME"
                        base_result["message"] = "기존 clubRank, rankNo와 동일하여 스킵"
                    else:
                        if dry_run:
                            updated_count += 1
                            base_result["status"] = "DRY_RUN_OK"
                            base_result["message"] = "업데이트 대상 확인 완료(dry-run)"
                            print(
                                f"[DRY-RUN] line={line_no} memberNo={member_no} clubRank {old_club_rank} -> {club_rank}, rankNo {old_rank_no} -> {rank_no}"
                            )
                        else:
                            update_member_info(cursor, member_no, club_rank, rank_no)
                            updated_count += 1
                            base_result["status"] = "UPDATED"
                            base_result["message"] = "clubRank, rankNo 업데이트 성공"
                            print(
                                f"[UPDATED] line={line_no} memberNo={member_no} clubRank {old_club_rank} -> {club_rank}, rankNo {old_rank_no} -> {rank_no}"
                            )

                    if rename_photos and base_result["memberNo"]:
                        try:
                            photo_result = rename_photo_file(
                                photos_dir=photos_dir,
                                member_name=member_name,
                                member_no=member_no,
                                renamed_sources=renamed_sources,
                            )
                            base_result.update(photo_result)

                            if photo_result["photoStatus"] == "PHOTO_RENAMED":
                                photo_renamed_count += 1
                            elif photo_result["photoStatus"] == "PHOTO_NOT_FOUND":
                                photo_not_found_count += 1
                            elif photo_result["photoStatus"] == "PHOTO_DUPLICATED":
                                photo_duplicate_count += 1
                            elif photo_result["photoStatus"] == "PHOTO_TARGET_EXISTS":
                                photo_exists_count += 1
                            elif photo_result["photoStatus"] in ["PHOTO_ERROR"]:
                                photo_error_count += 1

                            print(
                                f"[PHOTO] line={line_no} status={photo_result['photoStatus']} "
                                f"source={photo_result['photoSource']} target={photo_result['photoTarget']} "
                                f"msg={photo_result['photoMessage']}"
                            )
                        except Exception as photo_ex:
                            base_result["photoStatus"] = "PHOTO_ERROR"
                            base_result["photoMessage"] = f"{type(photo_ex).__name__}: {str(photo_ex)}"
                            photo_error_count += 1
                            print(f"[PHOTO_ERROR] line={line_no} {photo_ex}")

                    result_rows.append(base_result)
                    enriched_rows.append(make_enriched_row(base_result))

                except Exception as e:
                    error_count += 1
                    base_result["status"] = "ERROR"
                    base_result["message"] = f"{type(e).__name__}: {str(e)}"
                    result_rows.append(base_result)
                    enriched_rows.append(make_enriched_row(base_result))
                    print(f"[ERROR] line={line_no} {e}")

        if dry_run:
            conn.rollback()
            print("[INFO] dry-run 모드이므로 ROLLBACK 처리")
        else:
            conn.commit()
            print("[INFO] COMMIT 완료")

    except Exception as e:
        if conn:
            conn.rollback()
        print("[FATAL] 전체 작업 실패. ROLLBACK 처리")
        traceback.print_exc()
        raise e

    finally:
        if conn:
            conn.close()
            print("[INFO] DB 연결 종료")

    result_fieldnames = [
        "lineNo",
        "memberName",
        "clubName",
        "inputClubRank",
        "inputRankNo",
        "status",
        "message",
        "memberNo",
        "clubNo",
        "oldClubRank",
        "newClubRank",
        "oldRankNo",
        "newRankNo",
        "photoSource",
        "photoTarget",
        "photoStatus",
        "photoMessage",
    ]

    enriched_fieldnames = [
        "lineNo",
        "memberName",
        "clubName",
        "inputClubRank",
        "inputRankNo",
        "memberNo",
        "clubNo",
        "oldClubRank",
        "newClubRank",
        "oldRankNo",
        "newRankNo",
        "status",
        "message",
        "photoSource",
        "photoTarget",
        "photoStatus",
        "photoMessage",
    ]

    write_csv(result_log_path, result_rows, result_fieldnames)
    write_csv(enriched_csv_path, enriched_rows, enriched_fieldnames)

    summary_lines = [
        f"실행시각: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"입력파일: {csv_path}",
        f"사용 인코딩: {detected_encoding}",
        f"dry_run: {dry_run}",
        f"skip_same: {skip_same}",
        f"rename_photos: {rename_photos}",
        f"photos_dir: {photos_dir}",
        f"총 건수: {total_count}",
        f"업데이트 처리 건수: {updated_count}",
        f"동일값 스킵 건수: {skipped_same_count}",
        f"미매칭 건수: {not_found_count}",
        f"중복 건수: {duplicate_count}",
        f"유효성 오류 건수: {invalid_count}",
        f"에러 건수: {error_count}",
        f"사진 변경 성공 건수: {photo_renamed_count}",
        f"사진 미존재 건수: {photo_not_found_count}",
        f"사진 중복 건수: {photo_duplicate_count}",
        f"사진 대상파일 존재 건수: {photo_exists_count}",
        f"사진 에러 건수: {photo_error_count}",
        f"결과로그: {result_log_path}",
        f"확장CSV: {enriched_csv_path}",
    ]

    with open(summary_path, "w", encoding="utf-8") as f:
        f.write("\n".join(summary_lines))

    print("\n===== 처리 결과 =====")
    for line in summary_lines:
        print(line)

    return {
        "total": total_count,
        "updated": updated_count,
        "skipped_same": skipped_same_count,
        "not_found": not_found_count,
        "duplicate": duplicate_count,
        "invalid": invalid_count,
        "error": error_count,
        "photo_renamed": photo_renamed_count,
        "photo_not_found": photo_not_found_count,
        "photo_duplicate": photo_duplicate_count,
        "photo_exists": photo_exists_count,
        "photo_error": photo_error_count,
        "result_log": result_log_path,
        "enriched_csv": enriched_csv_path,
        "summary_file": summary_path,
    }


def parse_args():
    parser = argparse.ArgumentParser(
        description="CSV 기준으로 lionsMember의 clubRank, rankNo를 업데이트하고 사진 파일명을 mphoto_{memberNo} 형태로 변경합니다."
    )
    parser.add_argument("--csv", required=True, help="입력 CSV 파일 경로")
    parser.add_argument("--output", default="output", help="결과 파일 저장 디렉토리 (기본값: output)")
    parser.add_argument("--dry-run", action="store_true", help="실제 업데이트 없이 매칭 및 결과만 검증합니다.")
    parser.add_argument("--no-skip-same", action="store_true", help="기존 clubRank/rankNo와 같아도 스킵하지 않습니다.")
    parser.add_argument("--rename-photos", action="store_true", help="사진 파일명을 이름 -> mphoto_{memberNo}로 변경합니다.")
    parser.add_argument("--photos-dir", default="targetPhotos", help="사진 폴더 경로 (기본값: targetPhotos)")
    return parser.parse_args()


def main():
    args = parse_args()

    csv_path = args.csv
    output_dir = args.output
    dry_run = args.dry_run
    skip_same = not args.no_skip_same
    rename_photos = args.rename_photos
    photos_dir = args.photos_dir

    if not os.path.exists(csv_path):
        print(f"[ERROR] CSV 파일이 존재하지 않습니다: {csv_path}")
        sys.exit(1)

    try:
        process_csv(
            csv_path=csv_path,
            output_dir=output_dir,
            dry_run=dry_run,
            skip_same=skip_same,
            rename_photos=rename_photos,
            photos_dir=photos_dir,
        )
    except Exception as e:
        print(f"[ERROR] 프로그램 실행 실패: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
