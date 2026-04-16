import json
import socket
import unittest
import warnings
from io import BytesIO
from email.message import Message
from urllib.error import HTTPError, URLError

import jobcarbon


class FakeHTTPStream:
    def __init__(self, body: str, status: int = 200) -> None:
        self._body = body.encode("utf-8")
        self.status = status
        self.headers = Message()
        self.headers.add_header("Content-Type", "application/json; charset=utf-8")

    def read(self) -> bytes:
        return self._body

    def getcode(self) -> int:
        return self.status

    def __enter__(self) -> "FakeHTTPStream":
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        return False


class JobcarbonUnitTests(unittest.TestCase):
    def test_detect_platform_parses_supported_hosts(self) -> None:
        lever = jobcarbon.detect_platform(
            "https://jobs.lever.co/skio/bbdd5a7b-652a-43ad-b92e-58f4e970c694"
        )
        greenhouse = jobcarbon.detect_platform(
            "https://job-boards.greenhouse.io/applytogreenspark/jobs/4169702004"
        )
        ashby = jobcarbon.detect_platform(
            "https://jobs.ashbyhq.com/glimpse/767a3a59-53d6-4306-afae-6b05a265ba82"
        )
        smartrecruiters = jobcarbon.detect_platform(
            "https://jobs.smartrecruiters.com/ServiceNow/744000103790775-software-engineer"
        )
        rippling = jobcarbon.detect_platform(
            "https://ats.rippling.com/rippling/jobs/bda12f6a-6afc-45af-8e6a-b0056facf15c"
        )
        dover = jobcarbon.detect_platform(
            "https://app.dover.com/apply/netnow/2bfb58ac-c3f9-46c6-8f94-ceb6b4950cff"
        )
        workable = jobcarbon.detect_platform(
            "https://jobs.workable.com/view/5Sz2Mnf9VdJsXnPCvoYudJ/captain---n-u-piraeus-port"
        )
        icims = jobcarbon.detect_platform(
            "https://globalcareers-customer0.icims.com/jobs/6341/login"
        )
        workday = jobcarbon.detect_platform(
            "https://walmart.wd5.myworkdayjobs.com/en-US/WalmartExternal/job/Staff--Software-Engineer_R-2403353"
        )
        oracle = jobcarbon.detect_platform(
            "https://eeho.fa.us2.oraclecloud.com/hcmUI/CandidateExperience/en/sites/CX_1/job/12345"
        )
        bamboohr = jobcarbon.detect_platform("https://signal1.bamboohr.com/careers/39")
        brassring = jobcarbon.detect_platform(
            "https://sjobs.brassring.com/TGnewUI/Search/home/HomeWithPreLoad?PageType=JobDetails&jobid=3328041&partnerid=16030&siteid=6091"
        )
        adp = jobcarbon.detect_platform(
            "https://workforcenow.adp.com/mascsr/default/mdf/recruitment/recruitment.html?cid=abc123&ccId=19000101_000001&type=JS&lang=en_US&jobId=500123"
        )
        jobvite = jobcarbon.detect_platform(
            "https://jobs.jobvite.com/clinch/job/oD2D4fw6"
        )
        avature = jobcarbon.detect_platform(
            "https://bloomberg.avature.net/careers/JobDetail/Senior-Software-Engineer-BQuant/4661"
        )
        amazon = jobcarbon.detect_platform(
            "https://www.amazon.jobs/en/jobs/3202233/software-engineer-amazon"
        )
        teamtailor = jobcarbon.detect_platform(
            "https://career.teamtailor.com/jobs/7217456-head-of-group-accounting"
        )
        recruitee = jobcarbon.detect_platform(
            "https://mcdugaldsteele.recruitee.com/o/start-your-career-with-mcdugald-steele"
        )
        personio = jobcarbon.detect_platform(
            "https://contabo.jobs.personio.de/job/2563171?language=en"
        )
        breezy = jobcarbon.detect_platform(
            "https://jobs.breezy.hr/p/865698971aa0-customer-success-agent/apply"
        )
        jazzhr = jobcarbon.detect_platform(
            "https://publiccitizen.applytojob.com/apply/VZj90FMXn0/Democracy-Team-Manager"
        )
        stripe = jobcarbon.detect_platform(
            "https://stripe.com/jobs/listing/account-executive-hunter-uk-enterprise-retail/7451366"
        )
        goldman = jobcarbon.detect_platform("https://higher.gs.com/roles/165686")
        bending_spoons = jobcarbon.detect_platform(
            "https://jobs.bendingspoons.com/positions/6617c4b6b0f3c7a11f8d2a8e"
        )
        clearcompany = jobcarbon.detect_platform(
            "https://recruiting.ultiprotest.hrmdirect.com/employment/job-opening.php?req=12345"
        )
        gem = jobcarbon.detect_platform(
            "https://jobs.gem.com/gem/am9icG9zdDpN6-87TjRV1EFRX86qqvez"
        )

        self.assertEqual(
            (lever.platform, lever.org, lever.job_id),
            ("lever", "skio", "bbdd5a7b-652a-43ad-b92e-58f4e970c694"),
        )
        self.assertEqual(
            (greenhouse.platform, greenhouse.org, greenhouse.job_id),
            ("greenhouse", "applytogreenspark", "4169702004"),
        )
        self.assertEqual(
            (ashby.platform, ashby.org, ashby.job_id),
            ("ashby", "glimpse", "767a3a59-53d6-4306-afae-6b05a265ba82"),
        )
        self.assertEqual(
            (smartrecruiters.platform, smartrecruiters.org, smartrecruiters.job_id),
            ("smartrecruiters", "ServiceNow", "744000103790775"),
        )
        self.assertEqual(
            (rippling.platform, rippling.org, rippling.job_id),
            ("rippling", "rippling", "bda12f6a-6afc-45af-8e6a-b0056facf15c"),
        )
        self.assertEqual(
            (dover.platform, dover.org, dover.job_id),
            ("dover", "netnow", "2bfb58ac-c3f9-46c6-8f94-ceb6b4950cff"),
        )
        self.assertEqual(
            (workable.platform, workable.org, workable.job_id),
            ("workable", None, "5Sz2Mnf9VdJsXnPCvoYudJ"),
        )
        self.assertEqual((icims.platform, icims.job_id), ("icims", "6341"))
        self.assertEqual(
            (
                workday.platform,
                workday.org,
                workday.job_id,
                workday.extra.get("site"),
                workday.extra.get("job_path"),
            ),
            (
                "workday",
                "walmart",
                "Staff--Software-Engineer_R-2403353",
                "WalmartExternal",
                "Staff--Software-Engineer_R-2403353",
            ),
        )
        self.assertEqual(
            (oracle.platform, oracle.job_id, oracle.extra.get("site")),
            ("oracle_hcm", "12345", "CX_1"),
        )
        self.assertEqual(
            (bamboohr.platform, bamboohr.org, bamboohr.job_id),
            ("bamboohr", "signal1", "39"),
        )
        self.assertEqual(
            (
                brassring.platform,
                brassring.job_id,
                brassring.extra.get("partner_id"),
                brassring.extra.get("site_id"),
            ),
            ("brassring", "3328041", "16030", "6091"),
        )
        self.assertEqual(
            (adp.platform, adp.org, adp.job_id, adp.extra.get("cc_id")),
            ("adp", "abc123", "500123", "19000101_000001"),
        )
        self.assertEqual(
            (jobvite.platform, jobvite.org, jobvite.job_id),
            ("jobvite", "clinch", "oD2D4fw6"),
        )
        self.assertEqual(
            (avature.platform, avature.job_id, avature.extra.get("portal")),
            ("avature", "4661", "careers"),
        )
        self.assertEqual(
            (amazon.platform, amazon.job_id, amazon.extra.get("resolver")),
            ("custom_backend", "3202233", "amazon_jobs"),
        )
        self.assertEqual(
            (teamtailor.platform, teamtailor.job_id),
            ("teamtailor", "7217456-head-of-group-accounting"),
        )
        self.assertEqual(
            (recruitee.platform, recruitee.org, recruitee.job_id),
            ("recruitee", "mcdugaldsteele", "start-your-career-with-mcdugald-steele"),
        )
        self.assertEqual(
            (personio.platform, personio.org, personio.job_id),
            ("personio", "contabo", "2563171"),
        )
        self.assertEqual(
            (breezy.platform, breezy.job_id),
            ("breezy", "865698971aa0-customer-success-agent"),
        )
        self.assertEqual(
            (jazzhr.platform, jazzhr.org, jazzhr.job_id),
            ("jazzhr", "publiccitizen", "VZj90FMXn0"),
        )
        self.assertEqual(
            (stripe.platform, stripe.job_id, stripe.extra.get("resolver")),
            ("greenhouse", "7451366", "stripe"),
        )
        self.assertEqual(
            (goldman.platform, goldman.job_id, goldman.extra.get("resolver")),
            ("oracle_hcm", "165686", "goldman_sachs"),
        )
        self.assertEqual(
            (
                bending_spoons.platform,
                bending_spoons.job_id,
                bending_spoons.extra.get("resolver"),
            ),
            ("custom_backend", "6617c4b6b0f3c7a11f8d2a8e", "bending_spoons"),
        )
        self.assertEqual(clearcompany.platform, "clearcompany")
        self.assertEqual(
            (gem.platform, gem.org, gem.job_id),
            ("gem", "gem", "am9icG9zdDpN6-87TjRV1EFRX86qqvez"),
        )

    def test_detect_platform_handles_teamtailor_locale_prefix_and_breezy_subdomain(
        self,
    ) -> None:
        teamtailor = jobcarbon.detect_platform(
            "https://flower.teamtailor.com/en-GB/jobs/7498746-senior-software-engineer"
        )
        teamtailor_single_segment = jobcarbon.detect_platform(
            "https://flower.teamtailor.com/7498746-senior-software-engineer"
        )
        breezy = jobcarbon.detect_platform(
            "https://acme.breezy.hr/p/00000000-test/apply"
        )

        self.assertEqual(teamtailor.platform, "teamtailor")
        self.assertEqual(teamtailor.org, "flower")
        self.assertEqual(teamtailor.job_id, "7498746-senior-software-engineer")
        self.assertEqual(teamtailor_single_segment.platform, "teamtailor")
        self.assertEqual(
            teamtailor_single_segment.job_id,
            "7498746-senior-software-engineer",
        )
        self.assertEqual(breezy.platform, "breezy")
        self.assertEqual(breezy.job_id, "00000000-test")

    def test_detect_platform_supports_legacy_jobvite_query_urls(self) -> None:
        metadata = jobcarbon.detect_platform(
            "https://jobs.jobvite.com/CompanyJobs/Xml.aspx?c=q0oaVfwd&j=oD2D4fw6"
        )

        self.assertEqual(metadata.platform, "jobvite")
        self.assertEqual(metadata.job_id, "oD2D4fw6")
        self.assertEqual(metadata.extra.get("company_eid"), "q0oaVfwd")

    def test_extract_job_postings_handles_object_array_and_graph(self) -> None:
        html = """
        <script type="application/ld+json">
        {"@context":"https://schema.org","@type":"Organization","name":"Example"}
        </script>
        <script type="application/ld+json">
        [{"@type":"JobPosting","datePosted":"2024-01-02"},{"@type":"Thing"}]
        </script>
        <script type="application/ld+json">
        {"@graph":[{"@type":"WebPage"},{"@type":["JobPosting"],"datePosted":"2024-02-03"}]}
        </script>
        """

        postings = jobcarbon.extract_job_postings_from_html(html)

        self.assertEqual(len(postings), 2)
        self.assertEqual(postings[0]["datePosted"], "2024-01-02")
        self.assertEqual(postings[1]["datePosted"], "2024-02-03")

    def test_normalize_date_supports_multiple_formats(self) -> None:
        self.assertEqual(jobcarbon.normalize_date("2024-03-04T10:11:12Z"), "2024-03-04")
        self.assertEqual(jobcarbon.normalize_date(1710151200000), "2024-03-11")
        self.assertEqual(jobcarbon.normalize_date("20210405112233"), "2021-04-05")
        self.assertEqual(jobcarbon.normalize_date("March 4, 2024"), "2024-03-04")
        self.assertEqual(jobcarbon.normalize_date("03/04/2024"), "2024-03-04")
        self.assertEqual(
            jobcarbon.normalize_date(
                "2026-04-14T04:43:33.355+00:00",
                tz_name="America/Los_Angeles",
            ),
            "2026-04-13",
        )

    def test_choose_best_date_prefers_oldest_credible_posted_signal(self) -> None:
        dates = [
            jobcarbon.CandidateDate(
                "2024-02-01", "meta", "article:published_time", "published", "medium"
            ),
            jobcarbon.CandidateDate(
                "2024-01-10", "jsonld.jobposting", "datePosted", "posted", "high"
            ),
            jobcarbon.CandidateDate("2023-12-20", "sitemap", "lastmod", "crawl", "low"),
            jobcarbon.CandidateDate(
                "2023-12-01", "wayback.cdx", "first_snapshot", "archive", "low"
            ),
        ]

        chosen = jobcarbon.choose_best_date(dates)

        self.assertIsNotNone(chosen)
        self.assertEqual(chosen.date, "2024-01-10")
        self.assertEqual(chosen.source, "jsonld.jobposting")

    def test_detect_repost_flags_newer_refresh_signals(self) -> None:
        oldest = jobcarbon.CandidateDate(
            "2024-01-01", "jsonld.jobposting", "datePosted", "posted", "high"
        )
        dates = [
            oldest,
            jobcarbon.CandidateDate(
                "2024-03-20", "greenhouse.api", "updated_at", "refresh", "medium"
            ),
        ]
        self.assertTrue(jobcarbon.detect_repost(oldest, dates))

    def test_http_session_retries_transient_errors(self) -> None:
        calls = {"count": 0}
        sleep_calls = []

        def opener(request, timeout):
            calls["count"] += 1
            if calls["count"] < 3:
                raise URLError(socket.timeout("timed out"))
            return FakeHTTPStream('{"ok": true}')

        session = jobcarbon.HTTPSession(opener=opener, sleeper=sleep_calls.append)

        response = session.get("https://example.com", timeout=5)

        self.assertEqual(response.json(), {"ok": True})
        self.assertEqual(calls["count"], 3)
        self.assertEqual(sleep_calls, [0.5, 1.0])

    def test_platform_capabilities_expose_workable_and_integration_summary(
        self,
    ) -> None:
        capabilities = jobcarbon.list_platform_capabilities()
        platforms = {item["platform"]: item for item in capabilities}

        self.assertEqual(platforms["workable"]["integration"], "direct")
        self.assertTrue(platforms["workable"]["supported"])
        self.assertEqual(platforms["custom_backend"]["integration"], "direct")
        self.assertFalse(platforms["indeed"]["supported"])
        self.assertEqual(platforms["indeed"]["integration"], "blocked")

        summary = jobcarbon.summarize_platform_capabilities()
        self.assertGreaterEqual(summary["direct"], 20)
        self.assertGreaterEqual(summary["generic"], 2)
        self.assertEqual(summary["blocked"], 2)
        self.assertEqual(summary["unsupported"], 2)
        self.assertEqual(summary["supported"], summary["direct"] + summary["generic"])

    def test_unknown_platform_defaults_to_generic_capability(self) -> None:
        capability = jobcarbon.get_platform_capability("something_new")
        self.assertEqual(capability["integration"], "generic")
        self.assertTrue(capability["supported"])
        self.assertEqual(capability["detection"], [])

    def test_workable_embedded_extractor_reads_initial_state(self) -> None:
        payload = {
            "initialState": {
                "api/v1/jobs/5Sz2Mnf9VdJsXnPCvoYudJ": {
                    "data": {
                        "shortcode": "5Sz2Mnf9VdJsXnPCvoYudJ",
                        "title": "Captain",
                        "company": {"name": "Harbor Co"},
                        "location": {
                            "city": "Piraeus",
                            "region": "Attica",
                            "country": "Greece",
                        },
                        "employmentType": "FULL_TIME",
                        "department": {"name": "Operations"},
                        "workplace": "on_site",
                        "created": "2026-01-15T10:00:00Z",
                        "updated": "2026-02-03T12:00:00Z",
                    }
                }
            }
        }
        html = (
            "<html><body><script>window.jobBoard = "
            + json.dumps(payload)
            + ";</script></body></html>"
        )

        accumulator = jobcarbon.AnalysisAccumulator(
            url="https://jobs.workable.com/view/5Sz2Mnf9VdJsXnPCvoYudJ/captain",
            normalized_url="https://jobs.workable.com/view/5Sz2Mnf9VdJsXnPCvoYudJ/captain",
            platform="workable",
        )
        metadata = jobcarbon.URLMetadata(
            platform="workable", job_id="5Sz2Mnf9VdJsXnPCvoYudJ"
        )

        jobcarbon.extract_workable_embedded(accumulator, html, metadata)

        self.assertEqual(accumulator.title, "Captain")
        self.assertEqual(accumulator.company, "Harbor Co")
        self.assertEqual(accumulator.location, "Piraeus, Attica, Greece")
        self.assertEqual(accumulator.employment_type, "FULL_TIME")
        self.assertEqual(accumulator.hidden_insights["department"], "Operations")
        self.assertEqual(accumulator.hidden_insights["workplace"], "on_site")
        self.assertEqual(
            accumulator.hidden_insights["shortcode"], "5Sz2Mnf9VdJsXnPCvoYudJ"
        )
        posted = [
            d
            for d in accumulator.all_dates
            if d.source == "workable.embedded" and d.kind == "posted"
        ]
        refresh = [
            d
            for d in accumulator.all_dates
            if d.source == "workable.embedded" and d.kind == "refresh"
        ]
        self.assertEqual(len(posted), 1)
        self.assertEqual(posted[0].date, "2026-01-15")
        self.assertEqual(len(refresh), 1)
        self.assertEqual(refresh[0].date, "2026-02-03")

    def test_http_session_does_not_retry_non_retryable_http_errors(self) -> None:
        calls = {"count": 0}

        def opener(request, timeout):
            calls["count"] += 1
            raise HTTPError(
                url=request.full_url,
                code=404,
                msg="Not Found",
                hdrs=None,
                fp=BytesIO(b""),
            )

        session = jobcarbon.HTTPSession(opener=opener, sleeper=lambda _: None)

        with warnings.catch_warnings():
            warnings.simplefilter("ignore", ResourceWarning)
            with self.assertRaises(jobcarbon.HTTPRequestError) as ctx:
                session.get("https://example.com/missing", timeout=5)

        self.assertEqual(calls["count"], 1)
        self.assertEqual(ctx.exception.status_code, 404)
        self.assertFalse(ctx.exception.retryable)

    def test_fetch_json_raises_http_request_error_on_malformed_payload(self) -> None:
        class MalformedJSONResponse:
            text = "not json"

            @staticmethod
            def raise_for_status() -> None:
                return None

            @staticmethod
            def json() -> dict:
                raise json.JSONDecodeError("Expecting value", "not json", 0)

        class FakeSession:
            @staticmethod
            def get(url: str, timeout: int | float) -> MalformedJSONResponse:
                return MalformedJSONResponse()

        with self.assertRaises(jobcarbon.HTTPRequestError) as ctx:
            jobcarbon.fetch_json(FakeSession(), "https://example.com/bad.json")

        self.assertIn("Malformed JSON payload", str(ctx.exception))

    def test_budgeted_session_clamps_timeout_to_remaining_budget(self) -> None:
        calls: list[float] = []

        class FakeSession:
            @staticmethod
            def get(url: str, timeout: int | float) -> FakeHTTPStream:
                calls.append(float(timeout))
                return FakeHTTPStream('{"ok": true}')

        budget = jobcarbon.RequestBudget.start(1.2)
        session = jobcarbon.BudgetedSession(FakeSession(), budget)
        response = session.get("https://example.com", timeout=15)

        self.assertEqual(json.loads(response.read().decode("utf-8")), {"ok": True})
        self.assertEqual(len(calls), 1)
        self.assertLessEqual(calls[0], 1.2)
        self.assertGreaterEqual(calls[0], 0.01)

    def test_has_credible_posted_signal_detects_high_or_medium_posted_dates(
        self,
    ) -> None:
        accumulator = jobcarbon.AnalysisAccumulator(
            url="https://example.com/job",
            normalized_url="https://example.com/job",
            platform="example",
        )
        self.assertFalse(jobcarbon.has_credible_posted_signal(accumulator))

        accumulator.add_date(
            "2026-04-01",
            source="example.api",
            field="updated_at",
            kind="refresh",
            reliability="medium",
        )
        self.assertFalse(jobcarbon.has_credible_posted_signal(accumulator))

        accumulator.add_date(
            "2026-03-15",
            source="example.api",
            field="published_at",
            kind="published",
            reliability="medium",
        )
        self.assertTrue(jobcarbon.has_credible_posted_signal(accumulator))

    def test_has_comparison_evidence_detects_wayback_or_sitemap_sources(self) -> None:
        accumulator = jobcarbon.AnalysisAccumulator(
            url="https://example.com/job",
            normalized_url="https://example.com/job",
            platform="example",
        )
        self.assertFalse(jobcarbon.has_comparison_evidence(accumulator))

        accumulator.add_date(
            "2026-03-12",
            source="wayback.cdx",
            field="first_snapshot",
            kind="archive",
            reliability="low",
        )
        self.assertTrue(jobcarbon.has_comparison_evidence(accumulator))


if __name__ == "__main__":
    unittest.main()
