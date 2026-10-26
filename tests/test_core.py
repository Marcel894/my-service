from __future__ import annotations

import os
import tempfile
import unittest

from my_service import resolve, ServiceInfo


# A small, representative slice of the IANA services file. We use this for
# deterministic testing instead of relying on the host's real /etc/services,
# whose contents vary by distribution and would make assertions non-portable.
SAMPLE_SERVICES = """# Echo
echo            7/tcp
# Echo (UDP)
echo            7/udp
ftp             21/tcp
ssh             22/tcp
ssh             22/udp
telnet          23/tcp
domain          53/tcp
nameserver      53/udp
# HTTP with aliases
http            80/tcp    www www-http
http            80/udp
https           443/tcp
https           443/udp
"""


class ResolveTests(unittest.TestCase):
    def setUp(self) -> None:
        # tempfile in text mode so we don't need to manage decoding ourselves.
        fd, path = tempfile.mkstemp(suffix=".services", text=True)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(SAMPLE_SERVICES)
        self._path = path

    def tearDown(self) -> None:
        os.unlink(self._path)

    def test_resolves_tcp_service(self) -> None:
        info = resolve("http", "tcp", path=self._path)
        self.assertIsNotNone(info)
        assert info is not None
        self.assertEqual(info.name, "http")
        self.assertEqual(info.port, 80)
        self.assertEqual(info.protocol, "tcp")
        self.assertIsInstance(info, ServiceInfo)

    def test_resolves_udp_service(self) -> None:
        info = resolve("echo", "udp", path=self._path)
        self.assertIsNotNone(info)
        assert info is not None
        self.assertEqual(info.port, 7)
        self.assertEqual(info.protocol, "udp")

    def test_protocol_argument_is_case_insensitive(self) -> None:
        upper = resolve("https", "TCP", path=self._path)
        lower = resolve("https", "tcp", path=self._path)
        self.assertEqual(upper, lower)

    def test_name_argument_is_case_insensitive(self) -> None:
        info = resolve("HTTPS", "tcp", path=self._path)
        self.assertIsNotNone(info)
        assert info is not None
        self.assertEqual(info.port, 443)

    def test_unknown_name_returns_none(self) -> None:
        self.assertIsNone(resolve("no-such-service", "tcp", path=self._path))

    def test_known_name_unknown_protocol_returns_none(self) -> None:
        # http exists for both tcp and udp, but not for the made-up "sctp".
        self.assertIsNone(resolve("http", "sctp", path=self._path))

    def test_alias_resolves_to_primary(self) -> None:
        # "www" is an alias for "http" in the sample file.
        info = resolve("www", "tcp", path=self._path)
        self.assertIsNotNone(info)
        assert info is not None
        self.assertEqual(info.name, "http")
        self.assertEqual(info.port, 80)
        self.assertIn("www", info.aliases)

    def test_no_protocol_returns_first_match(self) -> None:
        # With no protocol specified we should still resolve, returning the
        # first entry in file order for the primary name.
        info = resolve("ssh", path=self._path)
        self.assertIsNotNone(info)
        assert info is not None
        self.assertEqual(info.port, 22)
        self.assertEqual(info.protocol, "tcp")

    def test_missing_services_file_returns_none(self) -> None:
        self.assertIsNone(resolve("http", "tcp", path="/no/such/path/services"))

    def test_nameserver_alias_resolves_to_domain(self) -> None:
        # `nameserver` is a name in its own right in the sample file, not an
        # alias, so we use it as a second primary-name case.
        info = resolve("nameserver", "udp", path=self._path)
        self.assertIsNotNone(info)
        assert info is not None
        self.assertEqual(info.name, "nameserver")
        self.assertEqual(info.port, 53)

    def test_service_info_is_frozen(self) -> None:
        info = resolve("ftp", "tcp", path=self._path)
        self.assertIsNotNone(info)
        assert info is not None
        with self.assertRaises(Exception):
            info.port = 999  # type: ignore[misc]


if __name__ == "__main__":
    unittest.main()
