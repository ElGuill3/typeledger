import random
import unittest

from typeledger.core.models import LANGUAGES
from typeledger.core.textgen import generate_text, load_words


class LoadWordsTest(unittest.TestCase):
    def test_word_lists_load_with_enough_unique_words(self):
        for language in LANGUAGES:
            with self.subTest(language=language):
                words = load_words(language)
                self.assertGreaterEqual(len(set(words)), 150)
                self.assertEqual(len(words), len(set(words)))
                for word in words:
                    self.assertTrue(word)
                    self.assertEqual(word, word.lower())
                    self.assertEqual(word, word.strip())
                    self.assertNotIn(" ", word)

    def test_spanish_keeps_accents(self):
        words = load_words("es")
        self.assertIn("también", words)
        self.assertIn("año", words)

    def test_unknown_language_raises(self):
        with self.assertRaises(ValueError):
            load_words("xx")
        with self.assertRaises(ValueError):
            generate_text("../en", 5)


class GenerateTextTest(unittest.TestCase):
    def test_exact_word_count(self):
        for count in (1, 10, 25, 50, 100):
            with self.subTest(count=count):
                text = generate_text("en", count, random.Random(count))
                self.assertEqual(len(text.split(" ")), count)
                self.assertEqual(text, text.strip())
                self.assertNotIn("  ", text)
                self.assertEqual(text, text.lower())

    def test_no_consecutive_duplicates(self):
        rng = random.Random(7)
        for language in LANGUAGES:
            for _ in range(50):
                words = generate_text(language, 100, rng).split(" ")
                for previous, current in zip(words, words[1:]):
                    self.assertNotEqual(previous, current)

    def test_seeded_determinism(self):
        first = generate_text("es", 50, random.Random(42))
        second = generate_text("es", 50, random.Random(42))
        self.assertEqual(first, second)
        self.assertNotEqual(first, generate_text("es", 50, random.Random(43)))

    def test_default_rng(self):
        self.assertEqual(len(generate_text("en", 10).split(" ")), 10)


if __name__ == "__main__":
    unittest.main()
