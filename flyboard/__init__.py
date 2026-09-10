# Import order matters on Windows: loading pyarrow.dataset (or torch) after scipy has
# initialized its native libraries crashes with an access violation.
import pyarrow.dataset  # noqa: F401
import torch  # noqa: F401
