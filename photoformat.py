import os
import re
from PIL import Image

TARGET_DIR = "targetPhotos"
SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".gif", ".webp", ".tif", ".tiff"}
DELETE_ORIGINAL = True


def normalize_base_name(filename_without_ext: str) -> str:
    name = filename_without_ext.strip()

    # 공백 제거
    name = re.sub(r"\s+", "", name)

    # 끝의 L 또는 l 제거
    name = re.sub(r"[Ll]+$", "", name)

    # 앞뒤 점/공백/언더스코어 정리
    name = name.strip(" ._-")


    return name


def make_unique_path(directory: str, base_name: str, extension: str) -> str:
    candidate = os.path.join(directory, f"{base_name}{extension}")
    if not os.path.exists(candidate):
        return candidate

    index = 1
    while True:
        candidate = os.path.join(directory, f"{base_name}_{index}{extension}")
        if not os.path.exists(candidate):
            return candidate
        index += 1


def convert_to_png(src_path: str, dst_path: str):
    with Image.open(src_path) as img:
        if img.mode in ("RGBA", "LA"):
            converted = img
        else:
            converted = img.convert("RGBA")
        converted.save(dst_path, "PNG")


def process_photos(target_dir: str):
    if not os.path.isdir(target_dir):
        print(f"[ERROR] 폴더가 존재하지 않습니다: {target_dir}")
        return

    files = sorted(os.listdir(target_dir))
    total = 0
    converted = 0
    skipped = 0
    errors = 0

    for filename in files:
        src_path = os.path.join(target_dir, filename)

        if not os.path.isfile(src_path):
            continue

        ext = os.path.splitext(filename)[1].lower()
        if ext not in SUPPORTED_EXTENSIONS:
            print(f"[SKIP] 지원하지 않는 확장자: {filename}")
            skipped += 1
            continue

        total += 1

        base_name = os.path.splitext(filename)[0]
        normalized_name = normalize_base_name(base_name)

        if not normalized_name:
            print(f"[SKIP] 정규화 후 파일명이 비어 있음: {filename}")
            skipped += 1
            continue

        dst_path = make_unique_path(target_dir, normalized_name, ".png")

        try:
            convert_to_png(src_path, dst_path)
            converted += 1
            print(f"[OK] {filename} -> {os.path.basename(dst_path)}")

            if DELETE_ORIGINAL:
                os.remove(src_path)
                print(f"[DEL] 원본 삭제: {filename}")

        except Exception as e:
            errors += 1
            print(f"[ERROR] {filename}: {e}")

    print("\n===== 완료 =====")
    print(f"전체 대상: {total}")
    print(f"변환 성공: {converted}")
    print(f"스킵: {skipped}")
    print(f"에러: {errors}")


if __name__ == "__main__":
    process_photos(TARGET_DIR)
