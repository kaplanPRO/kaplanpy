import regex

from collections import Counter
import csv
import io
from pathlib import Path
import string
import tempfile
import zipfile


class QAChecker:
    def __init__(self):
        '''
        Creates a QAChecker instance.
        '''

        self.letters = {}
        self.word_counter = {}

    def build(self, target_segments):
        target_segments = '\n'.join(target_segments)
        self.letters = set(filter(lambda x: regex.match('\p{L}', x),
                                   set(target_segments)))

        self.word_counter = Counter(self.__words(target_segments))

    def check(self, segments: dict):
        '''
        Checks a dict of segments.

        Args:
            segments dict(dict)
        '''
        results = {}

        _regex = regex.compile('([\.\!\?\:]+)$')

        for i, segment in segments.items():
            if segment.get('source', '') == '':
                continue
            elif segment.get('target', '') == '':
                results[i] = [{'level':'info',
                               'message':'Segment not translated.'}]
                continue

            segment_results = []

            source = segment['source']
            target = segment['target']

            if (source[0].lower() == source[0]) != (target[0].lower() == target[0]):
                segment_results.append({'level':'info',
                                        'type':'capitalization'})

            source_punctuation = _regex.search(source)
            target_punctuation = _regex.search(target)

            if (bool(source_punctuation) != bool(target_punctuation) or
                source_punctuation.groups() != target_punctuation.groups()):
                segment_results.append({'level':'info',
                                        'type':'punctuation'})

            if all((self.letters, self.word_counter)):
                for correction in self.corrections_for_sentence(target):
                    word = correction['word']
                    suggestions = correction['suggestions']
                    segment_results.append({'level':'info',
                                            'type':'typo',
                                            'word':word,
                                            'suggestions':suggestions})

            results[i] = segment_results

        return results

    def __P(self, word):
        return self.word_counter[word] / sum(self.word_counter.values())

    def corrections(self, word, n=5):
        return sorted(self.__candidates(word), key=self.__P, reverse=True)[:n]

    def corrections_for_sentence(self, sentence, n=5):
        for word in self.__words(sentence):
            if word in self.word_counter:
                continue
            yield {'word':word, 'suggestions':self.corrections(word)}

    @classmethod
    def open(cls, path):
        with zipfile.ZipFile(path) as zf:
            letters = set(zf.read('letters.txt').decode('UTF-8').strip())

            with zf.open('word_counter.csv') as csvfile:
                fieldnames = ['word', 'count']
                csvreader = csv.DictReader(io.TextIOWrapper(csvfile, 'UTF-8'), fieldnames=fieldnames)
                word_counter = Counter({row['word']:int(row['count']) for row in csvreader})

        qac = cls()
        qac.letters = letters
        qac.word_counter = word_counter

        return qac

    def save(self, path):
        path = Path(path).with_suffix('.kqac')

        with tempfile.TemporaryDirectory() as tmpdir:
            path_letters = Path(tmpdir, 'letters.txt')
            with open(path_letters, 'w', encoding='UTF-8') as f:
                for l in self.letters:
                    f.write(l)

            path_word_counter = Path(tmpdir, 'word_counter.csv')
            with open(path_word_counter, 'w', encoding='UTF-8') as csvfile:
                fieldnames = ['word', 'count']
                csvwriter = csv.DictWriter(csvfile, fieldnames=fieldnames)

                #csvwriter.writeheader()
                for word, count in self.word_counter.most_common():
                    csvwriter.writerow({'word':word, 'count':count})

            with zipfile.ZipFile(path, 'w') as zf:
                zf.write(path_letters, 'letters.txt')
                zf.write(path_word_counter, 'word_counter.csv')

    def __candidates(self, word, n_edits=2):
        words = set([word])

        for n in range(n_edits):
            words.update([edit for edit in self.__edits(word) for word in words])

        return self.__known(words)

    def __known(self, words):
        return set([w for w in words if w in self.word_counter])

    def __edits(self, word):
        letters    = self.letters
        splits     = [(word[:i], word[i:])    for i in range(len(word) + 1)]
        deletes    = [L + R[1:]               for L, R in splits if R]
        transposes = [L + R[1] + R[0] + R[2:] for L, R in splits if len(R)>1]
        replaces   = [L + c + R[1:]           for L, R in splits if R for c in letters]
        inserts    = [L + c + R               for L, R in splits for c in letters]
        return set(deletes + transposes + replaces + inserts)

    def __words(self, text):
        return filter(lambda x: len(x) > 1 and regex.match('^[\p{L}\'-]+$', x),
                      regex.sub('[^\p{L}\p{N}\s\'-]', '', text).split())
