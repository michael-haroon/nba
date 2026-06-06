"""Analyze winner target feature importance results."""
import json
import pandas as pd
import numpy as np
from pathlib import Path

base = Path('output/features/winner')
recipes_list = json.load(open(base / 'symbolic_recipes.json'))
recipes = {r['name']: r for r in recipes_list}
report = pd.read_csv(base / 'filtered/feature_report.csv')
sfi = pd.read_csv(base / 'importance_sfi.csv', index_col=0)
null_logloss = sfi['null_log_loss'].iloc[0]
accepted = report[report['tier'] == 'ACCEPTED']
sf_accepted = accepted[accepted['feature'].str.startswith('sf_')]

print("=" * 70)
print("SYMBOLIC FEATURES IN ACCEPTED SET")
print("=" * 70)
for _, row in sf_accepted.iterrows():
    name = row['feature']
    r = recipes.get(name, {})
    cols = r.get('columns', [])
    op = r.get('operation', '?')
    unary = r.get('unary', None)
    sfi_imp = null_logloss - row['sfi_mean']
    col_str = ", ".join(cols)
    desc = f"{op}({col_str})"
    if unary:
        desc += f" -> {unary}"
    print(f"\n  {name}: {desc}")
    print(f"    SFI_imp={sfi_imp:.6f}  MDI={row['mdi_mean']:.4f}  RESID={row['resid_mda_mean']:.2e}  rank={row['composite_rank']:.0f}")

print()
print("=" * 70)
print("KEY THRESHOLDS")
print("=" * 70)
sfi_threshold = accepted['sfi_mean'].max()
print(f"  Null log-loss: {null_logloss:.6f}")
print(f"  Weakest accepted SFI: {sfi_threshold:.6f} (improvement: {null_logloss - sfi_threshold:.6f})")
resid_threshold = accepted['resid_mda_mean'].min()
print(f"  Weakest accepted Residual-MDA: {resid_threshold:.2e}")
mdi_threshold = accepted['mdi_mean'].min()
print(f"  Weakest accepted MDI: {mdi_threshold:.6f}")

# Also show the 49 "absorbed" features
print()
print("=" * 70)
print("ABSORBED PATTERN (49): Pass MDI+SFI+PCA but fail RESID-MDA")
print("These features predict alone but add nothing new to the accepted set")
print("=" * 70)
needs = report[report['tier'] == 'NEEDS SPECIFICATION']
absorbed = needs[
    (needs['mdi_passes'] == True) &
    (needs['sfi_passes'] == True) &
    (needs['pca_mda_passes'] == True) &
    (needs['resid_mda_passes'] == False)
].sort_values('composite_rank')

for _, row in absorbed.iterrows():
    sfi_imp = null_logloss - row['sfi_mean']
    print(f"  {row['feature']:45s} SFI_imp={sfi_imp:.4f}  MDI={row['mdi_mean']:.3f}  RESID={row['resid_mda_mean']:.2e}")
