#  Drakkar-Software OctoBot-Commons
#  Copyright (c) Drakkar-Software, All rights reserved.
#
#  This library is free software; you can redistribute it and/or
#  modify it under the terms of the GNU Lesser General Public
#  License as published by the Free Software Foundation; either
#  version 3.0 of the License, or (at your option) any later version.
#
#  This library is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
#  Lesser General Public License for more details.
#
#  You should have received a copy of the GNU Lesser General Public
#  License along with this library.
import contextlib
import asyncio

import octobot_commons.databases.implementations as implementations
import octobot_commons.enums as enums


class MetaDatabase:
    def __init__(self, run_dbs_identifier, with_lock=False, cache_size=None):
        self.run_dbs_identifier = run_dbs_identifier
        self.with_lock = with_lock
        self.cache_size = cache_size
        self.database_adaptor = self.run_dbs_identifier.database_adaptor
        self.run_db: implementations.DBWriterReader = None
        self.orders_db: implementations.DBWriterReader = None
        self.trades_db: implementations.DBWriterReader = None
        self.transactions_db: implementations.DBWriterReader = None
        self.backtesting_metadata_db: implementations.DBWriterReader = None
        self.symbol_dbs: dict = {}

    def get_run_db(self):
        if self.run_db is None:
            self.run_db = self._get_db(self.run_dbs_identifier.get_run_data_db_identifier())
        return self.run_db

    def get_orders_db(self, exchange=None):
        if self.orders_db is None:
            self.orders_db = self._get_db(self.run_dbs_identifier.get_orders_db_identifier(
                exchange or self.run_dbs_identifier.context.exchange_name
            ))
        return self.orders_db

    def get_trades_db(self, exchange=None):
        if self.trades_db is None:
            self.trades_db = self._get_db(self.run_dbs_identifier.get_trades_db_identifier(
                exchange or self.run_dbs_identifier.context.exchange_name
            ))
        return self.trades_db

    def get_transactions_db(self, exchange=None):
        if self.transactions_db is None:
            self.transactions_db = self._get_db(self.run_dbs_identifier.get_transactions_db_identifier(
                exchange or self.run_dbs_identifier.context.exchange_name
            ))
        return self.transactions_db

    def get_backtesting_metadata_db(self):
        if self.backtesting_metadata_db is None:
            self.backtesting_metadata_db = self._get_db(self.run_dbs_identifier.get_backtesting_metadata_identifier())
        return self.backtesting_metadata_db

    async def get_backtesting_metadata_from_run(self):
        db = self.get_backtesting_metadata_db()
        return (await db.select(
            enums.CacheDatabaseTables.METADATA.value,
            (await db.search()).id == self.run_dbs_identifier.backtesting_id
        ))[0]

    def get_symbol_db(self, exchange, symbol):
        key = self._get_symbol_db_key(exchange, symbol)
        if key not in self.symbol_dbs:
            self.symbol_dbs[key] = self._get_db(self.run_dbs_identifier.get_symbol_db_identifier(exchange, symbol))
        return self.symbol_dbs[key]

    def all_basic_run_db(self, exchange=None):
        yield self.get_run_db()
        yield self.get_orders_db(exchange)
        yield self.get_trades_db(exchange)
        yield self.get_transactions_db(exchange)

    def _get_symbol_db_key(self, exchange, symbol):
        return f"{exchange}{symbol}"

    def _get_db(self, db_identifier):
        return implementations.DBWriterReader(db_identifier, with_lock=self.with_lock, cache_size=self.cache_size,
                                              database_adaptor=self.database_adaptor)

    async def close(self):
        await asyncio.gather(
            *(
                db.close()
                for db in (self.run_db, self.orders_db, self.trades_db, self.transactions_db,
                           self.backtesting_metadata_db, *self.symbol_dbs.values())
                if db is not None
            )
        )

    @classmethod
    @contextlib.asynccontextmanager
    async def database(cls, database_manager, with_lock=False, cache_size=None):
        meta_db = None
        try:
            meta_db = MetaDatabase(database_manager, with_lock=with_lock, cache_size=cache_size)
            yield meta_db
        finally:
            if meta_db is not None:
                await meta_db.close()