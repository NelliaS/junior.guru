from juniorguru.fetch.fetch_jobs import main as fetch_jobs
from juniorguru.fetch.fetch_metrics import main as fetch_metrics
from juniorguru.fetch.fetch_stories import main as fetch_stories
from juniorguru.fetch.fetch_supporters import main as fetch_supporters
from juniorguru.fetch.fetch_last_modified import main as fetch_last_modified
from juniorguru.fetch.fetch_press_releases import main as fetch_press_releases


def main():
    # order-insensitive
    fetch_stories()
    fetch_supporters()
    fetch_last_modified()
    fetch_press_releases()

    # order-sensitive
    fetch_jobs()
    fetch_metrics()


if __name__ == '__main__':
    main()
