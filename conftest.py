"""
Root conftest.py — ensures the project root is on sys.path so that
`import src.*` and `import config.*` work when running pytest from
the project root directory.
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
