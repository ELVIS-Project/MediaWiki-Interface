import logging
import datetime

from emailer import Emailer
from db import Piece
from settings import EMAIL_ADRR, EMAIL_PASS, PROXY_LIST, FUZZ_RANGE
from requester import ProxiedFuzzedRequester

DEFAULT_REQUESTER = ProxiedFuzzedRequester(PROXY_LIST, FUZZ_RANGE)
EMAILER = Emailer(('smtp.mail.com', 587), EMAIL_ADRR, EMAIL_PASS)
SHOULD_TERM = False  # Flag set to true when a TERM signal arrives.


def commit_session(session):
    """Commits the session then checks if we need to exit or send status emails.

    Point here is that if we get a TERM signal, we keep running
    until the next commit, then we exit, so no work gets wasted.
    """
    session.commit()

    if (datetime.datetime.now() - EMAILER._last_status_email).days >= 1:
        pieces_scraped = session.query(Piece).filter(Piece.scraped == True).count()
        total_pieces = session.query(Piece).count()
        send_status_update_email(pieces_scraped, total_pieces)
        EMAILER._last_status_email = datetime.datetime.now()
    if SHOULD_TERM:
        logging.info("Received TERM signal. Shutting down.")
        exit(0)


def set_should_term_true(signum, stack):
    """Set ourselves up to terminate after next database commit."""
    global SHOULD_TERM
    SHOULD_TERM = True


def send_status_update_email(pieces_scraped, total_pieces):
    EMAILER.send('a.g.parmentier@gmail.com', 'IMSLP status update.',
                 'CW scrapper has successfully scraped {}/{} pieces.'.format(pieces_scraped, total_pieces))


