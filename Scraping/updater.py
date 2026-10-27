import time
from pywaybackup import PyWayBackup

def main():
    with open("Scraping/scrapeTargets.txt", "r", encoding="utf-8") as f:
        urls = [line.strip() for line in f if line.strip()]

    for url in urls:
        print(f"Trying to download: {url}")
        try:
            backup = PyWayBackup(
                url=url,
                last=True,       # newest snapshot of each page (replaces mode="current")
                statuscode="200",    # only consider captures where the page loaded fine
                explicit=True,   # only this exact URL, not everything beneath it
                silent=False,    # show progress instead of running quietly
                delay=2,         # seconds between requests
                wait=15,         # seconds to cool off after an error
                retry=3,         # retry failed downloads
                workers=1,
            )
            backup.run()
        except Exception as e:
            print(f"Failed to download {url}: {e}")

        time.sleep(2)

if __name__ == "__main__":
    main()