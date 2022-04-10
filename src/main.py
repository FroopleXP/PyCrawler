import logging
from crawler import SingleDomainCrawler

START_POINT = "https://www.w3schools.com/"

# Configuring logger
logging.basicConfig(level=logging.DEBUG)

def main():

    crawler = SingleDomainCrawler(START_POINT, mediadir="./out")
    crawler.crawl()


if __name__ == "__main__":
    main()