"""
Tests for app/services/domain_filter.py -- the allowlist that is the
project's actual anti-scam mechanism (see the module's own docstring: this
is a deliberate choice over a fraud-classifier). Since the whole safety
argument rests on this filter behaving correctly, it earns direct tests
rather than only being exercised indirectly through the full pipeline.
"""

from app.services.domain_filter import list_trusted_platforms, match_trusted_platform

class TestMatchTrustedPlatform:
    def test_matches_known_domain(self):
        assert match_trusted_platform("https://www.amazon.in/dp/B0ABC123") == "Amazon"

    def test_matches_known_domain_without_www(self):
        assert match_trusted_platform("https://flipkart.com/product/xyz") == "Flipkart"

    def test_matches_regional_tld_variant(self):
        assert match_trusted_platform("https://www.amazon.com/dp/B0ABC123") == "Amazon"

    def test_matches_subdomain(self):
        assert match_trusted_platform("https://m.nykaa.com/product/123") == "Nykaa"

    def test_rejects_untrusted_domain(self):
        assert match_trusted_platform("https://scammy-deals-xyz.example.com/item") is None

    def test_rejects_lookalike_domain_not_a_substring_match_bypass(self):

        assert match_trusted_platform("https://amazon-deals-fake.net/x") is None

    def test_rejects_trusted_domain_used_as_a_suffix_bypass(self):
        assert match_trusted_platform("https://amazon.com.evil-scam.ru/x") is None
        assert match_trusted_platform("https://flipkart.com.phish.io/y") is None

    def test_matches_with_explicit_port(self):
        assert match_trusted_platform("https://www.amazon.in:443/dp/B0ABC123") == "Amazon"

    def test_empty_url_returns_none(self):
        assert match_trusted_platform("") is None

    def test_none_url_returns_none(self):
        assert match_trusted_platform(None) is None

    def test_malformed_url_does_not_raise(self):
        assert match_trusted_platform("not a url at all :://") is None

class TestListTrustedPlatforms:
    def test_returns_sorted_unique_names(self):
        platforms = list_trusted_platforms()
        assert platforms == sorted(set(platforms))

    def test_includes_expected_platforms(self):
        platforms = list_trusted_platforms()
        assert "Amazon" in platforms
        assert "Flipkart" in platforms

    def test_amazon_in_and_com_collapse_to_one_display_name(self):

        platforms = list_trusted_platforms()
        assert platforms.count("Amazon") == 1
