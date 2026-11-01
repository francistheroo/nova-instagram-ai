import pytest
from pydantic import ValidationError

from app.admin import SettingsUpdate


def _settings(**overrides):
    values = {
        "master_enabled": False,
        "provider_order": ["gemini"],
        "max_posts_per_day": 20,
        "max_stories_per_day": 20,
        "direct_publish_enabled": False,
        "post_times": ["09:00"],
        "story_times": ["13:00"],
    }
    values.update(overrides)
    return values


def test_admin_accepts_scheduler_caps_supported_by_publisher():
    settings = SettingsUpdate(**_settings())

    assert settings.max_posts_per_day == 20
    assert settings.max_stories_per_day == 20


@pytest.mark.parametrize(
    "field",
    ["max_posts_per_day", "max_stories_per_day"],
)
def test_admin_rejects_caps_above_publisher_safety_limit(field):
    with pytest.raises(ValidationError):
        SettingsUpdate(**_settings(**{field: 21}))
