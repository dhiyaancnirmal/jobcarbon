# How Old Is This Job? Chrome Extension

This extension injects age badges next to supported ATS job links on list pages.
It also recovers direct employer ATS links from LinkedIn, Indeed, and Google Careers pages when those pages expose a source/apply URL locally.
The popup can also manually scan the current page for supported job links and list quick-open results in a compact scrollable panel.

## Current coverage

- Lever
- Greenhouse
- Ashby
- SmartRecruiters
- Workable
- Teamtailor
- Recruitee
- Dayforce
- PageUp
- Taleo
- UKG Pro / UltiPro

## Aggregator assist

- LinkedIn
- Indeed
- Google Careers

On those pages, the extension does not scrape the aggregator itself. It looks for the original employer apply link already present in the page, unwraps common redirect URLs, and then runs the normal ATS age lookup on that source URL.

## Install locally

1. Open `chrome://extensions`.
2. Enable Developer Mode.
3. Click `Load unpacked`.
4. Select `/Users/dhiyaan/Code/howoldisthisjob/extension`.

The extension calls the production batch API at `https://api.howoldisthisjob.com/api/v1/batch-estimate`.

## Popup scan

1. Open the target page in Chrome.
2. Click the extension action.
3. Click `Scan current page`.

This uses Chrome's action-triggered tab access to inspect the active page for supported ATS links, query the batch API, and show a short result list that opens full searches on `howoldisthisjob.com`.

## Manual release check

Before shipping an unpacked extension build:

1. Open `chrome://extensions`, click `Reload` for `How Old Is This Job?`, and confirm there are no extension errors.
2. Open `https://jobs.lever.co/skio/bbdd5a7b-652a-43ad-b92e-58f4e970c694`, click the toolbar action, and confirm the popup shows a dated `Software Engineer` result.
3. Open `https://jobs.ashbyhq.com/openai`, click the toolbar action, and confirm the popup loads a small current window of jobs, shows pending jobs as `Waiting to scan` while loading, and then moves dated results to the top.
4. Confirm Ashby list badges appear only around the visible/near-visible jobs and scrolling loads more badges without extension errors.
