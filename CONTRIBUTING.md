# Contributing

Thanks for helping. These lists only work if they stay accurate.

## Add a company

Open a pull request that adds an entry to `config/companies.yml`:

```yaml
  - name: "Example"
    ats: greenhouse        # greenhouse, lever, lever-eu or ashby
    token: "example"       # the board name in the employer's careers address
    hq: "US"               # headquarters country code
    identity: "board name: Example"
    lists: [remote_eu, portugal, visa_eu]
```

- Add `india` only if the company is headquartered and founded outside India.
- Say how you know the board belongs to the company.
- Public employer boards only.

## Report a wrong row

Open an issue with the role's Apply link and what is wrong. A wrong sponsorship row is treated as urgent.
To remove a row at once, add its `id` to `config/exclusions.yml`.

## What we will not accept

- Sources other than official public job-board APIs. No scraping of LinkedIn, Indeed, Naukri or anything else.
- Inferred sponsorship. A posting has to say it in plain words.
- Redirects or link shorteners on Apply links.
- Job description text, beyond the short quote on the sponsorship list.

## Run it

```bash
pip install -r requirements.txt
python -m unittest discover -s tests -t .
python -m jobalfred_jobs --dry-run
```

Changes to the matching rules need a test in `tests/test_classify.py`, including the case that must not match.
