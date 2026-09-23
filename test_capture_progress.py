import unittest
from capture_progress import samples,numbers,advancing


class CaptureProgress(unittest.TestCase):
    def test_partial_write_cannot_be_mistaken_for_a_reversed_clock(self):
        text='out_time_us=1000000\nprogress=continue\nout_time_us=1500000\nprogress=continue\nout_time_us=16'
        values=numbers(samples(text),'out_time_us')
        self.assertEqual(values,[1000000,1500000])
        self.assertTrue(advancing(values))

    def test_incomplete_record_is_ignored_even_when_its_timestamp_line_is_complete(self):
        text='frame=30\nout_time_us=1000000\nprogress=continue\nframe=45\nout_time_us=1500000\n'
        self.assertEqual(numbers(samples(text),'frame'),[30])

    def test_short_duplicate_is_allowed_but_frozen_or_single_sample_is_not(self):
        self.assertTrue(advancing([10,11,11]))
        self.assertFalse(advancing([11,11,11,11]))
        self.assertFalse(advancing([11]))
        self.assertFalse(advancing([]))


if __name__=='__main__':unittest.main()
