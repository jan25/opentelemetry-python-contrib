# Copyright 2020, OpenTelemetry Authors
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
import asyncio
import os

import aiopg
import psycopg2
import pytest

from opentelemetry import trace as trace_api
from opentelemetry.instrumentation.aiopg import AiopgInstrumentor
from opentelemetry.test.test_base import TestBase

POSTGRES_HOST = os.getenv("POSTGRESQL_HOST", "127.0.0.1")
POSTGRES_PORT = int(os.getenv("POSTGRESQL_PORT", "5432"))
POSTGRES_DB_NAME = os.getenv("POSTGRESQL_DB_NAME", "opentelemetry-tests")
POSTGRES_PASSWORD = os.getenv("POSTGRESQL_PASSWORD", "testpassword")
POSTGRES_USER = os.getenv("POSTGRESQL_USER", "testuser")


def async_call(coro):
    loop = asyncio.get_event_loop()
    return loop.run_until_complete(coro)


class TestFunctionalAiopgConnect(TestBase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._connection = None
        cls._cursor = None
        cls._tracer = cls.tracer_provider.get_tracer(__name__)
        AiopgInstrumentor().instrument(tracer_provider=cls.tracer_provider)
        cls._connection = async_call(
            aiopg.connect(
                dbname=POSTGRES_DB_NAME,
                user=POSTGRES_USER,
                password=POSTGRES_PASSWORD,
                host=POSTGRES_HOST,
                port=POSTGRES_PORT,
            )
        )
        cls._cursor = async_call(cls._connection.cursor())

    @classmethod
    def tearDownClass(cls):
        if cls._cursor:
            cls._cursor.close()
        if cls._connection:
            cls._connection.close()
        AiopgInstrumentor().uninstrument()

    def validate_spans(self, span_name):
        spans = self.memory_exporter.get_finished_spans()
        self.assertEqual(len(spans), 2)
        for span in spans:
            if span.name == "rootSpan":
                root_span = span
            else:
                child_span = span
            self.assertIsInstance(span.start_time, int)
            self.assertIsInstance(span.end_time, int)
        self.assertIsNotNone(root_span)
        self.assertIsNotNone(child_span)
        self.assertEqual(root_span.name, "rootSpan")
        self.assertEqual(child_span.name, span_name)
        self.assertIsNotNone(child_span.parent)
        self.assertIs(child_span.parent, root_span.get_span_context())
        self.assertIs(child_span.kind, trace_api.SpanKind.CLIENT)
        self.assertEqual(child_span.attributes["db.system"], "postgresql")
        self.assertEqual(child_span.attributes["db.name"], POSTGRES_DB_NAME)
        self.assertEqual(child_span.attributes["db.user"], POSTGRES_USER)
        self.assertEqual(child_span.attributes["net.peer.name"], POSTGRES_HOST)
        self.assertEqual(child_span.attributes["net.peer.port"], POSTGRES_PORT)

    def test_execute(self):
        """Should create a child span for execute method"""
        stmt = "CREATE TABLE IF NOT EXISTS test (id integer)"
        with self._tracer.start_as_current_span("rootSpan"):
            async_call(self._cursor.execute(stmt))
        self.validate_spans("CREATE")

    def test_executemany(self):
        """Should create a child span for executemany"""
        stmt = "INSERT INTO test (id) VALUES (%s)"
        with pytest.raises(psycopg2.ProgrammingError):
            with self._tracer.start_as_current_span("rootSpan"):
                data = (("1",), ("2",), ("3",))
                async_call(self._cursor.executemany(stmt, data))
            self.validate_spans("INSERT")

    def test_callproc(self):
        """Should create a child span for callproc"""
        with self._tracer.start_as_current_span("rootSpan"), self.assertRaises(
            Exception
        ):
            async_call(self._cursor.callproc("test", ()))
            self.validate_spans("test")


class TestFunctionalAiopgCreatePool(TestBase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._connection = None
        cls._cursor = None
        cls._tracer = cls.tracer_provider.get_tracer(__name__)
        AiopgInstrumentor().instrument(tracer_provider=cls.tracer_provider)
        cls._dsn = (
            f"dbname='{POSTGRES_DB_NAME}' user='{POSTGRES_USER}' password='{POSTGRES_PASSWORD}'"
            f" host='{POSTGRES_HOST}' port='{POSTGRES_PORT}'"
        )
        cls._pool = async_call(
            aiopg.create_pool(
                dbname=POSTGRES_DB_NAME,
                user=POSTGRES_USER,
                password=POSTGRES_PASSWORD,
                host=POSTGRES_HOST,
                port=POSTGRES_PORT,
            )
        )
        cls._connection = async_call(cls._pool.acquire())
        cls._cursor = async_call(cls._connection.cursor())

    @classmethod
    def tearDownClass(cls):
        if cls._cursor:
            cls._cursor.close()
        if cls._connection:
            cls._connection.close()
        if cls._pool:
            cls._pool.close()
        AiopgInstrumentor().uninstrument()

    def validate_spans(self, span_name):
        spans = self.memory_exporter.get_finished_spans()
        self.assertEqual(len(spans), 2)
        for span in spans:
            if span.name == "rootSpan":
                root_span = span
            else:
                child_span = span
            self.assertIsInstance(span.start_time, int)
            self.assertIsInstance(span.end_time, int)
        self.assertIsNotNone(root_span)
        self.assertIsNotNone(child_span)
        self.assertEqual(root_span.name, "rootSpan")
        self.assertEqual(child_span.name, span_name)
        self.assertIsNotNone(child_span.parent)
        self.assertIs(child_span.parent, root_span.get_span_context())
        self.assertIs(child_span.kind, trace_api.SpanKind.CLIENT)
        self.assertEqual(child_span.attributes["db.system"], "postgresql")
        self.assertEqual(child_span.attributes["db.name"], POSTGRES_DB_NAME)
        self.assertEqual(child_span.attributes["db.user"], POSTGRES_USER)
        self.assertEqual(child_span.attributes["net.peer.name"], POSTGRES_HOST)
        self.assertEqual(child_span.attributes["net.peer.port"], POSTGRES_PORT)

    def test_execute(self):
        """Should create a child span for execute method"""
        stmt = "CREATE TABLE IF NOT EXISTS test (id integer)"
        with self._tracer.start_as_current_span("rootSpan"):
            async_call(self._cursor.execute(stmt))
        self.validate_spans("CREATE")

    def test_executemany(self):
        """Should create a child span for executemany"""
        stmt = "INSERT INTO test (id) VALUES (%s)"
        with pytest.raises(psycopg2.ProgrammingError):
            with self._tracer.start_as_current_span("rootSpan"):
                data = (("1",), ("2",), ("3",))
                async_call(self._cursor.executemany(stmt, data))
            self.validate_spans("INSERT")

    def test_callproc(self):
        """Should create a child span for callproc"""
        with self._tracer.start_as_current_span("rootSpan"), self.assertRaises(
            Exception
        ):
            async_call(self._cursor.callproc("test", ()))
            self.validate_spans("test")

    def test_instrumented_pool_with_multiple_acquires(self, *_, **__):
        async def double_acquire():
            pool = await aiopg.create_pool(dsn=self._dsn)
            async with pool.acquire() as conn:
                async with conn.cursor() as cursor:
                    query = "SELECT 1"
                    await cursor.execute(query)
            async with pool.acquire() as conn:
                async with conn.cursor() as cursor:
                    query = "SELECT 1"
                    await cursor.execute(query)

        async_call(double_acquire())
        spans = self.memory_exporter.get_finished_spans()
        self.assertEqual(len(spans), 2)
