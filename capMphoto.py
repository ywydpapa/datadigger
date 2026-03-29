import cv2
import numpy as np
import easyocr
import os
import re


def extract_and_name_photos(image_path, output_dir, reader):
    # 한글 경로 지원을 위해 numpy로 읽기
    img_array = np.fromfile(image_path, np.uint8)
    img = cv2.imdecode(img_array, cv2.IMREAD_COLOR)

    if img is None:
        print(f"이미지를 불러올 수 없습니다: {image_path}")
        return

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    # 1. 이진화: 흰색 배경은 검은색으로, 어두운 사진/글씨는 흰색으로 반전
    # 배경이 완전한 흰색이 아닐 수 있으므로 임계값을 240으로 설정
    _, thresh = cv2.threshold(gray, 240, 255, cv2.THRESH_BINARY_INV)

    # 2. 특수 팽창(Dilate): 세로로 길게 팽창시켜 사진과 그 아래의 이름표를 하나의 덩어리로 묶음
    # 가로(5)보다 세로(15)를 길게 주어 옆 사람과 붙는 것은 방지하고 아래 글씨와만 붙게 함
    kernel = np.ones((15, 5), np.uint8)
    dilated = cv2.dilate(thresh, kernel, iterations=2)

    # 3. 윤곽선 찾기
    contours, _ = cv2.findContours(dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    count = 0
    for cnt in contours:
        x, y, w, h = cv2.boundingRect(cnt)
        area = w * h
        aspect_ratio = h / float(w)

        # 4. 크기 및 비율 필터링
        # 면적이 너무 작거나, 비율이 너무 넓적하거나 길쭉한 노이즈 제외
        # 사진+글씨 덩어리는 보통 세로가 가로보다 1.2배 ~ 2.5배 정도 긺
        if area > 10000 and 1.2 <= aspect_ratio <= 2.5:

            # 5. 사진과 글씨 영역 분리
            # 증명사진의 표준 비율(가로:세로 = 1:1.35)을 적용하여 사진 부분만 계산
            photo_h = int(w * 1.35)

            # 만약 계산된 사진 높이가 전체 덩어리보다 크면 보정
            if photo_h > h:
                photo_h = h - 30

                # 사진 영역 (위쪽)
            photo_roi = img[y:y + photo_h, x:x + w]

            # 텍스트 영역 (사진 바로 아래부터 덩어리 끝까지)
            # 텍스트가 사진보다 약간 넓을 수 있으므로 좌우로 10픽셀씩 여유를 줌
            text_roi = img[y + photo_h:y + h, max(0, x - 10):min(img.shape[1], x + w + 10)]

            if text_roi.shape[0] < 10 or text_roi.shape[1] < 10:
                continue

            # 6. EasyOCR로 텍스트 읽기
            ocr_result = reader.readtext(text_roi, detail=0)
            extracted_text = " ".join(ocr_result)

            # 7. 파일명 정제
            clean_name = re.sub(r'[\\/*?:"<>|]', "", extracted_text)
            clean_name = " ".join(clean_name.split())

            if not clean_name:
                clean_name = f"unknown_photo_{count + 1}"

            # 8. 이미지 저장
            output_path = os.path.join(output_dir, f"{clean_name}.jpg")

            dup_count = 1
            while os.path.exists(output_path):
                output_path = os.path.join(output_dir, f"{clean_name}_{dup_count}.jpg")
                dup_count += 1

            extension = os.path.splitext(output_path)[1]
            result, encoded_img = cv2.imencode(extension, photo_roi)
            if result:
                with open(output_path, mode='w+b') as f:
                    encoded_img.tofile(f)
                print(f"저장 완료: {output_path}")
                count += 1

    print(f"[{os.path.basename(image_path)}] 총 {count}장의 사진 추출 완료.\n")


# --- 실행 부분 ---
if __name__ == "__main__":
    print("OCR 모델을 로딩 중입니다...")
    reader = easyocr.Reader(['ko', 'en'])
    print("모델 로딩 완료.\n")

    # 처리할 원본 이미지 파일 리스트
    image_files = [
        '20260314152233_002.jpg',
        '20260314152233_003.jpg',
        '20260314152233_004.jpg',
        '20260314152233_005.jpg',
        '20260314152233_006.jpg',
        '20260314152233_007.jpg',
        '20260314155502_008.jpg'
    ]

    # 새로운 폴더에 저장
    output_base_folder = './extracted_profiles'

    for img_file in image_files:
        if os.path.exists(img_file):
            extract_and_name_photos(img_file, output_base_folder, reader)
        else:
            print(f"파일을 찾을 수 없습니다: {img_file}")
