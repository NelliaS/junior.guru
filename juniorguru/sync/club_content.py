import asyncio

import arrow

from juniorguru.lib.timer import measure
from juniorguru.lib import loggers
from juniorguru.lib.club import EMOJI_PINS, discord_task, count_upvotes, count_downvotes, emoji_name, get_roles, count_pins
from juniorguru.models import ClubMessage, ClubUser, ClubPinReaction, db, with_db


logger = loggers.get('club_content')


WORKERS_COUNT = 5


@measure('club_content')
@with_db
@discord_task
async def main(client):
    db.drop_tables([ClubMessage, ClubUser, ClubPinReaction])
    db.create_tables([ClubMessage, ClubUser, ClubPinReaction])

    channels = (channel for channel in client.juniorguru_guild.text_channels
                if channel.permissions_for(client.juniorguru_guild.me).read_messages)
    authors = await process_channels(channels)

    users_logger = loggers.get('club_content.users')
    users_logger.info('Looking for members without a single message')
    remaining_members = [member async for member
                         in client.juniorguru_guild.fetch_members(limit=None)
                         if member.id not in authors]

    users_logger.info(f'There are {len(remaining_members)} remaining members')
    for member in remaining_members:
        users_logger.debug(f"Member '{member.display_name}' #{member.id}")
        ClubUser.create(id=member.id,
                        is_bot=member.bot,
                        is_member=True,
                        display_name=member.display_name,
                        mention=member.mention,
                        joined_at=arrow.get(member.joined_at).naive,
                        roles=get_roles(member))

    logger.info(f'Created {ClubMessage.count()} messages from {len(authors)} authors, '
                f'{ClubUser.members_count()} users, '
                f'{ClubPinReaction.count()} pins')


async def process_channels(channels):
    authors = {}

    queue = asyncio.Queue()
    for channel in channels:
        queue.put_nowait(channel)

    workers = [asyncio.create_task(channel_worker(worker_no, authors, queue))
               for worker_no in range(WORKERS_COUNT)]

    # trick to prevent hangs if workers raise, see https://stackoverflow.com/a/60710981/325365
    queue_completed = asyncio.create_task(queue.join())
    await asyncio.wait([queue_completed, *workers], return_when=asyncio.FIRST_COMPLETED)

    # if there's a worker which raised
    if not queue_completed.done():
        workers_done = [worker for worker in workers if worker.done()]
        logger.warning(f'Some workers ({len(workers_done)} of {WORKERS_COUNT}) finished before the queue is done!')
        workers_done[0].result()  # raises

    # cancel workers which are still runnning
    for worker in workers:
        worker.cancel()

    # return_exceptions=True silently collects CancelledError() exceptions
    await asyncio.gather(*workers, return_exceptions=True)

    return authors


async def channel_worker(worker_no, authors, queue):
    while True:
        channel = await queue.get()

        worker_logger = loggers.get(f'club_content.channel_workers.{worker_no}')
        worker_logger.info(f"Reading channel #{channel.id}")
        worker_logger.debug(f"Channel #{channel.id} is named '{channel.name}'")

        messages_count = 0
        users_count = 0
        pins_count = 0

        async for message in channel.history(limit=None, after=None):
            if message.flags.has_thread:
                worker_logger.debug(f'Thread {message.jump_url}')
                thread = await message.guild.fetch_channel(message.id)
                worker_logger.debug(f"Thread identified as #{thread.id}, named '{thread.name}'")
                queue.put_nowait(thread)

            if message.author.id not in authors:
                authors[message.author.id] = create_user(message.author)
                users_count += 1

            ClubMessage.create(id=message.id,
                               url=message.jump_url,
                               content=message.content,
                               upvotes_count=count_upvotes(message.reactions),
                               downvotes_count=count_downvotes(message.reactions),
                               pin_reactions_count=count_pins(message.reactions),
                               created_at=arrow.get(message.created_at).naive,
                               edited_at=(arrow.get(message.edited_at).naive if message.edited_at else None),
                               author=authors[message.author.id],
                               channel_id=channel.id,
                               channel_name=channel.name,
                               channel_mention=channel.mention,
                               type=message.type.name)
            messages_count += 1

            for reacting_user in (await get_reacting_users(message.reactions)):
                if reacting_user.id not in authors:
                    authors[reacting_user.id] = create_user(reacting_user)
                    users_count += 1

                create_reaction(reacting_user, message)
                pins_count += 1

        worker_logger.info(f"Channel #{channel.id} added {messages_count} messages, {users_count} users, {pins_count} pins")
        queue.task_done()


async def get_reacting_users(reactions):
    users = set()
    for reaction in reactions:
        if emoji_name(reaction.emoji) in EMOJI_PINS:
            for user in [user async for user in reaction.users()]:
                users.add(user)
    return users


def create_user(user):
    users_logger = loggers.get('club_content.users')
    users_logger.debug(f"User '{user.display_name}' #{user.id}")

    # The message.author can be an instance of Member, but it can also be an instance of User,
    # if the author isn't a member of the Discord guild/server anymore. User instances don't
    # have certain properties, hence the getattr() calls below.
    return ClubUser.create(id=user.id,
                           is_bot=user.bot,
                           is_member=bool(getattr(user, 'joined_at', False)),
                           display_name=user.display_name,
                           mention=user.mention,
                           joined_at=(arrow.get(user.joined_at).naive if hasattr(user, 'joined_at') else None),
                           roles=get_roles(user))


def create_reaction(user, message):
    pins_logger = loggers.get('club_content.pins')
    pins_logger.debug(f"Message {message.jump_url} is pinned by user '{user.display_name}' #{user.id}")
    return ClubPinReaction.create(user=user.id, message=message.id)


if __name__ == '__main__':
    main()
