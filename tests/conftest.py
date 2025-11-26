import os
import sys

# Adiciona a raiz do projeto (onde está a pasta "app" e "functions") no PYTHONPATH
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)