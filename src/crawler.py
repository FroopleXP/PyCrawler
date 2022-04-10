from collections import deque
import logging
import os
from time import time
from requests import Session, adapters
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
from enum import Enum

class DocumentType(Enum):
    UNKNOWN = 1
    MEDIA = 2
    WEBPAGE = 3

MEDIA_FILE_EXTS = [".jpg", ".jpeg", ".mov", ".zip", ".avi", ".gif", ".png", ".rar", ".mp3", ".mp4"]
DOCUMENT_FILE_EXTS = [".html", ".shtml", ".htm"]

class SingleDomainCrawler:
    """
        Crawls a single given domain whilst reporting
        back links to external domains for later
        crawling.
    """

    def __init__(self, domain: str, pool_size: int=100, max_pool_size: int=100, mediadir: str="./out") -> None:
        self._domain = domain
        self._adapter = adapters.HTTPAdapter(pool_connections=pool_size, pool_maxsize=max_pool_size)
        self._session = Session()
        self._start_session()
        self._media_dir = self._create_media_dir("%s/%s" % (mediadir, self._escape_and_replace_string(domain)))
        self._crawl_start_time_s = time()

    def _start_session(self) -> None:
        self._session.mount(self._domain, self._adapter)

    def _create_media_dir(self, dirname: str) -> str:
        logging.debug("Creating new media directory -> %s", dirname)
        try:
            os.makedirs(dirname)
            return dirname
        except Exception as e:
            logging.error("Failed to make media directory -> %s\nAborting...", str(e))
            quit(1)

    # TODO: I think this is more of a utility
    def _escape_and_replace_string(self, string: str) -> str:
        return string.replace(".", "_").replace("/", "").replace(":", "_")

    def _download_media_from_url(self, url: str, outdir: str) -> None:
        local_filename = self._get_document_name_from_url(url)
        logging.debug("Downloading media -> %s", local_filename)

        try:
            with self._session.get(url, stream=True) as r:
                r.raise_for_status()
                with open("%s/%s" % (outdir, local_filename), "wb") as f:
                    for chunk in r.iter_content(chunk_size=512):
                        f.write(chunk)

        except Exception as e:
            logging.error("Failed to download media -> %s", str(e))

    def _crawl_single(self, link) -> list:
        logging.debug("Crawling -> %s", link)
        found_links: list = []

        try:
            # Try to get the page contents
            resp = self._session.get(link)
            logging.debug("Response code -> %d", resp.status_code)
            if (resp.status_code != 200): return []

            # Parsing the DOM and getting the links - 
            # 'a'
            soup = BeautifulSoup(resp.content, "html.parser")
            for newlink in soup.find_all("a"):
                url = urljoin(link, newlink.get("href"), allow_fragments=True)
                found_links.append(url)

            # 'img'
            for newlink in soup.find_all("img"):
                url = urljoin(link, newlink.get("href"), allow_fragments=True)
                found_links.append(url)

            # 'source'
            for newlink in soup.find_all("source"):
                url = urljoin(link, newlink.get("src"), allow_fragments=True)
                found_links.append(url)

        except Exception as e:
            logging.error("Failed to get crawl, status -> %s", str(e))

        return found_links

    def _is_link_within_domain(self, link: str) -> bool:
        p_domain = urlparse(self._domain)
        p_link = urlparse(link)
        return True if p_link.netloc == p_domain.netloc else False

    def _get_document_name_from_url(self, url: str) -> str:
        p_url = urlparse(url)
        return os.path.basename(p_url.path)

    def _infer_link_document_type(self, link: str) -> str:
        try:
            filename = self._get_document_name_from_url(link)
            logging.debug("Inferring document type -> %s", filename)

            ext = os.path.splitext(filename)[1].lower()

            if ext in MEDIA_FILE_EXTS:
                return DocumentType.MEDIA
            if ext in DOCUMENT_FILE_EXTS:
                return DocumentType.WEBPAGE

            return DocumentType.UNKNOWN

        except Exception as e:
            logging.error("Failed to infer document type: %s", str(e))
            return DocumentType.UNKNOWN

    def newdomain(self, domain: str) -> None:
        """ Allows you to use the same class instance for a new domain """

        self._domain = domain
        self._start_session()

    def crawl(self) -> list:
        """ Starts the crawler against the specified domain """

        to_visit = deque()
        visited = deque()

        to_visit.append(self._domain)

        while (to_visit):
            current = to_visit[0]

            # Don't scrape if the link has already been seen or is not part of the domain
            if current in visited or not self._is_link_within_domain(current): 
                to_visit.popleft()
                continue
            
            logging.debug("Total left to crawl -> %d", len(to_visit))

            # Get the document type
            doctype = self._infer_link_document_type(current)
            logging.debug("Document type -> %s", doctype)

            # If we have a media link, download instead of crawling
            if doctype == DocumentType.MEDIA:
                self._download_media_from_url(current, self._media_dir)

            # Get the links from the current page and add them for crawling
            if doctype == DocumentType.WEBPAGE or doctype == DocumentType.UNKNOWN:
                new_links = self._crawl_single(current)
                for link in new_links:
                    to_visit.append(link)
            
            # So we know we've been there
            visited.append(current)

            # Pop the last (current) item of the to_visit stack
            to_visit.popleft()
        
        # Calculate the total time
        total_time_s: float = time() - self._crawl_start_time_s
        logging.debug("Crawl completed in %f second(s)", total_time_s)
