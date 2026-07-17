"""Curated production job URLs, 3 per supported ATS family.

Shared by scripts/run_prod_estimate_matrix.py (prod API smoke) and
tests/live/test_live_extractors.py (direct-extractor drift tier).
"""

from __future__ import annotations

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
    # NOTE: the prior GMU row (org 1128, job/10003873) was removed after the
    # posting was taken down and 302-redirected to listings.jobs.gmu.edu, a
    # generic search page that has no PageUp markup. Replaced with a verified
    # live Virginia Tech requisition that still serves the pageup.html date.
    ("pageup", "Virginia Tech", "https://careers.pageuppeople.com/968/cw/en-us/job/537012"),
    ("pageup", "CSU Careers", "https://careers.pageuppeople.com/873/cw/en-us/job/556173/2627-ay-temporary-faculty-pool-lecturer-information-systems"),
    ("pageup", "SUNY Upstate", "https://careers.pageuppeople.com/977/cw/en-us/job/497147/registered-nurse-1-ns26-coronary-care-unit-nights"),
    ("workable", "Jiffy", "https://apply.workable.com/jiffyshirts/j/5D4758376C/"),
    ("workable", "Jiffy", "https://apply.workable.com/jiffyshirts/j/61FE69559E/"),
    ("workable", "Jiffy", "https://apply.workable.com/jiffyshirts/j/46C6F7EA28/"),
    ("ashby", "AfterQuery", "https://jobs.ashbyhq.com/AfterQuery/489d6180-c2e4-4dcf-ae8b-5a9f3b84b8c3/application"),
    ("ashby", "OpenAI", "https://jobs.ashbyhq.com/openai/e8558280-69dc-438a-b905-623f75ae6d62"),
    ("ashby", "LangChain", "https://jobs.ashbyhq.com/langchain/c75915ba-a32b-4e17-873d-19b47564170d/"),
    # NOTE: two prior Rippling rows (jobs/9516d5f1... and jobs/0c59f357...) were
    # removed after those postings were taken down and 302-redirected to
    # www.rippling.com/careers/open-roles, a generic Next.js page whose
    # __NEXT_DATA__ has no jobPost.createdOn. Replaced with verified live
    # postings that still serve the rippling.embedded createdOn date.
    ("rippling", "Routeware", "https://ats.rippling.com/routeware-careers/jobs/8ef5cce4-e963-47f9-a8b8-2494a25af370"),
    ("rippling", "Just Appraised", "https://ats.rippling.com/just-appraised-jobs/jobs/c224bc39-251f-47ba-b6f8-45b187c40471"),
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
    ("jobvite", "Versa Networks", "https://jobs.jobvite.com/versa-networks/job/oynrAfwG"),
    ("jobvite", "Visionist", "https://jobs.jobvite.com/versa-networks/job/oTIuAfwp"),
    ("jobvite", "NinjaOne", "https://jobs.jobvite.com/versa-networks/job/oUN2zfw2"),
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
    ("avature", "Bloomberg", "https://bloomberg.avature.net/careers/JobDetail/Senior-Software-Engineer-ETL-Pipeline-Orchestration-Platform/14228"),
    ("avature", "Bloomberg", "https://bloomberg.avature.net/careers/JobDetail/Senior-Software-Engineer-Service-Mesh-Security-and-Configuration/14248"),
    ("avature", "Bloomberg", "https://bloomberg.avature.net/careers/JobDetail/Senior-Quantitative-Analyst-Interest-Rate-Modeling-Risk-Analytics/13711"),
    # NOTE: the prior teamtailor first row (job/7217456-head-of-group-
    # accounting on career.teamtailor.com) was removed after the posting was
    # taken down and returned HTTP 410 Gone. analyze_url raised PageFetchError on
    # it, which the live tier catches as an inconclusive skipTest — permanently
    # silencing the teamtailor drift signal. Replaced with a verified-live
    # Teamtailor posting (Legal Counsel) on the same career.teamtailor.com host
    # that still serves a native date (analyze_url chosen_source.source ==
    # 'html.regex', field='datePosted').
    ("teamtailor", "Teamtailor career host", "https://career.teamtailor.com/jobs/7952282-legal-counsel"),
    ("teamtailor", "Flower", "https://flower.teamtailor.com/en-GB/jobs/7498746-senior-software-engineer"),
    ("teamtailor", "Unleash", "https://unleash.teamtailor.com/jobs/7358005-senior-software-engineer"),
    ("recruitee", "Sioux", "https://sioux.recruitee.com/o/electrical-engineer"),
    ("recruitee", "Sioux", "https://sioux.recruitee.com/o/electrical-lead-engineer"),
    ("recruitee", "McDugald Steele", "https://mcdugaldsteele.recruitee.com/o/start-your-career-with-mcdugald-steele"),
    # NOTE: two prior Contabo personio rows (job/2558937 and job/2563171)
    # were removed after those postings were taken down and return HTTP 404.
    # The live tier catches that as an inconclusive skipTest, permanently
    # silencing the personio drift signal (and masking the fact that the prior
    # NATIVE_SOURCES=("personio.xml",) entry was unsatisfiable on healthy pages
    # — see tests/live/test_live_extractors.py). Replaced with verified-live
    # Contabo postings (job/2627040 and job/2650536) sourced from the Contabo
    # personio XML feed; both resolve via analyze_url with platform=personio,
    # chosen_source.source='jsonld.jobposting' field='datePosted'.
    ("personio", "Contabo", "https://contabo.jobs.personio.de/job/2627040?language=en"),
    ("personio", "Contabo", "https://contabo.jobs.personio.de/job/2552882?language=en"),
    ("personio", "Contabo", "https://contabo.jobs.personio.de/job/2650536?language=en"),
    ("breezy", "Betclic Group", "https://betclic-group.breezy.hr/p/34f0c1c3981801-senior-hr-business-partner-f-m"),
    ("breezy", "Betclic Group", "https://betclic-group.breezy.hr/p/8bf5c2979a7601-senior-software-engineer-f-m"),
    ("breezy", "Betclic Group", "https://betclic-group.breezy.hr/p/e78310f01f5e01-ai-augmented-data-engineer-f-m"),
    # NOTE: the prior Public Citizen jazzhr rows (jobCodes VZj90FMXn0,
    # geaavJOBFs, NO7zPVCUfT) were removed after all three postings were taken
    # down and returned HTTP 410 Gone (geaavJOBFs was further Wayback-rescued to
    # a status=success, which previously false-FAILed the live tier — see the
    # NON_NATIVE_FALLBACK_PREFIXES fix in tests/live/test_live_extractors.py).
    # Replaced with three verified-live postings across distinct employers:
    # each returns HTTP 200 and is dated natively via jsonld.jobposting
    # (analyze_url chosen_source.source == 'jsonld.jobposting').
    ("jazzhr", "Landing", "https://landing.applytojob.com/apply/9584th3Ncy/Billing-Analyst"),
    ("jazzhr", "The VA Group", "https://tvag.applytojob.com/apply/sLgZ8fTjhc/Executive-Assistant-To-CEO"),
    ("jazzhr", "Career.io", "https://talentwwinc.applytojob.com/apply/uw2WjsGMur/Product-Engineer"),
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
