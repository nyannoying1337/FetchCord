import unittest
from unittest import mock

from pypresence import exceptions

from fetch_cord.config import CycleConfig
from fetch_cord.ids import IdTable
from fetch_cord.presence import PresenceRunner

from .test_info import sample


class FakePresence:
    """Stands in for pypresence.Presence, recording what it was asked to do."""

    instances = []

    def __init__(self, client_id):
        self.client_id = client_id
        self.connected = False
        self.updates = []
        self.closed = False
        self.connect_error = None
        self.update_error = None
        FakePresence.instances.append(self)

    def connect(self):
        if self.connect_error:
            raise self.connect_error
        self.connected = True

    def update(self, **kwargs):
        if self.update_error:
            error, self.update_error = self.update_error, None
            raise error
        self.updates.append(kwargs)

    def close(self):
        self.closed = True
        self.connected = False


def runner(**kwargs):
    cycles = [
        CycleConfig("os", True, "kernel", "memory", True, 30),
        CycleConfig("hardware", True, "cpu", "gpu", True, 30),
    ]

    return PresenceRunner(sample(), IdTable(), cycles, **kwargs)


class PresenceTestCase(unittest.TestCase):
    def setUp(self):
        FakePresence.instances = []
        patcher = mock.patch("fetch_cord.presence.Presence", FakePresence)
        patcher.start()
        self.addCleanup(patcher.stop)

        sleep = mock.patch.object(PresenceRunner, "_sleep")
        self.sleep = sleep.start()
        self.addCleanup(sleep.stop)


class TestConnection(PresenceTestCase):
    def test_connect_opens_the_requested_application(self):
        run = runner()

        self.assertTrue(run.connect("123"))
        self.assertEqual(FakePresence.instances[-1].client_id, "123")
        self.assertTrue(FakePresence.instances[-1].connected)

    def test_reconnecting_to_the_same_application_is_a_no_op(self):
        run = runner()
        run.connect("123")
        run.connect("123")

        self.assertEqual(len(FakePresence.instances), 1)

    def test_switching_application_closes_the_old_one(self):
        run = runner()
        run.connect("123")
        first = FakePresence.instances[-1]
        run.connect("456")

        self.assertTrue(first.closed)
        self.assertEqual(len(FakePresence.instances), 2)
        self.assertEqual(FakePresence.instances[-1].client_id, "456")

    def test_waits_and_retries_while_discord_is_closed(self):
        """Discord not running is a wait, not a crash."""
        attempts = []
        original = FakePresence.__init__

        def flaky(self, client_id):
            original(self, client_id)
            attempts.append(client_id)
            if len(attempts) < 3:
                self.connect_error = exceptions.DiscordNotFound()

        with mock.patch.object(FakePresence, "__init__", flaky):
            run = runner()
            self.assertTrue(run.connect("123"))

        self.assertEqual(len(attempts), 3)
        self.assertTrue(self.sleep.called)

    def test_invalid_application_id_is_reported_not_retried(self):
        def bad(self, client_id):
            FakePresence.instances.append(self)
            self.client_id = client_id
            self.connect_error = exceptions.InvalidID()

        with mock.patch.object(FakePresence, "__init__", bad):
            run = runner()
            self.assertFalse(run.connect("nope"))

    def test_disconnect_survives_a_dead_pipe(self):
        run = runner()
        run.connect("123")
        FakePresence.instances[-1].close = mock.Mock(side_effect=OSError("pipe gone"))
        run.disconnect()

        self.assertIsNone(run._rpc)


class TestShow(PresenceTestCase):
    def payload(self, run):
        from fetch_cord.cycles import build_payload

        return build_payload(run.cycles[0], run.info, run.ids)

    def test_show_sends_the_payload(self):
        run = runner()
        payload = self.payload(run)

        self.assertTrue(run.show(payload))
        self.assertEqual(FakePresence.instances[-1].updates[0]["details"], "10.0.26100.4652")

    def test_show_reconnects_once_after_a_broken_pipe(self):
        run = runner()
        payload = self.payload(run)
        run.connect(payload.client_id)
        FakePresence.instances[-1].update_error = exceptions.PipeClosed()

        self.assertTrue(run.show(payload))
        self.assertEqual(len(FakePresence.instances), 2)
        self.assertTrue(FakePresence.instances[-1].updates)


class TestRunLoop(PresenceTestCase):
    def test_rotates_cycles_and_stops_cleanly_on_ctrl_c(self):
        run = runner()
        self.sleep.side_effect = [None, None, KeyboardInterrupt()]

        self.assertEqual(run.run(), 0)

        client_ids = [instance.client_id for instance in FakePresence.instances]
        self.assertEqual(client_ids[0], run.ids.os_id("windows11"))
        self.assertEqual(client_ids[1], run.ids.cpu_id("amd", "ryzen 7"))
        self.assertTrue(all(instance.closed for instance in FakePresence.instances))

    def test_refreshes_volatile_info_on_the_poll_rate(self):
        run = runner(poll_rate=2)
        run.info.refresh = mock.Mock()
        self.sleep.side_effect = [None, None, None, KeyboardInterrupt()]
        run.run()

        self.assertEqual(run.info.refresh.call_count, 1)

    def test_no_payloads_is_an_error(self):
        run = runner()
        run.cycles = []

        self.assertEqual(run.run(), 1)

    def test_time_override_replaces_the_configured_time(self):
        run = runner(time_override=99)
        self.sleep.side_effect = [None, KeyboardInterrupt()]
        run.run()

        self.assertEqual(self.sleep.call_args_list[0][0][0], 99)


if __name__ == "__main__":
    unittest.main()
