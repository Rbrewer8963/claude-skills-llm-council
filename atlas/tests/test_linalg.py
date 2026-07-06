import math
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from atlas import linalg


class TestLinalg(unittest.TestCase):
    def test_matmul_identity(self):
        A = [[1.0, 2.0], [3.0, 4.0]]
        I = linalg.identity(2)
        self.assertEqual(linalg.matmul(A, I), A)

    def test_matvec(self):
        A = [[1.0, 0.0], [0.0, 2.0]]
        self.assertEqual(linalg.matvec(A, [3.0, 4.0]), [3.0, 8.0])

    def test_cholesky_reconstructs(self):
        A = [[4.0, 2.0], [2.0, 3.0]]
        L = linalg.cholesky(A)
        LLt = linalg.matmul(L, linalg.transpose(L))
        for i in range(2):
            for j in range(2):
                self.assertAlmostEqual(LLt[i][j], A[i][j], places=9)

    def test_cholesky_rejects_non_pd(self):
        with self.assertRaises(ValueError):
            linalg.cholesky([[1.0, 2.0], [2.0, 1.0]])  # indefinite

    def test_inverse(self):
        A = [[4.0, 7.0], [2.0, 6.0]]
        inv = linalg.inverse(A)
        prod = linalg.matmul(A, inv)
        for i in range(2):
            for j in range(2):
                self.assertAlmostEqual(prod[i][j], 1.0 if i == j else 0.0, places=9)

    def test_inverse_singular_raises(self):
        with self.assertRaises(ValueError):
            linalg.inverse([[1.0, 2.0], [2.0, 4.0]])

    def test_solve(self):
        A = [[3.0, 2.0], [1.0, 2.0]]
        b = [5.0, 5.0]
        x = linalg.solve(A, b)
        self.assertAlmostEqual(x[0], 0.0, places=9)
        self.assertAlmostEqual(x[1], 2.5, places=9)

    def test_quad_form(self):
        # x^T A x for A = I is just ||x||^2
        self.assertAlmostEqual(linalg.quad_form([3.0, 4.0], linalg.identity(2)), 25.0)


if __name__ == "__main__":
    unittest.main()
