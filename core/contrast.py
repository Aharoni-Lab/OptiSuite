from __future__ import annotations

import math

import cv2
import numpy as np


def michelson_contrast(max_value: float, min_value: float, eps: float = 1e-9) -> float:
    return float((max_value - min_value) / (max_value + min_value + eps))


def percentile_contrast(values: np.ndarray, low: float = 5.0, high: float = 95.0) -> float:
    if values.size == 0:
        return 0.0
    low_value = float(np.percentile(values, low))
    high_value = float(np.percentile(values, high))
    return michelson_contrast(high_value, low_value)


def line_profile(gray_image: np.ndarray, pt_a: tuple[int, int], pt_b: tuple[int, int], width: int = 3) -> np.ndarray:
    mask = np.zeros_like(gray_image, dtype=np.uint8)
    cv2.line(mask, pt_a, pt_b, 255, width)
    return gray_image[mask > 0]


def frequency_at_threshold(frequencies: list[float], contrasts: list[float], threshold: float) -> float | None:
    if not frequencies or not contrasts or len(frequencies) != len(contrasts):
        return None

    above = [(freq, contrast) for freq, contrast in zip(frequencies, contrasts) if contrast >= threshold]
    if not above:
        return None

    return float(max(freq for freq, _contrast in above))


def dominant_frequency_1d(signal: np.ndarray, sample_spacing: float = 1.0) -> tuple[float | None, float]:
    if signal.size < 4:
        return None, 0.0

    centered = signal.astype(np.float64) - float(np.mean(signal))
    window = np.hanning(centered.size)
    spectrum = np.fft.rfft(centered * window)
    magnitudes = np.abs(spectrum)
    if magnitudes.size <= 1:
        return None, 0.0

    magnitudes[0] = 0.0
    peak_idx = int(np.argmax(magnitudes))
    if peak_idx <= 0 or magnitudes[peak_idx] <= 0:
        return None, 0.0

    frequencies = np.fft.rfftfreq(centered.size, d=sample_spacing)
    amplitude = float(magnitudes[peak_idx] / (centered.size / 2.0))
    return float(frequencies[peak_idx]), amplitude


def mtf_from_edge_samples(esf: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    if esf.size < 16:
        return np.array([]), np.array([])

    esf = esf.astype(np.float64)
    esf = np.convolve(esf, np.array([0.25, 0.5, 0.25]), mode="same")
    lsf = np.gradient(esf)
    window = np.hanning(lsf.size)
    spectrum = np.abs(np.fft.rfft(lsf * window))
    if spectrum.size == 0 or spectrum[0] == 0:
        return np.array([]), np.array([])

    spectrum /= spectrum[0]
    frequencies = np.fft.rfftfreq(lsf.size, d=1.0)
    return frequencies, spectrum


def sample_along_circle(
    gray_image: np.ndarray,
    center: tuple[float, float],
    radius: float,
    sample_count: int = 720,
) -> np.ndarray:
    angles = np.linspace(0.0, 2.0 * math.pi, sample_count, endpoint=False)
    xs = center[0] + radius * np.cos(angles)
    ys = center[1] + radius * np.sin(angles)
    xs = np.clip(xs, 0, gray_image.shape[1] - 1).astype(np.float32)
    ys = np.clip(ys, 0, gray_image.shape[0] - 1).astype(np.float32)
    samples = cv2.remap(
        gray_image,
        xs.reshape(1, -1),
        ys.reshape(1, -1),
        interpolation=cv2.INTER_LINEAR,
        borderMode=cv2.BORDER_REFLECT,
    )
    return samples.reshape(-1)

