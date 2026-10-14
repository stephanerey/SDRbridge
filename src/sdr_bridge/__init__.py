"""SDRbridge core package."""

import os

# Les wheels NumPy/OpenBLAS Windows réservent un tampon important par worker.
# Le flux V1 est mono-source et ses petites opérations vectorielles ne gagnent
# rien à 24 workers BLAS. Respecter néanmoins tout réglage opérateur explicite.
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("OMP_NUM_THREADS", "1")

__version__ = "0.3.0"

