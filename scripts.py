"""Contains assorted scripts that have been used on the data-dump over time."""
from db import *
from parsers import PiecePage
from scraper import get_dl_path
from sqlalchemy.orm.exc import NoResultFound
import json
import os
import shutil


def isolate_reiner_files(target_folder):
    """Isolate the pieces and files Reiner was originally interested in.

    Args:
        target_folder: Absolute path to directory to put files in.

    Returns: None
    """
    session = DB_SESSION()
    file_paths = []

    with open('motets.json') as f:
        motets = json.load(f)
    with open('renaissance.json') as f:
        renaissance = json.load(f)

    motets.extend(renaissance)
    sources = motets
    missed = 0

    for url in sources:
        rel_url = '/wiki/' + url.split('/wiki/')[-1]
        try:
            piece = session.query(Piece).filter(Piece.url == rel_url).one()
        except NoResultFound:
            missed += 1
            continue
        for score in piece.scores:
            file_paths.append(score.file_path)

    target_folder = '/mnt/choral/reiner_files/'

    # missed == 13
    # len(file_paths) == 26560

    for file_path in file_paths:
        if not file_path:
            continue
        new_path = os.path.join(target_folder, file_path.split('/mnt/choral/downloads/')[-1])
        shutil.copytree(file_path, new_path)


def re_parse_metadata():
    """Re parses the metadata of every piece.

    This is necessary because I forgot to include some special handling to parse
    movement names from pieces that have movements. These are not very standard, but
    the information is necessary.
    """
    session = DB_SESSION()
    for piece in session.query(Piece):
        # Initialization for this loop
        url, raw_html = piece.url, piece.html_dump
        if not piece.json_metadata:
            continue
        old_metadata = json.loads(piece.json_metadata)

        # Re parse the page
        parser = PiecePage(url, raw_html)
        new_metadata = parser.parse_metadata()
        new_metadata['scores'] = old_metadata['scores']

        # Output the new results
        with open(os.path.join(get_dl_path(old_metadata), 'meta.json'), 'w') as f:
            json.dump(new_metadata, f)

if __name__ == '__main__':
    re_parse_metadata()
