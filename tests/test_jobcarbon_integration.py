import json
import unittest
from pathlib import Path
from typing import Any

import jobcarbon


FIXTURES_DIR = Path(__file__).parent / "fixtures"


def load_text(name: str) -> str:
    return (FIXTURES_DIR / name).read_text()


def load_json(name: str) -> Any:
    return json.loads(load_text(name))


class FakeResponse:
    def __init__(self, *, text: str = "", json_data: Any = None, status_code: int = 200) -> None:
        self.text = text
        self._json_data = json_data
        self.status_code = status_code

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise jobcarbon.HTTPRequestError(f"HTTP {self.status_code}")

    def json(self) -> Any:
        if self._json_data is not None:
            return self._json_data
        return json.loads(self.text)


class FakeSession:
    def __init__(self, responses: dict[str, FakeResponse]) -> None:
        self.responses = responses

    def get(self, url: str, timeout: int) -> FakeResponse:
        return self.responses.get(url, FakeResponse(status_code=404))


class JobcarbonIntegrationTests(unittest.TestCase):
    def test_jsonld_primary_path_returns_rich_success_result(self) -> None:
        target_url = "https://jobs.lever.co/skio/bbdd5a7b-652a-43ad-b92e-58f4e970c694"
        session = FakeSession({target_url: FakeResponse(text=load_text("lever_job_page.html"))})

        result = jobcarbon.analyze_url(target_url, session=session, today=jobcarbon.date(2024, 3, 1))

        self.assertEqual(result["platform"], "lever")
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["likely_posted_date"], "2021-10-21")
        self.assertEqual(result["confidence"], "high")
        self.assertEqual(result["chosen_source"]["source"], "jsonld.jobposting")
        self.assertTrue(any(item["field"] == "datePosted" for item in result["all_dates"]))

    def test_greenhouse_api_beats_refresh_and_archive_signals(self) -> None:
        target_url = "https://job-boards.greenhouse.io/applytogreenspark/jobs/4169702004"
        session = FakeSession(
            {
                target_url: FakeResponse(text=load_text("no_jsonld_page.html")),
                "https://boards-api.greenhouse.io/v1/boards/applytogreenspark/jobs/4169702004": FakeResponse(
                    json_data=load_json("greenhouse_job_api.json")
                ),
                "https://web.archive.org/cdx/search/cdx?url=https%3A%2F%2Fjob-boards.greenhouse.io%2Fapplytogreenspark%2Fjobs%2F4169702004&limit=1&output=json&fl=timestamp,original&filter=statuscode:200&sort=ascending": FakeResponse(
                    json_data=load_json("wayback_first_snapshot.json")
                ),
            }
        )

        result = jobcarbon.analyze_url(target_url, session=session, today=jobcarbon.date(2024, 3, 1))

        self.assertEqual(result["likely_posted_date"], "2021-11-03")
        self.assertEqual(result["chosen_source"]["source"], "greenhouse.api")
        self.assertTrue(any(item["field"] == "updated_at" for item in result["all_dates"]))
        self.assertTrue(any(item["kind"] == "archive" for item in result["all_dates"]))

    def test_smartrecruiters_api_handles_js_blocked_page(self) -> None:
        target_url = "https://jobs.smartrecruiters.com/ServiceNow/744000103790775-software-engineer"
        session = FakeSession(
            {
                target_url: FakeResponse(text="<html><body>Please enable JS and disable any ad blocker</body></html>"),
                "https://api.smartrecruiters.com/v1/companies/ServiceNow/postings/744000103790775": FakeResponse(
                    text=json.dumps(
                        {
                            "name": "Software Engineer",
                            "company": {"name": "ServiceNow"},
                            "location": {"fullLocation": "San Diego, California, United States"},
                            "typeOfEmployment": {"label": "Full-time"},
                            "releasedDate": "2026-02-13T18:34:40.956Z",
                            "department": {"label": "Customer Outcomes"},
                        }
                    )
                ),
                "https://r.jina.ai/http://jobs.smartrecruiters.com/ServiceNow/744000103790775-software-engineer": FakeResponse(
                    text="No visible date"
                ),
                "https://web.archive.org/cdx/search/cdx?url=https%3A%2F%2Fjobs.smartrecruiters.com%2FServiceNow%2F744000103790775-software-engineer&limit=1&output=json&fl=timestamp,original&filter=statuscode:200&sort=ascending": FakeResponse(
                    json_data=[["timestamp", "original"]]
                ),
            }
        )

        result = jobcarbon.analyze_url(target_url, session=session, today=jobcarbon.date(2026, 4, 14))

        self.assertEqual(result["platform"], "smartrecruiters")
        self.assertEqual(result["company"], "ServiceNow")
        self.assertEqual(result["employment_type"], "Full-time")
        self.assertEqual(result["likely_posted_date"], "2026-02-13")
        self.assertEqual(result["chosen_source"]["source"], "smartrecruiters.api")

    def test_jina_render_supplies_visible_date_when_static_page_is_thin(self) -> None:
        target_url = "https://apply.workable.com/remote/j/8D1C44BDF7/"
        session = FakeSession(
            {
                target_url: FakeResponse(text="<html><body><div id='app'></div></body></html>"),
                "https://r.jina.ai/http://apply.workable.com/remote/j/8D1C44BDF7": FakeResponse(
                    text="Senior Engineer\nDate Posted: March 3, 2024\nRemote"
                ),
                "https://web.archive.org/cdx/search/cdx?url=https%3A%2F%2Fapply.workable.com%2Fremote%2Fj%2F8D1C44BDF7%2F&limit=1&output=json&fl=timestamp,original&filter=statuscode:200&sort=ascending": FakeResponse(
                    json_data=[["timestamp", "original"]]
                ),
            }
        )

        result = jobcarbon.analyze_url(target_url, session=session, today=jobcarbon.date(2024, 3, 10))

        self.assertEqual(result["platform"], "workable")
        self.assertEqual(result["likely_posted_date"], "2024-03-03")
        self.assertEqual(result["chosen_source"]["source"], "jina.render")

    def test_rippling_embedded_next_data_supplies_created_on_and_hidden_metadata(self) -> None:
        target_url = "https://ats.rippling.com/rippling/jobs/bda12f6a-6afc-45af-8e6a-b0056facf15c"
        session = FakeSession(
            {
                target_url: FakeResponse(
                    text=(
                        '<html><head><script id="__NEXT_DATA__" type="application/json">'
                        + json.dumps(
                            {
                                "props": {
                                    "pageProps": {
                                        "apiData": {
                                            "jobPost": {
                                                "uuid": "bda12f6a-6afc-45af-8e6a-b0056facf15c",
                                                "name": "Business Operations Manager",
                                                "companyName": "Rippling",
                                                "createdOn": "2022-12-16T10:56:58.858000-08:00",
                                                "employmentType": {
                                                    "label": "SALARIED_FT",
                                                    "id": "Salaried, full-time",
                                                },
                                                "workLocations": ["San Francisco, CA"],
                                                "department": {"name": "Bizops"},
                                                "hasAIEvaluationsEnabled": True,
                                                "payRangeDetails": [
                                                    {
                                                        "location": "Tier 1",
                                                        "currency": "USD",
                                                        "frequency": "YEAR",
                                                        "rangeStart": 180000,
                                                        "rangeEnd": 245000,
                                                        "isRemote": False,
                                                    }
                                                ],
                                            }
                                        }
                                    }
                                }
                            }
                        )
                        + "</script></head><body></body></html>"
                    )
                ),
                "https://ats.rippling.com/sitemap.xml": FakeResponse(status_code=404),
                "https://web.archive.org/cdx/search/cdx?url=https%3A%2F%2Fats.rippling.com%2Frippling%2Fjobs%2Fbda12f6a-6afc-45af-8e6a-b0056facf15c&limit=1&output=json&fl=timestamp,original&filter=statuscode:200&sort=ascending": FakeResponse(
                    json_data=[["timestamp", "original"]]
                ),
            }
        )

        result = jobcarbon.analyze_url(target_url, session=session, today=jobcarbon.date(2026, 4, 14))

        self.assertEqual(result["platform"], "rippling")
        self.assertEqual(result["company"], "Rippling")
        self.assertEqual(result["location"], "San Francisco, CA")
        self.assertEqual(result["employment_type"], "Salaried, full-time")
        self.assertEqual(result["likely_posted_date"], "2022-12-16")
        self.assertEqual(result["chosen_source"]["source"], "rippling.embedded")
        self.assertEqual(result["hidden_insights"]["department"], "Bizops")
        self.assertTrue(result["hidden_insights"]["ai_evaluations_enabled"])
        self.assertEqual(result["hidden_insights"]["pay_range_details"][0]["currency"], "USD")

    def test_icims_api_uses_base_href_host_and_prefers_posted_date(self) -> None:
        target_url = "https://globalcareers-customer0.icims.com/jobs/6341/login"
        session = FakeSession(
            {
                target_url: FakeResponse(
                    text=(
                        '<html><head><base href="https://c-12326-20260303-careers-icims-com.i.icims.com/careers-home" />'
                        "</head><body></body></html>"
                    )
                ),
                "https://c-12326-20260303-careers-icims-com.i.icims.com/api/jobs?limit=100&page=1": FakeResponse(
                    text=json.dumps(
                        {
                            "jobs": [
                                {
                                    "data": {
                                        "req_id": "6341",
                                        "slug": "6341",
                                        "title": "Sr. Customer Success Manager",
                                        "hiring_organization": "iCIMS",
                                        "full_location": "Mexico",
                                        "employment_type": "Full-time",
                                        "posted_date": "2026-04-09T15:58:00+0000",
                                        "update_date": "2026-04-14T16:04:24+0000",
                                        "apply_url": "https://globalcareers-customer0.icims.com/jobs/6341/login",
                                        "category": "Customer Success",
                                        "location_type": "remote",
                                    }
                                }
                            ]
                        }
                    )
                ),
                "https://globalcareers-customer0.icims.com/sitemap.xml": FakeResponse(status_code=404),
                "https://web.archive.org/cdx/search/cdx?url=https%3A%2F%2Fglobalcareers-customer0.icims.com%2Fjobs%2F6341%2Flogin&limit=1&output=json&fl=timestamp,original&filter=statuscode:200&sort=ascending": FakeResponse(
                    json_data=[["timestamp", "original"]]
                ),
            }
        )

        result = jobcarbon.analyze_url(target_url, session=session, today=jobcarbon.date(2026, 4, 14))

        self.assertEqual(result["platform"], "icims")
        self.assertEqual(result["company"], "iCIMS")
        self.assertEqual(result["location"], "Mexico")
        self.assertEqual(result["employment_type"], "Full-time")
        self.assertEqual(result["likely_posted_date"], "2026-04-09")
        self.assertEqual(result["chosen_source"]["source"], "icims.api")
        self.assertEqual(result["hidden_insights"]["category"], "Customer Success")
        self.assertEqual(result["hidden_insights"]["location_type"], "remote")
        self.assertTrue(any(item["field"] == "update_date" for item in result["all_dates"]))

    def test_dover_api_returns_created_date_and_metadata(self) -> None:
        target_url = "https://app.dover.com/apply/netnow/2bfb58ac-c3f9-46c6-8f94-ceb6b4950cff"
        session = FakeSession(
            {
                target_url: FakeResponse(text="<html><body><div id='root'></div></body></html>"),
                "https://app.dover.com/api/v1/inbound/application-portal-job/2bfb58ac-c3f9-46c6-8f94-ceb6b4950cff": FakeResponse(
                    text=json.dumps(
                        {
                            "id": "2bfb58ac-c3f9-46c6-8f94-ceb6b4950cff",
                            "client_name": "Netnow",
                            "title": "Front-end Engineer",
                            "created": "2025-07-16T16:23:18.435814Z",
                            "locations": [
                                {"name": "Canada", "location_type": "REMOTE"},
                                {"name": "United States", "location_type": "REMOTE"},
                                {"name": "New York, NY", "location_type": "HYBRID"},
                            ],
                            "compensation": {
                                "currency_code": "CAD",
                                "salary_range_type": "YEARLY",
                                "employment_type": "FULL_TIME",
                            },
                            "visa_support": False,
                            "active": True,
                        }
                    )
                ),
                "https://app.dover.com/sitemap.xml": FakeResponse(status_code=404),
                "https://web.archive.org/cdx/search/cdx?url=https%3A%2F%2Fapp.dover.com%2Fapply%2Fnetnow%2F2bfb58ac-c3f9-46c6-8f94-ceb6b4950cff&limit=1&output=json&fl=timestamp,original&filter=statuscode:200&sort=ascending": FakeResponse(
                    json_data=[["timestamp", "original"]]
                ),
            }
        )

        result = jobcarbon.analyze_url(target_url, session=session, today=jobcarbon.date(2026, 4, 14))

        self.assertEqual(result["platform"], "dover")
        self.assertEqual(result["company"], "Netnow")
        self.assertEqual(result["employment_type"], "FULL_TIME")
        self.assertEqual(result["likely_posted_date"], "2025-07-16")
        self.assertEqual(result["chosen_source"]["source"], "dover.api")
        self.assertEqual(result["hidden_insights"]["workplace_types"], ["hybrid", "remote"])
        self.assertEqual(result["hidden_insights"]["compensation"]["currency_code"], "CAD")

    def test_bamboohr_api_returns_date_posted_and_metadata(self) -> None:
        target_url = "https://signal1.bamboohr.com/careers/39"
        session = FakeSession(
            {
                target_url: FakeResponse(
                    text=(
                        "<html><head>"
                        "<meta property='og:site_name' content='Signal 1'/>"
                        "<meta property='og:title' content='Current Openings'/>"
                        "</head><body><div id='poRoot'></div></body></html>"
                    )
                ),
                "https://signal1.bamboohr.com/careers/39/detail": FakeResponse(
                    text=json.dumps(
                        {
                            "result": {
                                "jobOpening": {
                                    "jobOpeningShareUrl": "https://signal1.bamboohr.com/careers/39",
                                    "jobOpeningName": "Senior Full Stack Software Engineer",
                                    "jobOpeningStatus": "Open",
                                    "departmentLabel": "Application Engineering",
                                    "employmentStatusLabel": "Full-Time",
                                    "location": {
                                        "city": "Toronto",
                                        "state": "Ontario",
                                        "postalCode": "M5R 2E3",
                                        "addressCountry": "Canada",
                                    },
                                    "locationType": "Hybrid",
                                    "minimumExperience": "Senior",
                                    "seekPromoted": False,
                                    "compensation": {
                                        "payType": "Salary",
                                        "min": 180000,
                                        "max": 220000,
                                        "currency": "CAD",
                                    },
                                    "datePosted": "2026-02-24",
                                }
                            }
                        }
                    )
                ),
                "https://signal1.bamboohr.com/sitemap.xml": FakeResponse(status_code=404),
                "https://web.archive.org/cdx/search/cdx?url=https%3A%2F%2Fsignal1.bamboohr.com%2Fcareers%2F39&limit=1&output=json&fl=timestamp,original&filter=statuscode:200&sort=ascending": FakeResponse(
                    json_data=[["timestamp", "original"]]
                ),
            }
        )

        result = jobcarbon.analyze_url(target_url, session=session, today=jobcarbon.date(2026, 4, 14))

        self.assertEqual(result["platform"], "bamboohr")
        self.assertEqual(result["company"], "Signal 1")
        self.assertEqual(result["title"], "Senior Full Stack Software Engineer")
        self.assertEqual(result["location"], "Toronto, Ontario, Canada")
        self.assertEqual(result["employment_type"], "Full-Time")
        self.assertEqual(result["likely_posted_date"], "2026-02-24")
        self.assertEqual(result["chosen_source"]["source"], "bamboohr.api")
        self.assertEqual(result["hidden_insights"]["department"], "Application Engineering")
        self.assertEqual(result["hidden_insights"]["location_type"], "Hybrid")
        self.assertEqual(result["hidden_insights"]["compensation"]["currency"], "CAD")

    def test_jobvite_xml_feed_returns_posted_date_and_metadata(self) -> None:
        target_url = "https://jobs.jobvite.com/clinch/job/oD2D4fw6"
        session = FakeSession(
            {
                target_url: FakeResponse(
                    text=(
                        "<html><head>"
                        "<title>Clinch Careers - Rails Engineer (Jobvite)</title>"
                        "<meta property='og:title' content='Clinch is looking for Rails Engineer (Jobvite).'/>"
                        "</head><body><script>"
                        "window.jobviteSettings = { companyEId: 'q0oaVfwd', jobId: 'oD2D4fw6' };"
                        "</script></body></html>"
                    )
                ),
                "https://jobs.jobvite.com/CompanyJobs/Xml.aspx?c=q0oaVfwd&j=oD2D4fw6": FakeResponse(
                    text=(
                        "<?xml version='1.0' encoding='UTF-8'?>"
                        "<result>"
                        "<id>oD2D4fw6</id>"
                        "<title>Rails Engineer (Jobvite)</title>"
                        "<requisitionId>RE1234</requisitionId>"
                        "<category>Computers/Software</category>"
                        "<jobtype>Full-Time</jobtype>"
                        "<location>New York, NY, United States</location>"
                        "<date>10/5/2017</date>"
                        "<detail-url>https://jobs.jobvite.com/clinch/job/oD2D4fw6</detail-url>"
                        "</result>"
                    )
                ),
                "https://jobs.jobvite.com/sitemap.xml": FakeResponse(status_code=404),
                "https://web.archive.org/cdx/search/cdx?url=https%3A%2F%2Fjobs.jobvite.com%2Fclinch%2Fjob%2FoD2D4fw6&limit=1&output=json&fl=timestamp,original&filter=statuscode:200&sort=ascending": FakeResponse(
                    json_data=[["timestamp", "original"]]
                ),
            }
        )

        result = jobcarbon.analyze_url(target_url, session=session, today=jobcarbon.date(2026, 4, 14))

        self.assertEqual(result["platform"], "jobvite")
        self.assertEqual(result["company"], "Clinch")
        self.assertEqual(result["title"], "Rails Engineer (Jobvite)")
        self.assertEqual(result["location"], "New York, NY, United States")
        self.assertEqual(result["employment_type"], "Full-Time")
        self.assertEqual(result["likely_posted_date"], "2017-10-05")
        self.assertEqual(result["chosen_source"]["source"], "jobvite.xml")
        self.assertEqual(result["hidden_insights"]["category"], "Computers/Software")
        self.assertEqual(result["hidden_insights"]["requisition_id"], "RE1234")
        self.assertEqual(result["hidden_insights"]["jobvite_company_eid"], "q0oaVfwd")

    def test_brassring_html_returns_dc_date_and_company(self) -> None:
        target_url = "https://sjobs.brassring.com/TGnewUI/Search/home/HomeWithPreLoad?PageType=JobDetails&jobid=2244127&partnerid=25633&siteid=5439"
        session = FakeSession(
            {
                target_url: FakeResponse(
                    text=(
                        "<html><head>"
                        "<meta name='DC.Date' scheme='iso8601' content=' 2026-04-14' />"
                        "<meta property='og:title' content='Java Developer - Infosys - Job Details' />"
                        "</head><body></body></html>"
                    )
                ),
                "https://sjobs.brassring.com/sitemap.xml": FakeResponse(status_code=404),
                "https://web.archive.org/cdx/search/cdx?url=https%3A%2F%2Fsjobs.brassring.com%2FTGnewUI%2FSearch%2Fhome%2FHomeWithPreLoad%3FPageType%3DJobDetails%26jobid%3D2244127%26partnerid%3D25633%26siteid%3D5439&limit=1&output=json&fl=timestamp,original&filter=statuscode:200&sort=ascending": FakeResponse(
                    json_data=[["timestamp", "original"]]
                ),
            }
        )

        result = jobcarbon.analyze_url(target_url, session=session, today=jobcarbon.date(2026, 4, 14))

        self.assertEqual(result["platform"], "brassring")
        self.assertEqual(result["title"], "Java Developer")
        self.assertEqual(result["company"], "Infosys")
        self.assertEqual(result["likely_posted_date"], "2026-04-14")
        self.assertEqual(result["chosen_source"]["source"], "brassring.html")

    def test_successfactors_rss_promotes_unknown_page_by_html_fingerprint(self) -> None:
        target_url = "https://jobs.sap.com/job/Bangalore-Senior-Developer/1380193433/"
        session = FakeSession(
            {
                target_url: FakeResponse(
                    text=(
                        "<html lang='en-US'><head>"
                        "<meta itemprop='datePosted' content='Thu Apr 02 00:00:00 UTC 2026' />"
                        "</head><body>"
                        "<script>j2w.init({\"ssoCompanyId\":\"SAP\"});</script>"
                        "<img src='https://rmkcdn.successfactors.com/example.jpg'/>"
                        "</body></html>"
                    )
                ),
                "https://jobs.sap.com/services/rss/job/?locale=en_US&keywords=Bangalore-Senior-Developer": FakeResponse(
                    text=(
                        "<?xml version='1.0' encoding='UTF-8'?>"
                        "<rss version='2.0'><channel>"
                        "<item>"
                        "<title>Senior Developer</title>"
                        "<link>https://jobs.sap.com/job/Bangalore-Senior-Developer/1380193433/?feedId=null</link>"
                        "<pubDate>Thu, 02 Apr 2026 00:00:00 GMT</pubDate>"
                        "</item>"
                        "</channel></rss>"
                    )
                ),
                "https://jobs.sap.com/sitemap.xml": FakeResponse(status_code=404),
                "https://web.archive.org/cdx/search/cdx?url=https%3A%2F%2Fjobs.sap.com%2Fjob%2FBangalore-Senior-Developer%2F1380193433&limit=1&output=json&fl=timestamp,original&filter=statuscode:200&sort=ascending": FakeResponse(
                    json_data=[["timestamp", "original"]]
                ),
            }
        )

        result = jobcarbon.analyze_url(target_url, session=session, today=jobcarbon.date(2026, 4, 14))

        self.assertEqual(result["platform"], "successfactors")
        self.assertEqual(result["title"], "Senior Developer")
        self.assertEqual(result["likely_posted_date"], "2026-04-02")
        self.assertEqual(result["chosen_source"]["source"], "successfactors.rss")

    def test_avature_feed_returns_pubdate_and_matches_job_detail_url(self) -> None:
        target_url = "https://bloomberg.avature.net/careers/JobDetail/Senior-Software-Engineer-BQuant/4661"
        session = FakeSession(
            {
                target_url: FakeResponse(
                    text=(
                        "<html><head>"
                        "<meta property='og:title' content='Senior Software Engineer - BQuant' />"
                        '<meta name="avature.portal.id" content="careers" />'
                        "</head><body></body></html>"
                    )
                ),
                "https://bloomberg.avature.net/careers/SearchJobs/feed/": FakeResponse(
                    text=(
                        "<?xml version='1.0' encoding='UTF-8'?>"
                        "<rss version='2.0'><channel>"
                        "<item>"
                        "<title>Senior Software Engineer - BQuant</title>"
                        "<link>https://bloomberg.avature.net/careers/JobDetail/Senior-Software-Engineer-BQuant/4661</link>"
                        "<pubDate>Mon, 05 Aug 2024 00:00:00 +0000</pubDate>"
                        "</item>"
                        "</channel></rss>"
                    )
                ),
                "https://bloomberg.avature.net/careers/sitemap_index.xml": FakeResponse(
                    text=(
                        "<?xml version='1.0' encoding='UTF-8'?>"
                        "<sitemapindex xmlns='http://www.sitemaps.org/schemas/sitemap/0.9'>"
                        "<sitemap><loc>https://bloomberg.avature.net/careers/sitemap.xml</loc></sitemap>"
                        "</sitemapindex>"
                    )
                ),
                "https://bloomberg.avature.net/careers/sitemap.xml": FakeResponse(
                    text=(
                        "<?xml version='1.0' encoding='UTF-8'?>"
                        "<urlset xmlns='http://www.sitemaps.org/schemas/sitemap/0.9'>"
                        "<url><loc>https://bloomberg.avature.net/careers/JobDetail/Senior-Software-Engineer-BQuant/4661</loc><lastmod>2025-10-14</lastmod></url>"
                        "</urlset>"
                    )
                ),
                "https://bloomberg.avature.net/sitemap.xml": FakeResponse(status_code=404),
                "https://web.archive.org/cdx/search/cdx?url=https%3A%2F%2Fbloomberg.avature.net%2Fcareers%2FJobDetail%2FSenior-Software-Engineer-BQuant%2F4661&limit=1&output=json&fl=timestamp,original&filter=statuscode:200&sort=ascending": FakeResponse(
                    json_data=[["timestamp", "original"]]
                ),
            }
        )

        result = jobcarbon.analyze_url(target_url, session=session, today=jobcarbon.date(2026, 4, 14))

        self.assertEqual(result["platform"], "avature")
        self.assertEqual(result["title"], "Senior Software Engineer - BQuant")
        self.assertEqual(result["likely_posted_date"], "2024-08-05")
        self.assertEqual(result["chosen_source"]["source"], "avature.feed")
        self.assertTrue(any(item["source"] == "avature.sitemap" for item in result["all_dates"]))

    def test_sitemap_and_wayback_remain_comparison_evidence(self) -> None:
        target_url = "https://example.com/jobs/123"
        session = FakeSession(
            {
                target_url: FakeResponse(
                    text=(
                        "<html><head>"
                        "<meta property='article:published_time' content='2024-03-01T10:00:00Z'>"
                        "</head><body></body></html>"
                    )
                ),
                "https://example.com/sitemap.xml": FakeResponse(
                    text=(
                        "<?xml version='1.0' encoding='UTF-8'?>"
                        "<urlset xmlns='http://www.sitemaps.org/schemas/sitemap/0.9'>"
                        "<url><loc>https://example.com/jobs/123</loc><lastmod>2023-12-01</lastmod></url>"
                        "</urlset>"
                    )
                ),
                "https://web.archive.org/cdx/search/cdx?url=https%3A%2F%2Fexample.com%2Fjobs%2F123&limit=1&output=json&fl=timestamp,original&filter=statuscode:200&sort=ascending": FakeResponse(
                    json_data=load_json("wayback_first_snapshot.json")
                ),
            }
        )

        result = jobcarbon.analyze_url(target_url, session=session, today=jobcarbon.date(2024, 3, 10))

        self.assertEqual(result["likely_posted_date"], "2024-03-01")
        self.assertEqual(result["chosen_source"]["field"], "article:published_time")
        self.assertTrue(any(item["source"] == "sitemap" for item in result["all_dates"]))
        self.assertTrue(any(item["source"] == "wayback.cdx" for item in result["all_dates"]))

    def test_repost_conflict_is_flagged_when_refresh_date_is_much_newer(self) -> None:
        target_url = "https://example.com/jobs/reposted"
        session = FakeSession(
            {
                target_url: FakeResponse(
                    text=(
                        "<html><head>"
                        "<script type='application/ld+json'>"
                        '{"@type":"JobPosting","title":"Engineer","datePosted":"2024-01-01"}'
                        "</script>"
                        "<meta property='article:published_time' content='2024-03-15T10:00:00Z'>"
                        "</head><body></body></html>"
                    )
                ),
                "https://example.com/sitemap.xml": FakeResponse(status_code=404),
                "https://web.archive.org/cdx/search/cdx?url=https%3A%2F%2Fexample.com%2Fjobs%2Freposted&limit=1&output=json&fl=timestamp,original&filter=statuscode:200&sort=ascending": FakeResponse(
                    json_data=[["timestamp", "original"]]
                ),
            }
        )

        result = jobcarbon.analyze_url(target_url, session=session, today=jobcarbon.date(2024, 4, 1))

        self.assertEqual(result["likely_posted_date"], "2024-01-01")
        self.assertTrue(result["reposted_likely"])
        self.assertIn("reposting or refreshing is likely", result["summary"])

    def test_hidden_insights_collect_platform_metadata(self) -> None:
        target_url = "https://jobs.smartrecruiters.com/ServiceNow/744000103790775-software-engineer"
        session = FakeSession(
            {
                target_url: FakeResponse(text="<html><body>Please enable JS and disable any ad blocker</body></html>"),
                "https://api.smartrecruiters.com/v1/companies/ServiceNow/postings/744000103790775": FakeResponse(
                    text=json.dumps(
                        {
                            "name": "Software Engineer",
                            "company": {"name": "ServiceNow"},
                            "releasedDate": "2026-02-13T18:34:40.956Z",
                            "department": {"label": "Customer Outcomes"},
                            "customField": [
                                {"fieldLabel": "Work Persona", "valueLabel": "Flexible"},
                                {"fieldLabel": "Region", "valueLabel": "AMS - North America and Canada"},
                            ],
                        }
                    )
                ),
                "https://r.jina.ai/http://jobs.smartrecruiters.com/ServiceNow/744000103790775-software-engineer": FakeResponse(text="No visible date"),
                "https://web.archive.org/cdx/search/cdx?url=https%3A%2F%2Fjobs.smartrecruiters.com%2FServiceNow%2F744000103790775-software-engineer&limit=1&output=json&fl=timestamp,original&filter=statuscode:200&sort=ascending": FakeResponse(
                    json_data=[["timestamp", "original"]]
                ),
            }
        )

        result = jobcarbon.analyze_url(target_url, session=session, today=jobcarbon.date(2026, 4, 14))

        self.assertEqual(result["hidden_insights"]["department"], "Customer Outcomes")
        self.assertEqual(result["hidden_insights"]["work_persona"], "Flexible")
        self.assertEqual(result["hidden_insights"]["region"], "AMS - North America and Canada")

    def test_workable_embedded_payload_supplies_posted_date_and_metadata(self) -> None:
        target_url = "https://jobs.workable.com/view/5Sz2Mnf9VdJsXnPCvoYudJ/captain"
        workable_payload = {
            "initialState": {
                "api/v1/jobs/5Sz2Mnf9VdJsXnPCvoYudJ": {
                    "data": {
                        "shortcode": "5Sz2Mnf9VdJsXnPCvoYudJ",
                        "title": "Captain",
                        "company": {"name": "Harbor Co"},
                        "location": {"city": "Piraeus", "region": "Attica", "country": "Greece"},
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
            + json.dumps(workable_payload)
            + ";</script></body></html>"
        )
        session = FakeSession(
            {
                target_url: FakeResponse(text=html),
                "https://jobs.workable.com/sitemap.xml": FakeResponse(status_code=404),
                "https://web.archive.org/cdx/search/cdx?url=https%3A%2F%2Fjobs.workable.com%2Fview%2F5Sz2Mnf9VdJsXnPCvoYudJ%2Fcaptain&limit=1&output=json&fl=timestamp,original&filter=statuscode:200&sort=ascending": FakeResponse(
                    json_data=[["timestamp", "original"]]
                ),
            }
        )

        result = jobcarbon.analyze_url(target_url, session=session, today=jobcarbon.date(2026, 4, 14))

        self.assertEqual(result["platform"], "workable")
        self.assertEqual(result["title"], "Captain")
        self.assertEqual(result["company"], "Harbor Co")
        self.assertEqual(result["location"], "Piraeus, Attica, Greece")
        self.assertEqual(result["employment_type"], "FULL_TIME")
        self.assertEqual(result["likely_posted_date"], "2026-01-15")
        self.assertEqual(result["chosen_source"]["source"], "workable.embedded")
        self.assertEqual(result["hidden_insights"]["department"], "Operations")
        self.assertEqual(result["hidden_insights"]["workplace"], "on_site")
        self.assertTrue(any(item["field"] == "updated" and item["kind"] == "refresh" for item in result["all_dates"]))

    def test_workday_cxs_api_returns_start_date_and_metadata(self) -> None:
        target_url = "https://nvidia.wd5.myworkdayjobs.com/en-US/NVIDIAExternalCareerSite/job/US-CA-Santa-Clara/Senior-Software-Engineer_JR1990000"
        api_url = "https://nvidia.wd5.myworkdayjobs.com/wday/cxs/nvidia/NVIDIAExternalCareerSite/job/US-CA-Santa-Clara/Senior-Software-Engineer_JR1990000"
        session = FakeSession(
            {
                target_url: FakeResponse(text="<html><body><div id='root'></div></body></html>"),
                api_url: FakeResponse(
                    text=json.dumps(
                        {
                            "jobPostingInfo": {
                                "title": "Senior Software Engineer",
                                "location": "US-CA-Santa Clara",
                                "jobRequisitionLocation": {"descriptor": "US, CA, Santa Clara"},
                                "timeType": "Full time",
                                "jobReqId": "JR1990000",
                                "jobPostingSiteId": "NVIDIAExternalCareerSite",
                                "country": {"descriptor": "United States of America"},
                                "startDate": "2026-01-10",
                                "endDate": "2026-06-10",
                            },
                            "hiringOrganization": {"name": "NVIDIA"},
                        }
                    )
                ),
                "https://nvidia.wd5.myworkdayjobs.com/sitemap.xml": FakeResponse(status_code=404),
                "https://web.archive.org/cdx/search/cdx?url=https%3A%2F%2Fnvidia.wd5.myworkdayjobs.com%2Fen-US%2FNVIDIAExternalCareerSite%2Fjob%2FUS-CA-Santa-Clara%2FSenior-Software-Engineer_JR1990000&limit=1&output=json&fl=timestamp,original&filter=statuscode:200&sort=ascending": FakeResponse(
                    json_data=[["timestamp", "original"]]
                ),
            }
        )

        result = jobcarbon.analyze_url(target_url, session=session, today=jobcarbon.date(2026, 4, 14))

        self.assertEqual(result["platform"], "workday")
        self.assertEqual(result["company"], "NVIDIA")
        self.assertEqual(result["title"], "Senior Software Engineer")
        self.assertEqual(result["location"], "US, CA, Santa Clara")
        self.assertEqual(result["employment_type"], "Full time")
        self.assertEqual(result["likely_posted_date"], "2026-01-10")
        self.assertEqual(result["chosen_source"]["source"], "workday.cxs")
        self.assertEqual(result["hidden_insights"]["job_req_id"], "JR1990000")
        self.assertEqual(result["hidden_insights"]["country"], "United States of America")
        self.assertTrue(any(item["field"] == "endDate" and item["kind"] == "expiry" for item in result["all_dates"]))

    def test_oracle_hcm_api_returns_posted_start_date_and_hidden_insights(self) -> None:
        target_url = "https://eeho.fa.us2.oraclecloud.com/hcmUI/CandidateExperience/en/sites/CX_1/job/12345"
        api_url = (
            "https://eeho.fa.us2.oraclecloud.com/hcmRestApi/resources/latest/recruitingCEJobRequisitionDetails"
            "?onlyData=true&expand=all&finder=ById;Id=%2212345%22,siteNumber=CX_1"
        )
        session = FakeSession(
            {
                target_url: FakeResponse(text="<html><body><div id='root'></div></body></html>"),
                api_url: FakeResponse(
                    text=json.dumps(
                        {
                            "items": [
                                {
                                    "Title": "Principal Backend Engineer",
                                    "PrimaryLocation": "Austin, TX, United States",
                                    "JobSchedule": "Full-time",
                                    "Category": "Engineering",
                                    "RequisitionType": "Standard",
                                    "HotJobFlag": True,
                                    "WorkplaceType": "Hybrid",
                                    "ExternalPostedStartDate": "2025-11-03",
                                    "ExternalPostedEndDate": "2026-05-03",
                                }
                            ]
                        }
                    )
                ),
                "https://eeho.fa.us2.oraclecloud.com/sitemap.xml": FakeResponse(status_code=404),
                "https://web.archive.org/cdx/search/cdx?url=https%3A%2F%2Feeho.fa.us2.oraclecloud.com%2FhcmUI%2FCandidateExperience%2Fen%2Fsites%2FCX_1%2Fjob%2F12345&limit=1&output=json&fl=timestamp,original&filter=statuscode:200&sort=ascending": FakeResponse(
                    json_data=[["timestamp", "original"]]
                ),
            }
        )

        result = jobcarbon.analyze_url(target_url, session=session, today=jobcarbon.date(2026, 4, 14))

        self.assertEqual(result["platform"], "oracle_hcm")
        self.assertEqual(result["title"], "Principal Backend Engineer")
        self.assertEqual(result["location"], "Austin, TX, United States")
        self.assertEqual(result["employment_type"], "Full-time")
        self.assertEqual(result["likely_posted_date"], "2025-11-03")
        self.assertEqual(result["chosen_source"]["source"], "oracle_hcm.api")
        self.assertEqual(result["hidden_insights"]["category"], "Engineering")
        self.assertEqual(result["hidden_insights"]["workplace_type"], "Hybrid")
        self.assertTrue(any(item["field"] == "ExternalPostedEndDate" and item["kind"] == "expiry" for item in result["all_dates"]))

    def test_blocked_platform_returns_blocked_status(self) -> None:
        result = jobcarbon.analyze_url("https://www.indeed.com/viewjob?jk=123")

        self.assertEqual(result["platform"], "indeed")
        self.assertEqual(result["status"], "blocked")
        self.assertIsNone(result["likely_posted_date"])
        self.assertTrue(result["warnings"])


if __name__ == "__main__":
    unittest.main()
