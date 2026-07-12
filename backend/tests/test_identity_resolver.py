from identity_resolver import IdentityResolver


def test_reuses_logical_id_when_raw_id_changes_after_short_occlusion():
    resolver = IdentityResolver()
    assert resolver.resolve(1, [10, 10, 30, 50], now=0) == 1
    resolver.retire_missing(set(), now=1)
    assert resolver.resolve(9, [12, 10, 32, 50], now=2) == 1
