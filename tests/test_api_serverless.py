"""Import/serialization tests for the Vercel serverless API modules."""

import sys

import userscope.result as result_mod

sys.path.insert(0, "api")


def test_api_modules_import_cleanly():
    import api.hostscan
    import api.phone

    assert hasattr(api.phone, "handler")
    assert hasattr(api.hostscan, "handler")
    assert callable(api.phone.PhoneLookup)


def test_hostscan_default_curated_sites_are_small():
    from api.hostscan import DEFAULT_SITES

    assert len(DEFAULT_SITES) <= 12
    assert "Instagram" in DEFAULT_SITES and "GitHub" in DEFAULT_SITES


def test_hostscan_serialize_maps_result():
    from api.hostscan import _serialize

    qr = result_mod.QueryResult("x", "Instagram", "https://instagram.com/x",
                                result_mod.QueryStatus.CLAIMED, 1.5, "ctx")
    results, counts = _serialize({
        "Instagram": {
            "status": qr,
            "url_main": "https://instagram.com/{}",
            "url_user": "https://instagram.com/x",
            "http_status": 200,
        }
    })
    assert results["Instagram"]["status"] == "claimed"
    assert results["Instagram"]["time_ms"] == 1500
    assert counts["claimed"] == 1


def test_api_phone_module_reuses_offline_lookup():
    from api.phone import PhoneLookup

    data = PhoneLookup().lookup("+919876543210")
    assert data["valid"] is True
    assert data["region"] == "IN"