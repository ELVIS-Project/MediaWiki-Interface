import logging
import json
import urllib
import os
from unidecode import unidecode

from parsers import ComposerPage, ComposerListPage, PiecePage, PageRequestFailure, PageParseFailure
from db import Composer, Piece, Score
from settings import COMPOSER_LIST_URL, LOG_NAME, DOWNLOAD_PATH, EXTENSIONS
from globals import commit_session, DEFAULT_REQUESTER




def get_dl_path(metadata):
    """Computes and creates the path for a file to be downloaded."""
    composer = unidecode(metadata['Composer']['text'])
    piece = unidecode(metadata['Title']['text'])
    piece = piece.replace(' ', '_')
    composer = composer.replace(' ', '_')
    piece = piece if piece else "UNKNOWN"
    composer = composer if composer else "UNKNOWN"

    download_dir = os.path.join(DOWNLOAD_PATH, composer)

    if not os.path.exists(download_dir):
        os.mkdir(download_dir)

    download_dir = os.path.join(download_dir, piece)
    if not os.path.exists(download_dir):
        os.mkdir(download_dir)

    return download_dir


def download_score(score, metadata):
    download_dir = get_dl_path(metadata)
    file_paths = []
    for link in score.get('dl_links', []):
        if not any(link.endswith(x) for x in EXTENSIONS):
            continue
        filename = link.split('/')[-1]
        try:
            data = DEFAULT_REQUESTER.get(link)
        except Exception:
            logger = logging.getLogger(LOG_NAME)
            logger.warning("Failed to download score at {}".format(link))
            continue

        file_path = os.path.join(download_dir, filename)
        with open(file_path, 'wb') as f:
            f.write(data.content)
        file_paths.append(os.path.relpath(file_path, DOWNLOAD_PATH))

    return file_paths


class WebScraper:

    def __init__(self, db_session):
        """Connect to SQL DB"""
        self._session = db_session
        self._logger = logging.getLogger(LOG_NAME)

    def scrape_pieces_from_list(self, piece_list):
        # Load the list of things we've already downloaded.
        downloaded_list_path = os.path.join(DOWNLOAD_PATH, 'downloaded.json')
        if os.path.exists(downloaded_list_path):
            with open(downloaded_list_path, 'r') as f:
                already_downloaded = json.load(f)
        else:
            already_downloaded = []

        piece_list = list(set(piece_list) - set(already_downloaded))

        """Quick and dirty way to download a lot of files. Does not use database."""
        for piece_url in piece_list:
            try:
                pp = PiecePage(piece_url)
                scores, metadata = pp.parse_scores(), pp.parse_metadata()
            except PageRequestFailure:
                self._logger.warning("Failed to GET {}".format(piece_url))
                continue
            except PageParseFailure:
                self._logger.warning("Failed to parse {}".format(piece_url))
                continue

            for score in scores:
                score['piece_url'] = piece_url
                file_paths = download_score(score, metadata)
                score['file_paths'] = file_paths

            download_dir = get_dl_path(metadata)
            metadata['piece_url'] = piece_url
            json_out = {'piece_metadata': metadata, 'scores': scores}
            with open(os.path.join(download_dir, 'meta.json'), 'w') as f:
                json.dump(json_out, f, indent=4)

            # Add this to the list of things we've already downloaded.
            already_downloaded.append(piece_url)
            with open(downloaded_list_path, 'w') as f:
                json.dump(already_downloaded, f)



    def scrape_all_composers(self):
        """Scrapes piece links for every composer in the database.

        That is, populates the database with all the Piece objects which only
        contain a url. It is up to scrape_all_pieces() to actually access these urls
        and scrape them.

        Ignores a composer if it's 'all_scraped' variable is set to true. This means that
        the composer has already had all piece links scraped off the page.

        Assumes database has already been populated with composer information
        using the scrape_composer_list() method.
        """
        composers = self._session.query(Composer).all()
        for db_comp in composers:
            if not db_comp.all_scraped:
                self.scrape_composer(db_comp)

    def scrape_all_pieces(self):
        """Scrapes all pieces that are not yet scraped.

        Ignores any piece with 'scraped' set to True.

        Assumes database has already been populated with pieces by scrape_all_composers.
        """
        pieces = self._session.query(Piece)\
            .filter(Piece.scraped == False)\
            .filter(Piece.failed_scrape == False)
        for db_piece in pieces:
            self.scrape_piece(db_piece)

    def scrape_composer(self, db_composer):
        """Get all pieces related to a composer into the database."""

        # Download and parse the composer page
        composer_page = ComposerPage(db_composer.url)
        # Get all the pieces related to this composer
        all_pieces = composer_page.get_all_in_category()

        pieces_to_add = []
        for piece in all_pieces:
            name, url = piece
            if not self._piece_in_database(url):
                db_piece = Piece(name=name, url=url, composer=db_composer)
                pieces_to_add.append(db_piece)

        self._session.add_all(pieces_to_add)
        db_composer.all_scraped = True
        commit_session(self._session)

        piece_count = len(all_pieces)
        self._logger.info("Successfully scraped {} piece links for {}".format(piece_count, db_composer.name))

    def scrape_piece(self, db_piece):
        """Scrape a piece page associated with a database piece entry.

        Populates the database with Score objects based on what is parsed
        off the pgae.
        """

        # Download and parse the piece page
        try:
            piece_page = PiecePage(db_piece.url)
            scores = piece_page.parse_scores()
            metadata = piece_page.parse_metadata()
        except (PageRequestFailure, PageParseFailure) as e:
            if isinstance(e, PageParseFailure):
                self._logger.warning("Failed to parse page at {}".format(db_piece.url))
            else:
                self._logger.warning("Failed to download piece page at {}:".format(db_piece.url))
            self._logger.warning(e.original_exception)
            db_piece.failed_scrape = True
            commit_session(self._session)
            return

        # Create scores associated with this piece.
        scores_to_add = []
        for score in scores:
            for dli in score.get('download_links'):
                if not self._score_in_database(dli['url']):
                    db_score = Score(**dli, piece=db_piece, composer=db_piece.composer)
                    scores_to_add.append(db_score)
        self._session.add_all(scores_to_add)

        # Save scraping data in DB.
        db_piece.json_metadata = json.dumps(metadata)
        db_piece.html_dump = piece_page.get_raw_html()
        db_piece.scraped = True
        commit_session(self._session)
        self._logger.info("Successfully scraped {} scores from piece {}.".format(len(scores_to_add), db_piece.name))

    def scrape_composer_list(self, composer_list_url=COMPOSER_LIST_URL):
        """Get all the composers into the database.

        Assumes database is empty. Will crash if it tries to add a composer
        that already exists in the database, by the unique constraint on
        composer URLs.
        """
        composer_page = ComposerListPage(composer_list_url)
        all_composers = composer_page.get_all_in_category()

        for composer in all_composers:
            name, url = composer
            db_comp = Composer(name=name, url=url)
            self._session.add(db_comp)

        commit_session(self._session)
        self._logger.info("Successfully scraped all composer links")

    def _piece_in_database(self, piece_url):
        """Return True if piece with given URL is already in database."""
        result = self._session.query(Piece).filter(Piece.url == piece_url).count()
        return result == 1


    def _score_in_database(self, score_url):
        result = self._session.query(Score).filter(Score.url == score_url).count()
        return result == 1


class SearchAPIScraper:
    RESULTS_PER_PAGE = 50

    def __init__(self, base_search_url):
        self._base_search_url = base_search_url
        self._scraped_urls = []
        self._finished = False

    def scrapeAll(self):
        if self._finished:
            return self._scraped_urls

        scraped_urls = []

        parsed_url = urllib.parse.urlparse(self._base_search_url)
        parsed_query = urllib.parse.parse_qs(parsed_url.query)
        parsed_query['gsrlimit'] = self.RESULTS_PER_PAGE

        temp_url = *parsed_url[0:4], urllib.parse.urlencode(parsed_query, doseq=True), *parsed_url[5:]
        temp_url = urllib.parse.urlunparse(temp_url)

        resp = DEFAULT_REQUESTER.get(temp_url)
        resp_json = resp.json()
        while resp_json.get('query-continue', {}).get('search', {}).get('gsroffset'):
            results = resp_json.get('query', {}).get('pages', {})
            for page in results.values():
                scraped_urls.append(page.get('fullurl'))

            print("Finished scraping {}".format(temp_url))

            parsed_query['gsroffset'] = resp_json['query-continue']['search']['gsroffset']
            temp_url = *parsed_url[0:4], urllib.parse.urlencode(parsed_query, doseq=True), *parsed_url[5:]
            temp_url = urllib.parse.urlunparse(temp_url)
            resp = DEFAULT_REQUESTER.get(temp_url)
            resp_json = resp.json()
        self._scraped_urls = scraped_urls
        self._finished = True
        return self._scraped_urls
