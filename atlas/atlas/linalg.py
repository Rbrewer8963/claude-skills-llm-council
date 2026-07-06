"""Pure-Python linear algebra.

ATLAS deliberately depends on nothing outside the standard library, so the
matrix primitives every risk model needs live here: Cholesky factorisation for
correlated Monte-Carlo draws, a Gauss-Jordan inverse/solver for optimisation,
and the small helpers (matmul, matvec, transpose) that glue them together.

A "matrix" is a list of equal-length lists of floats (row-major). A "vector"
is a flat list of floats. Everything is intentionally boring and readable.
"""

from __future__ import annotations

from typing import List, Sequence

Matrix = List[List[float]]
Vector = List[float]


def shape(A: Matrix) -> tuple[int, int]:
    return (len(A), len(A[0]) if A else 0)


def zeros(rows: int, cols: int) -> Matrix:
    return [[0.0 for _ in range(cols)] for _ in range(rows)]


def identity(n: int) -> Matrix:
    return [[1.0 if i == j else 0.0 for j in range(n)] for i in range(n)]


def transpose(A: Matrix) -> Matrix:
    return [list(col) for col in zip(*A)]


def matmul(A: Matrix, B: Matrix) -> Matrix:
    ra, ca = shape(A)
    rb, cb = shape(B)
    if ca != rb:
        raise ValueError(f"incompatible shapes {shape(A)} @ {shape(B)}")
    Bt = transpose(B)
    return [[sum(a * b for a, b in zip(row, col)) for col in Bt] for row in A]


def matvec(A: Matrix, x: Vector) -> Vector:
    return [sum(a * xi for a, xi in zip(row, x)) for row in A]


def dot(x: Sequence[float], y: Sequence[float]) -> float:
    return sum(a * b for a, b in zip(x, y))


def quad_form(x: Vector, A: Matrix) -> float:
    """Return the scalar x^T A x (used constantly for portfolio variance)."""
    return dot(x, matvec(A, x))


def scale(A: Matrix, s: float) -> Matrix:
    return [[s * v for v in row] for row in A]


def add(A: Matrix, B: Matrix) -> Matrix:
    return [[a + b for a, b in zip(ra, rb)] for ra, rb in zip(A, B)]


def cholesky(A: Matrix) -> Matrix:
    """Lower-triangular L with L @ L^T == A for symmetric positive-definite A.

    Raises ValueError if A is not positive definite, which is a useful signal
    that an estimated covariance matrix is degenerate.
    """
    n = len(A)
    L = zeros(n, n)
    for i in range(n):
        for j in range(i + 1):
            s = sum(L[i][k] * L[j][k] for k in range(j))
            if i == j:
                diag = A[i][i] - s
                if diag <= 0:
                    raise ValueError(
                        "matrix is not positive definite (non-positive pivot); "
                        "covariance may be singular or ill-conditioned"
                    )
                L[i][j] = diag ** 0.5
            else:
                L[i][j] = (A[i][j] - s) / L[j][j]
    return L


def inverse(A: Matrix) -> Matrix:
    """Invert a square matrix via Gauss-Jordan elimination with partial pivoting."""
    n = len(A)
    # Augment [A | I] using copies so the caller's matrix is untouched.
    aug = [list(A[i]) + [1.0 if i == j else 0.0 for j in range(n)] for i in range(n)]
    for col in range(n):
        pivot = max(range(col, n), key=lambda r: abs(aug[r][col]))
        if abs(aug[pivot][col]) < 1e-15:
            raise ValueError("matrix is singular; cannot invert")
        aug[col], aug[pivot] = aug[pivot], aug[col]
        pv = aug[col][col]
        aug[col] = [v / pv for v in aug[col]]
        for r in range(n):
            if r == col:
                continue
            factor = aug[r][col]
            if factor != 0.0:
                aug[r] = [rv - factor * cv for rv, cv in zip(aug[r], aug[col])]
    return [row[n:] for row in aug]


def solve(A: Matrix, b: Vector) -> Vector:
    """Solve A x = b."""
    return matvec(inverse(A), b)


def is_symmetric(A: Matrix, tol: float = 1e-9) -> bool:
    n = len(A)
    return all(abs(A[i][j] - A[j][i]) <= tol for i in range(n) for j in range(n))
