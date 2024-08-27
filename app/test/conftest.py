import sys
import os
import pytest
import memory_package
from memory_package import PostgresDb, InMemoryDb

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))


# @pytest.fixture(scope="session")
# def db_url(request):
#     db_type = request.config.getoption("--db")
#     if db_type == "postgres":
#         memory_package.db = PostgresDb()
#         memory_package.db_type = 'postgres'
#     elif db_type == "memory":
#         memory_package.db = InMemoryDb()
#         memory_package.db_type = 'in_memory'
#     else:
#         raise ValueError("Unsupported database type")
