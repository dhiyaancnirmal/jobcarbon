#!/usr/bin/env python3
"""Production /api/v1/estimate matrix: 3 employer URLs per supported ATS family."""

from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

API = "https://api.howoldisthisjob.com/api/v1/estimate"
REQUEST_DELAY_SECONDS = float(os.environ.get("HOWOLDISTHISJOB_MATRIX_DELAY_SECONDS", "2.0"))
MAX_ATTEMPTS = int(os.environ.get("HOWOLDISTHISJOB_MATRIX_MAX_ATTEMPTS", "3"))
RATE_LIMIT_RETRY_SECONDS = float(
    os.environ.get("HOWOLDISTHISJOB_MATRIX_RATE_LIMIT_RETRY_SECONDS", "30.0")
)

# (expected_platform_label, employer, url) — label is the plan bucket; API may return resolver-specific platform.
MATRIX: list[tuple[str, str, str]] = [
    ("lever", "Skio", "https://jobs.lever.co/skio/bbdd5a7b-652a-43ad-b92e-58f4e970c694"),
    ("lever", "Plaid", "https://jobs.lever.co/plaid/0afb2b7b-7e54-40e4-a8f6-642ac1df00f6"),
    ("lever", "CAIS", "https://jobs.lever.co/aisafety/116247a4-2940-4dce-b7d5-a6190328fd4e"),
    ("greenhouse", "GreenSpark", "https://job-boards.greenhouse.io/applytogreenspark/jobs/4169702004"),
    ("greenhouse", "Tebra", "https://boards.greenhouse.io/tebra/jobs/4670199005"),
    ("greenhouse", "dbt Labs", "https://boards.greenhouse.io/dbtlabsinc/jobs/4666468005"),
    ("smartrecruiters", "ServiceNow", "https://jobs.smartrecruiters.com/ServiceNow/744000103790775-software-engineer"),
    ("smartrecruiters", "Wabtec", "https://jobs.smartrecruiters.com/Wabtec/3743990012009076-siemens-teamcenter-administrator"),
    ("smartrecruiters", "Bosch", "https://jobs.smartrecruiters.com/BoschGroup/744000118827217-senior-principal-engineer-end-to-end-ai-training-framework"),
    ("dayforce", "Cook & Boardman", "https://jobs.dayforcehcm.com/en-US/cookboardman/CANDIDATEPORTAL/jobs/9508"),
    ("dayforce", "Cook & Boardman", "https://jobs.dayforcehcm.com/en-US/cookboardman/CANDIDATEPORTAL/jobs/14035"),
    ("dayforce", "Cook & Boardman", "https://jobs.dayforcehcm.com/cookboardman/CANDIDATEPORTAL/jobs/11951"),
    ("pageup", "George Mason University", "https://careers.pageuppeople.com/1128/cw/en-us/job/10003873/personal-trainer"),
    ("pageup", "CSU Careers", "https://careers.pageuppeople.com/873/cw/en-us/job/556173/2627-ay-temporary-faculty-pool-lecturer-information-systems"),
    ("pageup", "SUNY Upstate", "https://careers.pageuppeople.com/977/cw/en-us/job/497147/registered-nurse-1-ns26-coronary-care-unit-nights"),
    ("workable", "Jiffy", "https://apply.workable.com/jiffyshirts/j/5D4758376C/"),
    ("workable", "Jiffy", "https://apply.workable.com/jiffyshirts/j/61FE69559E/"),
    ("workable", "Jiffy", "https://apply.workable.com/jiffyshirts/j/46C6F7EA28/"),
    ("ashby", "AfterQuery", "https://jobs.ashbyhq.com/AfterQuery/489d6180-c2e4-4dcf-ae8b-5a9f3b84b8c3/application"),
    ("ashby", "OpenAI", "https://jobs.ashbyhq.com/openai/e8558280-69dc-438a-b905-623f75ae6d62"),
    ("ashby", "LangChain", "https://jobs.ashbyhq.com/langchain/c75915ba-a32b-4e17-873d-19b47564170d/"),
    ("rippling", "Rippling", "https://ats.rippling.com/rippling/jobs/9516d5f1-0abb-435d-93a4-c1a669852103"),
    ("rippling", "Rippling", "https://ats.rippling.com/rippling/jobs/0c59f357-3095-40e9-a27b-d02039906c19"),
    ("rippling", "Rippling", "https://ats.rippling.com/rippling/jobs/84d388b6-7656-434c-8862-0312eb6b97ac"),
    ("icims", "DocuSign", "https://hubcareers-docusign.icims.com/jobs/28722/principal-engineer/job"),
    ("icims", "HealthEdge", "https://careers-healthedge.icims.com/jobs/7356/senior-software-engineer/job"),
    ("icims", "Peraton", "https://careers-peraton.icims.com/jobs/164159/senior-ai-ml-engineer/job"),
    ("dover", "Netnow", "https://app.dover.com/apply/netnow/2bfb58ac-c3f9-46c6-8f94-ceb6b4950cff"),
    ("dover", "Refine", "https://app.dover.com/apply/joinrefine/01f87af9-6558-4eb7-b7dc-20834c6b32ae"),
    ("dover", "Champ AI", "https://app.dover.com/apply/champ/aa7a49d7-9679-4401-8bff-6ace5a0521f9"),
    ("bamboohr", "Signal Advisors", "https://signal1.bamboohr.com/careers/39"),
    ("bamboohr", "Signal Advisors", "https://signal1.bamboohr.com/careers/40"),
    ("bamboohr", "Signal Advisors", "https://signal1.bamboohr.com/careers/41"),
    ("jobvite", "Versa Networks", "https://jobs.jobvite.com/versa-networks/job/ohCiufwp"),
    ("jobvite", "Visionist", "https://jobs.jobvite.com/visionist/job/o8qlxfwa"),
    ("jobvite", "NinjaOne", "https://jobs.jobvite.com/ninjaone/job/oJMWwfwH"),
    ("taleo", "Toronto Community Housing", "https://tre.tbe.taleo.net/tre01/ats/careers/requisition.jsp?cws=45&org=TCHC&rid=10531"),
    ("taleo", "Toronto Community Housing", "https://tre.tbe.taleo.net/tre01/ats/careers/requisition.jsp?cws=45&org=TCHC&rid=10526"),
    ("taleo", "Toronto Community Housing", "https://tre.tbe.taleo.net/tre01/ats/careers/requisition.jsp?cws=45&org=TCHC&rid=10530"),
    (
        "brassring",
        "Lockheed Martin",
        "https://sjobs.brassring.com/TGnewUI/Search/home/HomeWithPreLoad?PageType=JobDetails&jobid=844820&partnerid=25037&siteid=5010",
    ),
    ("brassring", "Lockheed Martin", "https://sjobs.brassring.com/TGnewUI/Search/home/HomeWithPreLoad?PageType=JobDetails&jobid=842693&partnerid=25037&siteid=5010"),
    ("brassring", "Lockheed Martin", "https://sjobs.brassring.com/TGnewUI/Search/home/HomeWithPreLoad?PageType=JobDetails&jobid=841172&partnerid=25037&siteid=5010"),
    ("successfactors", "SAP", "https://jobs.sap.com/job/Bangalore-Senior-Developer/1380193433/"),
    ("successfactors", "SAP", "https://jobs.sap.com/job/San-Ramon-Senior-Platform-Infrastructure-Engineer-CA-945-83/1381394633/"),
    ("successfactors", "SAP", "https://jobs.sap.com/job/Oak-Brook-RISE-Cloud-Architect-and-Advisor%2C-Global-Cloud-Operations%2C-Chicago-IL-60523/1381007333/"),
    ("avature", "Bloomberg", "https://bloomberg.avature.net/careers/JobDetail/Senior-Software-Engineer-Automation-Services/11267"),
    ("avature", "Bloomberg", "https://bloomberg.avature.net/careers/JobDetail/2026-Bloomberg-Customer-Support-Representative-Japanese-Speaker-Tokyo/6504"),
    ("avature", "Bloomberg", "https://bloomberg.avature.net/careers/JobDetail/Sr-Financial-Specialist-Technology-Finance-Finance-Administration/10402"),
    ("teamtailor", "Teamtailor career host", "https://career.teamtailor.com/jobs/7217456-head-of-group-accounting"),
    ("teamtailor", "Flower", "https://flower.teamtailor.com/en-GB/jobs/7498746-senior-software-engineer"),
    ("teamtailor", "Unleash", "https://unleash.teamtailor.com/jobs/7358005-senior-software-engineer"),
    ("recruitee", "Sioux", "https://sioux.recruitee.com/o/electrical-engineer"),
    ("recruitee", "Sioux", "https://sioux.recruitee.com/o/electrical-lead-engineer"),
    ("recruitee", "McDugald Steele", "https://mcdugaldsteele.recruitee.com/o/start-your-career-with-mcdugald-steele"),
    ("personio", "Contabo", "https://contabo.jobs.personio.de/job/2558937?language=en"),
    ("personio", "Contabo", "https://contabo.jobs.personio.de/job/2552882?language=en"),
    ("personio", "Contabo", "https://contabo.jobs.personio.de/job/2563171?language=en"),
    ("breezy", "Breezy HR", "https://jobs.breezy.hr/p/aed06a3baa44-senior-backend-product-engineer-node-js-llm-assistants-automation"),
    ("breezy", "Breezy HR", "https://jobs.breezy.hr/p/865698971aa0-customer-success-agent"),
    ("breezy", "Breezy HR", "https://jobs.breezy.hr/p/1ab950cd7b1d-senior-cloud-platform-engineer-aws?gh_src=Obvious+Ventures+Portfolio+Companies+job+board"),
    ("jazzhr", "Public Citizen", "https://publiccitizen.applytojob.com/apply/VZj90FMXn0/Democracy-Team-Manager"),
    ("jazzhr", "Public Citizen", "https://publiccitizen.applytojob.com/apply/geaavJOBFs/Legal-Director"),
    ("jazzhr", "Public Citizen", "https://publiccitizen.applytojob.com/apply/NO7zPVCUfT/Human-Resources-Assistant"),
    ("gem", "Gem", "https://jobs.gem.com/gem/4965519002"),
    ("gem", "Gem", "https://jobs.gem.com/gem/am9icG9zdDqDithvbhmHP-qlNqqexmro"),
    ("gem", "Gem", "https://jobs.gem.com/gem/am9icG9zdDr7_B0I_F2XWut73Lt3y18F"),
    ("workday", "NVIDIA", "https://nvidia.wd5.myworkdayjobs.com/en-US/NVIDIAExternalCareerSite/job/US-TX-Austin/Senior-Software-Engineer---Compilers-and-Applied-AI_JR2016639"),
    ("workday", "NVIDIA", "https://nvidia.wd5.myworkdayjobs.com/en-US/NVIDIAExternalCareerSite/job/US-NY-New-York/Senior-Research-Scientist--Digital-Biology_JR2016635-1"),
    ("workday", "NVIDIA", "https://nvidia.wd5.myworkdayjobs.com/en-US/NVIDIAExternalCareerSite/job/US-CA-Santa-Clara/Software-Engineering-Intern--Robot-Learning-Platform---Fall-2026_JR2015575"),
    ("oracle_hcm", "Goldman Sachs", "https://higher.gs.com/roles/161630"),
    ("oracle_hcm", "Goldman Sachs", "https://higher.gs.com/roles/165052"),
    ("oracle_hcm", "Goldman Sachs", "https://higher.gs.com/roles/168356"),
    ("adp", "LIIF", "https://workforcenow.adp.com/mascsr/default/mdf/recruitment/recruitment.html?ccId=19000101_000001&cid=cb73ca7c-d700-429b-a6ab-bf50165187ec&lang=en_US&source=IN&jobId=588407"),
    ("adp", "LIIF", "https://workforcenow.adp.com/mascsr/default/mdf/recruitment/recruitment.html?ccId=19000101_000001&cid=cb73ca7c-d700-429b-a6ab-bf50165187ec&lang=en_US&source=IN&jobId=577942"),
    ("adp", "LIIF", "https://workforcenow.adp.com/mascsr/default/mdf/recruitment/recruitment.html?ccId=19000101_000001&cid=cb73ca7c-d700-429b-a6ab-bf50165187ec&lang=en_US&source=IN&jobId=589253"),
    ("ukg_pro", "American Renal", "https://recruiting.ultipro.com/AME1108AMRL/JobBoard/3391213d-67ca-497b-be36-e41affd954f7/OpportunityDetail?opportunityId=b330caec-91c7-4200-85cb-48a13027d347"),
    ("ukg_pro", "ACTS", "https://recruiting.ultipro.com/ACT1002ACTS/JobBoard/73856c51-3afd-4794-a61e-077a4b32a17d/OpportunityDetail?opportunityId=a5ff9485-2f8f-4876-83c1-24d512d9492d"),
    ("ukg_pro", "Pacific Premier Bank", "https://recruiting.ultipro.com/PAC1009/JobBoard/37e95049-80e2-145c-b48c-f826b780e4d6/OpportunityDetail?opportunityId=0725ff83-f983-4196-ae6b-b6d46682c9f6"),
    ("paycor", "Diocese of Green Bay", "https://www.gbdioc.org/careers?gnk=job&gni=8a7883ac9be7cb38019bf368c0720352&gns=Internal%20Applicant"),
    ("paycor", "Cincinnati Zoo", "https://cincinnatizoo.org/about-us/job-opportunities/?gnk=job&gni=8a7885ac96d0a1a0019722fb4ec77619&lang=en"),
    ("paycor", "Populous", "https://populous.com/careers?gnk=job&gni=8a78879e9c9ca640019cbacb46066ef9&gns=Recruiter"),
    ("custom_backend", "Stripe", "https://stripe.com/jobs/listing/account-executive-hunter-uk-enterprise-retail/7451366"),
    ("custom_backend", "Amazon", "https://www.amazon.jobs/en/jobs/a9f39b36-86c7-45fe-b7f1-49b7670ab13e/software-engineer"),
    ("custom_backend", "Bending Spoons", "https://jobs.bendingspoons.com/positions/6617c4b6b0f3c7a11f8d2a8e"),
]


def fetch(url: str, timeout: float = 120.0) -> tuple[int, dict]:
    q = f"{API}?url={urllib.parse.quote(url, safe='')}"
    req = urllib.request.Request(q, method="GET", headers={"User-Agent": "howoldisthisjob-matrix/1.0"})
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                body = resp.read().decode()
                return resp.status, json.loads(body)
        except urllib.error.HTTPError as e:
            try:
                body = e.read().decode()
                payload = json.loads(body)
            except Exception:
                payload = {"error": {"message": str(e)}}
            if e.code == 429 and attempt < MAX_ATTEMPTS:
                retry_after = e.headers.get("Retry-After")
                try:
                    delay = float(retry_after) if retry_after else RATE_LIMIT_RETRY_SECONDS
                except ValueError:
                    delay = RATE_LIMIT_RETRY_SECONDS
                time.sleep(delay)
                continue
            return e.code, payload
        except Exception as e:
            return 0, {"error": {"message": str(e)}}
    return 0, {"error": {"message": "Request attempts exhausted."}}


def main() -> None:
    rows: list[dict] = []
    for index, (platform, employer, job_url) in enumerate(MATRIX):
        if index > 0 and REQUEST_DELAY_SECONDS > 0:
            time.sleep(REQUEST_DELAY_SECONDS)
        t0 = time.perf_counter()
        code, payload = fetch(job_url)
        elapsed_ms = int((time.perf_counter() - t0) * 1000)
        status = payload.get("status") if isinstance(payload, dict) else None
        plat = payload.get("platform") if isinstance(payload, dict) else None
        err = (payload.get("error") or {}).get("message") if isinstance(payload, dict) else None
        summary = (payload.get("summary") or "")[:120] if isinstance(payload, dict) else ""
        rows.append(
            {
                "matrix_platform": platform,
                "employer": employer,
                "url": job_url,
                "http": code,
                "result_status": status,
                "detected_platform": plat,
                "error": err,
                "summary_snip": summary,
                "elapsed_ms": elapsed_ms,
            }
        )
        print(json.dumps(rows[-1], ensure_ascii=False), flush=True)

    out_path = sys.argv[1] if len(sys.argv) > 1 else "matrix_results.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(rows, f, indent=2, ensure_ascii=False)
    print(f"Wrote {len(rows)} rows to {out_path}", file=sys.stderr)


if __name__ == "__main__":
    main()
