"""Two-sample Kolmogorov-Smirnov statistic and asymptotic p-value.

Implements the KS statistic via a merged walk over two sorted
samples (O(n1+n2)) and the Smirnov asymptotic series for the
two-sample p-value. No external dependencies — pure Python.
"""

from __future__ import annotations

import math


def ks_statistic(r: list[float], s: list[float]) -> float:
    """Two-sample KS statistic: max |ecdf_r(x) - ecdf_s(x)|.

    Walks both sorted samples in lockstep, accumulating the
    empirical CDF counts and tracking the maximum absolute
    difference. Ties are advanced on both sides so identical
    inputs give d = 0. O(n1 + n2), no per-step sorting.
    """
    n1, n2 = len(r), len(s)
    d = c1 = c2 = 0.0
    i1 = i2 = 0
    while i1 < n1 or i2 < n2:
        if i1 >= n1:
            c2 += 1.0
            i2 += 1
        elif i2 >= n2:
            c1 += 1.0
            i1 += 1
        elif r[i1] < s[i2]:
            c1 += 1.0
            i1 += 1
        elif r[i1] > s[i2]:
            c2 += 1.0
            i2 += 1
        else:  # tied: advance both ECDFs together
            c1 += 1.0
            c2 += 1.0
            i1 += 1
            i2 += 1
        d = max(d, abs(c1 / n1 - c2 / n2))
    return d


def ks_pvalue(d: float, n1: int, n2: int) -> float:
    """Two-sample KS p-value via Smirnov's asymptotic series.

    Q(λ) = 2 * Σ_{j=1}^∞ (-1)^(j-1) * exp(-2 * j^2 * λ^2)
    where λ = sqrt(n1*n2/(n1+n2)) * d. Truncates when the next
    term contributes < 1e-12.
    """
    if n1 == 0 or n2 == 0 or d <= 0.0:
        return 1.0
    en = math.sqrt(n1 * n2 / (n1 + n2)) * d
    if en < 1e-10:
        return 1.0
    psum = 0.0
    for j in range(1, 200):
        t = 2 * ((-1) ** (j - 1)) * math.exp(-2 * (j * en) ** 2)
        psum += t
        if abs(t) < 1e-12:
            break
    return min(1.0, max(0.0, psum))
