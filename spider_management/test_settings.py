from .settings import *

# Use in-memory SQLite for tests to avoid touching existing MySQL database
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': ':memory:',
    }
}

# Faster password hashing in tests
PASSWORD_HASHERS = [
    'django.contrib.auth.hashers.MD5PasswordHasher',
]

# Use a fixed secret for tests
SECRET_KEY = 'test-secret-key'

# Reduce logging noise
LOGGING = {
    'version': 1,
    'disable_existing_loggers': True,
}

# Use test-only migrations for the spiders app so tests run against schema matching current models
MIGRATION_MODULES = {
    'spiders': 'spiders.test_migrations',
}
