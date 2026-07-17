"""Env-gated live drift-detection tier for direct-integration ATS extractors.

This module hits the REAL internet (no mocks) to catch drift the fixture-based
suite cannot: when an ATS changes its API/HTML, the fixture tests stay green
while production silently degrades. Here we call
``howoldisthisjob.analyze_url`` on one curated URL per *direct*-integration
platform and assert the *native* extractor still produces the chosen date.

These tests are OFF by default and never run in the PR gate. Enable with:

    HOWOLDISTHISJOB_LIVE_TESTS=1 python3 -m unittest tests.live.test_live_extractors -v

Run a single platform (the method name is ``test_live_<platform>``):

    HOWOLDISTHISJOB_LIVE_TESTS=1 python3 -m unittest \\
        tests.live.test_live_extractors.TestLiveExtractors.test_live_ashby -v

Run a few platforms at once by listing multiple method paths (unittest's
``-k`` flag takes a single substring/glob and does not reliably support
``or``-style multi-selection across Python versions, so multiple explicit
paths are preferred here):

    HOWOLDISTHISJOB_LIVE_TESTS=1 python3 -m unittest -v \\
        tests.live.test_live_extractors.TestLiveExtractors.test_live_ashby \\
        tests.live.test_live_extractors.TestLiveExtractors.test_live_greenhouse \\
        tests.live.test_live_extractors.TestLiveExtractors.test_live_lever

Notes:
    * ``analyze_url`` budgets up to ~30 s per URL internally, so the full tier
      (~27 platforms) can take several minutes. Spot-check a handful, not all.
    * The full 111-test suite is unaffected: this tier reports as skipped when
      the env var is unset (``python3 -m unittest discover -s tests``).
    * Assertions tolerate job churn: there are NO exact-date assertions. A job
      that has been filled/blocked/removed is treated as INCONCLUSIVE (skipped),
      not a failure. A *success* whose chosen source is a non-native fallback
      that only wins when the live page gave the native extractor nothing
      (wayback/sitemap/jina — see NON_NATIVE_FALLBACK_PREFIXES) is also a SKIP
      (churn, not drift). The only hard failure is a *success* whose chosen
      source is an on-page source (jsonld/meta/html) that is NOT the platform's
      native extractor prefix — i.e. the native extractor stopped working while
      generic parsers still date the page. That is drift.
"""

from __future__ import annotations

import os
import unittest

import howoldisthisjob
from scripts.ats_matrix import MATRIX

# Module-level env gate. Re-checked at class level via @unittest.skipUnless so
# the test runner reports the skip clearly, but checking once here keeps the
# intent obvious for readers and static analysis.
LIVE_TESTS_ENABLED = os.environ.get("HOWOLDISTHISJOB_LIVE_TESTS") == "1"

# Platform (MATRIX plan-bucket label) -> tuple of acceptable *detected*
# platforms reported by analyze_url["platform"].
#
# detect_platform is URL-pattern based and normally echoes the label back, but
# two direct platforms resolve through a generic host before the page is
# fetched:
#   * successfactors  -> first MATRIX URL is jobs.sap.com (detected "unknown"
#                        pre-fetch; upgraded to "successfactors" during fetch).
#   * custom_backend  -> first MATRIX URL is stripe.com/jobs/listing/...
#                        which detect_platform maps to "greenhouse"
#                        (resolver=stripe). The other two custom_backend URLs
#                        (amazon.jobs, bendingspoons) detect as "custom_backend".
# "unknown" and "greenhouse" are therefore accepted for those two labels so a
# transient detection reordering does not produce a false drift signal.
EXPECTED_PLATFORMS: dict[str, tuple[str, ...]] = {
    "successfactors": ("successfactors", "unknown"),
    "custom_backend": ("custom_backend", "greenhouse"),
}

# Platform (MATRIX label) -> tuple of native chosen_source["source"] prefixes.
#
# Built from the integration test assertions in
# tests/test_howoldisthisjob_integration.py (e.g. "lever.api", "workday.cxs",
# "greenhouse.api") cross-referenced with the source strings emitted by the
# extract_*, extract_*_api / _embedded / _html / _xml functions in
# howoldisthisjob.py. If a platform's *native* extractor stops working, the
# resolver falls back to sitemap / wayback.cdx / generic meta / jsonld sourced
# from elsewhere, and the prefix check below FAILS — the drift signal.
#
# A handful of platforms do NOT have a dedicated extractor (teamtailor, taleo,
# jazzhr) and natively rely on a generic parser (jsonld.jobposting /
# open_graph / html.regex). For those the prefix is the generic source itself
# and the signal is a generic-path health check — it cannot distinguish
# platform-specific JSON-LD death from a generic parser regression. See the
# per-entry comments below. NATIVE_FIELDS (further down) is reserved for the
# stronger field-disambiguation variant but is currently empty.
NATIVE_SOURCES: dict[str, tuple[str, ...]] = {
    "lever": ("lever.api",),
    "greenhouse": ("greenhouse.api", "greenhouse.html"),
    "ashby": ("ashby.api",),
    "smartrecruiters": ("smartrecruiters.api",),
    "workable": ("workable.api", "workable.embedded"),
    "dayforce": ("dayforce.next",),
    "pageup": ("pageup.html",),
    "rippling": ("rippling.embedded",),
    "icims": ("icims.api",),
    "dover": ("dover.api",),
    "bamboohr": ("bamboohr.api",),
    "jobvite": ("jobvite.xml", "jobvite.jsonld"),
    # No dedicated extractor; jsonld.jobposting is a generic-path health signal
    # that can't distinguish taleo JSON-LD death from a generic parser regression.
    "taleo": ("jsonld.jobposting",),
    "brassring": ("brassring.html",),
    "successfactors": ("successfactors.rss",),
    "avature": ("avature.feed", "avature.sitemap"),
    # B1: teamtailor has NO dedicated extractor. Healthy postings resolve via
    # jsonld.jobposting (e.g. flower.teamtailor.com) or html.regex
    # (unleash.teamtailor.com); article:published_time is emitted by
    # extract_meta_and_open_graph with source="open_graph" (NOT "meta"), so the
    # old ("meta",) + NATIVE_FIELDS="article:published_time" pairing was
    # unsatisfiable and false-FAILed every cron. This is a generic-path health
    # signal, not a platform-extractor death check.
    "teamtailor": ("jsonld.jobposting", "open_graph", "html.regex"),
    "recruitee": ("recruitee.api",),
    # personio.xml is a deliberate fallback: extract_personio_xml_fallback
    # early-returns once ANY posted/published candidate exists, and every
    # healthy personio job page emits JSON-LD datePosted, so the XML path never
    # runs on healthy pages (personio.xml never appears in all_dates). The
    # honest signal for the healthy path is therefore jsonld.jobposting, a
    # generic-path health check; personio.xml remains listed for the degraded-
    # page case where the fallback legitimately produces the chosen date.
    "personio": ("personio.xml", "jsonld.jobposting"),
    "breezy": ("breezy.embedded",),
    # No dedicated extractor; jsonld.jobposting is a generic-path health signal
    # that can't distinguish jazzhr JSON-LD death from a generic parser regression.
    "jazzhr": ("jsonld.jobposting",),
    "gem": ("gem.api",),
    "workday": ("workday.cxs",),
    "oracle_hcm": ("oracle_hcm.api", "goldman_sachs.oracle"),
    "adp": ("adp.api",),
    "ukg_pro": ("ukg_pro.embedded",),
    # custom_backend's first MATRIX URL (Stripe) resolves via a dedicated
    # stripe.greenhouse extractor; amazon/bendingspoons have their own. All
    # three prefixes are accepted.
    "custom_backend": (
        "amazon_jobs.api",
        "stripe.greenhouse",
        "bendingspoons.objectid",
    ),
}

# Platforms whose native source prefix is a *generic* parser name and therefore
# needs a field check to be a meaningful drift signal. Reserved for future use:
# teamtailor previously lived here ("article:published_time") but was removed in
# the B1 fix because that field is emitted with source="open_graph", making the
# ("meta",) + field pairing unsatisfiable. Empty for now; the generic-prefix
# entries in NATIVE_SOURCES are documented as weaker health signals instead.
NATIVE_FIELDS: dict[str, str] = {}

# M1: chosen_source["source"] prefixes for fallbacks that ONLY win when the live
# page gave the native extractor nothing. A success sourced from one of these
# means the posting is effectively gone and the date is an archive/freshness
# echo — churn, not drift — so the live test skips instead of false-alarming.
# The exact fallback source strings emitted by howoldisthisjob.py (grep them
# there) are:
#   "wayback.cdx"  (extract_wayback)
#   "sitemap"      (extract_sitemap_dates)
#   "jina.render"  (extract_jina_render)
# NOTE "avature.sitemap" is a NATIVE avature source (in NATIVE_SOURCES above) and
# is intentionally NOT matched here: it starts with "avature.", not "sitemap".
# jsonld.jobposting / open_graph / meta / html.regex are generic parsers but are
# NOT in this list — a success via one of those still reaches the native-prefix
# assertion and FAILs if it is not the platform's native prefix (that is drift).
NON_NATIVE_FALLBACK_PREFIXES: tuple[str, ...] = ("wayback.", "sitemap", "jina.")

# Per-platform extra drift checks beyond "chosen source is native".
#
# jobvite: the live page's JobPosting JSON-LD (`jobvite.jsonld`) is often an
# OLDER posted date than the XML feed's `<date>` and legitimately wins the
# date-first sort, so the chosen source can be `jobvite.jsonld` even when the
# real XML feed is perfectly healthy. A chosen-source prefix check on its own
# therefore cannot detect a dead feed — it would be masked by surviving page
# JSON-LD (the exact defect from Finding 1 of the adversarial review). The
# un-maskable signal is "a `jobvite.xml`-sourced candidate exists at all": if
# the XML feed (CompanyJobs/Xml.aspx) dies platform-wide, no `jobvite.xml`
# candidate is produced even though `jobvite.jsonld` keeps surfacing. Asserting
# its presence here restores the strict feed-alive drift signal.
# Confirmed alive as of 2026-07: CompanyJobs/Xml.aspx?c=qBTaVfwj&j=oynrAfwG
# returns 200 + valid XML with <date>7/14/2026</date> for a live Versa posting.
STRICT_NATIVE_CANDIDATES: dict[str, str] = {
    "jobvite": "jobvite.xml",
}


def _direct_platform_first_urls() -> list[tuple[str, str, str]]:
    """First MATRIX URL per platform whose capability has integration == 'direct'.

    Returns a list of (platform_label, employer, url) preserving MATRIX order.
    """
    first_by_platform: dict[str, tuple[str, str, str]] = {}
    for platform, employer, url in MATRIX:
        if platform in first_by_platform:
            continue
        capability = howoldisthisjob.PLATFORM_CAPABILITIES.get(platform, {})
        if capability.get("integration") == "direct":
            first_by_platform[platform] = (platform, employer, url)
    return list(first_by_platform.values())


@unittest.skipUnless(
    LIVE_TESTS_ENABLED,
    "Live internet drift tests disabled. Set HOWOLDISTHISJOB_LIVE_TESTS=1 to run.",
)
class TestLiveExtractors(unittest.TestCase):
    """One test method per direct-integration platform.

    Methods are generated below the class body so that each platform is an
    independently selectable test (``-k lever``) and one platform's failure
    cannot hide another's. Each method calls the real ``analyze_url`` and asserts
    the NATIVE extractor is still the chosen source.
    """

    # Shared constant for generated methods (avoids a late-binding closure pitfall).
    maxDiff = None

    def _run_live_platform(self, platform: str, employer: str, url: str) -> None:
        """Shared body for every generated platform test method.

        Assertion policy (tolerates job churn, no exact-date checks):
          1. platform sanity check against EXPECTED_PLATFORMS.
          2. non-success statuses (blocked/unsupported/no_date/error or a
             network failure) are INCONCLUSIVE -> skipTest, not fail.
          3. on success, if the chosen source is a non-native fallback that only
             wins when the live page gave the native extractor nothing
             (wayback.*/sitemap/jina.* — NON_NATIVE_FALLBACK_PREFIXES), that is
             churn, not drift -> skipTest.
          4. otherwise the chosen source MUST come from the platform's native
             extractor (NATIVE_SOURCES prefix match). A fallback to a generic
             on-page source (jsonld/meta/html) that is NOT native is a DRIFT
             FINDING and fails hard.
        """
        # analyze_url can raise on total budget exhaustion / network failure;
        # treat any exception as inconclusive rather than a harness failure.
        try:
            result = howoldisthisjob.analyze_url(url)
        except Exception as exc:  # noqa: BLE001 - broad on purpose (live network)
            self.skipTest(
                f"inconclusive: analyze_url raised {type(exc).__name__}: {exc}"
            )

        detected = result.get("platform")
        acceptable = EXPECTED_PLATFORMS.get(platform, (platform,))
        self.assertIn(
            detected,
            acceptable,
            f"platform mismatch for {platform} ({employer!r}): "
            f"expected one of {acceptable}, got {detected!r}. "
            f"This is a detection-layer finding, not a drift finding.",
        )

        status = result.get("status")
        if status != "success":
            # Job gone, blocked, no date surfaced, or upstream error: cannot
            # assert anything about the native extractor today.
            self.skipTest(
                f"inconclusive: status={status!r} for {platform} ({employer!r}). "
                f"warnings={result.get('warnings')}"
            )

        chosen = result.get("chosen_source")
        self.assertIsNotNone(
            chosen,
            f"{platform} ({employer!r}) status=success but no chosen_source was set",
        )
        source = chosen.get("source")

        # M1: a success whose date only comes from a non-native fallback
        # (wayback/sitemap/jina) means the live page gave the native extractor
        # nothing — the posting is gone and an archive/freshness echo dated it.
        # That is churn, not drift, so skip. We keep the hard FAIL for a page
        # whose native extractor stopped producing while other ON-PAGE sources
        # (jsonld/meta/html) still date it — that reaches the prefix check below
        # and is genuine drift.
        if source.startswith(NON_NATIVE_FALLBACK_PREFIXES):
            self.skipTest(
                f"posting gone; rescued by {source!r} for {platform} "
                f"({employer!r}) — churn, not drift. full chosen_source={chosen}"
            )

        prefixes = NATIVE_SOURCES[platform]
        self.assertTrue(
            any(source.startswith(prefix) for prefix in prefixes),
            f"DRIFT: {platform} ({employer!r}) native extractor did not win. "
            f"chosen_source={source!r} does not start with any native prefix "
            f"{prefixes}; likely fell back to sitemap/wayback/generic meta. "
            f"full chosen_source={chosen}",
        )

        # Field-level disambiguation for platforms whose native source is a
        # generic parser name. Reserved for future use; currently empty (see
        # NATIVE_FIELDS comment above for why teamtailor was removed).
        native_field = NATIVE_FIELDS.get(platform)
        if native_field is not None:
            field = chosen.get("field")
            self.assertEqual(
                field,
                native_field,
                f"DRIFT: {platform} ({employer!r}) native source matched "
                f"({source!r}) but field was {field!r}, expected "
                f"{native_field!r}. full chosen_source={chosen}",
            )

        # Strict per-platform native-candidate presence check. For jobvite the
        # XML feed (`jobvite.xml`) can legitimately lose the date-first sort to
        # an older page-JSON-LD date (`jobvite.jsonld`), so chosen-source alone
        # is not the un-maskable feed-alive signal — we additionally require a
        # `jobvite.xml`-sourced candidate to exist. See STRICT_NATIVE_CANDIDATES.
        strict_candidate = STRICT_NATIVE_CANDIDATES.get(platform)
        if strict_candidate is not None:
            all_dates = result.get("all_dates") or []
            present = any(
                isinstance(d, dict) and d.get("source") == strict_candidate
                for d in all_dates
            )
            self.assertTrue(
                present,
                f"DRIFT: {platform} ({employer!r}) native candidate "
                f"{strict_candidate!r} is missing from all_dates; the "
                f"{strict_candidate.split('.')[0]} feed is likely dead (the "
                f"page-JSON-LD path can mask this). all_dates={all_dates}",
            )


def _make_test(platform: str, employer: str, url: str):
    def test(self):
        self._run_live_platform(platform, employer, url)

    test.__name__ = f"test_live_{platform}"
    test.__doc__ = (
        f"Live: {platform} native extractor still wins for {employer!r} "
        f"({url})."
    )
    return test


# Generate one test method per direct-integration platform. Default-arg binding
# sidesteps Python's late-binding-in-loop pitfall.
for _platform, _employer, _url in _direct_platform_first_urls():
    setattr(
        TestLiveExtractors,
        f"test_live_{_platform}",
        _make_test(_platform, _employer, _url),
    )


class TestLiveMatrixIntegrity(unittest.TestCase):
    """M2: hermetic, ALWAYS-ON guard against a silent-green live tier.

    These tests are NOT env-gated and make NO network calls — they run in the
    normal PR gate (``python3 -m unittest discover -s tests``). They exist so
    that if ``_direct_platform_first_urls()`` ever returns ``[]`` (e.g.
    PLATFORM_CAPABILITIES integration labels change, the import path breaks, or
    MATRIX is reordered so no direct platform surfaces), the suite does not
    silently report ``Ran 0 tests`` and exit 0 with drift detection dead.
    Instead this guard FAILs in the PR and the cron's Ran-0 guard
    (``.github/workflows/live-drift.yml``) is the second line of defence.
    """

    def test_direct_matrix_has_at_least_twenty_platforms(self) -> None:
        """A healthy direct tier has ~27 platforms; 20 is a generous floor."""
        urls = _direct_platform_first_urls()
        self.assertGreaterEqual(
            len(urls),
            20,
            f"_direct_platform_first_urls() returned only {len(urls)} platforms; "
            f"the live drift tier would attach {len(urls)} methods and report "
            f"'Ran {len(urls)} tests'. Investigate PLATFORM_CAPABILITIES / MATRIX.",
        )

    def test_native_sources_keys_match_direct_matrix(self) -> None:
        """NATIVE_SOURCES must cover exactly the generated direct platforms.

        Key parity in BOTH directions: a platform appearing in the generated
        live tier but missing from NATIVE_SOURCES would raise KeyError at drift
        time, and a stale NATIVE_SOURCES key would silently rot. This runs in
        the PR gate, not only at live time.
        """
        direct_platforms = {p for p, _, _ in _direct_platform_first_urls()}
        self.assertEqual(
            set(NATIVE_SOURCES),
            direct_platforms,
            "NATIVE_SOURCES keys must equal the set of direct-integration "
            "platforms. If you added/removed a platform, update BOTH "
            "NATIVE_SOURCES and the MATRIX / PLATFORM_CAPABILITIES.",
        )

    def test_generated_live_methods_match_direct_matrix(self) -> None:
        """The count of generated ``test_live_*`` methods must match the matrix.

        Catches the exact M2 failure mode: the generation loop attaching zero
        methods while the matrix is non-empty (e.g. an import or setattr bug).
        """
        direct_platforms = {p for p, _, _ in _direct_platform_first_urls()}
        generated = {
            attr[len("test_live_") :]
            for attr in dir(TestLiveExtractors)
            if attr.startswith("test_live_")
        }
        self.assertEqual(
            generated,
            direct_platforms,
            "Generated test_live_* method set must equal the direct-integration "
            "platform set. A mismatch means the generation loop did not attach a "
            "method for every platform (or attached extras).",
        )


if __name__ == "__main__":
    unittest.main()
