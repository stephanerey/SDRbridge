"""SDRbridge core package."""

import logging
import os

# Les wheels NumPy/OpenBLAS Windows réservent un tampon important par worker.
# Le flux V1 est mono-source et ses petites opérations vectorielles ne gagnent
# rien à 24 workers BLAS. Respecter néanmoins tout réglage opérateur explicite.
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("OMP_NUM_THREADS", "1")

# Une utilisation comme bibliothèque ne doit pas écrire via le lastResort de
# Python. L'application configure ses handlers persistants au démarrage.
logging.getLogger(__name__).addHandler(logging.NullHandler())

__version__ = "0.4.0"

