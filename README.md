# JobAlfred job lists

[![Refresh job lists](https://github.com/BytArc/jobalfred-jobs/actions/workflows/refresh.yml/badge.svg)](https://github.com/BytArc/jobalfred-jobs/actions/workflows/refresh.yml)
[![Data: CC BY 4.0](https://img.shields.io/badge/data-CC%20BY%204.0-lightgrey)](LICENSE-DATA.md)
[![Code: MIT](https://img.shields.io/badge/code-MIT-lightgrey)](LICENSE)

Free lists of open roles, built from employers' own public job boards and refreshed daily.

Every Apply link goes straight to the employer. Closed roles are removed on every run.

<!-- counts:start -->
Refreshed 05 Nov 2026, 22:29 UTC.

| List | Open roles | Table | JSON |
| --- | --- | --- | --- |
| India roles at global companies | 1095 | [Open](lists/india-gcc.md) | [india-gcc.json](data/india-gcc.json) |
| Remote roles in the EU | 1048 | [Open](lists/remote-eu.md) | [remote-eu.json](data/remote-eu.json) |
| Roles in Portugal | 370 | [Open](lists/portugal.md) | [portugal.json](data/portugal.json) |
| EU roles that state visa sponsorship | 29 | [Open](lists/eu-visa-sponsorship.md) | [eu-visa-sponsorship.json](data/eu-visa-sponsorship.json) |
<!-- counts:end -->

## Before you apply

- **Roles change fast.** If a role has closed since the last refresh, the employer's page will say so.
- **Visa sponsorship:** a posting saying it offers sponsorship is not a guarantee. Confirm with the employer in writing that it applies to your role, your nationality and your country, before you resign, move or pay for anything. This is not immigration advice.
- **Remote EU:** Europe and EMEA are wider than the EU, and employers may limit which countries they hire in. The Stated scope column shows what each employer lists.

## Fill with JobAlfred

Each row also has a **Fill with JobAlfred** link. That is our own product, and these lists are how we introduce it: a free Chrome extension, by [BytArc](https://bytarc.com/), that fills job application forms from your CV. You check every answer and press Submit yourself.

JobAlfred is the new name for JobPilot. The Chrome Web Store listing still shows JobPilot until the rename ships.

You never need the extension to use these lists.

## How the lists are built

**Sources.** Official public job-board APIs only:

| Source | Used | Why |
|---|---|---|
| [Greenhouse Job Board API](https://docs.greenhouse.io/job-board.html) | Yes | Public read access, no key needed |
| [Lever Postings API](https://github.com/lever/postings-api) | Yes | Public read access. We keep to its `Crawl-delay: 1` |
| [Ashby public job posting API](https://developers.ashbyhq.com/docs/public-job-posting-api) | Yes | Unlisted jobs are skipped |
| Workday | No | We have not found an official public API |
| iCIMS | No | We have not found an official public API |
| SmartRecruiters, Workable | No | Their `robots.txt` rules out general crawling |
| Recruitee | No | Its docs require a token from 10 February 2027 |
| LinkedIn, Indeed, Naukri | Never | We do not scrape job boards |

So these lists show only part of what a company has open. Many large employers hire through Workday, which matters most for the India list.

**Rate.** One request at a time per host, at most one a second on Lever and Ashby and two a second on Greenhouse. The User-Agent names this repository.

**Matching.** Each list has one rule, tested in `tests/test_classify.py`:

| List | A role is on it when |
|---|---|
| India | It is located in India, at a company headquartered and founded outside India |
| Remote EU | The employer marks it remote and it names the EU, Europe, EMEA or an EU country |
| Portugal | It is located in Portugal |
| EU visa sponsorship | It is in the EU-27 and its posting states sponsorship, for that role's country |

**Visa sponsorship is never inferred.** A row needs a clear statement in the posting, quoted in the table. These do not count: relocation support alone, "may be available", "where applicable", "for some roles", promises about another country, or any refusal anywhere in the posting. The UK, Norway and Switzerland are not in the EU, so they are not on this list. Postings in English only, for now.

**Freshness.** Rows come from the live APIs on every run, so a role that leaves a board leaves the list. Roles first posted more than a year ago are left out, because they are usually evergreen. If a board fails, its rows are kept for up to 3 days. If more than 30% of boards fail, the run stops and nothing changes.

**Links.** Apply links carry UTM parameters and no redirect, so the address you see is the employer's own. The employer may see that the visit came from JobAlfred.

## Use the data

Each list is available as JSON in [`data/`](data/). Job descriptions are read for matching and are not stored.

## Licence

Data: [CC BY 4.0](LICENSE-DATA.md). Code: [MIT](LICENSE). Employers keep all rights in their names, marks and posting text.

## Help

Spotted a wrong row, or want a company added? See [CONTRIBUTING.md](CONTRIBUTING.md).
