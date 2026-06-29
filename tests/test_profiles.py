import pytest

from utils import profiles as pf


@pytest.fixture
def tmp_profiles(tmp_path, monkeypatch):
    cfg = tmp_path / "config.yaml"
    cfg.write_text(
        "competitors:\n"
        "  - name: Config Brand\n"
        "    facebook_page: cfgfb\n"
        "    instagram_handle: cfgig\n"
        "    tiktok_handle: cfgtt\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(pf, "CONFIG_PATH", str(cfg))
    monkeypatch.setattr(pf, "PROFILES_PATH", str(tmp_path / "data" / "profiles.json"))
    return tmp_path


def test_effective_falls_back_to_config(tmp_profiles):
    comps = pf.effective_competitors()
    assert [c["name"] for c in comps] == ["Config Brand"]
    assert pf.is_override_active() is False


def test_override_wins_over_config(tmp_profiles):
    pf.save_profiles([{"name": "Subway", "instagram_handle": "subwaypl"}])
    assert [c["name"] for c in pf.effective_competitors()] == ["Subway"]
    assert pf.is_override_active() is True


def test_effective_uses_passed_config_seed_when_no_override(tmp_profiles):
    seed = [{"name": "Seed Brand", "instagram_handle": "seed"}]
    assert pf.effective_competitors(seed) == seed


def test_save_normalizes_and_drops_unknown_keys(tmp_profiles):
    saved = pf.save_profiles([{"name": "  KFC  ", "instagram_handle": " kfc_pl ", "evil": "x"}])
    assert saved[0]["name"] == "KFC"
    assert saved[0]["instagram_handle"] == "kfc_pl"
    assert set(saved[0].keys()) == set(pf.PROFILE_FIELDS)


def test_save_rejects_empty_list(tmp_profiles):
    with pytest.raises(pf.ProfilesError):
        pf.save_profiles([])


def test_save_rejects_nameless_profile(tmp_profiles):
    with pytest.raises(pf.ProfilesError):
        pf.save_profiles([{"name": "  ", "instagram_handle": "x"}])


def test_save_rejects_profile_without_handles(tmp_profiles):
    with pytest.raises(pf.ProfilesError):
        pf.save_profiles([{"name": "Brand", "facebook_page": "", "instagram_handle": ""}])


def test_reset_reverts_to_config(tmp_profiles):
    pf.save_profiles([{"name": "Subway", "instagram_handle": "subwaypl"}])
    reverted = pf.reset_profiles()
    assert pf.is_override_active() is False
    assert reverted[0]["name"] == "Config Brand"
