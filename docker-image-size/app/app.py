"""Tiny Streamlit payload. The Dockerfiles, not this file, are the size experiment."""

import numpy as np
import pandas as pd
import streamlit as st

st.set_page_config(page_title="Image size is a deploy-time cost", layout="centered")
st.title("Same app. The image around it is the variable.")
st.write(
    "This process is a few Python files. A bloated Dockerfile still ships a compiler, "
    "a pip cache, Jupyter, Node.js, and a frontend `node_modules` tree that this runtime "
    "never imports. The multi-stage build copies only a virtualenv onto `python:3.12-slim`."
)
st.caption(f"Runtime imports that stay in the image: numpy {np.__version__}, pandas {pd.__version__}.")

st.subheader("What the three recipes are doing")
st.markdown(
    """
- **Bloated:** `python:3.12`, extra apt packages, pip with its cache left on disk,
  Jupyter and test tools, `npm install`.
- **Streamlit tutorial:** `python:3.12-slim` plus `build-essential`, curl, and git
  left in the final image. Streamlit measured that image at **1.02 GB**.
- **Multi-stage:** compile in a builder, copy `/opt/venv` onto slim, no gcc, no cache,
  no JavaScript toolchain.
"""
)

st.caption(
    "Numbers and figures live in the folder README. This container only needs to run."
)
