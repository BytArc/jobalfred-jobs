import unittest

from jobalfred_jobs.classify import (eu_countries, eu_location, has_non_eu_location, in_india, in_portugal,
                                     remote_eu_scope, sponsorship)
from jobalfred_jobs.sources import Job, html_to_text


def job(*locations, countries=None, remote=False):
    return Job("t", "t", "1", "C", "R", "https://x", "2026-01-01", "created", list(locations), countries or [], remote)


class Locations(unittest.TestCase):
    def test_india_cities_and_country(self):
        for loc in ("Bengaluru", "Hyderabad, India", "Gurugram, Haryana", "Remote - India"):
            self.assertTrue(in_india(job(loc)), loc)
        self.assertTrue(in_india(job("Anywhere", countries=["IN"])))

    def test_not_india(self):
        for loc in ("Indiana", "Indianapolis, IN", "Hyderabad, Pakistan", "New Delhi, NY", "Pune, OH"):
            self.assertFalse(in_india(job(loc)), loc)

    def test_portugal(self):
        for loc in ("Lisbon", "Porto, Portugal", "Lisboa", "Remote, Portugal", "Braga"):
            self.assertTrue(in_portugal(job(loc)), loc)

    def test_not_portugal(self):
        for loc in ("Porto Alegre", "Porto Alegre, Brazil", "New Lisbon, OH", "Lisbon, ME"):
            self.assertFalse(in_portugal(job(loc)), loc)

    def test_remote_eu(self):
        self.assertEqual(remote_eu_scope(job("Remote - EU")), "EU")
        self.assertEqual(remote_eu_scope(job("Remote, Europe")), "Europe")
        self.assertEqual(remote_eu_scope(job("Remote EMEA")), "EMEA")
        self.assertEqual(remote_eu_scope(job("Remote in Germany")), "Germany")
        self.assertEqual(remote_eu_scope(job("Spain", remote=True)), "Spain")
        self.assertEqual(remote_eu_scope(job("Somewhere", countries=["FR"], remote=True)), "France")

    def test_not_remote_eu(self):
        for j in (job("Berlin"), job("Remote - US"), job("Remote"), job("Remote - UK"),
                  job("Remote - US; Dublin"), job("Remote, Georgia")):
            self.assertIsNone(remote_eu_scope(j), j.locations)

    def test_eu_means_eu(self):
        self.assertEqual(eu_location(job("Dublin")), "Ireland")
        self.assertEqual(eu_location(job("Lisbon")), "Portugal")
        self.assertIsNone(eu_location(job("Porto Alegre, Brazil")))
        for loc in ("London", "Zurich, Switzerland", "Oslo, Norway", "Dublin, OH", "Paris, TX", "Athens, GA"):
            self.assertIsNone(eu_location(job(loc)), loc)


class Sponsorship(unittest.TestCase):
    def stated(self, text):
        self.assertEqual(sponsorship(text)[0], "stated", text)

    def rejected(self, text):
        self.assertNotEqual(sponsorship(text)[0], "stated", text)

    def test_stated(self):
        self.stated("We offer visa sponsorship for this role.")
        self.stated("Visa sponsorship is available.")
        self.stated("We sponsor work visas and help you relocate.")
        self.stated("Relocation package and visa sponsorship.")
        self.stated("Visa sponsorship and relocation support")
        self.stated("Benefits:\nVisa sponsorship\nPrivate health insurance")

    def test_refusals(self):
        self.rejected("We do not offer visa sponsorship.")
        self.rejected("We are unable to sponsor visas for this role.")
        self.rejected("No visa sponsorship is available.")
        self.rejected("Visa sponsorship is not available.")
        self.rejected("Unfortunately, we can't provide work permit sponsorship.")
        self.rejected("You must have the right to work without visa sponsorship.")
        self.rejected("Candidates must not require visa sponsorship now or in the future.")

    def test_any_refusal_wins(self):
        self.rejected("We offer visa sponsorship. We do not offer visa sponsorship for contractors.")

    def test_questions(self):
        self.rejected("Will you now or in the future require visa sponsorship?")
        self.rejected("Do you need visa sponsorship?")

    def test_conditions(self):
        self.assertEqual(sponsorship("Visa sponsorship may be available.")[0], "conditional")
        self.assertEqual(sponsorship("We offer visa sponsorship on a case-by-case basis.")[0], "conditional")
        self.assertEqual(sponsorship("We can provide visa sponsorship if needed.")[0], "conditional")

    def test_other_countries(self):
        self.rejected("We offer H-1B visa sponsorship.")
        self.rejected("We offer visa sponsorship in the US.")
        self.rejected("We offer UK Skilled Worker visa sponsorship.")
        self.rejected("Visa sponsorship is available for our London office.")

    def test_not_about_immigration(self):
        self.rejected("Our company offers relocation support.")
        self.rejected("We offer a great conference sponsorship budget.")
        self.rejected("We sponsor Visa and Mastercard BIN sponsorship programmes.")
        self.rejected("Visa sponsorship from the card scheme is included for issuers.")

    def test_never_inferred(self):
        self.assertEqual(sponsorship("We help you relocate to Berlin.")[0], "none")
        self.assertEqual(sponsorship("")[0], "none")

    def test_quote_is_short_and_verbatim(self):
        long = ("Everyone who joins this team in Berlin gets a generous package and, because we value talent "
                "from everywhere, we offer visa sponsorship for this role along with many other perks we are proud of.")
        status, quote = sponsorship(long)
        self.assertEqual(status, "stated")
        words = [w for w in quote.split() if w != "..."]
        self.assertLessEqual(len(words), 15)
        self.assertIn("visa sponsorship", quote)


class SponsorshipFitsTheRole(unittest.TestCase):
    TEXT = "We can sponsor visas to Germany; for any other country, you need to have existing right to work."

    def test_role_in_the_named_country(self):
        status, quote = sponsorship(self.TEXT, {"Germany"})
        self.assertEqual(status, "stated")
        self.assertEqual(quote, "We can sponsor visas to Germany")

    def test_role_in_another_country(self):
        self.assertEqual(sponsorship(self.TEXT, {"Ireland"})[0], "elsewhere")

    def test_city_counts_as_its_country(self):
        self.assertEqual(sponsorship("We offer visa sponsorship for roles in Berlin.", {"Germany"})[0], "stated")

    def test_unqualified_promise_on_a_role_that_also_sits_outside_the_eu(self):
        self.assertEqual(sponsorship("We can sponsor visas", {"Spain"}, elsewhere_too=True)[0], "conditional")
        self.assertEqual(sponsorship("We can sponsor visas", {"France"}, elsewhere_too=False)[0], "stated")

    def test_mixed_locations(self):
        self.assertTrue(has_non_eu_location(job("Barcelona; Cardiff, London")))
        self.assertTrue(has_non_eu_location(job("Berlin Office; Bosnia")))
        self.assertFalse(has_non_eu_location(job("Paris")))
        self.assertFalse(has_non_eu_location(job("Germany; Remote; Europe")))
        self.assertEqual(eu_countries(job("Berlin Office; Bosnia; Porto")), {"Germany", "Portugal"})


class MultiCityStrings(unittest.TestCase):
    def test_a_us_city_does_not_hide_lisbon_or_bengaluru(self):
        self.assertTrue(in_portugal(job("Hybrid; Austin, TX, United States; Lisbon, Portugal")))
        self.assertTrue(in_india(job("Austin, TX; Bengaluru, India")))


class Text(unittest.TestCase):
    def test_html(self):
        raw = "&lt;p&gt;Hello&amp;nbsp;there&lt;/p&gt;&lt;ul&gt;&lt;li&gt;One&lt;/li&gt;&lt;/ul&gt;"
        self.assertEqual(html_to_text(raw), "Hello there\nOne")


if __name__ == "__main__":
    unittest.main()
