import unittest
from unittest.mock import patch, mock_open, MagicMock
import socket
import latency
from latency import validate_ip, validate_port, parse_address, measure_latency, save_results, ValidationError

class TestLatency(unittest.TestCase):

    def test_validate_ip(self):
        # Valid IPs
        self.assertTrue(validate_ip("192.168.1.1"))
        self.assertTrue(validate_ip("1.1.1.1"))
        self.assertTrue(validate_ip("0.0.0.0"))
        self.assertTrue(validate_ip("255.255.255.255"))

        # Invalid IPs
        self.assertFalse(validate_ip("256.0.0.0"))
        self.assertFalse(validate_ip("-1.0.0.0"))
        self.assertFalse(validate_ip("1.1.1"))
        self.assertFalse(validate_ip("1.1.1.1.1"))
        self.assertFalse(validate_ip("abc.def.ghi.jkl"))
        self.assertFalse(validate_ip("192.168.1.a"))

    def test_validate_port(self):
        # Valid ports
        self.assertTrue(validate_port(80))
        self.assertTrue(validate_port(443))
        self.assertTrue(validate_port(65535))
        self.assertTrue(validate_port(1))

        # Invalid ports
        self.assertFalse(validate_port(0))
        self.assertFalse(validate_port(65536))
        self.assertFalse(validate_port(-1))

    def test_parse_address(self):
        # Valid address
        ip, port, info = parse_address("1.1.1.1, 443, US, Cloudflare")
        self.assertEqual(ip, "1.1.1.1")
        self.assertEqual(port, 443)
        self.assertEqual(info, ["US", "Cloudflare"])

        # Valid address minimal
        ip, port, info = parse_address("8.8.8.8, 53")
        self.assertEqual(ip, "8.8.8.8")
        self.assertEqual(port, 53)
        self.assertEqual(info, [])

        # Invalid format
        with self.assertRaises(ValidationError):
            parse_address("invalid")

        # Invalid IP
        with self.assertRaises(ValidationError):
            parse_address("999.999.999.999, 80")

        # Invalid Port (not int)
        with self.assertRaises(ValidationError):
            parse_address("1.1.1.1, abc")

        # Invalid Port (out of range)
        with self.assertRaises(ValidationError):
            parse_address("1.1.1.1, 70000")

    @patch('socket.create_connection')
    @patch('time.perf_counter')
    def test_measure_latency_success(self, mock_perf_counter, mock_create_connection):
        mock_perf_counter.side_effect = [100.0, 100.05] # 50ms latency
        mock_sock = MagicMock()
        mock_create_connection.return_value.__enter__.return_value = mock_sock

        parsed_addr = ('1.1.1.1', 443, '1.1.1.1,443,US,CF')
        original_addr, latency_ms, error = measure_latency(parsed_addr)

        self.assertEqual(original_addr, '1.1.1.1,443,US,CF')
        self.assertAlmostEqual(latency_ms, 50.0)
        self.assertIsNone(error)
        mock_create_connection.assert_called_with(('1.1.1.1', 443), timeout=5.0)

    @patch('socket.create_connection')
    def test_measure_latency_timeout(self, mock_create_connection):
        mock_create_connection.side_effect = socket.timeout

        parsed_addr = ('1.1.1.1', 443, '1.1.1.1,443,US,CF')
        original_addr, latency_ms, error = measure_latency(parsed_addr)

        self.assertEqual(original_addr, '1.1.1.1,443,US,CF')
        self.assertEqual(latency_ms, float('inf'))
        self.assertEqual(error, "Connection timeout")

    @patch('socket.create_connection')
    def test_measure_latency_refused(self, mock_create_connection):
        mock_create_connection.side_effect = ConnectionRefusedError

        parsed_addr = ('1.1.1.1', 443, '1.1.1.1,443,US,CF')
        original_addr, latency_ms, error = measure_latency(parsed_addr)

        self.assertEqual(original_addr, '1.1.1.1,443,US,CF')
        self.assertEqual(latency_ms, float('inf'))
        self.assertEqual(error, "Connection refused")

    @patch('socket.create_connection')
    def test_measure_latency_oserror(self, mock_create_connection):
        mock_create_connection.side_effect = OSError("Some network error")

        parsed_addr = ('1.1.1.1', 443, '1.1.1.1,443,US,CF')
        original_addr, latency_ms, error = measure_latency(parsed_addr)

        self.assertEqual(original_addr, '1.1.1.1,443,US,CF')
        self.assertEqual(latency_ms, float('inf'))
        self.assertTrue(error.startswith("Network error:"))

    @patch('builtins.open', new_callable=mock_open)
    def test_save_results(self, mock_file):
        results = {
            '1.1.1.1,443,US,CF': [10.0, 20.0, 15.0],
            '8.8.8.8,53,US,Google': [float('inf'), float('inf'), float('inf')],
            '9.9.9.9,999,Quad9': [5.0, float('inf'), 6.0]
        }

        save_results(results, "output.txt")

        mock_file.assert_called_with("output.txt", 'w')
        handle = mock_file()

        # Expected calls:
        # 1. 9.9.9.9 should have max latency of 6.0 ms (fastest successful)
        # 2. 1.1.1.1 should have max latency of 20.0 ms
        # 3. 8.8.8.8 should be failed

        # The code sorts by latency.
        # 9.9.9.9: max(5.0, 6.0) = 6.0
        # 1.1.1.1: max(10.0, 20.0, 15.0) = 20.0
        # 8.8.8.8: inf

        expected_calls = [
            unittest.mock.call("9.9.9.9:999#Quad9 6.00 ms\n"),
            unittest.mock.call("1.1.1.1:443#US CF 20.00 ms\n"),
            unittest.mock.call("8.8.8.8:53#US Google Failed\n")
        ]

        handle.write.assert_has_calls(expected_calls, any_order=False)

if __name__ == '__main__':
    unittest.main()
