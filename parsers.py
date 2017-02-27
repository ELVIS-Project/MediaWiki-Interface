from bs4 import BeautifulSoup
from bs4.element import Tag as bsTag
from bs4.element import NavigableString as bsString
from main import DEFAULT_REQUESTER
import logging
from settings import LOG_NAME
from requester import RippingError


class PageRequestFailure(Exception):
    def __init__(self, *args, **kwargs):
        self.original_exception = kwargs.get('original')


class PageParseFailure(Exception):
    def __init__(self, *args, **kwargs):
        self.original_exception = kwargs.get('original')


def replace_all(string, old_lst, new):
    """Replace any substring in old_lst that occurs in string with new."""
    for substring in old_lst:
        string = string.replace(substring, new)
        Exception()
    return string


class BaseParser:
    """Some defaults for parsers."""
    __PARSER_NAME__ = "BaserParser"

    def __init__(self, page_url, raw_html=None, requester=None):
        self.url = page_url
        self._requester = requester if requester else DEFAULT_REQUESTER
        if raw_html:
            self.raw_html = raw_html
            self.soup = BeautifulSoup(raw_html, 'html5lib')
        else:
            self.raw_response = self._get_page()
            self.raw_html = self.raw_response.text
            self.soup = BeautifulSoup(self.raw_response.text, 'html5lib')
        self._logger = logging.getLogger(LOG_NAME)

    def __repr__(self):
        return '{}("{}")'.format(self.__PARSER_NAME__, self.url)

    def get_raw_html(self):
        if self.raw_html:
            return self.raw_html
        return self.raw_response.text

    def _get_page(self):
        try:
            return self._requester.get(self.url)
        except Exception as e:
            raise PageRequestFailure("Failed to GET page at {}".format(self.url),
                                     original=e)

class PiecePage(BaseParser):
    """Responsible for retrieving and parsing a piece page on choralWiki"""

    # Substrings that occur all over that obscure metadata.
    _IGNORED_SUBSTRINGS = ['\xa0', '[tag/del]']
    __PARSER_NAME__ = "PiecePage"
    _FILE_FORMATS = ('PDF', )

    def parse_metadata(self):
        try:
            return self._parse_metadata()
        except RippingError:
            raise
        except Exception as e:
            raise PageParseFailure("Failed to parse page at {}".format(self.url),
                                   original=e)

    def _parse_metadata(self):
        """Parse the metadata off the page which applies to all files on the page."""
        table_header = self.soup.find('span', id='General_Information').parent
        table_walker = table_header.nextSibling
        metadata_paragraphs = []
        while table_walker.name != 'h2':
            if table_walker.name == 'p':
                metadata_paragraphs.append(table_walker)
            table_walker = table_walker.nextSibling

        metadata = {}
        for entry in metadata_paragraphs:
            metadata.update(self.parse_metadata_table_row(entry))
        return metadata

    def parse_scores(self):
        try:
            return self._parse_scores()
        except RippingError:
            raise
        except Exception as e:
            raise PageParseFailure("Failed to parse page at {}".format(self.url),
                                   original=e)

    @staticmethod
    def parse_metadata_table_row(table_row):
        """Parse metadata in a paragraph."""
        metadata = {}
        children = [child for child in table_row.children]
        i = 0
        while i < len(children):
            if children[i].name == 'b':
                tag = children[i].text[:-1]
                tag_text = ""
                links = []
                i += 1
                while i < len(children) and children[i].name != 'b':
                    if isinstance(children[i], bsTag):
                        if children[i].get('style') == 'display:none':
                            i += 1
                            continue
                        tag_text += children[i].text
                        if children[i].find('a'):
                            links.append(children[i].find('a').get('href'))
                        elif children[i].name == 'a':
                            links.append(children[i].get('href'))
                    if isinstance(children[i], bsString):
                        tag_text += children[i]
                    i += 1
                tag_text = tag_text.replace('\xa0', ' ')
                tag_text = tag_text.replace('\n', '')
                tag_text = tag_text.strip()
                metadata[tag] = {'text': tag_text, 'links': links}
            else:
                i += 1
        return metadata

    def _parse_scores(self):
        """Return list of PDFs on page with metadata associated with each pdf."""
        parsed_scores = self.soup.find_all('a', {'href': lambda x : x and (x.endswith('.mid') or x.endswith('.midi'))})
        parsed_scores = [x.get('href') for x in parsed_scores]

        table_header = self.soup.find('span', id='Music_files').parent
        table_walker = table_header.nextSibling
        score_info = []
        while table_walker.name != 'h2':
            score_info.append(table_walker)
            table_walker = table_walker.nextSibling

        i = 0
        scores = []
        while i < len(score_info):
            if score_info[i].name == 'ul':
                one_score = [score_info[i]]
                i += 1
                while i < len(score_info) and score_info[i].name != 'ul':
                    one_score.append(score_info[i])
                    i += 1
                scores.append(one_score)
            else:
                i += 1

        parsed_scores = []
        for score in scores:
            parsed_score = {}
            meta = {}
            for s in score:
                if not isinstance(s, bsTag):
                    continue
                if s.name == 'ul':
                    parsed_score['dl_links'] = [a.get('href') for a in s.find_all('a')]
                    bolds = s.find_all('b')
                    CPDL = [x for x in bolds if x.text.startswith('CPDL')]
                    if CPDL:
                        CPDL = CPDL[0]
                        meta['CPDL#'] = CPDL.text.split('#')[-1][:-1]
                if s.name == 'dl':
                    for dd in s.find_all('dd'):
                        meta.update(self.parse_metadata_table_row(dd))
                parsed_score['meta'] = meta
            parsed_scores.append(parsed_score)
        return parsed_scores

    def _parse_download_metadata(self, download_table):
        """Parse the metadata from a download table which applies to all the file sin the table"""

        IGNORED_SUBSTRINGS = ['\xa0', '[tag/del]']
        meta = {}
        metadata = download_table.find('td', {'class': 'we_edition_info_i'})
        if metadata:
            labels = metadata.find_all('th')
            values = metadata.find_all('td')
            for l, v in zip(labels, values):
                stripped_label = replace_all(l.text, IGNORED_SUBSTRINGS, '').strip()
                stripped_value = replace_all(v.text, IGNORED_SUBSTRINGS, '').strip()
                if stripped_label != 'Purchase':
                    meta[stripped_label] = stripped_value
        return meta

class CategoryPage(BaseParser):
    """Abstract class for scraping category pages.

    The only difference between the sub-classes is what class of link they scrape
    for, as this is different on lists of categories and lists of items.

    Used as the base classes for:
        ComposerPage: Get all links to pieces off a composer's page.
        CompoesrListPage: Get all links to composer pages off the composer list page.
    """

    __PARSER_NAME__ = "CategoryPage"
    __TARGET_LINK_CLASS__ = None

    def get_all_in_category(self):
        """Return a list of the URL's associated with this category.

        target_link_class: the class of the kind of links to scrape off the page.
        """
        all_urls = []
        current_page = self.soup
        counter = 1

        while True:
            category_table = self._get_first_category_div(current_page)
            category_list = category_table.find_all('a', {'class': self.__TARGET_LINK_CLASS__})
            for link in category_list:
                page_link = link.get('href')
                name = link.text
                all_urls.append((name, page_link))

            self._logger.info("Scraped {} pages of links from {}".format(counter, self.url))
            counter += 1

            next_page = self._get_next_page_url(current_page)
            if not next_page:
                break

            raw_response = self._requester.get(next_page)
            current_page = BeautifulSoup(raw_response.text, 'html5lib')
        return all_urls

    def _get_first_category_div(self, page):
        """Get the first div on the page with links.

        Recurses into tested 'mw-content-ltr' divs until the base one is found.
        This solves the problem of multiple unrelated tabs of content being scraped
        at the same time.
        """
        outer = page.find('div', {'class': 'mw-content-ltr'})
        inner = outer.find('div', {'class': 'mw-content-ltr'})
        while inner:
            outer = inner
            inner = outer.find('div', {'class': 'mw-content-ltr'})
        return outer

    def _get_next_page_url(self, page):
        """Returns the url of the next page of pieces for this composer, if it exists."""

        category_table = page.find('div', {'class': 'mw-content-ltr'})
        next_page = category_table.find('a', text='next 200')
        if next_page:
            return next_page.get('href')
        else:
            return None

    def get_metadata(self):
        """Return a dict ready to be dumped to database for this composer."""
        name = self.soup.find('h1', id='firstHeading').text.replace('Category:', '').strip()
        url = self.url

        return {'name': name, 'url': url}


class ComposerPage(CategoryPage):
    """Get all piece links off of the composer list page.

    Scrapes all links with class 'categorypagelink' off the page's main table.
    """
    __PARSER_NAME__ = "ComposerPage"
    __TARGET_LINK_CLASS__ = 'categorypagelink'


class ComposerListPage(CategoryPage):
    """Get all composer links off of the composer list page.

    Scrapes all links with class 'categorysubcatlink' off the page's main table.
    """
    __PARSER_NAME__ = "ComposerListPage"
    __TARGET_LINK_CLASS__ = 'categorysubcatlink'
