# immobilien-Krabbler
scraper for Immobilienscout24.de

install
```
    pip3 install selenium==3.4.1 SQLAlchemy==1.2.11 SQLAlchemy-Utils==0.32.14
    npm install -g phantomjs@2.1.1
```

```
usage: immoKrabbler.py [-h] [--database [DATABASE]] [--debug]
                       [--url URL [URL ...]] [--update-db] [--json]
                       [--photos [PHOTO_DIR]] [--csv] [--outfile [OUTFILE]]

immoKrabbler, der Immobilienscout scraper

positional arguments:
  search

optional arguments:
  -h, --help            show this help message and exit
  --database [DATABASE]
                        SqlAlchemy connection string, defaults to
                        [sqlite:///immobilien.db]
  --debug               debugging
  --url URL [URL ...]   Immobilienscout search urls (space delimited)
  --update-db           update search results in db
  --json                write json to stdout
  --photos [PHOTO_DIR]  save photos to dir
  --csv                 write csv to stdout
  --outfile [OUTFILE]   write [csv|json] to file```
