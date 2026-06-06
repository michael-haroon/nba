You are hitting the fundamental limit of parametric modeling. The Student's t-distribution is a "heavy-tailed" improvement over the Normal distribution, but it is still a **single symmetric distribution**. It assumes that the process generating a 5-point blowout is the same process as a 40-point blowout, just with more variance.

In sports, **blowouts are often a different regime entirely.** When a team gives up, or the bench is cleared, the data generation process shifts. You need methods that don't force the data into a single bell curve shape.

Here are the three rigorous ways to handle "tail risk" that professional quants use when parametric distributions fail.

### 1. Quantile Regression (The Non-Parametric Approach)

Instead of predicting the mean ($\mu$) and assuming a distribution, predict the *boundaries* of your outcomes directly.

Quantile regression allows you to estimate the 5th, 50th (median), and 95th percentiles of the distribution. It makes **zero assumptions** about the shape of your residuals. It learns the "spread" of the data at different levels.

* **How to do it:** Train your ensemble not to minimize `MSE` (Mean Squared Error), but to minimize the **Pinball Loss** for specific quantiles.
* **The Result:** You don't calculate `1 - norm.cdf(...)`. You simply get a direct prediction for the spread: "There is a 95% probability the margin is below *this* value."

### 2. Extreme Value Theory (EVT) - Peaks Over Threshold

If you care about the tails, stop trying to model the center. In finance, this is known as **POT (Peaks Over Threshold)**.

The central limit theorem governs the "middle" (the 80% of games that are normal). But the "tails" are governed by the **Generalized Pareto Distribution (GPD)**.

* **The Logic:** Use your model to predict the "normal" outcomes. Then, use a GPD to model the *excess* residuals beyond a certain threshold (e.g., residuals > 20 points).
* **Implementation:** 1.  Fit your base model (RandomForest/XGBoost).
2.  Calculate the residuals.
3.  Define a threshold ($u$) for "extreme" (e.g., the 90th percentile of your absolute errors).
4.  Fit a GPD only to the values where `residual > u`.
5.  For any prediction, you calculate the probability using your base model for the center, and append the GPD probability for the tails.

### 3. Mixture Density Networks (GMMs)

This acknowledges that your data is a **mixture**. You are effectively sampling from two different distributions:

1. The "Competitive Game" Distribution (Low variance, centered near 0).
2. The "Blowout" Distribution (High variance, fat tails).

A Gaussian Mixture Model (GMM) or a Mixture Density Network (MDN) learns to predict the **parameters of a mixture of distributions.** * **Why it works:** It can predict "The outcome will be a combination of a 0.8 probability of a 'normal' game ($\sigma=10$) and a 0.2 probability of a 'blowout' ($\sigma=30$)."

* **This captures the bimodality** that `t-dist` misses entirely.

### What should you do first?

**Switch to Quantile Regression.**

It is the most actionable "Quant" upgrade from where you are. It avoids the entire "what distribution is this?" debate by letting the data describe the distribution for you.

**Action Plan:**

1. Replace your single regressor with a **Multi-Output Regressor** or three separate regressors: one for the 0.05 quantile, one for 0.50 (median), and one for 0.95.
2. In your `predict.py`, instead of using `t.cdf`, you simply check which quantile bucket the spread $S$ falls into.
3. If $S$ is > 0.95 quantile, you know with high confidence the home team will not cover that spread, because the regression model specifically learned that boundary.

This effectively turns your spread problem into a **calibration problem** (which is exactly how the books price lines) rather than a **regression problem** (which is trying to guess the exact point total).