import cv2
import numpy as np
import os


def extract_tight_photos(image_path, output_dir, start_index):
    img_array = np.fromfile(image_path, np.uint8)
    img = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
    if img is None:
        print(f"이미지를 불러올 수 없습니다: {image_path}")
        return start_index
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    _, thresh = cv2.threshold(gray, 240, 255, cv2.THRESH_BINARY_INV)
    kernel = np.ones((5, 5), np.uint8)
    closed = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel, iterations=2)
    contours, _ = cv2.findContours(closed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    valid_boxes = []
    for cnt in contours:
        x, y, w, h = cv2.boundingRect(cnt)
        area = w * h
        aspect_ratio = h / float(w)
        if area > 10000 and 1.1 <= aspect_ratio <= 1.6:
            valid_boxes.append((x, y, w, h))
    valid_boxes.sort(key=lambda b: (b[1] // 150, b[0]))
    current_index = start_index
    for x, y, w, h in valid_boxes:
        photo_roi = img[y + 2:y + h - 2, x + 2:x + w - 2]
        filename = f"Coinv-{current_index:04d}.jpg"
        output_path = os.path.join(output_dir, filename)
        extension = os.path.splitext(output_path)[1]
        result, encoded_img = cv2.imencode(extension, photo_roi)
        if result:
            with open(output_path, mode='w+b') as f:
                encoded_img.tofile(f)
            current_index += 1
    print(f"[{os.path.basename(image_path)}] {len(valid_boxes)}장의 사진 추출 완료.")
    return current_index
if __name__ == "__main__":
    image_files = [
        '20260314152233_002.jpg',
        '20260314152233_003.jpg',
        '20260314152233_004.jpg',
        '20260314152233_005.jpg',
        '20260314152233_006.jpg',
        '20260314152233_007.jpg',
        '20260314155502_008.jpg'
    ]
    output_base_folder = './extracted_photos_only'
    global_index = 1
    print("사진 추출을 시작합니다...")
    for img_file in image_files:
        if os.path.exists(img_file):
            global_index = extract_tight_photos(img_file, output_base_folder, global_index)
        else:
            print(f"파일을 찾을 수 없습니다: {img_file}")
    print(f"\n모든 작업이 완료되었습니다. 총 {global_index - 1}장의 사진이 저장되었습니다.")
