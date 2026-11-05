"""Decide which list a role belongs to. Conservative on purpose.

Precision beats recall here: a missing role costs little, a wrong "sponsors visas" row can
cost someone months. Sponsorship is never inferred; the posting must say it in plain words.
"""
from __future__ import annotations

import re

from .sources import Job

US_STATE = (r"(?:AL|AK|AZ|AR|CA|CO|CT|DE|FL|GA|HI|ID|IL|IN|IA|KS|KY|LA|ME|MD|MA|MI|MN|MS|MO|MT|NE|NV|"
            r"NH|NJ|NM|NY|NC|ND|OH|OK|OR|PA|RI|SC|SD|TN|TX|UT|VT|VA|WA|WV|WI|WY)")
US_SUFFIX = re.compile(rf",\s*{US_STATE}\b|\b(usa|united states)\b|\bU\.?S\.?A?\.?$")

INDIA = re.compile(
    r"\b(india|bengaluru|bangalore|hyderabad|pune|chennai|gurugram|gurgaon|mumbai|noida|new delhi|delhi|"
    r"kolkata|ahmedabad|kochi|cochin|coimbatore|thiruvananthapuram|trivandrum|jaipur|indore|mohali|"
    r"chandigarh|nagpur|vadodara|visakhapatnam|mysuru|mysore|bhubaneswar)\b", re.I)
NOT_INDIA = re.compile(r"\b(pakistan|sindh)\b", re.I)

PORTUGAL = re.compile(
    r"\b(portugal|lisbon|lisboa|oporto|porto(?!\s+(alegre|velho|seguro|rico|de\s+galinhas))|braga|"
    r"coimbra|aveiro|faro|funchal|guimar[aã]es|matosinhos|oeiras|sintra|cascais|covilh[aã]|leiria|viseu)\b",
    re.I)

EU_COUNTRIES = {
    "austria": "Austria", "belgium": "Belgium", "bulgaria": "Bulgaria", "croatia": "Croatia",
    "cyprus": "Cyprus", "czechia": "Czechia", "czech republic": "Czechia", "denmark": "Denmark",
    "estonia": "Estonia", "finland": "Finland", "france": "France", "germany": "Germany",
    "deutschland": "Germany", "greece": "Greece", "hungary": "Hungary", "ireland": "Ireland",
    "italy": "Italy", "latvia": "Latvia", "lithuania": "Lithuania", "luxembourg": "Luxembourg",
    "malta": "Malta", "netherlands": "Netherlands", "the netherlands": "Netherlands",
    "poland": "Poland", "portugal": "Portugal", "romania": "Romania", "slovakia": "Slovakia",
    "slovenia": "Slovenia", "spain": "Spain", "sweden": "Sweden",
}
EU_ISO = {
    "AT": "Austria", "BE": "Belgium", "BG": "Bulgaria", "HR": "Croatia", "CY": "Cyprus", "CZ": "Czechia",
    "DK": "Denmark", "EE": "Estonia", "FI": "Finland", "FR": "France", "DE": "Germany", "GR": "Greece",
    "HU": "Hungary", "IE": "Ireland", "IT": "Italy", "LV": "Latvia", "LT": "Lithuania", "LU": "Luxembourg",
    "MT": "Malta", "NL": "Netherlands", "PL": "Poland", "PT": "Portugal", "RO": "Romania", "SK": "Slovakia",
    "SI": "Slovenia", "ES": "Spain", "SE": "Sweden",
}
EU_CITIES = {
    "vienna": "Austria", "wien": "Austria", "brussels": "Belgium", "antwerp": "Belgium", "ghent": "Belgium",
    "sofia": "Bulgaria", "zagreb": "Croatia", "nicosia": "Cyprus", "limassol": "Cyprus", "prague": "Czechia",
    "praha": "Czechia", "brno": "Czechia", "copenhagen": "Denmark", "aarhus": "Denmark", "tallinn": "Estonia",
    "helsinki": "Finland", "espoo": "Finland", "tampere": "Finland", "paris": "France", "lyon": "France",
    "toulouse": "France", "nantes": "France", "bordeaux": "France", "lille": "France", "marseille": "France",
    "berlin": "Germany", "munich": "Germany", "münchen": "Germany", "hamburg": "Germany", "frankfurt": "Germany",
    "cologne": "Germany", "köln": "Germany", "stuttgart": "Germany", "düsseldorf": "Germany", "dusseldorf": "Germany",
    "leipzig": "Germany", "karlsruhe": "Germany", "athens": "Greece", "thessaloniki": "Greece", "budapest": "Hungary",
    "dublin": "Ireland", "cork": "Ireland", "galway": "Ireland", "limerick": "Ireland", "rome": "Italy",
    "milan": "Italy", "milano": "Italy", "turin": "Italy", "riga": "Latvia", "vilnius": "Lithuania",
    "kaunas": "Lithuania", "amsterdam": "Netherlands", "rotterdam": "Netherlands", "utrecht": "Netherlands",
    "eindhoven": "Netherlands", "the hague": "Netherlands", "warsaw": "Poland", "krakow": "Poland", "kraków": "Poland",
    "wroclaw": "Poland", "wrocław": "Poland", "gdansk": "Poland", "gdańsk": "Poland", "poznan": "Poland",
    "poznań": "Poland", "bucharest": "Romania", "cluj": "Romania", "iasi": "Romania", "bratislava": "Slovakia",
    "ljubljana": "Slovenia", "madrid": "Spain", "barcelona": "Spain", "valencia": "Spain", "seville": "Spain",
    "malaga": "Spain", "málaga": "Spain", "bilbao": "Spain", "stockholm": "Sweden", "gothenburg": "Sweden",
    "malmö": "Sweden", "malmo": "Sweden", "valletta": "Malta",
}
_EU_NAME = re.compile(r"\b(" + "|".join(sorted(map(re.escape, EU_COUNTRIES), key=len, reverse=True)) + r")\b", re.I)
_EU_CITY = re.compile(r"\b(" + "|".join(sorted(map(re.escape, EU_CITIES), key=len, reverse=True)) + r")\b", re.I)

_SEGMENT = re.compile(r"\s*(?:;|\||/|\bor\b|\s&\s)\s*", re.I)
_REMOTE = re.compile(r"\b(remote|work\s+from\s+home|wfh|telecommute|distributed)\b", re.I)
_NOT_REMOTE = re.compile(r"\b(non[- ]remote|not\s+remote)\b", re.I)
_REGION = [
    ("EU", re.compile(r"\b(EU|E\.U\.|european union|EEA)\b")),
    ("Europe", re.compile(r"\beurope(an)?\b", re.I)),
    ("EMEA", re.compile(r"\bEMEA\b", re.I)),
    ("CET timezone", re.compile(r"\b(CET|CEST)\b")),
]


def _segments(job: Job) -> list[str]:
    out = []
    for loc in job.locations:
        out.extend(s for s in _SEGMENT.split(loc) if s and s.strip())
    return out


def eu_country(text: str) -> str | None:
    """EU-27 country named by a location string, else None. The UK, Norway and Switzerland are not EU."""
    if US_SUFFIX.search(text):
        return None
    m = _EU_NAME.search(text)
    if m:
        return EU_COUNTRIES[m.group(1).lower()]
    m = _EU_CITY.search(text)
    if m:
        return EU_CITIES[m.group(1).lower()]
    if PORTUGAL.search(text):
        return "Portugal"
    return None


def in_india(job: Job) -> bool:
    if "IN" in job.countries or "India" in job.countries:
        return True
    return any(INDIA.search(seg) and not NOT_INDIA.search(seg) and not US_SUFFIX.search(seg)
               for seg in _segments(job))


def in_portugal(job: Job) -> bool:
    if "PT" in job.countries or "Portugal" in job.countries:
        return True
    return any(PORTUGAL.search(seg) and not US_SUFFIX.search(seg) for seg in _segments(job))


def remote_eu_scope(job: Job) -> str | None:
    """Return the stated scope of a remote EU role: EU, Europe, EMEA, CET timezone, or a country."""
    segments = [s for s in _segments(job) if not _NOT_REMOTE.search(s)]
    for seg in segments:
        if not _REMOTE.search(seg):
            continue
        for label, rx in _REGION:
            if rx.search(seg):
                return label
        country = eu_country(seg)
        if country:
            return country
    if job.remote:  # the API says remote: read the location as the place of work
        for seg in segments:
            for label, rx in _REGION:
                if rx.search(seg):
                    return label
            country = eu_country(seg)
            if country:
                return country
        for code in job.countries:
            if code in EU_ISO:
                return EU_ISO[code]
            if code in EU_COUNTRIES.values():
                return code
    return None


def eu_location(job: Job) -> str | None:
    for seg in _segments(job):
        country = eu_country(seg)
        if country:
            return country
    for code in job.countries:
        if code in EU_ISO:
            return EU_ISO[code]
        if code in EU_COUNTRIES.values():
            return code
    return None


def eu_countries(job: Job) -> set[str]:
    found = {c for c in (eu_country(seg) for seg in _segments(job)) if c}
    found |= {EU_ISO[c] for c in job.countries if c in EU_ISO}
    found |= {c for c in job.countries if c in EU_COUNTRIES.values()}
    return found


_NEUTRAL = re.compile(r"^\W*(remote|hybrid|on[- ]?site|europe|eu|eea|emea|european union|global|worldwide|anywhere)?\W*$", re.I)


def has_non_eu_location(job: Job) -> bool:
    """True when the role also sits outside the EU, so an unqualified promise may mean somewhere else."""
    return any(not eu_country(seg) and not _NEUTRAL.match(seg) for seg in _segments(job))


# ---- visa sponsorship ------------------------------------------------------------------------

_SPONSOR = r"sponsor(?:s|ed|ing|ship)?"
_PERMIT = r"(?:visas?|work(?:ing)?\s+permits?|blue\s+cards?|residence\s+permits?)"
_MENTION = re.compile(rf"\b{_PERMIT}\b[^.\n]{{0,40}}\b{_SPONSOR}\b|\b{_SPONSOR}\b[^.\n]{{0,40}}\b{_PERMIT}\b", re.I)
_SENTENCE = re.compile(r"(?<=[.!?;])\s+|\n+")

_NEGATIVE = re.compile(
    r"\b(no|not|non|never|none|unable|cannot|can.t|won.t|don.t|doesn.t|isn.t|aren.t|wouldn.t|couldn.t|"
    r"without|unfortunately|neither|nor|regret|must|requires?|required|requiring|needs?|needing|"
    r"eligible|eligibility|authori[sz]ed|authori[sz]ation|right\s+to\s+work|future|currently|already|"
    r"do\s+you|will\s+you|would\s+you|are\s+you|have\s+you|applicants?\s+who)\b", re.I)
_CONDITIONAL = re.compile(
    r"\b(may|might|could|can\s+be|possible|possibly|potential(?:ly)?|case[- ]by[- ]case|depending|depends|"
    r"subject\s+to|where\s+(?:applicable|possible|needed|necessary|eligible)|"
    r"if\s+(?:applicable|needed|necessary|required|eligible|you)|when\s+(?:applicable|needed)|"
    r"some\s+cases|certain\s+(?:cases|roles|positions|countries)|exceptional|limited|considered?|"
    r"discuss(?:ed)?|open\s+to|selected|right\s+candidate|for\s+some)\b", re.I)
_NON_EU_CS = re.compile(r"\b(US|U\.S\.A?\.?|USA|UK|U\.K\.|UAE|OPT|CPT|TN|E-3)\b")
_NON_EU = re.compile(
    r"\b(h-?1-?b|l-?1|o-?1|uscis|green\s+card|united\s+states|america[n]?|united\s+kingdom|british|britain|"
    r"england|scotland|wales|london|manchester|skilled\s+worker|canada|canadian|toronto|vancouver|montreal|"
    r"australia[n]?|sydney|melbourne|new\s+zealand|japan|tokyo|singapore|hong\s+kong|china|dubai|abu\s+dhabi|"
    r"saudi|qatar|israel|switzerland|swiss|zurich|norway|oslo|turkey|istanbul|brazil|mexico|india|south\s+africa)\b",
    re.I)
_PAYMENTS = re.compile(r"\b(mastercard|amex|american\s+express|bin\s+sponsor\w*|card\s+scheme\w*|issuer|issuing)\b", re.I)
_AFFIRM = re.compile(
    r"\b(we|we.ll|we.re|our\s+company|the\s+company|employer)\b[^.\n]{0,70}\b"
    r"(offer|offers|offering|provide|provides|providing|sponsor|sponsors|sponsoring|cover|covers|"
    r"support|supports|supporting|handle|handles|arrange|arranges|include|includes|will\s+sponsor)\b"
    r"|\b(?:visa|work\s+permit|blue\s+card)\s+sponsorship\s+(?:is\s+|are\s+|will\s+be\s+)?"
    r"(?:available|provided|offered|included|supported|on\s+offer)\b"
    r"|\brelocat\w*\b[^.\n]{0,40}\b(?:and|&|plus|with|including)\s+(?:a\s+)?(?:work\s+)?visa\s+sponsorship\b"
    r"|\b(?:work\s+)?visa\s+sponsorship\s+(?:and|&|plus)\s+(?:\w+\s+)?relocation\b"
    r"|^\W*(?:full\s+|complete\s+)?(?:work\s+)?visa\s+sponsorship\W*$",
    re.I)


def _quote(sentence: str, start: int, end: int, limit: int = 15) -> str:
    """Up to `limit` words around the match, copied from the posting and never reworded."""
    words = list(re.finditer(r"\S+", sentence))
    hit = next((i for i, w in enumerate(words) if w.end() > start), 0)
    last = next((i for i, w in enumerate(words) if w.start() >= end), len(words))
    span = max(last - hit, 1)
    pad = max(limit - span, 0)
    first = max(hit - pad // 2, 0)
    upto = min(first + limit, len(words))
    first = max(upto - limit, 0)
    text = " ".join(w.group() for w in words[first:upto])
    return ("... " if first else "") + text + (" ..." if upto < len(words) else "")


def _named_eu(sentence: str) -> set[str]:
    named = {EU_COUNTRIES[m.lower()] for m in _EU_NAME.findall(sentence)}
    named |= {EU_CITIES[m.lower()] for m in _EU_CITY.findall(sentence)}
    if PORTUGAL.search(sentence):
        named.add("Portugal")
    return named


def sponsorship_mentions(text: str) -> list[tuple[str, str, set[str]]]:
    """Every clause that mentions visa sponsorship, as (status, quote, EU countries it names)."""
    out = []
    for raw in _SENTENCE.split(text or ""):
        sentence = raw.strip()
        m = _MENTION.search(sentence)
        if not m or len(sentence) > 400:
            continue
        if sentence.endswith("?") or _PAYMENTS.search(sentence) or _NON_EU_CS.search(sentence) or _NON_EU.search(sentence):
            status = "negative"
        elif _NEGATIVE.search(sentence):
            status = "negative"
        elif _CONDITIONAL.search(sentence):
            status = "conditional"
        elif _AFFIRM.search(sentence):
            status = "stated"
        else:
            status = "negative"  # a mention that affirms nothing is not a statement
        out.append((status, _quote(sentence, m.start(), m.end()).rstrip(" ;,"), _named_eu(sentence)))
    return out


def sponsorship(text: str, countries: set[str] | None = None, elsewhere_too: bool = False) -> tuple[str, str]:
    """Return (status, quote). Only "stated" counts.

    stated       an affirmative clause that applies to this role
    conditional  hedged wording, or a promise that could mean a non-EU location of the same role
    elsewhere    the promise names a country this role is not in
    negative     any refusal, question or non-EU promise: this wins outright
    none         no mention
    """
    countries = countries or set()
    mentions = sponsorship_mentions(text)
    for status, quote, _ in mentions:
        if status == "negative":
            return "negative", quote
    best, best_quote = "none", ""
    rank = {"none": 0, "elsewhere": 1, "conditional": 2, "stated": 3}
    for status, quote, named in mentions:
        if status == "stated" and named and countries and not named & countries:
            status = "elsewhere"
        elif status == "stated" and not named and elsewhere_too:
            status = "conditional"
        if rank[status] > rank[best]:
            best, best_quote = status, quote
    return best, best_quote
