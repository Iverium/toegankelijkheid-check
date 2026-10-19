"""Quick accessibility check: the parts of WCAG 2.1/2.2 that can be verified automatically from a page's HTML.

Checks language, title, text alternatives, zoom, autoplay, form labels, names for links and buttons, link texts,
headings, landmarks, skip link, duplicate ids, tab order, iframe titles and a link to an accessibility statement.
Colour contrast and real keyboard use need a browser and a person, so they are not scored. Reports are in Dutch.
Standard library only, Python 3.8+.

The engine behind https://www.iverium.nl/toegankelijkheid-check, by Iverium Software.
"""
import re
import time
from collections import Counter
from html.parser import HTMLParser
from urllib.parse import urlsplit

from ._common import fetch_page, item, score as score_items

GENERIC_LINK_TEXT = {"klik hier", "hier", "lees meer", "meer", "meer info", "meer informatie", "klik", "link",
                     "read more", "click here", "more", "here", "bekijk", "verder", "lees verder", ">", ">>", "»"}
LABELLED_INPUT_TYPES_EXEMPT = {"hidden", "submit", "button", "reset", "image"}


class _A11yParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.lang = None
        self.title = None
        self._in_title = False
        self.meta = {}
        self.ids = Counter()
        self.label_for = set()
        self._label_depth = 0
        self.fields = []            # dict(id, named)
        self.images = 0
        self.images_no_alt = 0
        self.headings = []          # levels in document order
        self.h1 = 0
        self.links = []             # dict(text, named)
        self.buttons = []           # dict(named)
        self._stack = []            # open <a>/<button> collecting text
        self.iframes = 0
        self.iframes_no_title = 0
        self.autoplay = 0
        self.positive_tabindex = 0
        self.main = False
        self.nav = False
        self.skip_link = False
        self._first_links = 0
        self._skip = 0
        self.statement = False

    def handle_starttag(self, tag, attrs):
        a = {k.lower(): (v or "") for k, v in attrs}
        if a.get("id"):
            self.ids[a["id"]] += 1
        tabindex = a.get("tabindex", "").strip()
        if tabindex.lstrip("-").isdigit() and int(tabindex) > 0:
            self.positive_tabindex += 1
        aria_named = bool(a.get("aria-label", "").strip() or a.get("aria-labelledby", "").strip() or
                          a.get("title", "").strip())
        if tag == "html":
            self.lang = a.get("lang") or self.lang
        elif tag == "title" and self.title is None:
            self.title, self._in_title = "", True
        elif tag == "meta":
            key = (a.get("name") or "").lower()
            if key:
                self.meta.setdefault(key, a.get("content", ""))
        elif tag == "label":
            self._label_depth += 1
            if a.get("for"):
                self.label_for.add(a["for"])
        elif tag in ("input", "select", "textarea"):
            kind = a.get("type", "text").lower() if tag == "input" else tag
            hidden_from_at = a.get("aria-hidden") == "true" and a.get("tabindex", "").strip() == "-1"
            if kind not in LABELLED_INPUT_TYPES_EXEMPT and not hidden_from_at:
                # A placeholder is not a label: it disappears while typing and many screen readers skip it
                self.fields.append(dict(id=a.get("id", ""), named=aria_named or self._label_depth > 0))
            if tag == "input" and kind == "image":
                self.images += 1
                if not a.get("alt", "").strip():
                    self.images_no_alt += 1
        elif tag == "img":
            self.images += 1
            if "alt" not in a and a.get("role") != "presentation" and a.get("aria-hidden") != "true":
                self.images_no_alt += 1
            for entry in self._stack:
                entry["text"] += " " + a.get("alt", "")
        elif tag == "svg":
            for entry in self._stack:
                if aria_named:
                    entry["text"] += " " + a.get("aria-label", "x")
            self._skip += 1
        elif re.fullmatch(r"h[1-6]", tag):
            level = int(tag[1])
            self.headings.append(level)
            if level == 1:
                self.h1 += 1
        elif tag == "a" and "href" in a:
            entry = dict(kind="a", text="", named=aria_named, href=a.get("href", ""))
            self._stack.append(entry)
            self.links.append(entry)
            if self._first_links < 3:
                self._first_links += 1
                if a["href"].startswith("#") and len(a["href"]) > 1:
                    self.skip_link = True
        elif tag == "button":
            entry = dict(kind="button", text="", named=aria_named)
            self._stack.append(entry)
            self.buttons.append(entry)
        elif tag == "iframe":
            self.iframes += 1
            if not a.get("title", "").strip() and not aria_named and a.get("aria-hidden") != "true":
                self.iframes_no_title += 1
        elif tag in ("video", "audio"):
            if "autoplay" in a and not (tag == "video" and "muted" in a):
                self.autoplay += 1
        elif tag == "main" or a.get("role") == "main":
            self.main = True
        if tag == "nav" or a.get("role") == "navigation":
            self.nav = True
        if tag in ("script", "style", "noscript", "template"):
            self._skip += 1

    def handle_endtag(self, tag):
        if tag == "title":
            self._in_title = False
        elif tag == "label":
            self._label_depth = max(0, self._label_depth - 1)
        elif tag in ("a", "button"):
            for i in range(len(self._stack) - 1, -1, -1):
                if self._stack[i]["kind"] == tag:
                    self._stack.pop(i)
                    break
        if tag in ("script", "style", "noscript", "template", "svg"):
            self._skip = max(0, self._skip - 1)

    def handle_data(self, data):
        if self._in_title:
            self.title += data
        if self._skip:
            return
        for entry in self._stack:
            entry["text"] += data
        lowered = data.lower()
        if "toegankelijkheidsverklaring" in lowered or "accessibility statement" in lowered:
            self.statement = True


def analyse(page):
    html = page["body"].decode("utf-8", errors="replace")
    parser = _A11yParser()
    try:
        parser.feed(html)
        parser.close()
    except Exception:
        pass
    for field in parser.fields:
        if field["id"] and field["id"] in parser.label_for:
            field["named"] = True
    items = []
    group_text, group_nav, group_forms, group_page = ("Teksten en afbeeldingen", "Navigatie en bediening",
                                                       "Formulieren", "Pagina-opbouw")

    items.append(item("lang", group_page, "Taal van de pagina", "goed" if parser.lang else "slecht",
                       "Taal ingesteld: %s." % parser.lang if parser.lang else "De taal van de pagina is niet "
                       "ingesteld, dus schermlezers lezen de tekst mogelijk met de verkeerde uitspraak voor.",
                       None if parser.lang else "Zet lang=\"nl\" op het html-element (WCAG 3.1.1).", weight=1.5))
    title = " ".join((parser.title or "").split())
    items.append(item("title", group_page, "Paginatitel", "goed" if title else "slecht",
                       "'%s'." % title[:80] if title else "De pagina heeft geen titel.",
                       None if title else "Geef elke pagina een beschrijvende titel (WCAG 2.4.2).", weight=1))
    levels = parser.headings
    skipped = sum(1 for prev, cur in zip(levels, levels[1:]) if cur > prev + 1)
    if parser.h1 == 1 and not skipped:
        status, detail = "goed", "Eén hoofdkop en een logische opbouw van de koppen."
    elif parser.h1 == 0:
        status, detail = "slecht", "De pagina heeft geen hoofdkop (H1)."
    else:
        status, detail = "matig", ("%d hoofdkoppen" % parser.h1 if parser.h1 > 1 else "Eén hoofdkop") + \
            (", en %d keer wordt een kopniveau overgeslagen (bijvoorbeeld van H2 naar H4)." % skipped if skipped
             else ".")
    items.append(item("headings", group_page, "Koppenstructuur", status, detail,
                       None if status == "goed" else "Gebruik één H1 en daarna H2, H3 in volgorde, zodat "
                       "schermlezergebruikers door de pagina kunnen springen (WCAG 1.3.1).", weight=1))
    # Navigation landmarks and skip links only matter on pages with menus (not, say, an embedded form)
    few_links = len(parser.links) < 5
    landmarks_ok = parser.main and (parser.nav or few_links)
    items.append(item("landmarks", group_page, "Hoofdgebied en navigatie gemarkeerd",
                       "goed" if landmarks_ok else "matig",
                       "De pagina markeert het hoofdgedeelte en de navigatie." if landmarks_ok else
                       "De pagina mist een <main>- of <nav>-element.",
                       None if landmarks_ok else "Gebruik <main> voor de inhoud en <nav> voor menu's, "
                       "zodat hulpsoftware er direct naartoe kan.", weight=0.5))
    duplicates = [key for key, count in parser.ids.items() if count > 1]
    items.append(item("ids", group_page, "Unieke id's", "goed" if not duplicates else "matig",
                       "Alle id's zijn uniek." if not duplicates else "%d id's komen vaker dan één keer voor (zoals "
                       "'%s')." % (len(duplicates), duplicates[0][:30]),
                       None if not duplicates else "Maak id's uniek: koppelingen tussen labels en velden werken "
                       "anders niet betrouwbaar.", weight=0.5))

    if parser.images:
        missing = parser.images_no_alt
        items.append(item("alt", group_text, "Tekstalternatief bij afbeeldingen",
                           "goed" if missing == 0 else "matig" if missing <= parser.images / 4 else "slecht",
                           "Alle %d afbeeldingen hebben een alt-attribuut." % parser.images if missing == 0 else
                           "%d van de %d afbeeldingen hebben geen alt-attribuut." % (missing, parser.images),
                           None if missing == 0 else "Beschrijf informatieve afbeeldingen in de alt-tekst en geef "
                           "decoratieve afbeeldingen alt=\"\" (WCAG 1.1.1).", weight=2))
    viewport = parser.meta.get("viewport", "").replace(" ", "").lower()
    match = re.search(r"maximum-scale=([\d.]+)", viewport)
    zoom_blocked = "user-scalable=no" in viewport or "user-scalable=0" in viewport or \
        (match is not None and float(match.group(1) or 0) < 2)
    items.append(item("zoom", group_text, "Inzoomen toegestaan", "slecht" if zoom_blocked else "goed",
                       "De pagina blokkeert inzoomen op telefoons." if zoom_blocked else "Bezoekers kunnen inzoomen.",
                       "Haal user-scalable=no en een lage maximum-scale weg uit de viewport (WCAG 1.4.4)."
                       if zoom_blocked else None, weight=1.5))
    if parser.autoplay:
        items.append(item("autoplay", group_text, "Geen automatisch afspelend geluid", "matig",
                           "%d video's of audiofragmenten spelen automatisch af met geluid." % parser.autoplay,
                           "Laat geluid niet automatisch afspelen, of geef een duidelijke pauzeknop (WCAG 1.4.2).",
                           weight=1))

    unnamed_links = [link for link in parser.links if not link["named"] and not link["text"].strip()]
    generic = [link for link in parser.links if " ".join(link["text"].split()).lower() in GENERIC_LINK_TEXT]
    if parser.links:
        items.append(item("link_names", group_nav, "Links met een naam",
                           "goed" if not unnamed_links else "matig" if len(unnamed_links) <= 3 else "slecht",
                           "Alle links hebben een tekst of label." if not unnamed_links else
                           "%d links hebben geen tekst of label, bijvoorbeeld een icoon zonder beschrijving." %
                           len(unnamed_links),
                           None if not unnamed_links else "Geef icoonlinks (zoals social media) een aria-label of "
                           "verborgen tekst (WCAG 2.4.4, 4.1.2).", weight=1.5))
        items.append(item("link_text", group_nav, "Duidelijke linkteksten", "goed" if len(generic) <= 1 else "matig",
                           "Linkteksten zeggen waar ze naartoe gaan." if len(generic) <= 1 else
                           "%d links heten alleen 'lees meer', 'klik hier' of iets vergelijkbaars." % len(generic),
                           None if len(generic) <= 1 else "Schrijf linkteksten die ook los van de zin duidelijk zijn, "
                           "zoals 'Bekijk onze tarieven'.", weight=0.5))
    unnamed_buttons = [button for button in parser.buttons if not button["named"] and not button["text"].strip()]
    if parser.buttons:
        items.append(item("button_names", group_nav, "Knoppen met een naam",
                           "goed" if not unnamed_buttons else "slecht",
                           "Alle knoppen hebben een tekst of label." if not unnamed_buttons else
                           "%d knoppen hebben geen tekst of label (vaak een menuknop met alleen een icoon)." %
                           len(unnamed_buttons),
                           None if not unnamed_buttons else "Geef elke knop een zichtbare tekst of een aria-label, "
                           "zoals 'Menu openen' (WCAG 4.1.2).", weight=1.5))
    skip_ok = parser.skip_link or few_links
    items.append(item("skip", group_nav, "Link 'naar de inhoud'", "goed" if skip_ok else "matig",
                       "Toetsenbordgebruikers kunnen het menu overslaan." if parser.skip_link else
                       "De pagina heeft geen menu om over te slaan." if skip_ok else
                       "Er is geen link om direct naar de inhoud te springen.",
                       None if skip_ok else "Zet een 'Naar de inhoud'-link als eerste op de pagina "
                       "(WCAG 2.4.1).", weight=0.5))
    items.append(item("tabindex", group_nav, "Logische tabvolgorde", "goed" if not parser.positive_tabindex else
                       "matig", "Geen afwijkende tabvolgorde ingesteld." if not parser.positive_tabindex else
                       "%d elementen hebben een tabindex groter dan 0, wat de tabvolgorde door elkaar haalt." %
                       parser.positive_tabindex,
                       None if not parser.positive_tabindex else "Gebruik geen tabindex hoger dan 0 (WCAG 2.4.3).",
                       weight=0.5))
    if parser.iframes:
        items.append(item("iframes", group_nav, "Titels bij ingesloten inhoud",
                           "goed" if not parser.iframes_no_title else "matig",
                           "Ingesloten inhoud (zoals kaarten en video's) heeft een titel." if not parser.iframes_no_title
                           else "%d ingesloten elementen (iframes) hebben geen titel." % parser.iframes_no_title,
                           None if not parser.iframes_no_title else "Geef iframes een title, zoals 'Kaart van onze "
                           "locatie' (WCAG 4.1.2).", weight=0.5))

    if parser.fields:
        unnamed = [field for field in parser.fields if not field["named"]]
        items.append(item("labels", group_forms, "Labels bij formuliervelden",
                           "goed" if not unnamed else "matig" if len(unnamed) <= 1 else "slecht",
                           "Alle %d velden hebben een label." % len(parser.fields) if not unnamed else
                           "%d van de %d velden hebben geen gekoppeld label (een placeholder telt niet)." %
                           (len(unnamed), len(parser.fields)),
                           None if not unnamed else "Koppel elk veld aan een <label for=\"...\">, zodat schermlezers "
                           "voorlezen wat er ingevuld moet worden (WCAG 1.3.1, 3.3.2).", weight=2))
    items.append(item("statement", group_page, "Toegankelijkheidsverklaring", "goed" if parser.statement else "info",
                       "De pagina verwijst naar een toegankelijkheidsverklaring." if parser.statement else
                       "We vonden geen verwijzing naar een toegankelijkheidsverklaring. Voor bedrijven die onder de "
                       "Europese toegankelijkheidswet vallen, is die verplicht.", None, weight=0))

    score = score_items(items)
    return dict(score=score, items=items)


def check_accessibility(raw_url):
    """Fetch a page and check it. Raises CheckError with a Dutch, visitor-friendly message on failure."""
    started = time.monotonic()
    page = fetch_page(raw_url)
    result = analyse(page)
    result.update(url=page["url"], host=urlsplit(page["url"]).hostname,
                  duration=round(time.monotonic() - started, 1))
    return result
