import unittest
from types import SimpleNamespace

import search


VALID_CLAIMS = '''{
  "claims": [{
    "claim": "Example claim.",
    "confidence": "high",
    "evidence": [{
      "url": "https://example.com/source",
      "support": "The source states the example claim.",
      "source_type": "official"
    }]
  }],
  "limitations": ["Only one source was reviewed."]
}'''


class ClaimsParserTests(unittest.TestCase):
    def test_accepts_complete_claims_schema(self):
        self.assertEqual(search.parse_claims(VALID_CLAIMS)["claims"][0]["confidence"], "high")

    def test_rejects_empty_claims_array(self):
        with self.assertRaises(ValueError):
            search.parse_claims('{"claims": [], "limitations": ["Research not yet complete; gathering official Brave documentation."]}')

    def test_rejects_missing_evidence(self):
        with self.assertRaisesRegex(ValueError, "evidence"):
            search.parse_claims('{"claims":[{"claim":"x","confidence":"high","evidence":[]}],"limitations":[]}')

    def test_rejects_invalid_evidence_fields(self):
        with self.assertRaises(ValueError):
            search.parse_claims('{"claims":[{"claim":"x","confidence":"high","evidence":[{"url":"file:///tmp/source","support":"x","source_type":"official"}]}],"limitations":[]}')
        with self.assertRaises(ValueError):
            search.parse_claims('{"claims":[{"claim":"x","confidence":"high","evidence":[{"url":"https://example.com","support":"x","source_type":"unknown"}]}],"limitations":[]}')

    def test_uses_final_structured_stream_content_without_concatenation(self):
        progressive_chunks = ['{"claims":[]', '{"claims":[],"limitations":[]}']
        response = SimpleNamespace(content='{"claims":[],"limitations":[]}')
        self.assertEqual(search.final_content(response, progressive_chunks, "claims"), response.content)
        self.assertEqual(search.final_content(SimpleNamespace(content=""), progressive_chunks, "claims"), progressive_chunks[-1])
        self.assertEqual(search.final_content(response, ["hello", " world"], "prose"), "hello world")


if __name__ == "__main__":
    unittest.main()
