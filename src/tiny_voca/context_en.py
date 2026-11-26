"""Context-dependent pronunciations for English heteronyms in the bilingual frontend."""
import re

# A star marks the stressed vowel. Other tokens use the existing en_text inventory.
_READINGS = {
    'read': ('ɹ *ɛ d', r'(?:stayed inside and |proof is |has been |had )(read)'),
    'live': ('l *ɪ v', r"(?:i |who |to |we might |they |actually |can.t )(live)"),
    'use': ('j *uː z', r'(?:never |i |americans |you |can |to |should |we |please |to smartly )(use)(?! of\b)'),
    'close': ('k l *oʊ z', r'(close) that confounded window'),
    'minute': ('m aɪ n *uː t', r'(minute), clear detail'),
    'lead': ('l *ɛ d', r'salt and (lead)'),
    'project': ('p ɹ ə dʒ *ɛ k t', r'heads that (project)'),
    'record': ('ɹ ɪ k *ɔːɹ d', r're-(record)'),
    'present': ('p ɹ ɪ z *ɛ n t', r'did that exciting scene (present)'),
    'wound': ('w *aʊ n d', r'(wound) up a clock'),
    'suspect': ('s ə s p *ɛ k t', r'would (suspect)'),
    'tear': ('t *ɛɹ', r'to (tear) (?:my hair|him)'),
    'attribute': ('ə t ɹ *ɪ b j uː t', r'(?:did not |with you, )(attribute)'),
    'abuse': ('ə b j *uː z', r'can you (abuse)'),
    'excuse': ('ɪ k s k j *uː z', r'will (excuse) me'),
    'separate': ('s *ɛ p ə ɹ eɪ t', r'to (separate) us'),
    'graduate': ('ɡ ɹ *æ dʒ uː eɪ t', r'(?:to |after i |能|要先)(graduate)(?! (?:school|students?|programs?|courses?)\b)'),
    'contract': ('k ə n t ɹ *æ k t', r'forbidden to (contract)'),
    'produce': ('p ɹ *oʊ d uː s', r'vegetable (produce)'),
    'increase': ('ɪ n k ɹ *iː s', r'to (increase)'),
    'insult': ('ɪ n s *ʌ l t', r"can't (insult)"),
    'estimate': ('*ɛ s t ə m eɪ t', r'would you (estimate)'),
}

_RULES = [(re.compile(r'(?<![a-z])(?:' + pattern + r')(?![a-z])', re.I),
           [('en/' + phone.lstrip('*'), int(phone.startswith('*'))) for phone in phones.split()])
          for phones, pattern in _READINGS.values()]


def context_phones(text):
    """Map word offsets to corrected phones without affecting homographs elsewhere."""
    result = {}
    for pattern, phones in _RULES:
        for match in pattern.finditer(text):
            result[match.start(1)] = phones
    return result
