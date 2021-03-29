#!/usr/bin/env python3
# coding: utf-8
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from string import Template
from textwrap import dedent, indent
from typing import Any, Dict, Generator, List, Literal, Optional, Tuple, Union
from urllib.parse import urljoin

import requests
import yaml

DEFAULT_STASH_PATH: Path = Path.home() / '.stash'
VERIFY_TLS = False


if not VERIFY_TLS:
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


def show_image(image: str):
    try:
        from PIL import Image
    except ImportError:
        print('ERROR: Viewing the image requires the Python Imaging Library "Pillow" to be installed.', file=sys.stderr)
        return

    # Decode `data:image/<type>;base64,<data>`
    from urllib.request import urlopen
    data = urlopen(image)

    with Image.open(data) as im:
        im.show()


def ask(q: str, default: bool) -> bool:
    d_answer, d_str = ('y', '[Y/n]') if default else ('n', '[y/N]')
    answer = input(f'{q} {d_str} >> ').strip().lower()
    if not answer or answer == d_answer:
        return default
    if answer not in ('y', 'n'):
        raise ValueError('Invalid answer!')
    return not default


class Config:
    def __init__(self, cfg: Dict[str, Any]) -> None:
        _host = cfg.get('host') or 'localhost'
        self.host: str = 'localhost' if _host == '0.0.0.0' else _host
        self.port: str = str(cfg.get('port') or 9999)
        self.username: str = cfg.get('username') or ''
        self.password_set: bool = bool(cfg.get('password'))
        self.api_key: str = cfg.get('api_key') or ''

        self.ssl: bool = (DEFAULT_STASH_PATH / 'stash.crt').is_file() and (DEFAULT_STASH_PATH / 'stash.key').is_file()

    @classmethod
    def read(cls, path: Path):
        with path.open() as fh:
            return cls(yaml.safe_load(fh))

    @property
    def stash_url(self) -> str:
        s = 's' if self.ssl else ''
        return f'http{s}://{self.host}:{self.port}'


class GQLQuery():
    """A GraphQL Query"""

    def __init__(self) -> None:
        self.operation_name: str = ''
        self.object_name: str = ''
        self.variables: Dict[str, Any] = {}

    def __str__(self) -> str:
        raise NotImplementedError

    def json(self) -> Dict[str, Any]:
        return {
            'operationName': self.operation_name,
            'query': str(self),
            'variables': self.variables,
        }

    def template_to_query(self, tmpl: Template) -> str:
        return tmpl.safe_substitute(
            operation_name=self.operation_name,
            object_name=self.object_name,
        )


class MutationReloadScrapers(GQLQuery):
    """ReloadScrapers Mutation"""

    def __init__(self) -> None:
        self.operation_name: str = 'ReloadScrapers'
        self.object_name: str = 'reloadScrapers'
        self.variables: Dict[str, Any] = {}

    def __str__(self) -> str:
        # https://github.com/stashapp/stash/blob/v0.4.0/graphql/documents/mutations/scrapers.graphql
        tmpl = Template(dedent("""
            mutation $operation_name {
                $object_name
            }
        """).strip())
        return self.template_to_query(tmpl)


class QueryScrapeSceneURL(GQLQuery):
    """ScrapeSceneURL Query"""

    def __init__(self) -> None:
        self.operation_name: str = 'ScrapeSceneURL'
        self.object_name: str = 'scrapeSceneURL'
        self.variables: Dict[str, Any] = {}

    @property
    def url(self) -> Optional[str]:
        return self.variables.get('url')

    @url.setter
    def url(self, url: str) -> None:
        self.variables['url'] = url

    def __str__(self) -> str:
        # https://github.com/stashapp/stash/blob/v0.4.0/graphql/documents/queries/scrapers/scrapers.graphql
        tmpl = Template(dedent("""
            query $operation_name($url: String!) {
                $object_name(url: $url) {
                    title
                    details
                    url
                    date
                    image

                    studio {
                        name
                    }

                    tags {
                        name
                    }

                    performers {
                        name
                        url
                    }

                    movies {
                        name
                    }
                }
            }
        """).strip())
        return self.template_to_query(tmpl)


class QueryScrapeGalleryURL(GQLQuery):
    """ScrapeGalleryURL Query"""

    def __init__(self) -> None:
        self.operation_name: str = 'ScrapeGalleryURL'
        self.object_name: str = 'scrapeGalleryURL'
        self.variables: Dict[str, Any] = {}

    @property
    def url(self) -> Optional[str]:
        return self.variables.get('url')

    @url.setter
    def url(self, url: str) -> None:
        self.variables['url'] = url

    def __str__(self) -> str:
        # https://github.com/stashapp/stash/blob/v0.4.0/graphql/documents/queries/scrapers/scrapers.graphql
        tmpl = Template(dedent("""
            query $operation_name($url: String!) {
                $object_name(url: $url) {
                    title
                    details
                    url
                    date

                    studio {
                        name
                    }

                    tags {
                        name
                    }

                    performers {
                        name
                        url
                    }
                }
            }
        """).strip())
        return self.template_to_query(tmpl)


class StashAuthenticationError(Exception):
    pass


class StashInterface:
    def __init__(self, cfg: Config, password: Optional[str] = None):
        self.base_url = cfg.stash_url
        self.endpoint = urljoin(self.base_url, '/graphql')

        self.session = requests.Session()
        self.session.headers.update({
            'Content-Type': 'application/json',
        })
        self.session.verify = VERIFY_TLS

        if cfg.api_key:
            self.session.headers.update({
                'ApiKey': cfg.api_key,
            })
        elif cfg.username and password:
            self._login(cfg.username, password)

    def _login(self, username: str, password: str):
        print('Authenticating with Stash...')

        try:
            response = self.session.request(
                method='POST',
                url=urljoin(self.base_url, '/login'),
                headers={
                    'Content-Type': 'application/x-www-form-urlencoded',
                },
                data={
                    'username': username,
                    'password': password,
                    'returnURL': '/',
                },
            )
        except requests.exceptions.RequestException as error:
            raise StashAuthenticationError('Unable to authenticate with Stash') from error

        try:
            response.raise_for_status()
        except requests.exceptions.HTTPError as error:
            raise StashAuthenticationError('Unexpected response from Stash while authenticating') from error

        return 'Set-Cookie' in response.headers

    def _call(self, query: GQLQuery):
        json_data = query.json()

        response = self.session.post(
            url=self.endpoint,
            json=json_data,
        )
        try:
            result = response.json()
        except ValueError:
            print(f'ERROR: Invalid API response ({response.status_code}):\n{response.text}')
            return

        if 'errors' in result:
            print('GraphQL Errors:')
            for error in result['errors']:
                if 'locations' in error:
                    for location in error['locations']:
                        print(f"At line {location['line']} column {location['column']}")
                        print(f"  [{error['extensions']['code']}] {error['message']}")
                elif 'path' in error:
                    print(f"At path /{'/'.join(map(str, error['path']))}: {error['message']}")
                else:
                    print(error)
            return None

        data = result['data']
        if not data:
            return

        return data[query.object_name]

    def reload_scrapers(self) -> Optional[bool]:
        print('Reloading scrapers...')

        query = MutationReloadScrapers()

        results = self._call(query)

        if results is None:
            return

        return results

    def scrape_scene_url(self, url: str) -> Optional[Dict[str, Any]]:
        print(f'Scraping scene URL {url}')

        query = QueryScrapeSceneURL()
        query.url = url

        results = self._call(query)

        if not results:
            return

        return results

    def scrape_gallery_url(self, url: str) -> Optional[Dict[str, Any]]:
        print(f'Scraping gallery URL {url}')

        query = QueryScrapeGalleryURL()
        query.url = url

        results = self._call(query)

        if not results:
            return

        return results


def chunks(lst, n: int):
    """Yield successive n-sized chunks from lst."""
    for i in range(0, len(lst), n):
        yield lst[i:i + n]


def try_len(lst: Any) -> int:
    try:
        return len(lst)
    except TypeError:
        return 0


def print_scene(scraped_scene: Dict[str, Any]) -> None:
    title: Optional[str] = scraped_scene.pop('title')
    date: Optional[str] = scraped_scene.pop('date')

    details: Optional[str] = scraped_scene.pop('details')
    details_p = ('{\n' + indent(details, '  ') + '\n}') if details is not None else details

    url: Optional[str] = scraped_scene.pop('url')

    image: Optional[str] = scraped_scene.pop('image')
    image_p: str = 'Yes' if image else 'No'

    studio: Optional[Dict[Literal['name', 'url'], str]] = scraped_scene.pop('studio')
    studio_p = (studio.get('name'), studio.get('url')) if studio is not None else studio

    tags: Optional[List[Dict[Literal['name'], str]]] = scraped_scene.pop('tags')
    if tags is not None:
        tags_c = chunks([repr(t.get('name')) for t in tags], 7)
        tags_p = '\n  '.join(', '.join(tc) for tc in tags_c)
    else:
        tags_p = tags

    performers: Optional[List[Dict[Literal['name', 'url'], str]]] = scraped_scene.pop('performers')
    performers_p = '\n  '.join([repr((p.get('name'), p.get('url'))) for p in performers]) if performers is not None else performers

    movies: Optional[List[Dict[Literal['name', 'url'], str]]] = scraped_scene.pop('movies')
    movies_p = '\n  '.join([repr((m.get('name'), m.get('url'))) for m in movies]) if movies is not None else movies

    print(f'Title: {title!r}')
    print(f'Date: {date!r}')
    print(f'Image: {image_p}')
    print(f'URL: {url!r}')
    print(f'Details: {details_p}')
    print(f'Studio: {studio_p!r}')
    print(f'Tags ({try_len(tags)}):\n  {tags_p}')
    print(f'Performers ({try_len(performers)}):\n  {performers_p}')
    print(f'Movies ({try_len(movies)}):\n  {movies_p}')

    if scraped_scene:
        print()
        print('EXTRA DATA:')
        print(json.dumps(scraped_scene, sort_keys=True, indent=2))

    if image and ask('\nShow image using default image viewer?', default=False):
        show_image(image)


def print_gallery(scraped_gallery: Dict[str, Any]) -> None:
    title: Optional[str] = scraped_gallery.pop('title')
    date: Optional[str] = scraped_gallery.pop('date')

    details: Optional[str] = scraped_gallery.pop('details')
    details_p = ('{\n' + indent(details, '  ') + '\n}') if details is not None else details

    url: Optional[str] = scraped_gallery.pop('url')

    studio: Optional[Dict[Literal['name', 'url'], str]] = scraped_gallery.pop('studio')
    studio_p = (studio.get('name'), studio.get('url')) if studio is not None else studio

    tags: Optional[List[Dict[Literal['name'], str]]] = scraped_gallery.pop('tags')
    if tags is not None:
        tags_c = chunks([repr(t.get('name')) for t in tags], 7)
        tags_p = '\n  '.join(', '.join(tc) for tc in tags_c)
    else:
        tags_p = tags

    performers: Optional[List[Dict[Literal['name', 'url'], str]]] = scraped_gallery.pop('performers')
    performers_p = '\n  '.join([repr((p.get('name'), p.get('url'))) for p in performers]) if performers is not None else performers

    print(f'Title: {title!r}')
    print(f'Date: {date!r}')
    print(f'URL: {url!r}')
    print(f'Details: {details_p}')
    print(f'Studio: {studio_p!r}')
    print(f'Tags ({try_len(tags)}):\n  {tags_p}')
    print(f'Performers ({try_len(performers)}):\n  {performers_p}')

    if scraped_gallery:
        print()
        print('EXTRA DATA:')
        print(json.dumps(scraped_gallery, sort_keys=True, indent=2))


def url_generator(args: 'Arguments') -> Tuple[Union[Generator[str, None, None], List[str]], Optional[int]]:
    if not args.urls:
        def _generator() -> Generator[str, None, None]:
            url = input('\nEnter first URL to scrape:\n>> ').strip()
            while url:
                yield url
                url = input('\nEnter next URL to scrape (empty to stop):\n>> ').strip()

        return _generator(), None

    if args.is_list:
        list_path = Path(args.urls)
        try:
            urls = list_path.read_text('utf-8').strip().splitlines()
        except Exception as error:
            print(f'Error: Unable to read file {list_path}: {error!r}')
            raise StopIteration
    else:
        urls = args.urls.splitlines()

    urls = list(filter(None, map(str.strip, urls)))

    return urls, len(urls)


def run(args: 'Arguments'):
    config_path = Path(args.config)
    try:
        print(f'Using config: {config_path}')
        cfg = Config.read(config_path)
    except OSError:
        print(f'Unable to load Stash config from {config_path}')
        return

    if cfg.password_set and not (cfg.api_key or args.password):
        print(f'Password required for user {cfg.username}, provide it using `-p password`.')
        return

    try:
        stash = StashInterface(cfg, args.password)
    except StashAuthenticationError:
        raise

    if args.reload:
        reloaded = stash.reload_scrapers()
        if not reloaded:
            print('Failed to reload')
            return

    url_gen, total = url_generator(args)

    for idx, url in enumerate(url_gen, 1):
        if total and idx > 1 and not ask('\nContinue?', default=True):
            break

        if args.type == 'scene':
            scrape_result = stash.scrape_scene_url(url)
            if not scrape_result:
                print(f'{url} : Failed')
                continue

            print()
            print_scene(scrape_result)

        elif args.type == 'gallery':
            scrape_result = stash.scrape_gallery_url(url)
            if not scrape_result:
                print(f'{url} : Failed')
                continue

            print()
            print_gallery(scrape_result)


class Arguments(argparse.Namespace):
    urls: str
    is_list: bool

    config: str
    password: str

    type: str
    reload: bool


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        '-c', '--config', default=str(DEFAULT_STASH_PATH / 'config.yml'),
        help='Stash config path.',
    )
    parser.add_argument(
        '-p', '--password',
        help='Stash password, if set. Required in order to use GraphQL.',
    )

    parser.add_argument(
        '-t', '--type', default='scene', choices=['scene', 'gallery'],
        help='Type of scraped object (default is "scene").',
    )
    parser.add_argument(
        '-nr', '--no-reload', dest='reload', action='store_false',
        help='Disable reloading the scrapers and clearing the scraper cache before scraping.',
    )

    parser.add_argument(
        '-l', '--list', dest='is_list', action='store_true',
        help='Load URLs list from the provided list file path.',
    )

    parser.add_argument(
        'urls', nargs='?',
        help='URL(s) to scrape - one per line, a path to a list file (with `--list`), or nothing for continuous input.',
    )

    args = parser.parse_args(namespace=Arguments())

    if args.is_list and not args.urls:
        print('Error: `--list` requires a file path.')
        return

    try:
        run(args)
    except (KeyboardInterrupt, SystemExit):
        pass


if __name__ == '__main__':
    main()
