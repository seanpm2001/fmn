# SPDX-FileCopyrightText: Contributors to the Fedora Project
#
# SPDX-License-Identifier: MIT

import asyncio
import os
from datetime import datetime
from functools import partial

import collectd
from cashews import cache
from sqlalchemy import func, select

from fmn.cache import configure_cache
from fmn.database import async_session_maker, init_model
from fmn.database.model import Rule, User

CONFIG = {
    "Interval": "3600",
    "Hostname": None,
}


class Collector:
    def __init__(self, config):
        self.config = config
        self._loop = None

    def setup(self):
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        configure_cache()
        self._loop.run_until_complete(init_model())

    def shutdown(self):
        self._loop.run_until_complete(cache.close())
        # Now shutdown the asyncio loop. Use a Runner when Python 3.11 is more widespread
        to_cancel = asyncio.all_tasks(self._loop)
        for task in to_cancel:
            task.cancel()
        self._loop.run_until_complete(asyncio.gather(*to_cancel, return_exceptions=True))
        self._loop.run_until_complete(self._loop.shutdown_asyncgens())
        self._loop.run_until_complete(self._loop.shutdown_default_executor())
        asyncio.set_event_loop(None)
        self._loop.close()

    def collect(self):
        self._loop.run_until_complete(self._collect())

    async def _collect(self):
        await self._collect_cache()
        await self._collect_users()

    async def _collect_cache(self):
        now = datetime.now().timestamp()
        async for key in cache.scan("duration:*"):
            _, name, when = key.split(":", 2)
            duration = await cache.get(key)
            if duration is None:
                collectd.debug(f"Not dispatching {name} at {when}: value is None")
                continue
            when = datetime.fromisoformat(when).timestamp()
            if now - when > int(self.config["Interval"]) * 24:
                collectd.debug(f"Not dispatching {name} at {when}: too old")
                continue
            collectd.debug(f"Dispatching {name} at {when}: {duration!r}")
            await self._loop.run_in_executor(
                None,
                partial(
                    self._dispatch,
                    duration,
                    name,
                    data_type="fmn_cache",
                    timestamp=when,
                    category="cache",
                ),
            )

    async def _collect_users(self):
        async with async_session_maker.begin() as db:
            result = await db.execute(
                select(func.count(User.id)).where(
                    # Disable E712 until this is fixed: https://github.com/charliermarsh/ruff/issues/4560
                    User.rules.any(Rule.disabled == False)  # noqa: E712
                )
            )
            count = result.scalar()
            collectd.debug(f"Dispatching users count: {count}")
            await self._loop.run_in_executor(
                None,
                partial(
                    self._dispatch,
                    count,
                    "active_users",
                    data_type="fmn_users",
                    category="users",
                ),
            )

    def _dispatch(self, value, name, data_type, timestamp=None, subname=None, category=None):
        vl = collectd.Values()
        vl.type = data_type
        vl.plugin = category or name
        if timestamp is not None:
            vl.time = timestamp
        hostname = self.config.get("Hostname")
        if hostname is not None:
            vl.host = hostname
        vl.interval = int(self.config["Interval"])
        type_instance = name
        if subname is not None:
            type_instance = f"{type_instance}-{subname}"
        vl.type_instance = type_instance
        if not hasattr(value, "__iter__"):
            value = [value]
        vl.dispatch(values=value)


def configure(plugin_config):
    config = CONFIG.copy()
    for conf_entry in plugin_config.children:
        collectd.debug(f"{conf_entry.key} = {conf_entry.values}")
        try:
            if conf_entry.key == "SetEnv":
                envvar, value = conf_entry.values
                os.environ[envvar] = value
            else:
                if len(conf_entry.values) != 1:
                    raise ValueError
                config[conf_entry.key] = conf_entry.values[0]
        except ValueError:
            collectd.warning(
                f"Invalid configuration value for {conf_entry.key}: {conf_entry.values!r}"
            )
            continue

    collector = Collector(config=config)
    collectd.register_init(collector.setup)
    collectd.register_shutdown(collector.shutdown)
    collectd.register_read(collector.collect, int(config["Interval"]))


collectd.register_config(configure)
