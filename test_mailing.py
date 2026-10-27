import os
import tempfile
import io
import unittest
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
            'from_env': "user@domain.com",
            'headers': {
                'from': "Alice User <user@domain.com>",
                'subject': "Hello All",
                'message-id': "<msg123@domain.com>"
            },
            'body_lines': ["Line 1\n", "Line 2\n"]
        }
        formatted_list = mailing.format_outgoing_message(msg_data, mailing_list="picolisp@software-lab.de", reply_to_list=True)

        self.assertIn("From: Alice User <picolisp@software-lab.de>\r\n", formatted_list)
        self.assertIn("Sender: Alice User <user@domain.com>\r\n", formatted_list)
        self.assertIn("Reply-To: picolisp@software-lab.de\r\n", formatted_list)
        self.assertIn("To: picolisp@software-lab.de\r\n", formatted_list)
        self.assertIn("Subject: Hello All\r\n", formatted_list)
        self.assertIn("List-Subscribe: <mailto:picolisp@software-lab.de?subject=Subscribe>\r\n", formatted_list)
        self.assertIn("List-Unsubscribe: <mailto:picolisp@software-lab.de?subject=Unsubscribe>\r\n", formatted_list)
        self.assertIn("Message-ID: <msg123@domain.com>\r\n", formatted_list)
        self.assertIn("Line 1\nLine 2\n", formatted_list)
        self.assertNotIn("UNSUBSCRIBE:", formatted_list)
        self.assertNotIn("Fridays for Functions", formatted_list)

        formatted_sender = mailing.format_outgoing_message(msg_data, mailing_list="picolisp@software-lab.de", reply_to_list=False)
        self.assertIn("Reply-To: Alice User <user@domain.com>\r\n", formatted_sender)

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

        stderr_capture = io.StringIO()
        original_stderr = mailing.sys.stderr
        try:
            mailing.sys.stderr = stderr_capture
            mailing.process_spool(
                spool_file=self.spool_file,
                mailings_file=self.mailings_file,
                mailing_list="picolisp@software-lab.de",
                smtp_sender=mock_smtp_sender
            )
        finally:
            mailing.sys.stderr = original_stderr

        self.assertEqual(len(sent_calls), 0)
        self.assertIn("eve@example.com discarded", stderr_capture.getvalue())
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
            mailing_list="picolisp@software-lab.de",
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
            mailing_list="picolisp@software-lab.de",
            smtp_sender=mock_smtp_sender
        )

        # Check alice was removed from mailings
        mailings = mailing.load_mailings(self.mailings_file)
        self.assertNotIn("alice@example.com", mailings)
        self.assertIn("bob@example.com", mailings)
        self.assertEqual(len(sent_calls), 1)
        self.assertEqual(sent_calls[0]['recipients'], ["alice@example.com"])
        self.assertIn("Good bye Alice <alice@example.com> :-(\r\nYou are now unsubscribed", sent_calls[0]['raw_message'])


if __name__ == "__main__":
    unittest.main()
