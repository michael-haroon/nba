"""Generate all analysis plots for winner target feature importance."""
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.colors import ListedColormap
import pandas as pd
import numpy as np
from pathlib import Path
import json

base = Path('output/features/winner')
report = pd.read_csv(base / 'filtered/feature_report.csv')
sfi = pd.read_csv(base / 'importance_sfi.csv', index_col=0)
null_logloss = sfi['null_log_loss'].iloc[0]

accepted = report[report['tier'] == 'ACCEPTED'].sort_values('composite_rank')
needs = report[report['tier'] == 'NEEDS SPECIFICATION'].copy()

def pattern_label(r):
    parts = []
    if r.mdi_passes: parts.append('MDI')
    if r.sfi_passes: parts.append('SFI')
    if r.pca_mda_passes: parts.append('PCA')
    if r.resid_mda_passes: parts.append('RESID')
    return '+'.join(parts) if parts else 'NONE'

needs['pattern'] = needs.apply(pattern_label, axis=1)

# ─────────────────────────────────────────────────────────────────────
# PLOT 1: Accepted features — all 4 methods scores
# ─────────────────────────────────────────────────────────────────────
fig, axes = plt.subplots(2, 2, figsize=(16, 14))
fig.suptitle('ACCEPTED Features (28) — All 4 Methods Pass\nWinner Target', fontsize=14, fontweight='bold')

y = range(len(accepted))

ax = axes[0, 0]
ax.barh(y, accepted['mdi_mean'], xerr=[accepted['mdi_mean'] - accepted['mdi_ci_lo'],
        accepted['mdi_ci_hi'] - accepted['mdi_mean']], color='steelblue', alpha=0.7, capsize=3)
ax.set_yticks(y)
ax.set_yticklabels(accepted['feature'], fontsize=7)
ax.set_xlabel('MDI Mean Importance')
ax.set_title('MDI (In-sample, Tree Impurity)')
ax.axvline(0, color='red', linestyle='--', alpha=0.5)
ax.invert_yaxis()

ax = axes[0, 1]
sfi_improvement = null_logloss - accepted['sfi_mean'].values
ax.barh(y, sfi_improvement, color='forestgreen', alpha=0.7)
ax.set_yticks(y)
ax.set_yticklabels(accepted['feature'], fontsize=7)
ax.set_xlabel('Log-loss improvement over null')
ax.set_title(f'SFI (Standalone, vs null={null_logloss:.4f})')
ax.axvline(0, color='red', linestyle='--', alpha=0.5)
ax.invert_yaxis()

ax = axes[1, 0]
ax.barh(y, accepted['pca_mda_mean'], color='darkorange', alpha=0.7)
ax.set_yticks(y)
ax.set_yticklabels(accepted['feature'], fontsize=7)
ax.set_xlabel('PCA-MDA Mean Accuracy Loss')
ax.set_title('PCA-MDA (Feature contribution in PCA space)')
ax.axvline(0, color='red', linestyle='--', alpha=0.5)
ax.invert_yaxis()

ax = axes[1, 1]
ax.barh(y, accepted['resid_mda_mean'], color='mediumpurple', alpha=0.7)
ax.set_yticks(y)
ax.set_yticklabels(accepted['feature'], fontsize=7)
ax.set_xlabel('Residual-MDA Mean (unique info after denoising)')
ax.set_title('Residual-MDA (Unique orthogonalized contribution)')
ax.axvline(0, color='red', linestyle='--', alpha=0.5)
ax.invert_yaxis()

plt.tight_layout()
plt.savefig(base / 'analysis_accepted_features.png', dpi=150, bbox_inches='tight')
plt.close()
print('Saved: analysis_accepted_features.png')

# ─────────────────────────────────────────────────────────────────────
# PLOT 2: SFI distribution — standalone predictive power
# ─────────────────────────────────────────────────────────────────────
fig, ax = plt.subplots(figsize=(14, 6))
improvement_all = null_logloss - report['sfi_mean'].values

colors = []
for _, r in report.iterrows():
    if r['tier'] == 'ACCEPTED':
        colors.append('green')
    elif r['tier'] == 'REJECTED':
        colors.append('red')
    else:
        colors.append('gray')

sorted_idx = np.argsort(improvement_all)[::-1]
ax.bar(range(len(improvement_all)), improvement_all[sorted_idx],
       color=[colors[i] for i in sorted_idx], alpha=0.6, width=1.0)
ax.axhline(0, color='black', linewidth=1)
ax.set_xlabel('Feature rank (sorted by standalone improvement)')
ax.set_ylabel('Log-loss improvement over null baseline')
ax.set_title(f'SFI: Standalone Feature Importance — All 1719 Features\n(null baseline = {null_logloss:.6f}, positive = better than random)')

green_patch = mpatches.Patch(color='green', alpha=0.6, label='ACCEPTED (28)')
gray_patch = mpatches.Patch(color='gray', alpha=0.6, label='NEEDS SPECIFICATION (1686)')
red_patch = mpatches.Patch(color='red', alpha=0.6, label='REJECTED (5)')
ax.legend(handles=[green_patch, gray_patch, red_patch])
plt.tight_layout()
plt.savefig(base / 'analysis_sfi_distribution.png', dpi=150, bbox_inches='tight')
plt.close()
print('Saved: analysis_sfi_distribution.png')

# ─────────────────────────────────────────────────────────────────────
# PLOT 3: Method disagreement heatmap for top 80 features
# ─────────────────────────────────────────────────────────────────────
top_n = 80
top = report.sort_values('composite_rank').head(top_n).copy()

fig, ax = plt.subplots(figsize=(10, 20))
method_cols = ['mdi_passes', 'sfi_passes', 'pca_mda_passes', 'resid_mda_passes']
method_labels = ['MDI', 'SFI', 'PCA-MDA', 'Resid-MDA']
matrix = top[method_cols].values.astype(float)

cmap = ListedColormap(['#ff4444', '#44bb44'])
ax.imshow(matrix, aspect='auto', cmap=cmap, interpolation='nearest')
ax.set_xticks(range(4))
ax.set_xticklabels(method_labels, fontsize=10)
ax.set_yticks(range(len(top)))
labels = []
for _, r in top.iterrows():
    tier_mark = "✓" if r['tier'] == 'ACCEPTED' else " "
    labels.append(f"{tier_mark} {r['feature']}")
ax.set_yticklabels(labels, fontsize=6)
ax.set_title(f'Method Pass/Fail — Top {top_n} Features by Composite Rank\n(Green=Pass, Red=Fail)', fontsize=12)
plt.tight_layout()
plt.savefig(base / 'analysis_method_disagreement.png', dpi=150, bbox_inches='tight')
plt.close()
print('Saved: analysis_method_disagreement.png')

# ─────────────────────────────────────────────────────────────────────
# PLOT 4: Pattern-specific scatter plots
# ─────────────────────────────────────────────────────────────────────
fig, axes = plt.subplots(1, 2, figsize=(16, 7))

palette = {'MDI+PCA': '#999999', 'MDI+PCA+RESID': '#ff8800', 'PCA+RESID': '#0088ff',
           'PCA': '#cccccc', 'MDI+SFI+PCA': '#aa00aa'}

ax = axes[0]
for pat in ['PCA', 'MDI+PCA', 'MDI+PCA+RESID', 'PCA+RESID', 'MDI+SFI+PCA']:
    subset = needs[needs['pattern'] == pat]
    sfi_imp = null_logloss - subset['sfi_mean']
    ax.scatter(sfi_imp, subset['resid_mda_mean'],
              alpha=0.3, s=15, label=f'{pat} ({len(subset)})',
              color=palette.get(pat, 'gray'))

sfi_imp_acc = null_logloss - accepted['sfi_mean']
ax.scatter(sfi_imp_acc, accepted['resid_mda_mean'],
          alpha=0.9, s=80, label=f'ACCEPTED ({len(accepted)})',
          color='green', marker='*', edgecolors='black', linewidths=0.5)

ax.axhline(0, color='red', linestyle='--', alpha=0.4)
ax.axvline(0, color='red', linestyle='--', alpha=0.4)
ax.set_xlabel('SFI Improvement (log-loss reduction over null)')
ax.set_ylabel('Residual-MDA (unique orthogonalized contribution)')
ax.set_title('SFI vs Residual-MDA by Pattern')
ax.legend(fontsize=7, loc='upper left')

ax = axes[1]
for pat in ['PCA', 'MDI+PCA', 'MDI+PCA+RESID', 'PCA+RESID', 'MDI+SFI+PCA']:
    subset = needs[needs['pattern'] == pat]
    sfi_imp = null_logloss - subset['sfi_mean']
    ax.scatter(sfi_imp, subset['mdi_mean'],
              alpha=0.3, s=15, label=f'{pat} ({len(subset)})',
              color=palette.get(pat, 'gray'))

sfi_imp_acc = null_logloss - accepted['sfi_mean']
ax.scatter(sfi_imp_acc, accepted['mdi_mean'],
          alpha=0.9, s=80, label=f'ACCEPTED ({len(accepted)})',
          color='green', marker='*', edgecolors='black', linewidths=0.5)

ax.axhline(0, color='red', linestyle='--', alpha=0.4)
ax.axvline(0, color='red', linestyle='--', alpha=0.4)
ax.set_xlabel('SFI Improvement (log-loss reduction over null)')
ax.set_ylabel('MDI (In-sample tree importance)')
ax.set_title('MDI vs SFI by Pattern')
ax.legend(fontsize=7, loc='upper left')
plt.tight_layout()
plt.savefig(base / 'analysis_pattern_scatter.png', dpi=150, bbox_inches='tight')
plt.close()
print('Saved: analysis_pattern_scatter.png')

# ─────────────────────────────────────────────────────────────────────
# PLOT 5: Top 30 "nearly accepted" features (3/4 methods pass)
# ─────────────────────────────────────────────────────────────────────
three_pass = needs[needs['n_methods_passed'] == 3].sort_values('composite_rank').head(30)

fig, axes = plt.subplots(1, 3, figsize=(18, 10))

ax = axes[0]
sfi_imp = null_logloss - three_pass['sfi_mean']
colors_sfi = ['forestgreen' if r['sfi_passes'] else '#cc0000' for _, r in three_pass.iterrows()]
ax.barh(range(len(three_pass)), sfi_imp, color=colors_sfi, alpha=0.7)
ax.set_yticks(range(len(three_pass)))
ax.set_yticklabels(three_pass['feature'], fontsize=7)
ax.axvline(0, color='black', linewidth=1)
ax.set_xlabel('SFI: Log-loss improvement over null')
ax.set_title('Top 30 "Nearly Accepted" (3/4 pass)\nSFI Score (green=pass, red=fail)')
ax.invert_yaxis()

ax = axes[1]
colors_mdi = ['steelblue' if r['mdi_passes'] else '#cc0000' for _, r in three_pass.iterrows()]
ax.barh(range(len(three_pass)), three_pass['mdi_mean'], color=colors_mdi, alpha=0.7)
ax.set_yticks(range(len(three_pass)))
ax.set_yticklabels(three_pass['feature'], fontsize=7)
ax.set_xlabel('MDI Mean')
ax.set_title('MDI Score (blue=pass, red=fail)')
ax.invert_yaxis()

ax = axes[2]
colors_res = ['mediumpurple' if r['resid_mda_passes'] else '#cc0000' for _, r in three_pass.iterrows()]
ax.barh(range(len(three_pass)), three_pass['resid_mda_mean'], color=colors_res, alpha=0.7)
ax.set_yticks(range(len(three_pass)))
ax.set_yticklabels(three_pass['feature'], fontsize=7)
ax.set_xlabel('Residual-MDA Mean')
ax.set_title('Residual-MDA Score (purple=pass, red=fail)')
ax.invert_yaxis()

plt.tight_layout()
plt.savefig(base / 'analysis_nearly_accepted.png', dpi=150, bbox_inches='tight')
plt.close()
print('Saved: analysis_nearly_accepted.png')

# ─────────────────────────────────────────────────────────────────────
# PLOT 6: Distribution of scores by pattern group (boxplots)
# ─────────────────────────────────────────────────────────────────────
fig, axes = plt.subplots(2, 2, figsize=(14, 10))
fig.suptitle('Score Distributions by Failure Pattern Group', fontsize=13, fontweight='bold')

patterns_order = ['MDI+PCA', 'MDI+PCA+RESID', 'PCA+RESID', 'PCA', 'MDI+SFI+PCA']
pattern_colors = ['#999999', '#ff8800', '#0088ff', '#cccccc', '#aa00aa']

ax = axes[0, 0]
data_sfi = [null_logloss - needs[needs['pattern'] == p]['sfi_mean'].values for p in patterns_order]
bp = ax.boxplot(data_sfi, labels=[p.replace('+', '\n') for p in patterns_order],
                patch_artist=True, showfliers=False)
for patch, color in zip(bp['boxes'], pattern_colors):
    patch.set_facecolor(color)
    patch.set_alpha(0.5)
ax.axhline(0, color='red', linestyle='--', alpha=0.5)
ax.set_ylabel('SFI improvement over null')
ax.set_title('Standalone Predictive Power')

ax = axes[0, 1]
data_mdi = [needs[needs['pattern'] == p]['mdi_mean'].values for p in patterns_order]
bp = ax.boxplot(data_mdi, labels=[p.replace('+', '\n') for p in patterns_order],
                patch_artist=True, showfliers=False)
for patch, color in zip(bp['boxes'], pattern_colors):
    patch.set_facecolor(color)
    patch.set_alpha(0.5)
ax.axhline(0, color='red', linestyle='--', alpha=0.5)
ax.set_ylabel('MDI mean')
ax.set_title('Tree Impurity Importance')

ax = axes[1, 0]
data_pca = [needs[needs['pattern'] == p]['pca_mda_mean'].values for p in patterns_order]
bp = ax.boxplot(data_pca, labels=[p.replace('+', '\n') for p in patterns_order],
                patch_artist=True, showfliers=False)
for patch, color in zip(bp['boxes'], pattern_colors):
    patch.set_facecolor(color)
    patch.set_alpha(0.5)
ax.axhline(0, color='red', linestyle='--', alpha=0.5)
ax.set_ylabel('PCA-MDA mean')
ax.set_title('PCA Component Contribution')

ax = axes[1, 1]
data_res = [needs[needs['pattern'] == p]['resid_mda_mean'].values for p in patterns_order]
bp = ax.boxplot(data_res, labels=[p.replace('+', '\n') for p in patterns_order],
                patch_artist=True, showfliers=False)
for patch, color in zip(bp['boxes'], pattern_colors):
    patch.set_facecolor(color)
    patch.set_alpha(0.5)
ax.axhline(0, color='red', linestyle='--', alpha=0.5)
ax.set_ylabel('Residual-MDA mean')
ax.set_title('Unique Orthogonalized Info')

plt.tight_layout()
plt.savefig(base / 'analysis_pattern_distributions.png', dpi=150, bbox_inches='tight')
plt.close()
print('Saved: analysis_pattern_distributions.png')

# ─────────────────────────────────────────────────────────────────────
# PLOT 7: SFI gap — MDI+PCA+RESID pattern features vs SFI threshold
# ─────────────────────────────────────────────────────────────────────
sfi_fail_only = needs[needs['pattern'] == 'MDI+PCA+RESID'].sort_values('sfi_mean')
sfi_threshold = accepted['sfi_mean'].max()

fig, ax = plt.subplots(figsize=(14, 6))
sfi_vals = null_logloss - sfi_fail_only['sfi_mean'].values
sfi_vals_sorted = np.sort(sfi_vals)[::-1]

ax.bar(range(len(sfi_vals_sorted)), sfi_vals_sorted, color='darkorange', alpha=0.6, width=1.0)
ax.axhline(0, color='red', linewidth=2, label='Null baseline (no improvement)')

sfi_thresh_improvement = null_logloss - sfi_threshold
ax.axhline(sfi_thresh_improvement, color='green', linewidth=2, linestyle='--',
           label=f'Weakest accepted SFI ({sfi_thresh_improvement:.4f})')

above_thresh = np.sum(sfi_vals_sorted > sfi_thresh_improvement)
above_zero = np.sum(sfi_vals_sorted > 0)
ax.set_xlabel('Feature rank (MDI+PCA+RESID pattern, sorted by SFI)')
ax.set_ylabel('SFI improvement over null')
ax.set_title(f'MDI+PCA+RESID Pattern (304 features): How close to passing SFI?\n'
             f'{above_zero}/304 beat null, {above_thresh}/304 exceed weakest accepted threshold')
ax.legend()
plt.tight_layout()
plt.savefig(base / 'analysis_sfi_gap.png', dpi=150, bbox_inches='tight')
plt.close()
print('Saved: analysis_sfi_gap.png')

# ─────────────────────────────────────────────────────────────────────
# PLOT 8: Category breakdown
# ─────────────────────────────────────────────────────────────────────
def categorize_feature(name):
    if name.startswith('sf_'):
        return 'Symbolic/Random Combo'
    elif 'massey' in name or 'colley' in name:
        return 'Massey/Colley Rating'
    elif 'roll5' in name:
        return 'Rolling-5'
    elif 'roll10' in name:
        return 'Rolling-10'
    elif 'roll20' in name:
        return 'Rolling-20'
    elif 'venue' in name:
        return 'Venue-adjusted'
    elif 'h2h' in name:
        return 'Head-to-Head'
    elif 'bpi' in name or 'elo' in name or 'sag' in name or 'predictor' in name:
        return 'Power Rating'
    elif any(x in name for x in ['margin', 'streak', 'win_pct', 'pyth']):
        return 'Momentum/Form'
    elif 'log5' in name:
        return 'Implied Probability'
    else:
        return 'Other'

report['category'] = report['feature'].apply(categorize_feature)

fig, ax = plt.subplots(figsize=(12, 7))
cat_all = report['category'].value_counts()
cat_acc = report[report['tier'] == 'ACCEPTED']['category'].value_counts()
cat_acc_rate = (cat_acc / cat_all * 100).fillna(0).sort_values(ascending=True)

bars = ax.barh(range(len(cat_acc_rate)), cat_acc_rate.values, color='steelblue', alpha=0.7)
ax.set_yticks(range(len(cat_acc_rate)))
ax.set_yticklabels(cat_acc_rate.index, fontsize=9)
ax.set_xlabel('Acceptance Rate (%)')
ax.set_title('Feature Category Acceptance Rates\n(Higher = category has more signal for winner prediction)')
for i, (v, idx) in enumerate(zip(cat_acc_rate.values, cat_acc_rate.index)):
    count = int(cat_acc.get(idx, 0))
    total = int(cat_all.get(idx, 0))
    ax.text(v + 0.3, i, f'{count}/{total}', va='center', fontsize=8)

plt.tight_layout()
plt.savefig(base / 'analysis_category_breakdown.png', dpi=150, bbox_inches='tight')
plt.close()
print('Saved: analysis_category_breakdown.png')

print("\nAll plots generated successfully!")
