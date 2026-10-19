import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from toegankelijkheid_check import CheckError, analyse, check_accessibility  # noqa: E402

GOOD_HTML = """<!doctype html><html lang="nl"><head><title>Contact | Voorbeeld</title>
<meta name="viewport" content="width=device-width, initial-scale=1"></head><body>
<a href="#inhoud">Naar de inhoud</a>
<nav><a href="/">Home</a><a href="/diensten">Diensten</a><a href="/over">Over ons</a><a href="/contact">Contact</a>
<a href="https://instagram.com/x" aria-label="Instagram"><svg></svg></a></nav>
<main id="inhoud"><h1>Contact</h1><h2>Formulier</h2>
<form><label for="naam">Naam</label><input id="naam" name="naam">
<label>E-mail <input type="email" name="email"></label><button type="submit">Versturen</button></form>
<img src="/team.jpg" alt="Ons team"><img src="/lijn.svg" alt="">
<iframe src="https://maps.example/x" title="Kaart van onze locatie"></iframe></main>
<footer><a href="/toegankelijkheid">Toegankelijkheidsverklaring</a></footer></body></html>"""

BAD_HTML = """<html><head><meta name="viewport" content="width=device-width, user-scalable=no"></head><body>
<div><a href="/">Home</a><a href="/a">lees meer</a><a href="/b">klik hier</a><a href="/c"><img src="i.png"></a>
<a href="/d"></a><a href="/e"></a><a href="/f"></a><a href="/g"></a></div>
<h2>Dienst</h2><h4>Detail</h4><button><svg></svg></button>
<input name="q" placeholder="Zoeken"><span id="x"></span><span id="x"></span>
<div tabindex="3">x</div><iframe src="/v"></iframe></body></html>"""


def page(html):
    return dict(url="https://www.voorbeeld.nl/contact", status=200, headers={"content-type": "text/html"},
                body=html.encode("utf-8"), first_byte=0.1, cert_ok=True, cert_expires=None, chain=[], cookies=[])


def by_key(result):
    return {entry["key"]: entry for entry in result["items"]}


class Analyse(unittest.TestCase):
    def test_good_page(self):
        result = analyse(page(GOOD_HTML))
        self.assertEqual(result["score"], 100, [e for e in result["items"] if e["status"] not in ("goed", "info")])
        self.assertEqual(by_key(result)["statement"]["status"], "goed")

    def test_bad_page(self):
        result = analyse(page(BAD_HTML))
        items = by_key(result)
        self.assertLess(result["score"], 40)
        for key in ("lang", "title", "headings", "alt", "zoom", "button_names", "link_names"):
            self.assertEqual(items[key]["status"], "slecht", key)
        for key in ("landmarks", "ids", "tabindex", "iframes", "link_text", "skip", "labels"):
            self.assertEqual(items[key]["status"], "matig", key)

    def test_guard(self):
        with self.assertRaises(CheckError):
            check_accessibility("http://127.0.0.1/")


if __name__ == "__main__":
    unittest.main()
