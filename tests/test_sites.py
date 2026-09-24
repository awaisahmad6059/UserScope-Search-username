"""Offline tests for the site registry bundled with UserScope."""

import pathlib

from userscope.sites import SitesInformation

ROOT = pathlib.Path(__file__).resolve().parent.parent
DATA = ROOT / "userscope" / "resources" / "data.json"


def load(sites_path=None):
    return SitesInformation(str(sites_path or DATA), honor_exclusions=False)


def test_sites_load_offline():
    sites = load()
    assert len(sites.sites) > 300


def test_sites_required_keys():
    sites = load()
    for name, site in list(sites.sites.items())[:60]:
        info = site.information
        assert "urlMain" in info, name
        assert "url" in info, name
        assert "username_claimed" in info, name


def test_every_site_has_its_url_recorded():
    sites = load()
    for name, site in sites.sites.items():
        assert site.url_username_format, name
        assert site.information.get("urlMain"), name


def test_nsfw_filter_never_grows():
    sites = load()
    full = len(sites.sites)
    sites.remove_nsfw_sites()
    assert len(sites.sites) <= full


def test_data_schema_present():
    schema = ROOT / "userscope" / "resources" / "data.schema.json"
    assert schema.is_file()