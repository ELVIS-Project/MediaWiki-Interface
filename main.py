import IPython
from bs4 import BeautifulSoup
import requests
import logging
import argparse
import signal
import datetime

from settings import LOG_FILE
from db import DB_SESSION
from globals import set_should_term_true, EMAILER, DEFAULT_REQUESTER


def start_shell():
    """Opens up an IPython window and a DB session to browse the database."""
    from scraper import WebScraper
    session = DB_SESSION()
    IS = WebScraper(session)
    IPython.embed()


def start_scrape():
    """Searches for things to scrape and gets to work."""
    from scraper import WebScraper

    logging.info("Starting to scrape.")

    session = DB_SESSION()
    IS = WebScraper(session)

    # Get list of composers into database, if it's not already there.
    if not _already_scraped_composers_list(session):
        IS.scrape_composer_list()

    # Scrape the links to all pieces from list of composers, for those
    # which are not yet done.
    IS.scrape_all_composers()

    # Scrape all piece information
    IS.scrape_all_pieces()


def _already_scraped_composers_list(session):
    from db import Composer
    composer_count = session.query(Composer).count()
    return composer_count >= 14740


def parse_args():
    """Parse and return command line args."""
    parser = argparse.ArgumentParser(description="Rip stuff from websites dude.")
    parser.add_argument('action', choices=('shell', 'scrape'))
    return parser.parse_args()


def init_logging():
    """Initiate logging behaviour for project."""
    logging.basicConfig(filename=LOG_FILE, level=logging.INFO)


def init_sig_handel():
    """Bind graceful exit behaviour to SIGTERM."""
    signal.signal(signal.SIGTERM, set_should_term_true)

if __name__ == '__main__':
    from requester import RippingError

    init_logging()
    init_sig_handel()
    args = parse_args()
    action = args.action

    if action == 'shell':
        start_shell()
    elif action == 'scrape':
        try:
            start_scrape()
        except Exception as e:
            if isinstance(e, RippingError):
                logging.error("Ripping detected. Exiting.")
                EMAILER.send('a.g.parmentier@gmail.com',
                             "Ripping detected.",
                             "Scraping was stopped at {} as ripping was detected.".format(datetime.datetime.now()))

            EMAILER.send('a.g.parmentier@gmail.com',
                         'Exception hit on web scrapper.',
                         "Scraping was stopped at {} because some exception was hit. Investigate log files".format(datetime.datetime.now()))
            raise
