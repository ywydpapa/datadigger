import itertools
import numpy as np
import pandas as pd

# ==========================================
# 1. 설정 및 파라미터 (최적 백테스트 반영)
# ==========================================
TARGET_ROUND = 1245  # 목표 회차
W_PARAM = 20  # 최적 윈도우 크기 (최근 20회 이동평균)
ALPHA_PARAM = 1.0  # 적중률 최적화 가중치 (1.0 = 최근 20회 100% 반영)
CANDIDATE_POOL_SIZE = 12  # 조합 풀로 사용할 상위 후보 번호 개수 (12개 -> 924개 조합 생성)
CSV_FILE_PATH = "C:\\Users\\djkim\\Desktop\\lotto.csv"

# ==========================================
# 2. 데이터 로드 및 번호별 최적 점수 계산
# ==========================================
df = pd.read_csv(CSV_FILE_PATH,encoding='cp949')
df_sorted = df.sort_values('회차').reset_index(drop=True)
num_cols = ['번호1', '번호2', '번호3', '번호4', '번호5', '번호6']

# 목표 회차 이전 데이터만 반영
df_past = df_sorted[df_sorted['회차'] < TARGET_ROUND].copy()

candidate_stats = []
for num in range(1, 46):
    rounds = df_past[df_past[num_cols].isin([num]).any(axis=1)]['회차'].values
    if len(rounds) < 2:
        continue

    last_round = rounds[-1]
    intervals = np.diff(rounds)
    all_mean = np.mean(intervals)
    recent_intervals = intervals[-min(W_PARAM, len(intervals)):]
    recent_mean = np.mean(recent_intervals)

    # 최적 주기 및 예상 회차 계산
    est_interval = ALPHA_PARAM * recent_mean + (1.0 - ALPHA_PARAM) * all_mean
    pred_round = last_round + est_interval
    error = abs(TARGET_ROUND - pred_round)

    # 오차가 작을수록 높은 점수 부여
    score = 1.0 / (1.0 + error)

    # [수정 완료] 키 이름을 '예측회차'로 일치시켰습니다.
    candidate_stats.append({
        '번호': num,
        '최근출현': int(last_round),
        '미출현': int(df_past['회차'].max() - last_round),
        '추정주기': round(est_interval, 2),
        '예측회차': round(pred_round, 2),
        '오차': round(error, 2),
        '점수': score
    })

# 오차가 가장 작은 순서대로 상위 풀(Pool) 추출
cand_df = pd.DataFrame(candidate_stats).sort_values('오차').reset_index(drop=True)
pool_df = cand_df.head(CANDIDATE_POOL_SIZE)
pool_numbers = pool_df['번호'].tolist()
score_map = dict(zip(pool_df['번호'], pool_df['점수']))

print(f"=== [{TARGET_ROUND}회차 핵심 후보군 (Top {CANDIDATE_POOL_SIZE}개 번호)] ===")
print(pool_df[['번호', '최근출현', '미출현', '추정주기', '예측회차', '오차']].to_string(index=False))

# ==========================================
# 3. 10개 조합 생성 알고리즘
# ==========================================
# 1순위 조합: 상위 1~6위 번호 조합 (고정)
top1_combination = tuple(sorted(pool_numbers[:6]))

# 후보군(12개)으로 만들 수 있는 모든 6개 번호 조합 생성 (12C6 = 924개)
all_combinations = list(itertools.combinations(pool_numbers, 6))

scored_combinations = []
for comb in all_combinations:
    s_comb = tuple(sorted(comb))
    tot_score = sum(score_map[n] for n in s_comb)
    num_sum = sum(s_comb)
    odd_count = sum(1 for n in s_comb if n % 2 != 0)

    # 로또 통계적 균형 필터 (극단적인 합계나 올홀/올짝 배제)
    balanced_sum = 90 <= num_sum <= 185
    balanced_parity = 2 <= odd_count <= 4
    filter_passed = balanced_sum and balanced_parity

    scored_combinations.append({
        '조합': s_comb,
        '점수합계': tot_score,
        '총합': num_sum,
        '홀짝': f"{odd_count}:{6 - odd_count}",
        '필터통과': filter_passed
    })

# 필터 통과 우선, 점수 높은 순으로 정렬
sorted_comb_df = pd.DataFrame(scored_combinations).sort_values(
    by=['필터통과', '점수합계'], ascending=[False, False]
).reset_index(drop=True)

# 10개 조합 선별 (1순위 포함 및 조합 간 최대 중복수 4개 이하로 분산 적용)
selected_combinations = [top1_combination]

for _, row in sorted_comb_df.iterrows():
    cand = row['조합']
    if cand in selected_combinations:
        continue
    # 기존 선정된 조합들과 5개 이상 중복되지 않도록 분산 (다양성 확보)
    if all(len(set(cand) & set(prev)) <= 4 for prev in selected_combinations):
        selected_combinations.append(cand)
    if len(selected_combinations) == 10:
        break

# 분산 기준을 만족하는 조합이 모자랄 경우 상위 조합으로 보충
if len(selected_combinations) < 10:
    for _, row in sorted_comb_df.iterrows():
        cand = row['조합']
        if cand not in selected_combinations:
            selected_combinations.append(cand)
        if len(selected_combinations) == 10:
            break

# ==========================================
# 4. 최종 추천 10개 조합 출력
# ==========================================
print(f"\n=========================================================")
print(f"       [ {TARGET_ROUND}회차 최종 추천 10개 조합 ]")
print(f"=========================================================")

for idx, comb in enumerate(selected_combinations, 1):
    c_list = list(comb)
    comb_sum = sum(c_list)
    odds = sum(1 for x in c_list if x % 2 != 0)
    evens = 6 - odds

    tag = "★ 1순위 (TOP 6)" if idx == 1 else f"  조합 {idx:02d}          "
    nums_str = ", ".join(f"{x:02d}" for x in c_list)
    print(f"[{tag}]  [ {nums_str} ]  (합: {comb_sum:3d}, 홀짝: {odds}:{evens})")

print("=========================================================")