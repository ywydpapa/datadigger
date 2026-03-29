import cv2
import numpy as np
import os


def extract_photos_from_document(image_path, output_dir):
    # 한글 경로를 지원하기 위해 numpy로 읽어온 후 cv2로 디코딩
    img_array = np.fromfile(image_path, np.uint8)
    img = cv2.imdecode(img_array, cv2.IMREAD_COLOR)

    if img is None:
        print("이미지를 불러올 수 없습니다. 경로를 확인해주세요.")
        return

    # 1. 흑백 이미지로 변환
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    # 2. 노이즈 제거 및 엣지(윤곽선) 검출
    blur = cv2.GaussianBlur(gray, (5, 5), 0)
    edges = cv2.Canny(blur, 50, 150)

    # 3. 엣지를 팽창시켜 끊어진 선 연결 (사진 테두리를 명확히 함)
    kernel = np.ones((5, 5), np.uint8)
    dilated = cv2.dilate(edges, kernel, iterations=2)

    # 4. 윤곽선 찾기
    contours, _ = cv2.findContours(dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    # 저장할 폴더 생성
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    count = 1
    for cnt in contours:
        # 윤곽선을 감싸는 사각형 좌표 구하기
        x, y, w, h = cv2.boundingRect(cnt)
        area = w * h

        # 5. 조건 필터링 (글자나 작은 노이즈를 제외하기 위해 크기 제한)
        # 이미지 해상도에 따라 아래 면적(area)과 너비/높이 조건을 조절해야 할 수 있습니다.
        if area > 20000 and w > 150 and h > 150:
            # 원본 이미지에서 해당 영역만 잘라내기 (Crop)
            roi = img[y:y + h, x:x + w]

            # 저장할 파일 이름 설정
            output_path = os.path.join(output_dir, f"photo_{count}.jpg")

            # 한글 경로 저장을 위한 처리
            extension = os.path.splitext(output_path)[1]
            result, encoded_img = cv2.imencode(extension, roi)
            if result:
                with open(output_path, mode='w+b') as f:
                    encoded_img.tofile(f)
                print(f"저장 완료: {output_path} (크기: {w}x{h})")
                count += 1

    if count == 1:
        print("추출할 사진을 찾지 못했습니다. 면적(area) 조건을 낮춰보세요.")
    else:
        print(f"총 {count - 1}장의 사진 추출이 완료되었습니다.")


# --- 실행 부분 ---
# 원본 이미지 파일 이름과 저장할 폴더 이름을 지정하세요.
input_image = '20260314155502_008.jpg'  # 여기에 실제 파일 경로를 입력하세요
output_folder = './extracted_photos'

extract_photos_from_document(input_image, output_folder)
