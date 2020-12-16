# Stash Scraper Tester

Test scrapers in Stash quickly and efficiently.

## Requirements

- Python 3.8 (should work with >= 3.6)
- [`Pillow`](https://pypi.org/project/Pillow) >= 8.0.0 (for displaying the scraped image)
- [`PyYAML`](https://pypi.org/project/PyYAML) >= 5.2
- [`requests`](https://pypi.org/project/requests) >= 2.20.0

```
pip install -r requirements.txt
```

## Usage

```
scrape_url.py [-h] [-c CONFIG] [-p PASSWORD] [-t {scene,gallery}] [-r] [-l] [urls]

positional arguments:
  urls                  URL(s) to scrape - one per line,
                        a path to a list file (with `--list`),
                        or nothing for continuous input.

optional arguments:
  -h, --help            show this help message and exit
  -c CONFIG, --config CONFIG
                        Stash config path.
  -p PASSWORD, --password PASSWORD
                        Stash password, if set. Required in order to use GraphQL.
  -t {scene,gallery}, --type {scene,gallery}
                        Type of scraped object.
  -r, --reload          Reload scrapers before scraping.
  -l, --list            Load URLs list from the provided list file path.
```

### Example:
```
python scrape_url.py https://example.com/scenes/1234
```
