import unittest

from tiny_voca.zh_text import phrase_syllables


class CountingPronunciationTest(unittest.TestCase):
    def test_counting_people(self):
        syllables = phrase_syllables("我们又数了一遍人数")
        self.assertEqual([s.tone for s in syllables if s.char == "数"], [3, 4])

    def test_sandhi_after_pronunciation_correction(self):
        syllables = phrase_syllables("路口数了一遍人数")
        self.assertEqual([s.tone for s in syllables[1:3]], [2, 3])

    def test_nouns(self):
        for word in ("人数", "数字", "数量", "数学"):
            with self.subTest(word=word):
                self.assertEqual(next(s.tone for s in phrase_syllables(word) if s.char == "数"), 4)
