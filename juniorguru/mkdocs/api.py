import csv
from datetime import timedelta

import ics
from pod2gen import Podcast, Episode, Media, Person, Category, Funding

from juniorguru.lib.md import md
from juniorguru.models import Employment, Event, PodcastEpisode, with_db


@with_db
def build_events_ics(api_dir, config):
    calendar = ics.Calendar(events=[
        ics.Event(summary=event.title,
                  begin=event.start_at,
                  duration=timedelta(hours=1),
                  description=event.url)
        for event in Event.api_listing()
    ])
    api_file = api_dir / 'events.ics'
    with api_file.open('w', encoding='utf-8') as f:
        f.writelines(calendar)


@with_db
def build_czechitas_csv(api_dir, config):
    rows = [employment.to_api() for employment in Employment.api_listing()]
    api_file = api_dir / 'jobs.csv'
    with api_file.open('w', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


@with_db
def build_podcast_xml(api_dir, config):
    # TODO Category('Business'), Category('Education')
    # https://gitlab.com/caproni-podcast-publishing/pod2gen/-/issues/26

    person_hj = Person('Honza Javorek', 'honza@junior.guru')
    podcast = Podcast(name='Junior Guru podcast',
                      description='Jsme tu pro všechny juniory v IT! Jak začít s programováním? Jak najít práci v IT? Přinášíme odpovědi, inspiraci, motivaci.',
                      language='cs',
                      category=Category('Technology'),
                      website='https://junior.guru/podcast/',
                      feed_url='https://junior.guru/api/podcast.xml',
                      authors=[Person('Pája Froňková'), person_hj],
                      owner=person_hj,
                      web_master=person_hj,
                      copyright=f'© {PodcastEpisode.copyright_year()} Pavlína Froňková, Jan Javorek',
                      generator='JuniorGuruBot (+https://junior.guru)',
                      image='https://junior.guru/static/images/podcast-v1.png',
                      fundings=[Funding('Přidej se do klubu junior.guru', 'https://junior.guru/club/'),
                                Funding('Přispěj junior.guru', 'https://junior.guru/donate/')],
                      explicit=False)

    for number, db_episode in enumerate(PodcastEpisode.api_listing(), start=1):
        episode = Episode(id=db_episode.global_id,
                          episode_number=number,
                          episode_name=f'#{db_episode.number}',
                          title=db_episode.title_numbered,
                          publication_date=db_episode.publish_at_prg,
                          link=db_episode.url,
                          summary=md(db_episode.description),
                          media=Media(db_episode.media_url,
                                      size=db_episode.media_size,
                                      type=db_episode.media_type,
                                      duration=timedelta(seconds=db_episode.media_duration_s)))
        podcast.add_episode(episode)

    podcast.rss_file(str(api_dir / 'podcast.xml'))
