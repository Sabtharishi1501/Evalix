import os


class BaseConfig:
    DEBUG = False
    TESTING = False
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-change-me")
    RATELIMIT_DEFAULT = os.environ.get("RATELIMIT_DEFAULT", "30 per minute")


class DevelopmentConfig(BaseConfig):
    DEBUG = True


class TestingConfig(BaseConfig):
    TESTING = True
    RATELIMIT_ENABLED = False


class ProductionConfig(BaseConfig):
    DEBUG = False

    def __init__(self):
        if self.SECRET_KEY == "dev-secret-change-me":
            import logging

            logging.getLogger(__name__).warning(
                "SECRET_KEY is using the insecure default. Set the SECRET_KEY "
                "environment variable before deploying to production."
            )


CONFIG_BY_NAME = {
    "development": DevelopmentConfig,
    "testing": TestingConfig,
    "production": ProductionConfig,
}


def get_config(name=None):
    name = name or os.environ.get("FLASK_ENV", "production")
    return CONFIG_BY_NAME.get(name, ProductionConfig)