CW_DOMAIN = 'http://www3.cpdl.org'
DOWNLOAD_PATH = '/home/lexpar/Documents/DDMAL/media_grabber/downloads'
EXTENSIONS = ['.pdf', '.mid', '.midi', 'xml', 'mxl', '.mus', '.musx',
              '.sib', '.cap', '.capx', '.ly', '.mscz', '.zip', '.enc', '.nwc']
EXTENSIONS.extend([e.upper() for e in EXTENSIONS])

PROXY_LIST = []
FUZZ_RANGE = (0, 10)
SQLITE_FILE = '/home/lexpar/Documents/DDMAL/media_grabber/downloads/db.sqlite'
LOG_FILE = '/home/lexpar/Documents/DDMAL/media_grabber/downloads/log'
#SQLITE_FILE = '/mnt/imslp/db.sqlite'
#LOG_FILE = '/mnt/imslp/grabber.log'

LOG_NAME = 'web_scraper'

EMAIL_ADRR = 'alex.parmentier@mail.com'
EMAIL_PASS = 'dsfdsf'

COMPOSER_LIST_URL = 'http://www1.cpdl.org/wiki/index.php/Category:Composers'
