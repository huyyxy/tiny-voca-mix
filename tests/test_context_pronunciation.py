import unittest

from tiny_voca import context_en, text


def pronounced(phrase):
    return [(spelling, [p for p, _ in phones]) for spelling, phones in text.units(phrase) if spelling]


class ContextPronunciationTest(unittest.TestCase):
    def test_polyphones_and_aligner_spelling(self):
        self.assertIn(('chang', ['zh/ch', 'zh/ang2']), pronounced('很长的信'))
        self.assertIn(('zhang', ['zh/zh', 'zh/ang3']), pronounced('孩子长大了'))
        self.assertIn(('dou', ['zh/d', 'zh/ou1']), pronounced('大家都会'))
        self.assertIn(('du', ['zh/d', 'zh/u1']), pronounced('大都会'))
        self.assertIn(('shu', ['zh/sh', 'zh/u3']), pronounced('数着路边的电线杆'))

    def test_neutral_tone_depends_on_meaning(self):
        self.assertIn(('de', ['zh/d', 'zh/e5']), pronounced('认真地带上证件'))
        self.assertIn(('di', ['zh/d', 'zh/i4']), pronounced('热带地区'))
        self.assertIn(('xi', ['zh/x', 'zh/i5']), pronounced('买东西'))
        self.assertIn(('xi', ['zh/x', 'zh/i1']), pronounced('东西方向'))

    def test_digit_sequence_and_ordinal(self):
        for phrase in ('电话号码是16811331371', '21点19分', '第1季度', '11楼21号房间'):
            targets = [phones for spelling, phones in pronounced(phrase) if spelling == 'yi']
            self.assertTrue(targets)
            self.assertTrue(all(phones == ['zh/i1'] for phones in targets))
        self.assertIn(('yi', ['zh/i2']), pronounced('一件衣服'))
        self.assertIn(('yi', ['zh/i4']), pronounced('一封信'))

    def test_nasal_and_rhotic_coda(self):
        self.assertEqual(pronounced('嗯'), [('en', ['zh/en2'])])
        self.assertIn(('huir', ['zh/h', 'zh/ui4', 'zh/r']), pronounced('一会儿'))
        self.assertIn(('er', ['zh/er2']), pronounced('社会儿童福利'))

    def test_english_context_is_per_occurrence(self):
        phrase = 'I live here and watch live broadcasts'
        overrides = context_en.context_phones(phrase)
        self.assertEqual(set(overrides), {2})
        self.assertEqual(overrides[2], [('en/l', 0), ('en/ɪ', 1), ('en/v', 0)])
        self.assertFalse(context_en.context_phones('I applied to graduate school'))
        self.assertIn(('read', ['en/ɹ', 'en/ɛ', 'en/d']), pronounced('we stayed inside and read.'))
