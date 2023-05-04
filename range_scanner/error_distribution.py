import numpy as np

# for more distributions see: https://numpy.org/doc/stable/reference/random/generator.html#distributions


def applyNoise(mu: float | np.ndarray, sigma: float | np.ndarray) -> np.ndarray:
    return np.random.default_rng().normal(mu, sigma, None)
