import os
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

# ==========================================
# 1. 환경 및 파라미터 설정
# ==========================================
# 한글 폰트 설정 (Windows: Malgun Gothic, Mac: AppleGothic, Linux: NanumGothic)
plt.rcParams['font.family'] = 'Malgun Gothic'
plt.rcParams['axes.unicode_minus'] = False

# 백테스팅으로 도출된 최적 파라미터 선택
# MODEL_TYPE:
#   - 'HIT_MAX' : 적중률 극대화 모델 (최근 20회 이동평균, w=20, alpha=1.0)
#   - 'BALANCED': 오차-적중 균형 모델 (최근 8회 60% + 전체 40%, w=8, alpha=0.6)
#   - 'MAE_MIN' : 절대오차 최소화 모델 (최근 20회 10% + 전체 90%, w=20, alpha=0.1)
MODEL_TYPE = 'BALANCED'
TARGET_ROUND = 1246  # 예측하고자 하는 목표 회차
CSV_FILE_PATH = "C:\\Users\\djkim\\Desktop\\lotto.csv"

# 모델별 하이퍼파라미터 셋업
CONFIG = {
    'HIT_MAX': {'w': 30, 'alpha': 1.0, 'desc': '적중률 최우선 모델 (최근 30회 주기 100%)'},
    'BALANCED': {'w': 20, 'alpha': 0.6, 'desc': '균형 가중 모델 (최근 20회 60% + 전체 40%)'},
    'MAE_MIN': {'w': 20, 'alpha': 0.1, 'desc': '오차 최소화 모델 (최근 20회 10% + 전체 90%)'}
}

# ==========================================
# 2. 데이터 로드 및 전처리
# ==========================================
if not os.path.exists(CSV_FILE_PATH):
    raise FileNotFoundError(f"'{CSV_FILE_PATH}' 파일을 찾을 수 없습니다.")

df = pd.read_csv(CSV_FILE_PATH,encoding='cp949')
df_sorted = df.sort_values('회차').reset_index(drop=True)
num_cols = ['번호1', '번호2', '번호3', '번호4', '번호5', '번호6']

# 분석에 사용할 과거 회차만 필터링 (TARGET_ROUND 이전 데이터)
df_past = df_sorted[df_sorted['회차'] < TARGET_ROUND].copy()
last_available_round = df_past['회차'].max()

w_param = CONFIG[MODEL_TYPE]['w']
alpha_param = CONFIG[MODEL_TYPE]['alpha']

print("=" * 60)
print(f" [로또 번호 예측 시스템] - 목표: {TARGET_ROUND}회차")
print(f" 적용 모델 : {MODEL_TYPE} ({CONFIG[MODEL_TYPE]['desc']})")
print(f" 학습 데이터: 1회 ~ {last_available_round}회")
print("=" * 60)

# ==========================================
# 3. 1~45번 번호별 최적 주기 및 예측치 계산
# ==========================================
prediction_rows = []

for num in range(1, 46):
    # 해당 번호가 당첨된 과거 회차 배열
    rounds = df_past[df_past[num_cols].isin([num]).any(axis=1)]['회차'].values
    if len(rounds) < 2:
        continue

    last_appearance = rounds[-1]
    intervals = np.diff(rounds)

    # 1) 전체 평균 주기
    all_mean_int = np.mean(intervals)

    # 2) 최적 윈도우(w) 기반 최근 이동평균 주기
    recent_intervals = intervals[-min(w_param, len(intervals)):]
    recent_mean_int = np.mean(recent_intervals)

    # 3) 가중 결합 주기 산출 (alpha 반영)
    estimated_interval = alpha_param * recent_mean_int + (1.0 - alpha_param) * all_mean_int

    # 4) 다음 예상 출현 회차 계산
    predicted_round = last_appearance + estimated_interval

    # 5) 목표 회차와의 오차 및 미출현 간격
    error = abs(TARGET_ROUND - predicted_round)
    current_gap = last_available_round - last_appearance

    # 표준편차 기반 적합도 점수 (오차가 작을수록 1에 수렴)
    std_val = np.std(recent_intervals) if len(recent_intervals) > 1 else 1.0
    score = np.exp(- (error ** 2) / (2 * (std_val ** 2 + 1e-4)))

    prediction_rows.append({
        '번호': num,
        '최근출현회차': last_appearance,
        '현재미출현': current_gap,
        '최근주기': round(recent_mean_int, 2),
        '추정주기': round(estimated_interval, 2),
        '예측회차': round(predicted_round, 2),
        '목표오차': round(error, 2),
        '적합점수': round(score, 4)
    })

res_df = pd.DataFrame(prediction_rows)

# 목표 회차와의 오차가 가장 작은 순서대로 정렬
ranked_df = res_df.sort_values(by=['목표오차', '적합점수'], ascending=[True, False]).reset_index(drop=True)

# ==========================================
# 4. 분석 결과 출력
# ==========================================
top_15 = ranked_df.head(15)
top_6 = ranked_df.head(6)

print(f"\n▶ [{TARGET_ROUND}회차 추천 번호 TOP 10]")
print(top_15[['번호', '최근출현회차', '현재미출현', '추정주기', '예측회차', '목표오차', '적합점수']].to_string(index=False))

print(f"\n★ 1순위 추천 조합 (Top 6): {sorted(top_6['번호'].tolist())}")

# ==========================================
# 5. 상위 추천 번호 추세 시각화 그래프 저장
# ==========================================
plt.figure(figsize=(15, 8))
plt.suptitle(f"{TARGET_ROUND}회차 유력 후보 번호 출현 추세선 분석 ({MODEL_TYPE} 모델)", fontsize=15, fontweight='bold')

for i, num in enumerate(top_6['번호'], 1):
    plt.subplot(2, 3, i)
    rounds = df_past[df_past[num_cols].isin([num]).any(axis=1)]['회차'].values
    counts = np.arange(1, len(rounds) + 1)

    # 실제 출현 이력
    plt.plot(counts, rounds, marker='o', markersize=3.5, color='#1f77b4', label='과거 출현 회차')

    # 목표 예측 위치
    pred_val = ranked_df.loc[ranked_df['번호'] == num, '예측회차'].values[0]
    err_val = ranked_df.loc[ranked_df['번호'] == num, '목표오차'].values[0]

    plt.scatter([len(rounds) + 1], [pred_val], color='red', s=60, zorder=5, label=f'예측: {pred_val}회')
    plt.axhline(y=TARGET_ROUND, color='green', linestyle='--', alpha=0.7, label=f'목표 {TARGET_ROUND}회')

    plt.title(f"번호 {num}번 (오차: {err_val:.2f}회)", fontsize=11, fontweight='bold')
    plt.xlabel("출현 순번")
    plt.ylabel("회차")
    plt.grid(True, linestyle=':', alpha=0.6)
    plt.legend(fontsize=8, loc='upper left')

plt.tight_layout()
output_img = f"lotto_{TARGET_ROUND}_prediction.png"
plt.savefig(output_img, dpi=300)
print(f"\n[안내] 시각화 그래프가 '{output_img}' 파일로 저장되었습니다.")