import os
import tempfile
import io
import unittest
from unittest.mock import MagicMock, patch
import logging
import mailing


class TestMailing(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.test_dir.cleanup)
        self.mailings_file = os.path.join(self.test_dir.name, "Mailings")
        self.spool_file = os.path.join(self.test_dir.name, "spool")

    def test_load_and_save_mailings(self):
        # Empty when file does not exist
        self.assertEqual(mailing.load_mailings(self.mailings_file), [])

        # Save and reload
        addresses = ["alice@example.com", "bob@example.com"]
        mailing.save_mailings(addresses, self.mailings_file)
        loaded = mailing.load_mailings(self.mailings_file)
        self.assertEqual(loaded, addresses)

    def test_parse_mbox_stream_valid(self):
        mbox_content = (
            "From alice@example.com Mon Oct 26 12:00:00 2026\n"
            "From: Alice <alice@example.com>\n"
            "Subject: Test Message\n"
            "Date: Mon, 26 Oct 2026 12:00:00 +0000\n"
            "\n"
            "Hello World!\n"
            "This is a test message.\n"
        )
        stream = io.StringIO(mbox_content)
        valid, msgs = mailing.parse_mbox_stream(stream)
        self.assertTrue(valid)
        self.assertEqual(len(msgs), 1)

        msg = msgs[0]
        self.assertEqual(msg['from_env'], "alice@example.com")
        self.assertEqual(msg['headers']['from'], "Alice <alice@example.com>")
        self.assertEqual(msg['headers']['subject'], "Test Message")
        self.assertEqual(msg['headers']['date'], "Mon, 26 Oct 2026 12:00:00 +0000")
        self.assertEqual(msg['body_lines'], ["Hello World!\n", "This is a test message.\n"])

    def test_parse_mbox_stream_invalid(self):
        invalid_content = "Subject: Not starting with From\n\nSome body"
        stream = io.StringIO(invalid_content)
        valid, msgs = mailing.parse_mbox_stream(stream)
        self.assertFalse(valid)
        self.assertEqual(msgs, [])

    def test_format_outgoing_message(self):
        msg_data = {
            'from_env': "user@example.com",
            'headers': {
                'from': "Alice User <user@example.com>",
                'subject': "Hello All",
                'message-id': "<msg123@example.com>"
            },
            'body_lines': ["Line 1\n", "Line 2\n"]
        }
        formatted_list = mailing.format_outgoing_message(msg_data, mailing_list="picolisp@example.com", reply_to_list=True)

        self.assertIn('From: "Alice User via picolisp@example.com" <picolisp@example.com>\r\n', formatted_list)
        self.assertIn("X-Original-From: Alice User <user@example.com>\r\n", formatted_list)
        self.assertIn("Sender: Alice User <user@example.com>\r\n", formatted_list)
        self.assertIn("Reply-To: picolisp@example.com\r\n", formatted_list)
        self.assertIn("To: picolisp@example.com\r\n", formatted_list)
        self.assertIn("Subject: Hello All\r\n", formatted_list)
        self.assertIn("List-Subscribe: <mailto:picolisp@example.com?subject=Subscribe>\r\n", formatted_list)
        self.assertIn("List-Unsubscribe: <mailto:picolisp@example.com?subject=Unsubscribe>\r\n", formatted_list)
        self.assertIn("Message-ID: <msg123@example.com>\r\n", formatted_list)
        self.assertIn("Line 1\r\nLine 2\r\n", formatted_list)
        self.assertNotIn("UNSUBSCRIBE:", formatted_list)
        self.assertNotIn("Fridays for Functions", formatted_list)

        formatted_sender = mailing.format_outgoing_message(msg_data, mailing_list="picolisp@example.com", reply_to_list=False)
        self.assertIn("Reply-To: Alice User <user@example.com>\r\n", formatted_sender)

    def test_gecos_and_lhs_from_header(self):
        # Case 1: Sender with GECOS display name
        msg_data_gecos = {
            'from_env': "bob@example.com",
            'headers': {'from': "Bob Smith <bob@example.com>", 'subject': "Hi"},
            'body_lines': ["Test\n"]
        }
        res_gecos = mailing.format_outgoing_message(msg_data_gecos, mailing_list="picolisp@example.com")
        self.assertIn('From: "Bob Smith via picolisp@example.com" <picolisp@example.com>\r\n', res_gecos)
        self.assertIn('X-Original-From: Bob Smith <bob@example.com>\r\n', res_gecos)

        # Case 2: Sender without GECOS display name (using LHS of email)
        msg_data_no_gecos = {
            'from_env': "charlie@example.com",
            'headers': {'from': "charlie@example.com", 'subject': "Hi"},
            'body_lines': ["Test\n"]
        }
        res_no_gecos = mailing.format_outgoing_message(msg_data_no_gecos, mailing_list="picolisp@example.com")
        self.assertIn('From: "charlie via picolisp@example.com" <picolisp@example.com>\r\n', res_no_gecos)
        self.assertIn('X-Original-From: charlie@example.com\r\n', res_no_gecos)

    def test_multipart_mime_and_html_preservation(self):
        multipart_mbox = (
            "From alice@example.com Mon Oct 26 12:00:00 2026\n"
            "From: Alice <alice@example.com>\n"
            "To: picolisp@example.com\n"
            "Subject: HTML and Plaintext\n"
            "MIME-Version: 1.0\n"
            "Content-Type: multipart/alternative; boundary=\"boundary_test_123\"\n"
            "\n"
            "--boundary_test_123\n"
            "Content-Type: text/plain; charset=utf-8\n"
            "\n"
            "Plain text content\n"
            "--boundary_test_123\n"
            "Content-Type: text/html; charset=utf-8\n"
            "\n"
            "<h1>HTML content</h1>\n"
            "--boundary_test_123--\n"
        )
        stream = io.StringIO(multipart_mbox)
        valid, msgs = mailing.parse_mbox_stream(stream)
        self.assertTrue(valid)
        self.assertEqual(len(msgs), 1)

        formatted = mailing.format_outgoing_message(msgs[0], mailing_list="picolisp@example.com")

        self.assertIn('From: "Alice via picolisp@example.com" <picolisp@example.com>\r\n', formatted)
        self.assertIn("X-Original-From: Alice <alice@example.com>\r\n", formatted)
        self.assertIn('Content-Type: multipart/alternative; boundary="boundary_test_123"\r\n', formatted)
        self.assertIn("--boundary_test_123\r\n", formatted)
        self.assertIn("Content-Type: text/plain; charset=utf-8\r\n", formatted)
        self.assertIn("Plain text content\r\n", formatted)
        self.assertIn("Content-Type: text/html; charset=utf-8\r\n", formatted)
        self.assertIn("<h1>HTML content</h1>\r\n", formatted)
        self.assertIn("--boundary_test_123--\r\n", formatted)

    def test_process_spool_non_member_discard_logging(self):
        mailing.save_mailings(["bob@example.com"], self.mailings_file)

        non_member_mbox = (
            "From eve@example.com Mon Oct 26 12:00:00 2026\n"
            "From: Eve <eve@example.com>\n"
            "Subject: Spam message\n"
            "\n"
            "Spam content.\n"
        )
        with open(self.spool_file, "w") as f:
            f.write(non_member_mbox)

        sent_calls = []

        def mock_smtp_sender(**kwargs):
            sent_calls.append(kwargs)
            return True

        with self.assertLogs(mailing.logger, level="INFO") as log:
            mailing.process_spool(
                spool_file=self.spool_file,
                mailings_file=self.mailings_file,
                mailing_list="picolisp@example.com",
                smtp_sender=mock_smtp_sender
            )

        self.assertEqual(len(sent_calls), 0)
        self.assertTrue(any("eve@example.com discarded" in msg for msg in log.output))
        self.assertEqual(os.path.getsize(self.spool_file), 0)

    def test_process_spool_subscribe_and_unsubscribe(self):
        # Initial mailings file with bob
        mailing.save_mailings(["bob@example.com"], self.mailings_file)

        # 1. Subscribe message from alice@example.com
        subscribe_mbox = (
            "From alice@example.com Mon Oct 26 12:00:00 2026\n"
            "From: Alice <alice@example.com>\n"
            "Subject: Subscribe\n"
            "\n"
            "Please subscribe me.\n"
        )
        with open(self.spool_file, "w") as f:
            f.write(subscribe_mbox)

        sent_calls = []

        def mock_smtp_sender(**kwargs):
            sent_calls.append(kwargs)
            return True

        mailing.process_spool(
            spool_file=self.spool_file,
            mailings_file=self.mailings_file,
            mailing_list="picolisp@example.com",
            smtp_sender=mock_smtp_sender
        )

        # Check alice was added to mailings
        mailings = mailing.load_mailings(self.mailings_file)
        self.assertIn("alice@example.com", mailings)
        self.assertIn("bob@example.com", mailings)
        self.assertEqual(len(sent_calls), 1)
        self.assertEqual(sent_calls[0]['recipients'], ["alice@example.com"])
        self.assertIn("Hello Alice <alice@example.com> :-)\r\nYou are now subscribed", sent_calls[0]['raw_message'])

        # Check spool file was emptied
        self.assertEqual(os.path.getsize(self.spool_file), 0)

        # 2. Unsubscribe message from alice@example.com
        unsubscribe_mbox = (
            "From alice@example.com Mon Oct 26 12:05:00 2026\n"
            "From: Alice <alice@example.com>\n"
            "Subject: Unsubscribe\n"
            "\n"
            "Please remove me.\n"
        )
        with open(self.spool_file, "w") as f:
            f.write(unsubscribe_mbox)

        sent_calls.clear()
        mailing.process_spool(
            spool_file=self.spool_file,
            mailings_file=self.mailings_file,
            mailing_list="picolisp@example.com",
            smtp_sender=mock_smtp_sender
        )

        # Check alice was removed from mailings
        mailings = mailing.load_mailings(self.mailings_file)
        self.assertNotIn("alice@example.com", mailings)
        self.assertIn("bob@example.com", mailings)
        self.assertEqual(len(sent_calls), 1)
        self.assertEqual(sent_calls[0]['recipients'], ["alice@example.com"])
        self.assertIn("Good bye Alice <alice@example.com> :-(\r\nYou are now unsubscribed", sent_calls[0]['raw_message'])

    @patch("smtplib.SMTP_SSL")
    def test_send_smtp_message_port_465(self, mock_smtp_ssl):
        mock_instance = MagicMock()
        mock_smtp_ssl.return_value = mock_instance
        mock_instance.sendmail.return_value = {}

        res = mailing.send_smtp_message(
            recipients=["user@example.com"],
            raw_message="Test message",
            smtp_port=465
        )
        self.assertTrue(res)
        mock_smtp_ssl.assert_called_once_with("smtp.example.com", 465)
        mock_instance.helo.assert_called_once_with("example.com")
        mock_instance.login.assert_called_once_with("picolisp@example.com", "XXXX")
        mock_instance.sendmail.assert_called_once_with("picolisp@example.com", ["user@example.com"], "Test message")

    @patch("smtplib.SMTP")
    def test_send_smtp_message_port_587(self, mock_smtp):
        mock_instance = MagicMock()
        mock_smtp.return_value = mock_instance
        mock_instance.sendmail.return_value = {}

        res = mailing.send_smtp_message(
            recipients=["user@example.com"],
            raw_message="Test message",
            smtp_port=587
        )
        self.assertTrue(res)
        mock_smtp.assert_called_once_with("smtp.example.com", 587)
        mock_instance.starttls.assert_called_once()
        mock_instance.helo.assert_called_once_with("example.com")
        mock_instance.login.assert_called_once_with("picolisp@example.com", "XXXX")
        mock_instance.sendmail.assert_called_once_with("picolisp@example.com", ["user@example.com"], "Test message")


if __name__ == "__main__":
    unittest.main()
