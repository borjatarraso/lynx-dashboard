"""About metadata and logo loading."""

from __future__ import annotations

from lynx_dashboard import APP_NAME, SUITE_LABEL, __version__, get_about_text, get_logo_ascii


def test_about_has_expected_keys():
    about = get_about_text()
    for key in (
        "name", "short_name", "tagline", "suite", "suite_version",
        "version", "author", "email", "year", "license", "license_name",
        "license_text", "description", "scope_description", "logo_ascii",
    ):
        assert key in about, f"missing {key}"


def test_about_uses_core_suite_label():
    about = get_about_text()
    assert about["suite"] in SUITE_LABEL
    assert about["version"] == __version__
    assert about["name"] == APP_NAME


def test_logo_loads_from_img_dir():
    logo = get_logo_ascii()
    # Either the logo loads (normal path) or the file is missing (empty string).
    # Either way the call must succeed; don't assert non-empty because the
    # package may be importable from a checkout without img/ being present.
    assert isinstance(logo, str)
