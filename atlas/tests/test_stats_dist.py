import math
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from atlas import distributions as dist
from atlas import stats


class TestStats(unittest.TestCase):
    def test_mean_var_std(self):
        xs = [1.0, 2.0, 3.0, 4.0, 5.0]
        self.assertAlmostEqual(stats.mean(xs), 3.0)
        self.assertAlmostEqual(stats.variance(xs), 2.5)  # sample variance
        self.assertAlmostEqual(stats.stdev(xs), math.sqrt(2.5))

    def test_covariance_matrix_symmetric(self):
        returns = [[0.01, 0.02], [-0.01, -0.03], [0.02, 0.01], [0.0, 0.0]]
        cov = stats.covariance_matrix(returns)
        self.assertAlmostEqual(cov[0][1], cov[1][0])
        # diagonal equals per-series variance
        col0 = [r[0] for r in returns]
        self.assertAlmostEqual(cov[0][0], stats.variance(col0))

    def test_correlation_diagonal_is_one(self):
        returns = [[0.01, 0.02], [-0.01, -0.03], [0.02, 0.01], [0.005, -0.01]]
        corr = stats.correlation_matrix(returns)
        self.assertAlmostEqual(corr[0][0], 1.0)
        self.assertAlmostEqual(corr[1][1], 1.0)
        self.assertLessEqual(abs(corr[0][1]), 1.0 + 1e-9)

    def test_quantile(self):
        xs = list(range(101))  # 0..100
        self.assertAlmostEqual(stats.quantile(xs, 0.0), 0.0)
        self.assertAlmostEqual(stats.quantile(xs, 1.0), 100.0)
        self.assertAlmostEqual(stats.quantile(xs, 0.5), 50.0)


class TestDistributions(unittest.TestCase):
    def test_norm_cdf_known_values(self):
        self.assertAlmostEqual(dist.norm_cdf(0.0), 0.5, places=9)
        self.assertAlmostEqual(dist.norm_cdf(1.645), 0.95, places=3)

    def test_norm_ppf_inverse_of_cdf(self):
        for p in (0.01, 0.25, 0.5, 0.75, 0.99):
            x = dist.norm_ppf(p)
            self.assertAlmostEqual(dist.norm_cdf(x), p, places=6)

    def test_norm_ppf_known(self):
        self.assertAlmostEqual(dist.norm_ppf(0.95), 1.6448536, places=5)
        self.assertAlmostEqual(dist.norm_ppf(0.99), 2.3263479, places=5)

    def test_correlated_generator_recovers_covariance(self):
        mean = [0.0, 0.0]
        cov = [[1.0, 0.5], [0.5, 2.0]]
        gen = dist.CorrelatedNormalGenerator(mean, cov, seed=123)
        draws = gen.draws(40_000)
        est = stats.covariance_matrix(draws)
        # Monte-Carlo estimate should be close to the target covariance.
        self.assertAlmostEqual(est[0][0], 1.0, delta=0.05)
        self.assertAlmostEqual(est[1][1], 2.0, delta=0.10)
        self.assertAlmostEqual(est[0][1], 0.5, delta=0.05)


if __name__ == "__main__":
    unittest.main()
