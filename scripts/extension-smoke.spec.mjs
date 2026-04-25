import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { chromium } from "playwright";
import { expect, test } from "playwright/test";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const extensionPath = path.resolve(__dirname, "../extension");
const brandedBadgeSelector = '.howoldisthisjob-age-badge[href^="https://howoldisthisjob.com/?url="]';
const badgeTextPattern = /^(?:Today|\d+d|\d+mo|\d+y)$/;

const listCases = [
  {
    name: "lever-list",
    ats: "lever",
    url: "https://jobs.lever.co/skio",
    progressive: true,
  },
  {
    name: "ashby-list",
    ats: "ashby",
    url: "https://jobs.ashbyhq.com/openai",
    progressive: true,
  },
  {
    name: "greenhouse-list",
    ats: "greenhouse",
    url: "https://job-boards.greenhouse.io/vercel",
    progressive: true,
  },
  {
    name: "recruitee-list",
    ats: "recruitee",
    url: "https://mcdugaldsteele.recruitee.com/",
  },
];

const detailCases = [
  {
    name: "lever-detail",
    ats: "lever",
    url: "https://jobs.lever.co/skio/bbdd5a7b-652a-43ad-b92e-58f4e970c694",
  },
  {
    name: "greenhouse-detail",
    ats: "greenhouse",
    url: "https://job-boards.greenhouse.io/applytogreenspark/jobs/4169702004",
  },
  {
    name: "smartrecruiters-detail",
    ats: "smartrecruiters",
    url: "https://jobs.smartrecruiters.com/ServiceNow/744000103790775-software-engineer",
  },
  {
    name: "workable-detail",
    ats: "workable",
    url: "https://apply.workable.com/jiffyshirts/j/5D4758376C/",
  },
  {
    name: "ashby-detail",
    ats: "ashby",
    url: "https://jobs.ashbyhq.com/AfterQuery/489d6180-c2e4-4dcf-ae8b-5a9f3b84b8c3/application",
  },
  {
    name: "rippling-detail",
    ats: "rippling",
    url: "https://ats.rippling.com/rippling/jobs/9516d5f1-0abb-435d-93a4-c1a669852103",
  },
  {
    name: "dayforce-detail",
    ats: "dayforce",
    url: "https://jobs.dayforcehcm.com/en-US/cookboardman/CANDIDATEPORTAL/jobs/9508",
  },
  {
    name: "teamtailor-detail",
    ats: "teamtailor",
    url: "https://career.teamtailor.com/jobs/7217456-head-of-group-accounting",
  },
  {
    name: "recruitee-detail",
    ats: "recruitee",
    url: "https://mcdugaldsteele.recruitee.com/o/project-landscape-architect-high-end-residential-design-build",
  },
  {
    name: "personio-detail",
    ats: "personio",
    url: "https://contabo.jobs.personio.de/job/2558937?language=en",
  },
  {
    name: "breezy-detail",
    ats: "breezy",
    url: "https://jobs.breezy.hr/p/aed06a3baa44-senior-backend-product-engineer-node-js-llm-assistants-automation",
  },
  {
    name: "jazzhr-detail",
    ats: "jazzhr",
    url: "https://publiccitizen.applytojob.com/apply/VZj90FMXn0/Democracy-Team-Manager",
  },
  {
    name: "dover-detail",
    ats: "dover",
    url: "https://app.dover.com/apply/netnow/2bfb58ac-c3f9-46c6-8f94-ceb6b4950cff",
  },
  {
    name: "workday-detail",
    ats: "workday",
    url: "https://nvidia.wd5.myworkdayjobs.com/en-US/NVIDIAExternalCareerSite/job/US-TX-Austin/Senior-Software-Engineer---Compilers-and-Applied-AI_JR2016639",
  },
  {
    name: "successfactors-detail",
    ats: "successfactors",
    url: "https://jobs.sap.com/job/Bangalore-Senior-Developer/1380193433/",
  },
  {
    name: "icims-detail",
    ats: "icims",
    url: "https://hubcareers-docusign.icims.com/jobs/28722/principal-engineer/job",
    allowCardFallback: true,
  },
  {
    name: "jobvite-detail",
    ats: "jobvite",
    url: "https://jobs.jobvite.com/versa-networks/job/ohCiufwp",
  },
  {
    name: "gem-detail",
    ats: "gem",
    url: "https://jobs.gem.com/gem/4965519002",
  },
  {
    name: "adp-detail",
    ats: "adp",
    url: "https://workforcenow.adp.com/mascsr/default/mdf/recruitment/recruitment.html?ccId=19000101_000001&cid=cb73ca7c-d700-429b-a6ab-bf50165187ec&lang=en_US&source=IN&jobId=588407",
  },
  {
    name: "ukg-pro-detail",
    ats: "ukg_pro",
    url: "https://recruiting.ultipro.com/AME1108AMRL/JobBoard/3391213d-67ca-497b-be36-e41affd954f7/OpportunityDetail?opportunityId=b330caec-91c7-4200-85cb-48a13027d347",
  },
];

const knownGapCases = [
  {
    name: "brassring-detail-expired",
    ats: "brassring",
    url: "https://sjobs.brassring.com/TGnewUI/Search/home/HomeWithPreLoad?PageType=JobDetails&jobid=844820&partnerid=25037&siteid=5010",
  },
  {
    name: "pageup-detail-no-date",
    ats: "pageup",
    url: "https://careers.pageuppeople.com/346/cdw/en/job/678381/senior-software-engineer-javaapi",
  },
  {
    name: "taleo-detail-no-date",
    ats: "taleo",
    url: "https://php.taleo.net/careersection/40/jobdetail.ftl?job=106780",
  },
  {
    name: "oracle-detail-no-date",
    ats: "oracle_hcm",
    url: "https://eeho.fa.us2.oraclecloud.com/hcmUI/CandidateExperience/en/sites/CX_1/job/12345",
  },
  {
    name: "bamboohr-detail-flaky",
    ats: "bamboohr",
    url: "https://signal1.bamboohr.com/careers/39",
  },
  {
    name: "avature-detail-headless-error",
    ats: "avature",
    url: "https://bloomberg.avature.net/careers/JobDetail/Senior-Software-Engineer-BQuant/4661",
  },
];

let context;
let extensionId;
let userDataDir;

function truthyEnv(name) {
  const raw = process.env[name] || "";
  return ["1", "true", "yes"].includes(raw.toLowerCase());
}

function selectedCaseKeys() {
  const raw = process.env.HOWOLDISTHISJOB_EXTENSION_SMOKE_CASES?.trim();
  if (!raw) {
    return null;
  }

  return new Set(
    raw
      .split(",")
      .map((value) => value.trim().toLowerCase())
      .filter(Boolean)
  );
}

function shouldRunCase(testCase) {
  const selected = selectedCaseKeys();
  if (!selected) {
    return true;
  }
  return selected.has(testCase.name.toLowerCase()) || selected.has(testCase.ats.toLowerCase());
}

async function waitForServiceWorker(targetContext) {
  let [serviceWorker] = targetContext.serviceWorkers();
  if (!serviceWorker) {
    serviceWorker = await targetContext.waitForEvent("serviceworker");
  }
  return serviceWorker;
}

async function ensureExtensionContext() {
  if (context) {
    return { context, extensionId };
  }

  if (!userDataDir) {
    userDataDir = fs.mkdtempSync(path.join(os.tmpdir(), "howoldisthisjob-extension-smoke-"));
  }

  context = await chromium.launchPersistentContext(userDataDir, {
    channel: "chromium",
    headless: true,
    args: [
      `--disable-extensions-except=${extensionPath}`,
      `--load-extension=${extensionPath}`,
    ],
  });

  const serviceWorker = await waitForServiceWorker(context);
  extensionId = new URL(serviceWorker.url()).host;

  return { context, extensionId };
}

async function closeExtraPages(targetContext) {
  const pages = targetContext.pages();
  for (const page of pages.slice(1)) {
    await page.close();
  }
}

async function newPage() {
  const { context: targetContext } = await ensureExtensionContext();
  await closeExtraPages(targetContext);
  const page = targetContext.pages()[0] || (await targetContext.newPage());
  await page.bringToFront();
  return page;
}

async function newPopupPage() {
  const { context: targetContext, extensionId: currentExtensionId } = await ensureExtensionContext();
  const page = await targetContext.newPage();
  await page.goto(`chrome-extension://${currentExtensionId}/popup.html`, {
    waitUntil: "domcontentloaded",
    timeout: 30000,
  });
  return page;
}

async function installListProgressCapture(page) {
  await page.addInitScript(() => {
    const selector = '.howoldisthisjob-age-badge[data-howoldisthisjob-context="list"]';
    const events = [];

    const record = () => {
      const count = document.querySelectorAll(selector).length;
      const last = events[events.length - 1];
      if (!last || last.count !== count) {
        events.push({ count, t: Math.round(performance.now()) });
      }
      window.__howoldisthisjobSmokeListEvents = events;
    };

    const start = () => {
      record();
      const observer = new MutationObserver(() => record());
      observer.observe(document.documentElement, {
        childList: true,
        subtree: true,
      });
      window.addEventListener("load", record, { once: true });
      window.__howoldisthisjobSmokeListEvents = events;
    };

    window.__howoldisthisjobSmokeListEvents = events;
    if (document.documentElement) {
      start();
    } else {
      document.addEventListener("DOMContentLoaded", start, { once: true });
    }
  });
}

async function readListProgress(page) {
  return page.evaluate(() => window.__howoldisthisjobSmokeListEvents || []);
}

function positiveDeltas(events) {
  const deltas = [];
  for (let index = 1; index < events.length; index += 1) {
    const delta = events[index].count - events[index - 1].count;
    if (delta > 0) {
      deltas.push(delta);
    }
  }
  return deltas;
}

async function validateBrandedBadge(badge, page) {
  await expect(badge).toBeVisible();
  await expect(badge).toHaveAttribute("href", /https:\/\/howoldisthisjob\.com\/\?url=/);
  await expect(badge).toHaveAttribute("target", "_blank");
  await expect(badge).toHaveAttribute("rel", /noopener/);
  await expect(badge.locator(".howoldisthisjob-age-badge__logo")).toBeVisible();
  await expect(badge.locator(".howoldisthisjob-age-badge__label")).toHaveText(badgeTextPattern);

  const dataUrl = await badge.getAttribute("data-howoldisthisjob-url");
  const href = await badge.getAttribute("href");
  expect(dataUrl).toBeTruthy();
  expect(href).toBeTruthy();

  const parsedHref = new URL(href, page.url());
  expect(parsedHref.origin).toBe("https://howoldisthisjob.com");
  expect(parsedHref.searchParams.get("url")).toBe(dataUrl);

  const logoSrc = await badge.locator(".howoldisthisjob-age-badge__logo").getAttribute("src");
  expect(logoSrc).toMatch(/^chrome-extension:\/\/.+\/logo-badge\.svg$/);
}

async function waitForBadge(page, contextName, timeout = 30000) {
  const selector = `${brandedBadgeSelector}[data-howoldisthisjob-context="${contextName}"]`;
  const badge = page.locator(selector).first();
  await expect(badge).toBeVisible({ timeout });
  await validateBrandedBadge(badge, page);
  return badge;
}

async function waitForDetailCard(page, timeout = 30000) {
  const card = page.locator(".howoldisthisjob-detail-card").first();
  await expect(card).toBeVisible({ timeout });
  return card;
}

async function countVisibleBadges(page, contextName) {
  return page.locator(`${brandedBadgeSelector}[data-howoldisthisjob-context="${contextName}"]`).count();
}

test.beforeAll(async () => {
  await ensureExtensionContext();
});

test.afterAll(async () => {
  await context?.close();
});

test.describe.configure({ mode: "serial" });

for (const testCase of listCases.filter(shouldRunCase)) {
  test(`${testCase.name} renders branded list badges`, async () => {
    const page = await newPage();
    if (testCase.progressive) {
      await installListProgressCapture(page);
    }

    await page.goto(testCase.url, { waitUntil: "domcontentloaded", timeout: 60000 });
    await waitForBadge(page, "list", 45000);
  });
}

for (const testCase of detailCases.filter(shouldRunCase)) {
  test(`${testCase.name} renders a single branded detail control`, async () => {
    const page = await newPage();
    await page.goto(testCase.url, { waitUntil: "domcontentloaded", timeout: 60000 });

    const badgeLocator = page.locator(`${brandedBadgeSelector}[data-howoldisthisjob-context="detail"]`);
    const cardLocator = page.locator(".howoldisthisjob-detail-card");

    if (testCase.allowCardFallback) {
      await expect(async () => {
        const badgeCount = await badgeLocator.count();
        const cardCount = await cardLocator.count();
        expect(badgeCount + cardCount).toBeGreaterThan(0);
      }).toPass({ timeout: 45000 });

      if ((await badgeLocator.count()) > 0) {
        await waitForBadge(page, "detail", 5000);
        await expect(badgeLocator).toHaveCount(1);
        await expect(cardLocator).toHaveCount(0);
        return;
      }

      await waitForDetailCard(page, 5000);
      await expect(cardLocator).toHaveCount(1);
      await expect(badgeLocator).toHaveCount(0);
      return;
    }

    await waitForBadge(page, "detail", 45000);
    await expect(badgeLocator).toHaveCount(1);
    await expect(cardLocator).toHaveCount(0);
  });
}

for (const testCase of knownGapCases.filter(shouldRunCase)) {
  test(`${testCase.name} does not render a branded badge by default`, async () => {
    test.skip(
      !truthyEnv("HOWOLDISTHISJOB_EXTENSION_SMOKE_INCLUDE_KNOWN_GAPS"),
      "Known no-date or headless-hostile ATS cases are opt-in."
    );

    const page = await newPage();
    await page.goto(testCase.url, { waitUntil: "domcontentloaded", timeout: 60000 });
    await page.waitForTimeout(8000);

    await expect(page.locator(`${brandedBadgeSelector}[data-howoldisthisjob-context="detail"]`)).toHaveCount(0);
  });
}

test("popup page declared by the manifest renders", async () => {
  const popupPage = await newPopupPage();
  await expect(popupPage.getByText("How Old Is This Job?")).toBeVisible();
  await expect(popupPage.locator("#scan-summary")).toBeVisible();
  await expect(popupPage.locator("#scan-button")).toBeVisible();
});
