import unittest

from app.services.repetition_guard import deduplicate_chunks, collapse_repeated_phrases


class RepetitionGuardTests(unittest.TestCase):
    def test_deduplicate_chunks_removes_duplicate_context(self):
        chunks = [
            {"page_number": 1, "text": "Name is Ali."},
            {"page_number": 1, "text": "Name is Ali."},
            {"page_number": 1, "text": "Role: Developer"},
        ]

        deduped = deduplicate_chunks(chunks)

        self.assertEqual(len(deduped), 2)
        self.assertEqual(deduped[0]["text"], "Name is Ali.")
        self.assertEqual(deduped[1]["text"], "Role: Developer")

    def test_deduplicate_chunks_removes_near_duplicate_same_page_chunks(self):
        chunks = [
            {"page_number": 1, "text": "Name is Nora Wright. Name is Nora Wright."},
            {"page_number": 1, "text": "Name is Nora Wright. Name is Nora Wright. Name is Nora Wright."},
            {"page_number": 2, "text": "Role: Developer"},
        ]

        deduped = deduplicate_chunks(chunks)

        self.assertEqual(len(deduped), 2)
        self.assertEqual(deduped[0]["page_number"], 1)
        self.assertEqual(deduped[1]["text"], "Role: Developer")

    def test_collapse_repeated_phrases_removes_exact_duplicate_sentences(self):
        text = "The person is Kazim. The person is Kazim."

        result = collapse_repeated_phrases(text)

        self.assertEqual(result, "The person is Kazim.")


if __name__ == "__main__":
    unittest.main()
