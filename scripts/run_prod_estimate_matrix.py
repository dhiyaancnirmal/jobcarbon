#!/usr/bin/env python3
"""Production /api/v1/estimate matrix: 3 employer URLs per supported ATS family."""

from __future__ import annotations

import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

API = "https://api.howoldisthisjob.com/api/v1/estimate"

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
    ("workable", "Jiffy", "https://apply.workable.com/jiffyshirts/j/AE2ABAA399/"),
    ("workable", "Sur", "https://apply.workable.com/surglobal/j/F56F213200/"),
    ("workable", "Close Concerns", "https://apply.workable.com/closeconcerns/j/91B29C3C99/"),
    ("ashby", "AfterQuery", "https://jobs.ashbyhq.com/AfterQuery/489d6180-c2e4-4dcf-ae8b-5a9f3b84b8c3/application"),
    ("ashby", "1Password", "https://jobs.ashbyhq.com/1password/0efcd7aa-0bcf-4c65-b7dd-627833d90f37/application"),
    ("ashby", "Mercor", "https://jobs.ashbyhq.com/mercor/ccb3dbfb-c206-41d5-a553-f2616badf76f/application"),
    ("rippling", "Rippling", "https://ats.rippling.com/rippling/jobs/bda12f6a-6afc-45af-8e6a-b0056facf15c"),
    ("rippling", "Rippling ATS team", "https://ats.rippling.com/rippling/jobs/6fa5ed25-b905-49fe-91b8-cd20d1b6aa4c"),
    ("rippling", "The Information", "https://ats.rippling.com/theinformation-jobs/jobs/f25e44e1-a197-49ce-81d0-7ba0e2d83868"),
    ("icims", "DocuSign", "https://hubcareers-docusign.icims.com/jobs/28722/principal-engineer/job"),
    ("icims", "HealthEdge", "https://careers-healthedge.icims.com/jobs/7356/senior-software-engineer/job"),
    ("icims", "Peraton", "https://careers-peraton.icims.com/jobs/164159/senior-ai-ml-engineer/job"),
    ("dover", "Netnow", "https://app.dover.com/apply/netnow/2bfb58ac-c3f9-46c6-8f94-ceb6b4950cff"),
    ("dover", "Dover (invalid id)", "https://app.dover.com/apply/netnow/00000000-0000-0000-0000-000000000000"),
    ("dover", "Dover org probe", "https://app.dover.com/apply/acme-corp/2bfb58ac-c3f9-46c6-8f94-ceb6b4950cff"),
    ("bamboohr", "Signal Advisors", "https://signal1.bamboohr.com/careers/39"),
    ("bamboohr", "Bamboo probe A", "https://signal1.bamboohr.com/careers/40"),
    ("bamboohr", "Bamboo probe B", "https://signal1.bamboohr.com/careers/38"),
    ("jobvite", "Clinch", "https://jobs.jobvite.com/clinch/job/oD2D4fw6"),
    ("jobvite", "Jobvite search", "https://jobs.jobvite.com/search"),
    ("jobvite", "Jobvite root", "https://jobs.jobvite.com/"),
    (
        "brassring",
        "Sample partner",
        "https://sjobs.brassring.com/TGnewUI/Search/home/HomeWithPreLoad?PageType=JobDetails&jobid=2244127&partnerid=25633&siteid=5439",
    ),
    ("brassring", "Brassring minimal", "https://sjobs.brassring.com/TGnewUI/Search/home/HomeWithPreLoad?jobid=1&partnerid=1&siteid=1"),
    ("brassring", "Brassring host", "https://sjobs.brassring.com/"),
    ("successfactors", "SAP jobs", "https://jobs.sap.com/job/Bangalore-Senior-Developer/1380193433/"),
    ("successfactors", "SAP root", "https://jobs.sap.com/"),
    ("successfactors", "jobs.sap probe", "https://jobs.sap.com/job/placeholder-title/1/"),
    ("avature", "Bloomberg", "https://bloomberg.avature.net/careers/JobDetail/Senior-Software-Engineer-BQuant/4661"),
    ("avature", "Avature careers root", "https://bloomberg.avature.net/careers/"),
    ("avature", "Avature feed", "https://bloomberg.avature.net/careers/SearchJobs/feed/"),
    ("teamtailor", "Teamtailor career host", "https://career.teamtailor.com/jobs/7217456-head-of-group-accounting"),
    ("teamtailor", "Flower", "https://flower.teamtailor.com/en-GB/jobs/7498746-senior-software-engineer"),
    ("teamtailor", "Unleash", "https://unleash.teamtailor.com/jobs/7358005-senior-software-engineer"),
    ("recruitee", "McDugald Steele", "https://mcdugaldsteele.recruitee.com/o/start-your-career-with-mcdugald-steele"),
    ("recruitee", "Recruitee root", "https://mcdugaldsteele.recruitee.com/"),
    ("recruitee", "Recruitee board", "https://acme.recruitee.com/o/engineer"),
    ("personio", "Contabo", "https://contabo.jobs.personio.de/job/2563171?language=en"),
    ("personio", "Personio bad job", "https://contabo.jobs.personio.de/job/99999999"),
    ("personio", "Personio host", "https://contabo.jobs.personio.de/"),
    ("breezy", "Breezy sample", "https://jobs.breezy.hr/p/865698971aa0-customer-success-agent/apply"),
    ("breezy", "Breezy co", "https://acme.breezy.hr/p/00000000-test/apply"),
    ("breezy", "Breezy root", "https://jobs.breezy.hr/"),
    ("jazzhr", "Public Citizen", "https://publiccitizen.applytojob.com/apply/VZj90FMXn0/Democracy-Team-Manager"),
    ("jazzhr", "Applytojob root", "https://publiccitizen.applytojob.com/"),
    ("jazzhr", "Applytojob board", "https://acme.applytojob.com/apply/X/Y"),
    ("gem", "Gem board", "https://jobs.gem.com/gem/am9icG9zdDpN6-87TjRV1EFRX86qqvez"),
    ("gem", "Gem root", "https://jobs.gem.com/"),
    ("gem", "Gem acme", "https://jobs.gem.com/acme/am9icG9zdDoxMjM"),
    ("workday", "NVIDIA", "https://nvidia.wd5.myworkdayjobs.com/en-US/NVIDIAExternalCareerSite/job/US-CA-Santa-Clara/Senior-Software-Engineer_JR1990000"),
    ("workday", "WD tenant probe", "https://acme.wd1.myworkdayjobs.com/job/1"),
    ("workday", "Workday host", "https://nvidia.wd5.myworkdayjobs.com/"),
    ("oracle_hcm", "Goldman Sachs", "https://higher.gs.com/roles/165686"),
    ("oracle_hcm", "Oracle CX sample", "https://eeho.fa.us2.oraclecloud.com/hcmUI/CandidateExperience/en/sites/CX_1/job/12345"),
    ("oracle_hcm", "Oracle bad id", "https://eeho.fa.us2.oraclecloud.com/hcmUI/CandidateExperience/en/sites/CX_1/job/1"),
    ("adp", "ADP client A", "https://workforcenow.adp.com/mascsr/default/mdf/recruitment/recruitment.html?ccId=19000101_000003&jobId=577657&jwId=SYS%3AJW%3A001&lang=en_US"),
    ("adp", "ADP client B", "https://workforcenow.adp.com/mascsr/default/mdf/recruitment/recruitment.html?ccId=11980045_3457&type=MP&lang=en_US"),
    ("adp", "ADP client C", "https://workforcenow.adp.com/mascsr/default/mdf/recruitment/recruitment.html?ccId=9200648049722_3&jobId=506603&jwId=9200648049722_1&lang=en_US"),
    # Paycor: detector keys off gnk=job & gni=… on any host; public deep links are rare — use synthetic query on neutral hosts.
    ("paycor", "Paycor param probe A", "https://howoldisthisjob.com/?gnk=job&gni=aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa&gns=smoke-a"),
    ("paycor", "Paycor param probe B", "https://howoldisthisjob.com/?gnk=job&gni=bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb&gns=smoke-b"),
    ("paycor", "Paycor param probe C", "https://howoldisthisjob.com/?gnk=job&gni=cccccccccccccccccccccccccccccccc&gns=smoke-c"),
    ("custom_backend", "Stripe", "https://stripe.com/jobs/listing/account-executive-hunter-uk-enterprise-retail/7451366"),
    ("custom_backend", "Amazon", "https://www.amazon.jobs/en/jobs/3202233/software-engineer-amazon"),
    ("custom_backend", "Bending Spoons", "https://jobs.bendingspoons.com/positions/6617c4b6b0f3c7a11f8d2a8e"),
]


def fetch(url: str, timeout: float = 120.0) -> tuple[int, dict]:
    q = f"{API}?url={urllib.parse.quote(url, safe='')}"
    req = urllib.request.Request(q, method="GET", headers={"User-Agent": "jobcarbon-matrix/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode()
            return resp.status, json.loads(body)
    except urllib.error.HTTPError as e:
        try:
            body = e.read().decode()
            return e.code, json.loads(body)
        except Exception:
            return e.code, {"error": {"message": str(e)}}
    except Exception as e:
        return 0, {"error": {"message": str(e)}}


def main() -> None:
    rows: list[dict] = []
    for platform, employer, job_url in MATRIX:
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
