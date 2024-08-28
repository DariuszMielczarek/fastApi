import memory_package
from memory_package import PostgresDb, InMemoryDb, SQLModelDb


def pytest_addoption(parser):
    parser.addoption(
        "--db",
        action="store",
        default="memory",
        help="Type of database to use. Options are: 'memory', 'postgres', 'model'. Default is 'memory'."
    )


def pytest_generate_tests(metafunc):
    db_type = metafunc.config.option.db
    if db_type == "postgres":
        memory_package.db = PostgresDb()
        memory_package.db_type = 'postgres'
    elif db_type == "memory":
        memory_package.db = InMemoryDb()
        memory_package.db_type = 'memory'
    elif db_type == 'model':
        memory_package.db = SQLModelDb()
        memory_package.db_type = 'model'
    else:
        raise ValueError("Unsupported database type: {}".format(db_type))
