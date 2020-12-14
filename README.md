# Stash Scraper Tester

Test scrapers in Stash quickly and efficiently.

## Usage

```
usage: scrape_url.py [-h] [-c CONFIG] [-p PASSWORD] [-t {scene,gallery}] [-r] url

positional arguments:
  url                   URL to scrape.

optional arguments:
  -h, --help            show this help message and exit
  -c CONFIG, --config CONFIG
                        Stash config path.
  -p PASSWORD, --password PASSWORD
                        Stash password, if set. Required in order to use GraphQL.
  -t {scene,gallery}, --type {scene,gallery}
                        Type of scraped object.
  -r, --reload          Reload scrapers.
```

### Example:
```
python scrape_url.py https://example.com/scenes/1234
```
