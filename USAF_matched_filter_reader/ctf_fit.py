#!/usr/bin/env python3
"""
CTF curve fit for usaf_reader results.

The reader measures a Michelson contrast for each element. Those values are steps: the
limit can only be a whole element, and one noisy element near the threshold decides it.
This module fits a physical model to all the measured contrasts at once, separately for
horizontal (H) and vertical (V) lines, and reports where the fitted curve crosses the
contrast threshold, as a continuous frequency with an uncertainty.

Model (per direction): three bars of width w and gaps w,
    blurred by a Gaussian PSF (sigma, the fitted blur),
    averaged over the camera pixel (a square of the fitted pixel size, at the image's tilt),
    plus a uniform stray-light level f relative to the bar brightness (fitted).
Real lenses often have a sharp core with wider wings, which makes the contrast fall off more
gently than one Gaussian allows. A second, wider Gaussian (the halo: fraction a, width
sigma_halo) is therefore also tried, and kept only when it fits clearly better (BIC).
Bright bars:  C = (b - g) / (b + g + 2f)
Dark bars:    C = (b - g) / (2 + 2f - b - g)
where b and g are the blurred bar indicator at the 3 bar centres and the 2 gap centres.

The fit only reads the measured contrasts; it never changes them.

Usage as a module:  fit_ctf(rows, pixel_um, angle_deg, polarity, threshold)
"""

from __future__ import annotations

import math

import numpy as np
from scipy.optimize import brentq, least_squares
from scipy.special import erf

_SQ2 = math.sqrt(2.0)
_BARS = np.array([-2.0, 0.0, 2.0])
_GAPS = np.array([-1.0, 1.0])


def _pixel_offsets(pixel_um: float, angle_deg: float, n: int = 5) -> np.ndarray:
    """Positions inside one square pixel, projected on the bar normal at the image tilt."""
    t = math.radians(angle_deg)
    g = ((np.arange(n) + 0.5) / n - 0.5) * pixel_um
    u, v = np.meshgrid(g, g)
    return (u * math.cos(t) + v * math.sin(t)).ravel()


def model_contrast(w_um, sigma_um: float, flare: float, pix_off: np.ndarray, polarity: int = 1,
                   halo_frac: float = 0.0, halo_sigma_um: float | None = None):
    """Michelson contrast of 3 bars of width w_um (array) for the given blur and stray light.
    The PSF is (1 - halo_frac) * Gaussian(sigma_um) + halo_frac * Gaussian(halo_sigma_um)."""
    w = np.atleast_1d(np.asarray(w_um, dtype=float))[:, None, None, None]   # (N,1,1,1)
    centres = _BARS[None, None, :, None] * w                               # bars making the pattern

    def level(where, sigma):                                                # where: (P,)
        s = max(float(sigma), 1e-6) * _SQ2
        x = where[None, :, None, None] * w + pix_off[None, None, None, :]  # (N,P,1,S)
        a, b = centres - 0.5 * w, centres + 0.5 * w
        v = 0.5 * (erf((b - x) / s) - erf((a - x) / s))                    # (N,P,3,S)
        return v.sum(axis=2).mean(axis=(1, 2))                              # mean over positions, pixel

    bl, gl = level(_BARS, sigma_um), level(_GAPS, sigma_um)
    if halo_frac > 0 and halo_sigma_um:
        bl = (1 - halo_frac) * bl + halo_frac * level(_BARS, halo_sigma_um)
        gl = (1 - halo_frac) * gl + halo_frac * level(_GAPS, halo_sigma_um)
    if polarity > 0:
        return (bl - gl) / (bl + gl + 2 * flare)
    return (bl - gl) / (2 + 2 * flare - bl - gl)


def curve(d: dict, w_um, pix_off: np.ndarray, polarity: int = 1):
    """Fitted contrast at line widths w_um for one direction's result dict (fit_ctf output)."""
    halo = (d["halo_fraction"], d["halo_sigma_um"]) if d.get("psf", "gaussian") != "gaussian" else ()
    return model_contrast(w_um, d["sigma_um"], d["stray_light"], pix_off, polarity, *halo)


def _lp(w_um):
    return 1000.0 / (2.0 * np.asarray(w_um, dtype=float))


def _mc(w, p, pix_off, polarity):
    return model_contrast(w, p[0], p[1], pix_off, polarity, *(p[2:4] if len(p) > 2 else ()))


def _crossing(p, pix_off, polarity, thr, f_lo, f_hi):
    """First frequency (coarse -> fine) where the model drops below thr, or None."""
    fs = np.geomspace(f_lo, f_hi, 400)
    c = _mc(1000.0 / (2 * fs), p, pix_off, polarity) - thr
    if c[0] < 0:
        return 0.0                                      # never reaches the threshold
    idx = np.nonzero(c < 0)[0]
    if not len(idx):
        return None                                     # above threshold over the whole range
    i = idx[0]
    g = lambda lf: float(_mc([500.0 / 2 ** lf], p, pix_off, polarity)[0] - thr)
    return 2 ** brentq(g, math.log2(fs[i - 1]), math.log2(fs[i]), xtol=1e-6)


def _fit_direction(w, c, pix_off, polarity, flare_min):
    """Robust least squares, Gaussian PSF (sigma, flare) and core + halo (sigma, flare, a,
    halo_sigma); grid starts so it never lands in a bad minimum. Returns (solution, kind)."""
    def resid(p):
        return _mc(w, p, pix_off, polarity) - c

    def rcost(r):
        return float(np.sum(np.sqrt(1 + (r / 0.03) ** 2) - 1))

    best = None
    for s0 in np.geomspace(0.3, 0.6 * w.max(), 14):
        for f0 in (max(flare_min, 0.0), 0.1, 0.4):
            cost = rcost(resid((s0, f0)))
            if best is None or cost < best[0]:
                best = (cost, s0, f0)
    g1 = least_squares(resid, x0=[best[1], best[2]], bounds=([0.05, flare_min], [10 * w.max(), 20.0]),
                       loss="soft_l1", f_scale=0.03, x_scale=[best[1], 0.1])
    s1 = float(g1.x[0])
    g2 = None
    for a0 in (0.1, 0.3):
        for m0 in (3.0, 8.0):
            x0 = [s1 * 0.8, max(flare_min, float(g1.x[1]) * 0.5), a0, s1 * m0]
            try:
                sol = least_squares(resid, x0=x0,
                                    bounds=([0.05, flare_min, 0.0, 0.1], [10 * w.max(), 20.0, 0.9, 50 * w.max()]),
                                    loss="soft_l1", f_scale=0.03, x_scale=[s1, 0.1, 0.1, s1 * m0])
            except ValueError:
                continue
            if sol.x[3] > 1.5 * sol.x[0] and (g2 is None or sol.cost < g2.cost):
                g2 = sol
    n = len(c)

    def bic(sol, k):
        rss = max(float(np.sum(resid(sol.x) ** 2)), 1e-12)
        return n * math.log(rss / n) + k * math.log(n)

    if g2 is not None and n >= 8 and bic(g2, 4) < bic(g1, 2) - 6:
        return g2, "core + halo"
    return g1, "gaussian"


def fit_ctf(rows: list[dict], pixel_um: float, angle_deg: float = 0.0, polarity: int = 1,
            threshold: float = 0.2, key_prefix: str = "contrast_", flare_min: float = 0.0) -> dict:
    """Fit the CTF model to the reader's element rows (needs group, element, lp_per_mm,
    line_width_um, contrast_H/V, cut_off, undersampled). Returns a dict; the rows are not
    modified. flare_min: lower bound of the stray-light level (0 on a raw image, where offset
    and stray light can only add light; slightly negative after a background correction)."""
    pix_off = _pixel_offsets(pixel_um, angle_deg)
    nyq = 500.0 / pixel_um
    usable = [r for r in rows if not r.get("cut_off") and not r.get("undersampled")]
    out: dict = {"model": "3 bars x PSF x camera pixel, plus uniform stray light; PSF Gaussian, "
                          "or a Gaussian core + wider Gaussian halo when that fits clearly better",
                 "threshold": threshold, "n_elements": len(usable),
                 "n_saturated": sum(1 for r in usable if r.get("saturated")), "directions": {}}
    if len(usable) < 4:
        out["error"] = "too few measurable elements for a fit"
        return out

    w = np.array([r["line_width_um"] for r in usable])
    f_meas = _lp(w)
    f_lo, f_hi = 0.5 * f_meas.min(), max(4.0 * f_meas.max(), 2.0 * nyq)
    for q in ("H", "V"):
        c = np.array([r[f"{key_prefix}{q}"] for r in usable], dtype=float)
        ok = np.isfinite(c)
        sol, kind = _fit_direction(w[ok], c[ok], pix_off, polarity, flare_min)
        p = [float(v) for v in sol.x]
        sigma, flare = p[0], p[1]
        model = _mc(w[ok], p, pix_off, polarity)
        res = model - c[ok]
        rms = float(np.sqrt(np.mean(res ** 2)))
        fx = _crossing(p, pix_off, polarity, threshold, f_lo, f_hi)

        # uncertainty: parameter covariance from the Jacobian, propagated to the crossing
        unc = None
        try:
            J = sol.jac
            dof = max(1, ok.sum() - len(p))
            cov = np.linalg.pinv(J.T @ J) * float(np.sum(res ** 2)) / dof
            if fx:
                grads = []
                for i in range(len(p)):
                    h = 1e-3 * max(abs(p[i]), 1e-2)
                    pp = list(p)
                    pp[i] += h
                    fp = _crossing(pp, pix_off, polarity, threshold, f_lo, f_hi)
                    grads.append(((fp or fx) - fx) / h)
                g = np.array(grads)
                unc = float(math.sqrt(max(0.0, g @ cov @ g)))
            sig_unc = float(math.sqrt(max(0.0, cov[0, 0])))
        except np.linalg.LinAlgError:
            sig_unc = None
        out["directions"][q] = {
            "psf": kind,
            "sigma_um": round(sigma, 4),
            "sigma_um_unc": None if sig_unc is None else round(sig_unc, 4),
            "fwhm_um": round(2.3548 * sigma, 4),
            "stray_light": round(flare, 4),
            "halo_fraction": round(p[2], 4) if kind != "gaussian" else 0.0,
            "halo_sigma_um": round(p[3], 4) if kind != "gaussian" else None,
            "rms_residual": round(rms, 4),
            "crossing_lp_per_mm": None if fx is None else round(fx, 3),
            "crossing_lp_per_mm_unc": None if unc is None else round(unc, 3),
            "per_element": [{"group": r["group"], "element": r["element"],
                             "measured": round(float(cc), 4), "fitted": round(float(m), 4)}
                            for r, cc, m in zip([u for u, o in zip(usable, ok) if o], c[ok],
                                                model)],
        }

    # both directions must reach the threshold -> the lower crossing decides
    cr = {q: out["directions"][q]["crossing_lp_per_mm"] for q in ("H", "V")}
    if any(v is None for v in cr.values()):
        lim_q = next((q for q in ("H", "V") if cr[q] is not None), None)
    else:
        lim_q = min(cr, key=lambda q: cr[q])
    f_lim = None if lim_q is None else cr[lim_q]
    out["limiting_direction"] = lim_q
    out["crossing_lp_per_mm"] = f_lim
    out["crossing_lp_per_mm_unc"] = None if lim_q is None else out["directions"][lim_q]["crossing_lp_per_mm_unc"]
    if f_lim:
        k = 6 * math.log2(f_lim)                       # continuous element index: lp/mm = 2^(k/6)
        g, e = divmod(int(math.floor(k + 1e-9)), 6)
        out["crossing_group_element"] = round(k / 6, 3)
        out["limit_element"] = f"G{g}E{e + 1}"
        out["limit_fraction_to_next"] = round(k - math.floor(k + 1e-9), 3)
        out["crossing_line_width_um"] = round(500.0 / f_lim, 4)
        out["beyond_nyquist"] = bool(f_lim > nyq)
        out["extrapolated"] = bool(f_lim > f_meas.max())
        # a curve that never rises far above the threshold crosses it at a poorly defined point
        top = max(float(np.max(curve(out["directions"][q], w, pix_off, polarity))) for q in ("H", "V"))
        out["ill_defined"] = bool(top < 2.0 * threshold)
    out["camera_nyquist_lp_per_mm"] = round(nyq, 3)
    out["interpolated"] = _interpolated(usable, threshold, key_prefix)
    return out


def _interpolated(rows: list[dict], thr: float, key_prefix: str) -> dict:
    """Model-free cross-check: the first downward threshold crossing, coarse -> fine, stepping
    over one isolated failure as the element-by-element limit does, interpolated linearly in
    contrast vs log-frequency between the two neighbouring measured elements."""
    rows = sorted(rows, key=lambda r: r["lp_per_mm"])
    out = {}
    for q in ("H", "V", "min"):
        vals = [(r["lp_per_mm"], min(r[f"{key_prefix}H"], r[f"{key_prefix}V"]) if q == "min"
                 else r[f"{key_prefix}{q}"]) for r in rows]
        fx, skipped = None, False
        for i in range(len(vals) - 1):
            (f0, c0), (f1, c1) = vals[i], vals[i + 1]
            if c0 >= thr > c1:
                if not skipped and i + 2 < len(vals) and vals[i + 2][1] >= thr:
                    skipped = True
                    continue
                t = (c0 - thr) / (c0 - c1)
                fx = 2 ** (math.log2(f0) + t * (math.log2(f1) - math.log2(f0)))
                break
        out[q] = None if fx is None else round(fx, 3)
    return {"crossing_lp_per_mm_H": out["H"], "crossing_lp_per_mm_V": out["V"],
            "crossing_lp_per_mm": out["min"]}
