from app.core.config import Settings


def test_default_cors_origins_are_local_frontend_only() -> None:
    settings = Settings(_env_file=None)

    assert settings.cors_origins == [
        "http://127.0.0.1:3000",
        "http://localhost:3000",
    ]


def test_cors_origins_can_be_configured_from_comma_separated_value() -> None:
    settings = Settings(
        _env_file=None,
        FRONTEND_ORIGINS=(
            "http://127.0.0.1:3000, https://local.example ,"
        ),
    )

    assert settings.cors_origins == [
        "http://127.0.0.1:3000",
        "https://local.example",
    ]
