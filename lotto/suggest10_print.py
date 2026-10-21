import pandas as pd
import numpy as np
import itertools
from reportlab.lib.pagesizes import mm
from reportlab.pdfgen import canvas

# ==========================================================
# 1. 프린터 미세 보정 (출력 후 위치가 어긋나면 이 값을 조절)
# ==========================================================
OFFSET_X = 0.0 * mm  # 양수: 오른쪽 이동, 음수: 왼쪽 이동
OFFSET_Y = 0.0 * mm  # 양수: 위로 이동, 음수: 아래로 이동

# 로또 OMR 용지 규격 (실측 66mm x 150mm)
PAGE_WIDTH = 66.0 * mm
PAGE_HEIGHT = 150.0 * mm

# 마킹 사각형 크기 (약 3.5mm x 1.4mm)
MARK_W = 3.6 * mm
MARK_H = 1.3 * mm

# OMR 마크 좌표 기준 (A 게임 1번 위치 기준)
# 용지 하단(0,0) 기준: A게임은 용지 위쪽에 위치
START_X_NUM1 = 57.0 * mm + OFFSET_X  # 1번 열의 X 좌표 (우측)
COL_STEP_X = -5.1 * mm  # 열 간격 (왼쪽으로 이동)

START_Y_GAME_A = 117.5 * mm + OFFSET_Y  # A게임 첫번째 줄(1,8,15...) Y 좌표
ROW_STEP_Y = -2.9 * mm  # 같은 게임 내 줄 간격 (아래로 이동)
GAME_STEP_Y = -21.4 * mm  # 게임 간(A->B->C->D->E) 간격


def get_number_coord(game_idx, number):
    """
    game_idx: 0(A), 1(B), 2(C), 3(D), 4(E)
    number: 1 ~ 45
    """
    col = (number - 1) // 7  # 0~6열
    row = (number - 1) % 7  # 0~6행

    x = START_X_NUM1 + (col * COL_STEP_X)
    y = START_Y_GAME_A + (game_idx * GAME_STEP_Y) + (row * ROW_STEP_Y)
    return x, y


def generate_lotto_slip_pdf(combinations_10, output_pdf_name="lotto_print.pdf"):
    """
    10개 조합을 5개씩 나누어 2페이지짜리 OMR 마킹 PDF로 생성
    """
    c = canvas.Canvas(output_pdf_name, pagesize=(PAGE_WIDTH, PAGE_HEIGHT))

    # 2장 생성 (각 장당 5게임)
    for sheet_idx in range(2):
        games = combinations_10[sheet_idx * 5: (sheet_idx + 1) * 5]

        # 검은색 마킹 설정
        c.setFillColorRGB(0, 0, 0)

        for g_idx, numbers in enumerate(games):
            for num in numbers:
                x, y = get_number_coord(g_idx, num)
                # OMR 마킹 바 그리기 (중심 정렬)
                c.rect(x - (MARK_W / 2), y - (MARK_H / 2), MARK_W, MARK_H, fill=1, stroke=0)

        c.showPage()  # 페이지 넘김

    c.save()
    print(f"▶ '{output_pdf_name}' 파일이 생성되었습니다. (총 2페이지)")


# ==========================================================
# 2. 1245회차 10개 추천 번호 생성 및 PDF 출력 실행
# ==========================================================
if __name__ == "__main__":
    # 앞서 도출한 1245회차 10개 조합
    combs = [
        [19, 25, 33, 37, 39, 40],  # 1순위 (Top 6)
        [12, 19, 21, 33, 39, 40],
        [19, 20, 29, 33, 39, 40],
        [12, 25, 29, 33, 39, 40],
        [20, 21, 25, 33, 39, 40],
        [12, 19, 33, 36, 37, 39],
        [12, 20, 33, 37, 39, 40],
        [19, 20, 25, 33, 36, 39],
        [12, 19, 25, 33, 39, 42],
        [19, 20, 21, 33, 39, 42]
    ]

    generate_lotto_slip_pdf(combs, "lotto_slip_1245.pdf")