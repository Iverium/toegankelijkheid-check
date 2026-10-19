# toegankelijkheid-check

Een snelle toegankelijkheidscheck: controleert automatisch de onderdelen van WCAG 2.1/2.2 die uit de HTML van een pagina af te lezen zijn. Het rapport is in begrijpelijk Nederlands, met per punt het WCAG-criterium en advies.

Dit is de motor achter de gratis [Toegankelijkheid-check op iverium.nl](https://www.iverium.nl/toegankelijkheid-check).

- Alleen de Python-standaardbibliotheek, Python 3.8 of nieuwer
- Score van 0 tot 100
- Veilig te gebruiken in een webdienst waar bezoekers zelf een adres invullen (SSRF-bescherming)

## Wat wordt gecontroleerd

| Onderdeel | Controles |
| --- | --- |
| Pagina-opbouw | taal (3.1.1), paginatitel (2.4.2), koppenstructuur (1.3.1), `<main>` en `<nav>`, unieke id's, toegankelijkheidsverklaring |
| Teksten en afbeeldingen | alt-teksten (1.1.1), inzoomen toegestaan (1.4.4), geen automatisch afspelend geluid (1.4.2) |
| Navigatie en bediening | links en knoppen met een naam (2.4.4, 4.1.2), duidelijke linkteksten, link 'naar de inhoud' (2.4.1), tabvolgorde (2.4.3), titels bij iframes |
| Formulieren | gekoppelde labels bij velden (1.3.1, 3.3.2); een placeholder telt niet als label |

Kleurcontrast en echte bediening met het toetsenbord kun je niet uit de HTML afleiden. Daarvoor zijn een browser en een mens nodig, dus die tellen niet mee in de score. Een hoge score betekent dus nog niet dat een website volledig aan WCAG voldoet.

## Installeren

```bash
pip install git+https://github.com/Iverium/toegankelijkheid-check
```

## Gebruik

```bash
toegankelijkheid-check www.voorbeeld.nl
toegankelijkheid-check www.voorbeeld.nl --json
toegankelijkheid-check www.voorbeeld.nl --min-score 90
```

Met `--min-score` stopt het programma met exitcode 1 als de score lager is. Zo kunt u toegankelijkheid in CI bewaken. Een site op localhost controleren kan met `--allow-private`.

Vanuit Python:

```python
from toegankelijkheid_check import CheckError, analyse, check_accessibility

result = check_accessibility("www.voorbeeld.nl")
print(result["score"])

# Of op HTML die u al heeft, bijvoorbeeld in een test van uw eigen site:
page = {"url": "https://www.voorbeeld.nl/", "body": html_bytes}
print(analyse(page)["score"])
```

Elk item heeft `key`, `group`, `title`, `status` (`goed`, `matig`, `slecht` of `info`), `detail`, `advice` en `weight`.

## Veilig in een webdienst

Pagina's worden opgehaald zoals in [website-check](https://github.com/Iverium/website-check#veilig-in-een-webdienst):

- alleen openbare adressen op de poorten 80 en 443;
- de verbinding gaat naar het gecontroleerde IP-adres;
- elke doorverwijzing wordt opnieuw gecontroleerd;
- de grootte van antwoorden is begrensd.

Zet `ALLOW_PRIVATE` alleen aan op de opdrachtregel.

## English

`toegankelijkheid-check` runs the automatically checkable parts of WCAG 2.1/2.2 on one page:
- language and page title
- alt texts and zoom
- autoplaying audio
- names for links and buttons, and generic link texts
- heading order, landmarks, skip link, duplicate ids and positive tabindex
- iframe titles and form labels

Reports are in Dutch and come with WCAG references. It uses only the standard library and needs Python 3.8+. The fetcher is SSRF-safe. Contrast and keyboard use still need a human. Use `--min-score` to gate CI.

## Andere tools

- [website-check](https://github.com/Iverium/website-check): vindbaarheid en techniek
- [cookie-check](https://github.com/Iverium/cookie-check): tracking en cookies vóór toestemming
- [google-reviewlink](https://github.com/Iverium/google-reviewlink): directe Google-reviewlink maken
- [tinyqr](https://github.com/Iverium/tinyqr): QR-codes als SVG of PNG

## Licentie

MIT. Gemaakt door [Iverium Software](https://www.iverium.nl), webontwikkeling en vindbaarheid voor ondernemers in Groningen en Drenthe.
