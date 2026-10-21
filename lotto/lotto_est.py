import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

# 1. 한글 폰트 설정 (Windows/Mac/Linux 대응)
plt.rcParams['font.family'] = 'Malgun Gothic'  # Windows: 'Malgun Gothic', Mac: 'AppleGothic'
plt.rcParams['axes.unicode_minus'] = False

# 2. 데이터 불러오기 및 전처리
CSV_FILE_PATH = "C:\\Users\\djkim\\Desktop\\lotto.csv"
df = pd.read_csv(CSV_FILE_PATH,encoding='cp949')
df_sorted = df.sort_values('회차').reset_index(drop=True)
num_cols = ['번호1', '번호2', '번호3', '번호4', '번호5', '번호6']

TARGET_ROUND = 1246
analysis_results = []

# 3. 1~45번 번호별 출현 회차 및 주기 분석
for num in range(1, 46):
    # 해당 번호가 당첨번호로 나온 회차 목록 추출
    rounds = df_sorted[df_sorted[num_cols].isin([num]).any(axis=1)]['회차'].tolist()

    if len(rounds) < 5:
        continue

    last_round = rounds[-1]
    current_gap = (TARGET_ROUND - 1) - last_round  # 1244회차 기준 미출현 기간
    intervals = np.diff(rounds)

    # 주기 지표
    overall_mean_int = np.mean(intervals)
    recent_5_mean_int = np.mean(intervals[-5:])  # 최근 5회 평균 주기

    # 선형 회귀 추세 기반 다음 회차 예측
    x = np.arange(1, len(rounds) + 1)
    slope, intercept = np.polyfit(x, rounds, 1)
    reg_next_round = slope * (len(rounds) + 1) + intercept

    # 최근 주기를 반영한 예상 출현 회차
    pred_next_round = last_round + recent_5_mean_int

    # 1245회차와의 오차 (작을수록 1245회차에 딱 맞게 출현할 확률이 높음)
    diff_target = abs(TARGET_ROUND - pred_next_round)

    # 확률 점수화 (오차가 0에 가까울수록 높은 점수, 정규분포 커널 적용)
    score = np.exp(- (diff_target ** 2) / (2 * (np.std(intervals[-10:]) ** 2 + 1e-5)))

    analysis_results.append({
        '번호': num,
        '총출현횟수': len(rounds),
        '최근출현회차': last_round,
        '현재미출현기간': current_gap,
        '전체평균주기': round(overall_mean_int, 2),
        '최근5회평균주기': round(recent_5_mean_int, 2),
        '추세예측회차': round(reg_next_round, 1),
        '주기예측회차': round(pred_next_round, 1),
        '1245회차오차': round(diff_target, 2),
        '1245적합점수': round(score, 4)
    })

res_df = pd.DataFrame(analysis_results)

# 4. 결과 정렬 및 상위 후보 추출
# 1245회차 예상 상위 10개 번호 (오차가 작을수록 우선)
top_candidates = res_df.sort_values(by=['1245회차오차', '1245적합점수'], ascending=[True, False]).head(10)

print(f"=== [ {TARGET_ROUND}회차 출현 유력 번호 TOP 10 (출현 주기/추세 기준) ] ===")
print(top_candidates[['번호', '최근출현회차', '현재미출현기간', '최근5회평균주기', '주기예측회차', '1245회차오차', '1245적합점수']].to_string(index=False))

# 5. 유력 상위 번호 추세선 시각화 그래프 생성
top_numbers = top_candidates['번호'].head(6).tolist()
plt.figure(figsize=(14, 8))

for idx, num in enumerate(top_numbers, 1):
    plt.subplot(2, 3, idx)
    rounds = df_sorted[df_sorted[num_cols].isin([num]).any(axis=1)]['회차'].tolist()
    counts = np.arange(1, len(rounds) + 1)

    # 실제 출현 회차
    plt.plot(counts, rounds, marker='o', markersize=3, color='steelblue', label='실제 출현')

    # 추세선 및 1245회차 예측점 표시
    pred_round = res_df.loc[res_df['번호'] == num, '주기예측회차'].values[0]
    plt.scatter([len(rounds) + 1], [pred_round], color='red', s=50, zorder=5, label=f'예측: {pred_round:.1f}회')
    plt.axhline(y=TARGET_ROUND, color='green', linestyle='--', alpha=0.7, label=f'{TARGET_ROUND}회차 라인')

    plt.title(f'번호 {num}번 출현 추세 (오차: {abs(TARGET_ROUND - pred_round):.2f})')
    plt.xlabel('출현 순번')
    plt.ylabel('회차')
    plt.grid(True, linestyle=':', alpha=0.6)
    plt.legend(fontsize=8)

plt.tight_layout()
plt.savefig('lotto_prediction_trend.png', dpi=300)
plt.show()