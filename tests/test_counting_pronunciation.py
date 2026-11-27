import unittest

from tiny_voca.text import units


def tones(text, spelling):
    return [int(phones[-1][0][-1]) for word, phones in units(text) if word == spelling]


class CountingPronunciationTest(unittest.TestCase):
    def test_counting_people(self):
        self.assertEqual(tones("我们又数了一遍人数", "shu"), [3, 4])

    def test_sandhi_after_pronunciation_correction(self):
        self.assertEqual(tones("路口数了一遍人数", "kou"), [2])
        self.assertEqual(tones("路口数了一遍人数", "shu"), [3, 4])

    def test_nouns(self):
        for word in ("人数", "数字", "数量", "数学"):
            with self.subTest(word=word):
                self.assertEqual(tones(word, "shu"), [4])
